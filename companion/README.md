# Vocalis Companion

App Flutter (Android + Windows), offline-first, para grabar sesiones de terapia
vocal sin internet, medir el tono en el dispositivo (estilo SpeechPitch) y
sincronizar con VocalisLab cuando hay conexión.

Contrato del backend (fuente de verdad): `../docs/companion-api.md` §0–§7.

## Prioridades (en orden)
1. La grabación jamás se pierde (bloques WAV + recuperación al abrir).
2. Tono en Hz y dB medido en el dispositivo (YIN en isolate, sin Praat/Python).
3. La sesión llega a la ficha clínica (idempotencia por `device_session_id`).
4. Lo demás.

## Estructura
```
lib/
  main.dart, app.dart, config.dart
  core/dsp/      yin.dart, metrics.dart, dsp_isolate.dart
  core/audio/    wav.dart, recorder_service.dart, compressor.dart
  data/          db.dart, patient_repository.dart, session_store.dart,
                 secure_store.dart, settings_store.dart
  sync/          api_client.dart, tus_client.dart, sync_engine.dart,
                 pairing.dart, foreground_service.dart
  ui/            theme.dart + 7 pantallas
test/            yin/metrics/wav/sync/store (flutter test)
android/...      AndroidManifest (permisos) + MainActivity.kt (MediaCodec AAC)
```

## Instalación (con Flutter SDK ≥3.22)
```bash
cd companion
flutter pub get
flutter analyze
flutter test
flutter run -d windows    # o un dispositivo Android
```

> Estado: código completo y revisado, pero **sin ejecutar aquí** (esta máquina
> no tiene Flutter SDK). Antes de firmar un release, correr `flutter pub get`,
> `flutter analyze`, `flutter test` y validar las pruebas DSP contra
> grabaciones reales (ver §Validación).

## Emparejamiento
1. Web VocalisLab → Voz y sesiones → Dispositivos → Generar código (10 min).
2. Companion → pegar código + nombre del equipo → Emparejar.
3. El `device_token` queda en almacenamiento seguro; nunca se muestra.
4. Revocar desde la misma pantalla web.

## Compresión (decisión documentada)
- **Android**: MediaCodec vía MethodChannel (`MainActivity.kt`,
  `compressToAac`). Sin dependencias nativas extra.
- **Windows**: `ffmpeg.exe` empaquetado junto al `.exe` (misma carpeta) o en
  PATH. Comando equivalente:
  `ffmpeg -y -i sesion.wav -ac 1 -ar 44100 -c:a aac -b:a 48k sesion.m4a`.
- No se usa `ffmpeg_kit_flutter` (discontinuado).
- Proyecto base: generar con
  `flutter create --platforms=android,windows --org com.vocalis .`
  dentro de `companion/` y luego copiar encima `android/...` de este repo.

## Windows (instalador MSIX)
1. `dart run msix:create` (config en `pubspec.yaml:msix_config`).
2. Copiar `ffmpeg.exe` (builds oficiales: gyan.dev) junto al instalable o
   dejarlo en PATH.
3. Firmar con certificado propio (`vocalis.pfx`); sin firma Windows bloquea.

## Android (APK firmado)
1. Generar keystore: `keytool -genkey -v -keystore vocalis.keystore ...`
2. `android/key.properties` (NO commitear) + firma en `build.gradle`.
3. `flutter build apk --release --split-per-abi`.
4. En Android 13+: pedir `POST_NOTIFICATIONS` en runtime (el manifest ya lo declara).

## Primer proyecto Android/Windows
Este repo trae `android/` parcial (manifest + MainActivity). Para compilar:
`flutter create --platforms=android,windows --org com.vocalis --project-name
vocalis_companion .` en una copia temporal, copiar `android/` y `windows/`
generados aquí, y encima los archivos de este repo.

## Validación DSP (obligatoria antes del release)
- `flutter test` incluye tonos sintéticos (110/196/261.6/350 Hz, tolerancia
  ±1 Hz o ±1 %), ruido y silencio.
- Falta (con grabaciones reales + Praat): soltar WAVs de referencia en
  `test/fixtures/` (voz masculina, femenina, infantil, ruido, silencio) y
  comparar F0 medio contra Praat/SpeechPitch. El módulo no se da por
  terminado sin ese paso (ver `test/yin_test.dart`, sezione fixtures).

## Seguridad
- Audios cifrados en reposo (Salsa20, clave en keystore/DPAPI).
- PIN o biometría para abrir (`local_auth` + hash en secure storage).
- Base local solo con metadata; `sqflite_sqlcipher` queda como mejora documentada.
- Nunca borrar audio local hasta `processed` + retención configurable (def. 30 días).

## Flujo de pantallas
Elegir paciente (caché) → Consentimiento (obligatorio) → Grabar (tareas +
hablante + medidor dB) → Resumen inmediato (métricas + histograma + rango) →
Sincronizar (estados, 409 con acción) · Ajustes (Wi-Fi, retención, dB, PIN).
