import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

/// Contrato TUS (inyectable para tests).
abstract class TusGateway {
  Future<String> create(String uploadUrl, int length, String filename);
  Future<int> offset(String locationUrl, {required String bearerToken});
  Future<int> uploadFile(String locationUrl, File file,
      {int offset = 0,
      required String bearerToken,
      void Function(int sent, int total)? onProgress});
}

/// Cliente TUS mínimo y reanudable (Tus-Resumable 1.0.0) para las
/// `upload_url` firmadas del backend. Sin dependencias extra.
class TusClient implements TusGateway {
  final http.Client _http;

  TusClient({http.Client? httpClient}) : _http = httpClient ?? http.Client();

  /// Crea la subida. Devuelve la URL de destino (cabecera Location).
  @override
  Future<String> create(String uploadUrl, int length, String filename) async {
    final r = await _http.post(
      Uri.parse(uploadUrl),
      headers: {
        'Tus-Resumable': '1.0.0',
        'Upload-Length': '$length',
        'Upload-Metadata': 'filename ${base64Encode(utf8.encode(filename))}',
      },
    ).timeout(const Duration(seconds: 75));
    if (r.statusCode != 201 && r.statusCode != 200) {
      throw TusException('create: HTTP ${r.statusCode} ${r.body}');
    }
    final loc = r.headers['location'] ?? r.headers['Location'] ?? '';
    if (loc.isEmpty) throw const TusException('create sin Location');
    // Location puede ser relativa: resolver contra la URL firmada.
    return Uri.parse(uploadUrl).resolve(loc).toString();
  }

  /// Offset ya subido (para reanudar tras un corte).
  @override
  Future<int> offset(String locationUrl, {required String bearerToken}) async {
    final r = await _http.head(
      Uri.parse(locationUrl),
      headers: {'Tus-Resumable': '1.0.0', 'Authorization': 'Bearer $bearerToken'},
    ).timeout(const Duration(seconds: 60));
    if (r.statusCode != 200 && r.statusCode != 204) {
      throw TusException('offset: HTTP ${r.statusCode}');
    }
    return int.tryParse(r.headers['upload-offset'] ?? r.headers['Upload-Offset'] ?? '0') ?? 0;
  }

  /// Sube [file] desde [offset] en trozos de 5 MB. Devuelve el offset final.
  @override
  Future<int> uploadFile(
    String locationUrl,
    File file, {
    int offset = 0,
    required String bearerToken,
    void Function(int sent, int total)? onProgress,
  }) async {
    final total = await file.length();
    var off = offset;
    const chunk = 5 * 1024 * 1024;
    final raf = await file.open(mode: FileMode.read);
    try {
      await raf.setPosition(off);
      while (off < total) {
        final n = (total - off).clamp(0, chunk);
        final buf = await raf.read(n);
        final req = http.StreamedRequest('PATCH', Uri.parse(locationUrl))
          ..headers['Tus-Resumable'] = '1.0.0'
          ..headers['Authorization'] = 'Bearer $bearerToken'
          ..headers['Content-Type'] = 'application/offset+octet-stream'
          ..headers['Upload-Offset'] = '$off'
          ..headers['Content-Length'] = '${buf.length}';
        req.sink.add(buf);
        await req.sink.close();
        final resp = await req.send().timeout(const Duration(minutes: 5));
        await resp.stream.drain();
        if (resp.statusCode != 204 && resp.statusCode != 200) {
          throw TusException('patch @$off: HTTP ${resp.statusCode}');
        }
        final next = resp.headers['upload-offset'] ?? resp.headers['Upload-Offset'];
        off = next != null ? int.parse(next) : off + buf.length;
        onProgress?.call(off, total);
      }
    } finally {
      await raf.close();
    }
    return off;
  }

  void close() => _http.close();
}

class TusException implements Exception {
  final String message;
  const TusException(this.message);
  @override
  String toString() => 'TusException: $message';
}
