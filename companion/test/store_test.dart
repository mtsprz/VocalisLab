import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:vocalis_companion/data/db.dart';
import 'package:vocalis_companion/data/patient_repository.dart';
import 'package:vocalis_companion/data/session_store.dart';

void main() {
  group('SessionStore', () {
    test('CRUD + payload con forma de contrato', () async {
      sqfliteFfiInit();
      databaseFactory = databaseFactoryFfi;
      final db = await openAppDb(pathOverride: inMemoryDatabasePath);
      final store = SessionStore(db);
      await store.crear({
        'device_session_id': 'ds-1',
        'patient_id': 'p-1',
        'recorded_at': '2026-10-09T10:00:00',
        'audio_duration_sec': 120,
        'audio_codec': 'opus',
        'audio_bitrate_kbps': 48,
        'dsp_version': 'dsp/1',
        'device_info': '{"modelo":"x"}',
        'consent_recorded': 1,
        'status': 'ready',
        'created_at': '2026-10-09',
      });
      await store.guardarSegmentos('ds-1', [
        {'task_type': 'vocal_sostenida_a', 'speaker': 'paciente', 'start_sec': 0, 'end_sec': 20},
        {'task_type': 'conversacion_espontanea', 'speaker': 'fonoaudiologo', 'start_sec': 20, 'end_sec': 40},
      ]);
      await store.guardarAcustica('ds-1', 'vocal_sostenida_a',
          {'f0_median_hz': 210.0, 'jitter_pct': 0.4, 'dsp_version': 'dsp/1'});
      final p = await store.payloadParaServidor('ds-1');
      expect(p['device_session_id'], 'ds-1');
      expect(p['consent_recorded'], true);
      expect((p['segments'] as List).length, 2);
      expect((p['acoustics'] as List).first['task_type'], 'vocal_sostenida_a');
      expect((p['acoustics'] as List).first['jitter_pct'], 0.4);
      expect((p['clips'] as List), isEmpty);
      await store.estado('ds-1', 'synced');
      expect((await store.leer('ds-1'))!['status'], 'synced');
      await store.guardarServidor('ds-1', 'srv-9');
      expect((await store.leer('ds-1'))!['server_session_id'], 'srv-9');
      expect((await store.pendientes()).isEmpty, true);
      await store.borrarSesionLocal('ds-1');
      expect(await store.leer('ds-1'), isNull);
      await db.close();
    });
  });

  group('MockPatientRepository', () {
    test('seed y caché', () async {
      sqfliteFfiInit();
      databaseFactory = databaseFactoryFfi;
      final db = await openAppDb(pathOverride: inMemoryDatabasePath);
      final repo = MockPatientRepository(db);
      expect((await repo.listar()).length, 2); // seed
      await repo.guardarCache(const [
        PacienteMin(id: 'a', nombreAbreviado: 'Ana G.', sexoReferencia: 'femenino'),
      ]);
      final l = await repo.listar();
      expect(l.length, 1);
      expect(l.first.nombreAbreviado, 'Ana G.');
      await db.close();
    });
  });
}
