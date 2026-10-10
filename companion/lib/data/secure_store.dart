import 'dart:convert';
import 'dart:math';
import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Secretos en keystore (Android) / keychain-DPAPI (Windows).
/// - device_token del emparejamiento.
/// - clave AES-256-GCM para cifrar audios en reposo (se genera una vez;
///   ver AudioVault y README §Seguridad si se pierde).
/// - hash del PIN de apertura (la biometría se verifica con local_auth en UI).
class SecureStore {
  static const _tokenKey = 'device_token';
  static const _audioKey = 'audio_key_b64';
  static const _pinHashKey = 'pin_hash';

  final FlutterSecureStorage _s = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  Future<void> saveDeviceToken(String token) => _s.write(key: _tokenKey, value: token);
  Future<String?> readDeviceToken() => _s.read(key: _tokenKey);
  Future<void> clearDeviceToken() => _s.delete(key: _tokenKey);

  /// Clave de 32 bytes para AES-256-GCM (audios). Se crea una sola vez.
  Future<List<int>> audioKey() async {
    final saved = await _s.read(key: _audioKey);
    if (saved != null && saved.isNotEmpty) return base64Decode(saved);
    final rnd = Random.secure();
    final key = List<int>.generate(32, (_) => rnd.nextInt(256));
    await _s.write(key: _audioKey, value: base64Encode(key));
    return key;
  }

  Future<void> setPin(String pin) async {
    final salt = List<int>.generate(16, (_) => Random.secure().nextInt(256));
    final h = sha256.convert([...salt, ...utf8.encode(pin)]).toString();
    await _s.write(key: _pinHashKey, value: '${base64Encode(salt)}:$h');
  }

  Future<bool> hasPin() async => (await _s.read(key: _pinHashKey)) != null;

  Future<bool> checkPin(String pin) async {
    final saved = await _s.read(key: _pinHashKey);
    if (saved == null) return false;
    final parts = saved.split(':');
    if (parts.length != 2) return false;
    final h = sha256.convert([...base64Decode(parts[0]), ...utf8.encode(pin)]).toString();
    return h == parts[1];
  }
}
