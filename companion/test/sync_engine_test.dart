import 'dart:async';
import 'dart:io';


import 'package:flutter_test/flutter_test.dart';
import 'package:vocalis_companion/sync/api_client.dart';
import 'package:vocalis_companion/sync/sync_engine.dart';
import 'package:vocalis_companion/sync/tus_client.dart';

class FakeApi implements CompanionApi {
  final List<String> calls = [];
  int healthFails = 0;
  bool conflict409 = false;
  String pollStatus = 'processed';
  int uploads = 0;

  @override
  Future<Map<String, dynamic>> health() async {
    calls.add('health');
    if (healthFails > 0) {
      healthFails--;
      throw const SocketException('caído');
    }
    return {'ok': true};
  }

  @override
  Future<Map<String, dynamic>> pair(String code, String deviceName) async =>
      {'ok': true, 'device_token': 't'};

  @override
  Future<Map<String, dynamic>> postSessions(Map<String, dynamic> payload) async {
    calls.add('sessions');
    if (conflict409) throw ApiException(409, 'Sesión ya procesada');
    return {'ok': true, 'session_id': 'srv-1'};
  }

  @override
  Future<Map<String, dynamic>> postUploads(Map<String, dynamic> payload) async {
    calls.add('uploads:${payload['kind']}');
    uploads++;
    return {'ok': true, 'upload_url': 'https://tus/x', 'path': 'vault/a.m4a'};
  }

  @override
  Future<Map<String, dynamic>> confirmUpload(Map<String, dynamic> payload) async {
    calls.add('confirm');
    return {'ok': true, 'status': 'uploaded'};
  }

  @override
  Future<Map<String, dynamic>> getSession(String id) async {
    calls.add('poll');
    return {'ok': true, 'status': pollStatus};
  }

  @override
  Future<Map<String, dynamic>> getReferencias() async => {'ok': true, 'rangos': []};
}

class FakeTus implements TusGateway {
  final List<String> calls = [];
  int startOffset = 0;

  @override
  Future<String> create(String u, int l, String f) async {
    calls.add('create');
    return 'https://tus/x/loc';
  }

  @override
  Future<int> offset(String l, {required String bearerToken}) async {
    calls.add('offset');
    return startOffset;
  }

  @override
  Future<int> uploadFile(String l, File f,
      {int offset = 0, required String bearerToken, void Function(int, int)? onProgress}) async {
    calls.add('upload@$offset');
    return offset + await f.length();
  }
}

void main() {
  group('SyncEngine', () {
    test('flujo feliz en orden: health→sessions→uploads→tus→confirm→poll→synced', () async {
      final dir = await Directory.systemTemp.createTemp('synctest');
      final audio = File('${dir.path}/s.m4a');
      await audio.writeAsBytes(List<int>.filled(1000, 1));
      final payload = {
        'device_session_id': 'ds-1',
        'patient_id': 'p',
        'recorded_at': '2026-10-09',
        'audio_duration_sec': 10,
        'audio_codec': 'opus',
        'audio_bitrate_kbps': 48,
        'dsp_version': 'dsp/1',
        'device_info': {},
        'consent_recorded': true,
        'segments': [],
        'acoustics': [],
        'clips': [],
      };
      final fake = _StoreFake(payload);
      final api = FakeApi();
      final tus = FakeTus();
      final eng = SyncEngine(
        api: api,
        tus: tus,
        store: fake as dynamic,
        leerToken: () async => 'tok',
        hayRed: () async => true,
      );
      await eng.sincronizar('ds-1', {'audioPath': audio.path, 'audioMime': 'audio/mp4', 'wifiOnly': false});
      expect(fake.estados.last, 'synced');
      final order = api.calls.join(',');
      expect(order.indexOf('health') < order.indexOf('sessions'), true);
      expect(order.indexOf('sessions') < order.indexOf('uploads:session_audio'), true);
      expect(order.indexOf('uploads:session_audio') < order.indexOf('confirm'), true);
      expect(order.indexOf('confirm') < order.indexOf('poll'), true);
      await dir.delete(recursive: true);
    });

    test('409 marca ACCION_REQUERIDA y relanza', () async {
      final api = FakeApi()..conflict409 = true;
      final fake = _StoreFake({});
      final eng = SyncEngine(
        api: api, tus: FakeTus(), store: fake as dynamic,
        leerToken: () async => 'tok', hayRed: () async => true);
      // payload mínimo: el engine lo pide al store
      await expectLater(eng.sincronizar('ds-x', {'audioPath': '/no', 'wifiOnly': false}),
          throwsA(isA<ApiException>()));
      expect(fake.estados.last, 'error');
      expect(fake.ultimoError, contains('ACCION_REQUERIDA'));
    });

    test('health con fallo transitorio reintenta (backoff)', () async {
      final dir = await Directory.systemTemp.createTemp('synctest2');
      final audio = File('${dir.path}/s.m4a');
      await audio.writeAsBytes(List<int>.filled(100, 1));
      final api = FakeApi()..healthFails = 1;
      final fake = _StoreFake({'device_session_id': 'ds-2'});
      final eng = SyncEngine(
        api: api, tus: FakeTus(), store: fake as dynamic,
        leerToken: () async => 'tok', hayRed: () async => true);
      await eng.sincronizar('ds-2', {'audioPath': audio.path, 'audioMime': 'audio/mp4', 'wifiOnly': false});
      expect(api.calls.where((c) => c == 'health').length, 2);
      expect(fake.estados.last, 'synced');
      await dir.delete(recursive: true);
    });

    test('reanuda TUS desde el offset del servidor', () async {
      final dir = await Directory.systemTemp.createTemp('synctest3');
      final audio = File('${dir.path}/s.m4a');
      await audio.writeAsBytes(List<int>.filled(500, 2));
      final api = FakeApi();
      final tus = FakeTus()..startOffset = 500;
      final fake = _StoreFake({'device_session_id': 'ds-3'});
      final eng = SyncEngine(
        api: api, tus: tus, store: fake as dynamic,
        leerToken: () async => 'tok', hayRed: () async => true);
      await eng.sincronizar('ds-3', {'audioPath': audio.path, 'audioMime': 'audio/mp4', 'wifiOnly': false});
      expect(tus.calls, contains('upload@500'));
      await dir.delete(recursive: true);
    });
  });
}

/// Doble mínimo del SessionStore (solo lo que usa el engine).
class _StoreFake {
  final Map<String, dynamic> payload;
  final List<String> estados = [];
  String ultimoError = '';

  _StoreFake(this.payload);

  Future<Map<String, dynamic>> payloadParaServidor(String id) async => payload;

  Future<void> estado(String id, String status, {String error = ''}) async {
    estados.add(status);
    ultimoError = error;
  }

  Future<void> guardarServidor(String id, String serverId) async {}
}
