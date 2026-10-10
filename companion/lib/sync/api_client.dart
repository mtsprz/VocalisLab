import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import '../config.dart';
import '../data/secure_store.dart';

/// Error tipado del backend `{ok:false}`.
class ApiException implements Exception {
  final int status;
  final String message;
  final Map<String, dynamic>? body;

  ApiException(this.status, this.message, [this.body]);

  /// 409 de sesión ya procesada: el servidor pide acción (consentimiento, etc.).
  bool get needsAction => status == 409;

  @override
  String toString() => 'ApiException($status): $message';
}

/// Contrato de red (inyectable para tests).
abstract class CompanionApi {
  Future<Map<String, dynamic>> health();
  Future<Map<String, dynamic>> pair(String code, String deviceName);
  Future<Map<String, dynamic>> postSessions(Map<String, dynamic> payload);
  Future<Map<String, dynamic>> postUploads(Map<String, dynamic> payload);
  Future<Map<String, dynamic>> confirmUpload(Map<String, dynamic> payload);
  Future<Map<String, dynamic>> getSession(String serverSessionId);
  Future<Map<String, dynamic>> getReferencias();
}

class ApiClient implements CompanionApi {
  final SecureStore secure;
  final http.Client _http;

  ApiClient({required this.secure, http.Client? httpClient})
      : _http = httpClient ?? http.Client();

  String get _base => '${AppConfig.backendBase}${AppConfig.apiPrefix}';

  Future<Map<String, String>> _headers({bool auth = true}) async {
    final h = {'Content-Type': 'application/json'};
    if (auth) {
      final t = await secure.readDeviceToken();
      if (t == null || t.isEmpty) {
        throw ApiException(401, 'Sin emparejar: ingresá el código en Ajustes');
      }
      h['Authorization'] = 'Bearer $t';
    }
    return h;
  }

  Future<Map<String, dynamic>> _post(
      String path, Map<String, dynamic> body, Duration timeout,) async {
    final r = await _http
        .post(Uri.parse('$_base$path'),
            headers: await _headers(), body: jsonEncode(body),)
        .timeout(timeout);
    return _decode(r);
  }

  Future<Map<String, dynamic>> _get(String path, Duration timeout) async {
    final r = await _http
        .get(Uri.parse('$_base$path'), headers: await _headers())
        .timeout(timeout);
    return _decode(r);
  }

  Map<String, dynamic> _decode(http.Response r) {
    dynamic d;
    try {
      d = jsonDecode(r.body);
    } catch (_) {
      d = {};
    }
    if (r.statusCode >= 200 && r.statusCode < 300) {
      return d is Map<String, dynamic> ? d : {'ok': true, 'data': d};
    }
    final msg = d is Map && d['error'] is String
        ? d['error'] as String
        : (d is Map && d['detail'] is String ? d['detail'] as String : 'Error ${r.statusCode}');
    throw ApiException(r.statusCode, msg, d is Map<String, dynamic> ? d : null);
  }

  @override
  Future<Map<String, dynamic>> health() async {
    final r = await _http
        .get(Uri.parse('$_base/health'))
        .timeout(const Duration(seconds: AppConfig.healthTimeoutSeconds));
    return _decode(r);
  }

  @override
  Future<Map<String, dynamic>> pair(String code, String deviceName) async {
    final r = await http
        .post(Uri.parse('$_base/pair'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode({'code': code.trim().toUpperCase(), 'device_name': deviceName}),)
        .timeout(const Duration(seconds: 75));
    return _decode(r);
  }

  @override
  Future<Map<String, dynamic>> postSessions(Map<String, dynamic> payload) =>
      _post('/sessions', payload, const Duration(seconds: 75));

  @override
  Future<Map<String, dynamic>> postUploads(Map<String, dynamic> payload) =>
      _post('/uploads', payload, const Duration(seconds: 75));

  @override
  Future<Map<String, dynamic>> confirmUpload(Map<String, dynamic> payload) =>
      _post('/uploads/confirm', payload, const Duration(seconds: 75));

  @override
  Future<Map<String, dynamic>> getSession(String serverSessionId) =>
      _get('/sessions/$serverSessionId', const Duration(seconds: 75));

  @override
  Future<Map<String, dynamic>> getReferencias() =>
      _get('/referencias', const Duration(seconds: 75));

  void close() => _http.close();
}
