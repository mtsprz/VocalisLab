import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:vocalis_companion/sync/tus_client.dart';

const _firmada = 'https://abc.supabase.co/storage/v1/object/upload/sign/'
    'companion-audio-vault/vault/ses-1.m4a?token=TOKEN123';

void main() {
  test('deriva endpoint resumable, bucket, objeto y firma de la URL firmada', () {
    final d = DestinoTus.desde(_firmada);
    expect(d.endpoint.toString(), 'https://abc.supabase.co/storage/v1/upload/resumable');
    expect(d.bucket, 'companion-audio-vault');
    expect(d.objeto, 'vault/ses-1.m4a');
    expect(d.firma, 'TOKEN123');
  });

  test('URL TUS genérica se usa tal cual', () {
    final d = DestinoTus.desde('https://tus.example.com/files/');
    expect(d.esSupabaseFirmado, false);
    expect(d.endpoint.toString(), 'https://tus.example.com/files/');
  });

  test('bloques de 6 MB salvo el último, con x-signature y sin device_token', () async {
    final reqs = <http.Request>[];
    final client = MockClient((r) async {
      reqs.add(r);
      if (r.method == 'POST') {
        return http.Response('', 201, headers: {'location': '/storage/v1/upload/resumable/ID1'});
      }
      final off = int.parse(r.headers['Upload-Offset']!);
      return http.Response('', 204,
          headers: {'upload-offset': '${off + r.bodyBytes.length}'},);
    });
    final dir = await Directory.systemTemp.createTemp('tus');
    final f = File('${dir.path}/a.m4a');
    const total = 6 * 1024 * 1024 * 2 + 1234;
    await f.writeAsBytes(List<int>.filled(total, 7));
    final tus = TusClient(httpClient: client);
    final loc = await tus.create(_firmada, total, 'a.m4a', mime: 'audio/mp4');
    expect(loc, 'https://abc.supabase.co/storage/v1/upload/resumable/ID1');
    final fin = await tus.uploadFile(loc, f, bearerToken: 'DEVICE-TOKEN');
    expect(fin, total);

    final post = reqs.first;
    expect(post.headers['x-signature'], 'TOKEN123');
    final meta = post.headers['Upload-Metadata']!;
    expect(meta, contains('bucketName ${base64Encode(utf8.encode('companion-audio-vault'))}'));
    expect(meta, contains('objectName ${base64Encode(utf8.encode('vault/ses-1.m4a'))}'));
    final patches = reqs.where((r) => r.method == 'PATCH').toList();
    expect(patches.map((r) => r.bodyBytes.length).toList(),
        [6 * 1024 * 1024, 6 * 1024 * 1024, 1234],);
    for (final r in reqs) {
      expect(r.headers.containsKey('Authorization'), false);
    }
    expect(patches.every((r) => r.headers['x-signature'] == 'TOKEN123'), true);
    await dir.delete(recursive: true);
  });

  test('409 en create firmado → TusYaSubido', () async {
    final tus = TusClient(httpClient: MockClient((_) async => http.Response('exists', 409)));
    expect(() => tus.create(_firmada, 10, 'a'), throwsA(isA<TusYaSubido>()));
  });
}
