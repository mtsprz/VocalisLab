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
