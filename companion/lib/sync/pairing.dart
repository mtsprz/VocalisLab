import 'dart:io' show Platform;

import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';

import '../data/secure_store.dart';
import 'api_client.dart';

/// Emparejamiento: canjea el código de 10 min por el device_token y lo
/// guarda en almacenamiento seguro. El token nunca se muestra en UI.
Future<String> emparejar({
  required CompanionApi api,
  required SecureStore secure,
  required String code,
  required String deviceName,
}) async {
  final r = await api.pair(code, deviceName);
  final token = '${r['device_token'] ?? ''}';
  if (token.isEmpty) throw Exception('Emparejamiento sin token');
  await secure.saveDeviceToken(token);
  return token;
}

/// Android: esquema propio capturado por CallbackActivity (AndroidManifest).
/// Windows: flutter_web_auth_2 escucha en localhost (sin webview).
const _esquemaAndroid = 'vocaliscompanion';
const _localhostWindows = 'http://localhost:43823';

/// Vinculación con Google (necesita internet solo esta vez). El backend hace
/// el login, crea un código de un solo uso y vuelve a la app con `?code=`;
/// acá se canjea con [emparejar] igual que un código manual.
Future<String> emparejarConGoogle({
  required ApiClient api,
  required SecureStore secure,
  required String deviceName,
}) async {
  final returnTo = Platform.isWindows ? _localhostWindows : '$_esquemaAndroid://auth';
  final resultado = await FlutterWebAuth2.authenticate(
    url: api.googleStartUrl(returnTo),
    callbackUrlScheme: Platform.isWindows ? _localhostWindows : _esquemaAndroid,
    options: const FlutterWebAuth2Options(useWebview: false),
  );
  final q = Uri.parse(resultado).queryParameters;
  final error = q['error'];
  if (error != null) throw Exception(mensajeErrorGoogle(error, q['email'], q['detalle']));
  final code = q['code'] ?? '';
  if (code.isEmpty) throw Exception('Google no devolvió el código de vinculación');
  return emparejar(api: api, secure: secure, code: code, deviceName: deviceName);
}

String mensajeErrorGoogle(String error, [String? email, String? detalle]) => switch (error) {
      'no_habilitado' =>
        'La cuenta ${email ?? ''} no está habilitada. Agregala en Render → '
            'COMPANION_GOOGLE_EMAILS.',
      'cuenta_invalida' => 'Google no confirmó el email de la cuenta.',
      'google_token' => 'Google rechazó el inicio de sesión. Probá de nuevo.',
      'sin_base' => 'El servidor no tiene la base configurada.',
      _ => 'No se pudo vincular ($error). Probá de nuevo.'
          '${detalle == null ? '' : '\nDetalle: $detalle'}',
    };
