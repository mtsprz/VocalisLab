import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

/// Contrato TUS (inyectable para tests).
abstract class TusGateway {
  /// Crea la subida y devuelve la URL de destino (Location). Lanza
  /// [TusYaSubido] si el objeto ya existe completo en Storage.
  Future<String> create(String uploadUrl, int length, String filename,
      {String mime = 'application/octet-stream',});
  Future<int> offset(String locationUrl, {required String bearerToken});
  Future<int> uploadFile(String locationUrl, File file,
      {int offset = 0,
      required String bearerToken,
      void Function(int sent, int total)? onProgress,});
}

/// Destino TUS derivado de la `upload_url` que firma el backend.
///
/// El backend (`POST /uploads`) devuelve la URL de `create_signed_upload_url`
/// de Supabase: `https://<ref>.supabase.co/storage/v1/object/upload/sign/<bucket>/<objeto>?token=<t>`.
/// Ese endpoint es de subida estándar (PUT), no TUS. Para TUS, Supabase usa
/// `/storage/v1/upload/resumable` con el mismo token en `x-signature` y
/// bucket/objeto en `Upload-Metadata` (docs Supabase: Resumable Uploads).
class DestinoTus {
  final Uri endpoint;
  final String? bucket;
  final String? objeto;
  final String? firma;

  const DestinoTus(this.endpoint, {this.bucket, this.objeto, this.firma});

  bool get esSupabaseFirmado => firma != null;

  static const _marca = '/object/upload/sign/';

  /// Acepta la URL aunque traiga barras dobles (supabase-py arma
  /// ".../storage/v1//object/upload/sign/..."). Si no es una URL firmada de
  /// Supabase lanza [TusException]: nunca se sube a una URL desconocida ni se
  /// manda el device_token fuera del backend propio.
  factory DestinoTus.desde(String uploadUrl) {
    final u = Uri.parse(uploadUrl);
    final ruta = u.path.replaceAll(RegExp('/{2,}'), '/');
    final i = ruta.indexOf(_marca);
    final token = u.queryParameters['token'];
    if (i < 0 || token == null || token.isEmpty) {
      throw const TusException('URL de subida no reconocida (no es una URL firmada de Supabase)');
    }
    final resto = Uri.decodeComponent(ruta.substring(i + _marca.length));
    final barra = resto.indexOf('/');
    if (barra <= 0) throw const TusException('URL de subida sin bucket/objeto');
    return DestinoTus(
      Uri(scheme: u.scheme, host: u.host, port: u.port,
          path: '${ruta.substring(0, i)}/upload/resumable',),
      bucket: resto.substring(0, barra),
      objeto: resto.substring(barra + 1),
      firma: token,
    );
  }
}

/// Cliente TUS mínimo y reanudable (Tus-Resumable 1.0.0) para las
/// `upload_url` firmadas del backend. Sin dependencias extra.
///
/// Supabase exige bloques de exactamente 6 MB salvo el último.
/// El device_token NO se envía a Supabase (no es un JWT de Supabase y no
/// debe salir del backend propio); la autorización es la firma `x-signature`.
class TusClient implements TusGateway {
  static const chunkBytes = 6 * 1024 * 1024;

  final http.Client _http;
  final Map<String, String> _firmas = {};

  TusClient({http.Client? httpClient}) : _http = httpClient ?? http.Client();

  Map<String, String> _auth(String url, String bearerToken) {
    final firma = _firmas[url];
    if (firma == null) throw const TusException('Subida sin firma: se canceló por seguridad');
    return {'x-signature': firma};
  }

  String _b64(String v) => base64Encode(utf8.encode(v));

  /// Crea la subida. Devuelve la URL de destino (cabecera Location).
  @override
  Future<String> create(String uploadUrl, int length, String filename,
      {String mime = 'application/octet-stream',}) async {
    final d = DestinoTus.desde(uploadUrl);
    final meta = 'bucketName ${_b64(d.bucket!)},objectName ${_b64(d.objeto!)},'
        'contentType ${_b64(mime)},cacheControl ${_b64('3600')}';
    final r = await _http.post(
      d.endpoint,
      headers: {
        'Tus-Resumable': '1.0.0',
        'Upload-Length': '$length',
        'Upload-Metadata': meta,
        'x-signature': d.firma!,
      },
    ).timeout(const Duration(seconds: 75));
    if (r.statusCode == 409 && d.esSupabaseFirmado) {
      // El objeto ya está completo (subida previa sin confirmar).
      throw const TusYaSubido();
    }
    if (r.statusCode != 201 && r.statusCode != 200) {
      throw TusException('create: HTTP ${r.statusCode} ${r.body}');
    }
    final loc = r.headers['location'] ?? '';
    if (loc.isEmpty) throw const TusException('create sin Location');
    // Location puede ser relativa: resolver contra el endpoint.
    final destino = d.endpoint.resolve(loc).toString();
    if (d.esSupabaseFirmado) _firmas[destino] = d.firma!;
    return destino;
  }

  /// Offset ya subido (para reanudar tras un corte).
  @override
  Future<int> offset(String locationUrl, {required String bearerToken}) async {
    final r = await _http.head(
      Uri.parse(locationUrl),
      headers: {'Tus-Resumable': '1.0.0', ..._auth(locationUrl, bearerToken)},
    ).timeout(const Duration(seconds: 60));
    if (r.statusCode != 200 && r.statusCode != 204) {
      throw TusException('offset: HTTP ${r.statusCode}');
    }
    return int.tryParse(r.headers['upload-offset'] ?? '0') ?? 0;
  }

  /// Sube [file] desde [offset] en bloques de 6 MB (el último puede ser
  /// menor). Devuelve el offset final.
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
    final raf = await file.open(mode: FileMode.read);
    try {
      while (off < total) {
        await raf.setPosition(off);
        final n = ((total - off).clamp(0, chunkBytes)).toInt();
        final buf = await raf.read(n);
        final req = http.Request('PATCH', Uri.parse(locationUrl))
          ..headers['Tus-Resumable'] = '1.0.0'
          ..headers.addAll(_auth(locationUrl, bearerToken))
          ..headers['Content-Type'] = 'application/offset+octet-stream'
          ..headers['Upload-Offset'] = '$off'
          ..bodyBytes = buf;
        final resp = await _http.send(req).timeout(const Duration(minutes: 5));
        await resp.stream.drain<void>();
        if (resp.statusCode != 204 && resp.statusCode != 200) {
          throw TusException('patch @$off: HTTP ${resp.statusCode}');
        }
        final next = resp.headers['upload-offset'];
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

/// El objeto ya existe completo en Storage: no hay que volver a subirlo.
class TusYaSubido implements Exception {
  const TusYaSubido();
}
