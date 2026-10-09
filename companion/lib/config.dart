/// Configuración global de Vocalis Companion.
/// Sin secretos hardcodeados: el device_token vive en almacenamiento seguro.
class AppConfig {
  static const String backendBase = 'https://vocalislab-api.onrender.com';
  static const String apiPrefix = '/api/companion';

  /// true cuando el backend agregue GET /api/companion/pacientes
  /// (ver docs/pedido-endpoint-pacientes-companion.md). Mientras tanto: mock.
  static const bool remotePatientsEnabled = false;

  // Audio: mono PCM 16-bit 44.1 kHz, bloques de 30 s.
  static const int sampleRate = 44100;
  static const int channels = 1;
  static const int blockSeconds = 30;

  // Sincronización
  static const int healthTimeoutSeconds = 75;
  static const int maxUploadBytes = 45 * 1024 * 1024;
  static const List<int> backoffSeconds = [5, 15, 30, 60];
  static const int pollMinutesMax = 30;
  static const bool wifiOnlyDefault = true;

  // Compresión sesión: AAC/m4a mono ~48 kbps.
  static const int aacBitrate = 48000;

  // Retención local: no borrar audio hasta processed + N días.
  static const int localRetentionDaysDefault = 30;

  static const String dspVersion = 'companion-dsp/1.0';
}
