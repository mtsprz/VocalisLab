/// Configuración global de Vocalis Companion.
/// Sin secretos hardcodeados: el device_token vive en almacenamiento seguro.
class AppConfig {
  // Backend real de vocalis-lab.vercel.app (verificado en su bundle JS el
  // 2026-10-09). `vocalislab-api.onrender.com` (docs §0) no existe en Render.
  static const String backendBase = 'https://vocalislab.onrender.com';
  static const String apiPrefix = '/api/companion';

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
