# Vocalis Companion

App Flutter (Android + Windows), offline-first, para grabar sesiones de terapia
vocal sin internet, medir la **altura tonal** del paciente en el dispositivo
(F0 en Hz + nota musical) y sincronizar con VocalisLab cuando hay conexión.

Contrato del backend (fuente de verdad): `../docs/companion-api.md` §0–§7.

## Alcance
Lo que la app entrega del paciente es su **altura tonal** y los **Hz** de su
voz, medidos con YIN en Dart y solo sobre los tramos marcados
"Paciente habla":

- `f0_mean_hz`, `f0_median_hz`, `f0_p5_hz`, `f0_p95_hz`, `f0_min_hz`,
  `f0_max_hz`, `voiced_fraction`, `f0_sd_semitones`, `f0_sd_hz`,
  `f0_histogram`, `f0_contour`.
- **Métrica principal:** `f0_median_hz` de la conversación espontánea. Si no
  se marcó esa tarea, la de todos los tramos del paciente juntos (calculada
  localmente, archivo `tono_global.json`; no viaja al backend).
- **Nota musical** (solo presentación, no se envía): `n = round(12·log2(f/440))`,
  nombres Do, Do#, Re, Re#, Mi, Fa, Fa#, Sol, Sol#, La, La#, Si, octava en
  notación científica (convención franco-belga: La3 = 440 Hz, Do3 = Do central, Do0 ≈ 33 Hz). Ej.: `Do#2 · 139 Hz`.

**Fuera de alcance:** jitter, shimmer, HNR, tiempo máximo de fonación (MPT) e
intensidad en dB. No se calculan ni se muestran; en `acoustics[]` viajan como
`null` (el contrato los admite: §3 los muestra en null y el servidor los lee
con `a.get(...)`). Durante la grabación queda solo un **indicador de nivel**
sin cifras, que avisa si la entrada satura.

Transcripción, diarización, audio, ficha, sincronización y emparejamiento no
cambian.

## Equipos destino (únicos)
- **Samsung Galaxy A02 (SM-A022M)**: Android 11 (SDK 30), **32 bits
  (`armeabi-v7a`)**, 1,9 GB de RAM. Por eso:
  - El análisis de tono lee el WAV **por tramos de 5 s desde disco** y hace
    una sola pasada. Cargarlo entero (45 min ≈ 950 MB como doubles) haría que
    Android cerrara la app.
  - El clip se recorta copiando bytes, sin cargar el WAV.
  - Al grabar por primera vez se pide **quedar fuera del ahorro de batería**:
    One UI duerme las apps en segundo plano y corta el micrófono y la
    sincronización.
  - Usar la build **release** (`flutter build apk --release --target-platform
    android-arm`): en debug el análisis va varias veces más lento.
  - Las reglas de Android 13/14 (permiso de notificaciones en runtime, tipo de
    servicio exigido) no aplican en este equipo; el código las respeta igual.
- **PC Windows 10 Pro 64 bits**: necesita Visual Studio 2022 con la carga
  "Desarrollo para el escritorio con C++" para compilar (`flutter build
  windows`) y `ffmpeg.exe` en PATH para comprimir (ya está, instalado con winget).
  En Windows no hay servicio en primer plano ni WorkManager: la sincronización
  es manual desde la pestaña Sincronizar.

## Prioridades (en orden)
1. La grabación jamás se pierde (bloques WAV de 30 s + recuperación).
2. Altura tonal en Hz medida en el dispositivo (YIN en isolate).
3. La sesión llega a la ficha clínica (idempotencia por `device_session_id`).
4. Lo demás.

## Estructura
```
lib/
  main.dart, app.dart, config.dart
  core/dsp/      yin.dart, metrics.dart, nota.dart, dsp_isolate.dart
  core/audio/    wav.dart, recorder_service.dart, compressor.dart
  core/          finalizar_sesion.dart (Detener y recuperación usan el mismo camino)
  data/          db.dart, patient_repository.dart, session_store.dart,
                 secure_store.dart, settings_store.dart, audio_vault.dart
  sync/          api_client.dart, tus_client.dart, sync_engine.dart,
                 pairing.dart, foreground_service.dart, tareas_fondo.dart
  ui/            theme.dart + 7 pantallas
test/            yin, metrics, nota, wav, store, sync, tus, cifrado,
                 fixtures_praat (validación contra Praat)
android/, windows/  generados con `flutter create` + manifest y MainActivity propios
```

## Instalación (Flutter SDK ≥3.22; verificado con 3.47.7)
```bash
cd companion
flutter pub get
flutter analyze
flutter test
flutter run            # Android conectado, o -d windows
```

## Grabación y segmentos
- Fuente Android `VOICE_RECOGNITION` + AGC/supresión de ruido/cancelación de eco
  apagados. El CDD de Android exige que esa fuente no tenga AGC ni reducción de
  ruido.
- Cada cambio de "Paciente habla / Fonoaudiólogo" corta el tramo en curso: cada
  segmento tiene un único hablante.
- Si no se marca ninguna tarea, los turnos de hablante se envían como
  `conversacion_espontanea` (el servidor exige `segments` no vacío con
  `task_type` válido).
- La sesión se crea en la base al empezar a grabar y las marcas se guardan en
  `marcas.json` cada 5 s. Si la app muere, la sesión aparece en
  **Sincronizar → "Grabación interrumpida: recuperar"**.
- Cambiar de pestaña no corta la grabación (`IndexedStack`), y el servicio en
  primer plano de tipo `microphone` la mantiene con la pantalla apagada.

## Emparejamiento
1. Web VocalisLab → Voz y sesiones → Dispositivos → Generar código (10 min).
2. Companion → pegar código + nombre del equipo → Emparejar.
3. El `device_token` queda en almacenamiento seguro y nunca se muestra.
4. Se revoca desde la misma pantalla web.

## Subida TUS (Supabase)
`POST /uploads` devuelve la URL de `create_signed_upload_url` de Supabase
(`/storage/v1/object/upload/sign/<bucket>/<objeto>?token=…`), que es un
endpoint de subida estándar. El cliente deriva de esa URL el endpoint TUS
`/storage/v1/upload/resumable`, manda el token en `x-signature` y
`bucketName`/`objectName` en `Upload-Metadata`, en **bloques de 6 MB salvo el
último**, como pide la doc de Supabase (Resumable Uploads). El `device_token`
no se envía a Supabase.

## Compresión
- **Android**: MediaCodec vía MethodChannel (`MainActivity.kt`, `compressToAac`).
- **Windows**: `ffmpeg.exe` junto al `.exe` o en PATH
  (`ffmpeg -y -i sesion.wav -ac 1 -ar 44100 -c:a aac -b:a 48k sesion.m4a`).
- No se usa `ffmpeg_kit_flutter` (discontinuado).

## Seguridad
- **Audio cifrado en reposo con AES-256-GCM** (`cryptography` +
  `cryptography_flutter`, nativo en Android), en bloques de 1 MiB con nonce
  aleatorio y AAD de índice + "último bloque", así que se detecta
  manipulación, reordenamiento y truncado. Se cifran `sesion.wav`, `sesion.m4a`
  y los clips (`*.enc`). Los WAV planos se borran solo **después** de verificar
  el `.enc` completo. Para comprimir o subir se descifra a un temporal en caché,
  que se borra al terminar.
- Clave de 32 bytes en `flutter_secure_storage` (Android Keystore /
  Windows DPAPI). `android:allowBackup="false"`.
- **Si se pierde la clave** (desinstalar la app, "Borrar datos", restablecer el
  equipo o un fallo del Keystore): los `.enc` locales **no se pueden
  descifrar**. Ningún audio que el servidor ya tenga en `processed` se pierde,
  porque está en VocalisLab. Las sesiones sin sincronizar pierden el audio. Sus
  métricas de F0 siguen en la base local (no se cifra) y se ven en el resumen,
  pero la sesión queda en ERROR y no sincroniza, porque el flujo exige el
  archivo de audio. Se genera una clave nueva para lo que se grabe después,
  pero la app no borra ni pisa los
  `.enc` ilegibles: muestra `ClaveAudioInvalida` y los deja en disco por si la
  clave reaparece. **Recomendación operativa:** sincronizar al terminar cada
  jornada y no borrar datos de la app con sesiones pendientes.
- Las sesiones grabadas antes del cifrado (WAV/m4a planos) se siguen leyendo.
- PIN o biometría para abrir (`local_auth`; `MainActivity` es
  `FlutterFragmentActivity`, que la biometría necesita).
- El audio local nunca se borra antes de `processed` (estado SYNCED). "Liberar
  espacio" solo borra sesiones SYNCED más viejas que la retención configurada
  (30 días por defecto).

## Validación de F0 (obligatoria antes del release)
- `flutter test` incluye tonos sintéticos (110 / 196 / 261,6 / 350 Hz,
  tolerancia ±1 Hz o ±1 %), ruido y silencio.
- **Con grabaciones reales:** dejar 4-5 WAV (PCM 16-bit mono 44,1 kHz, solo voz
  del paciente) en `test/fixtures/` y completar `f0_median_hz` y `f0_mean_hz`
  medidos con Praat o SpeechPitch en `test/fixtures/referencias_praat.json`.
  `test/fixtures_praat_test.dart` compara mediana y media (±1 Hz o ±1 %). Los
  casos sin valores aparecen como *skipped*.

## Android (APK)
- Debug: `flutter build apk --debug`.
- Release: keystore propio + `android/key.properties` (no commitear) + firma en
  `android/app/build.gradle.kts`; `flutter build apk --release --split-per-abi`.
- `POST_NOTIFICATIONS` se pide en tiempo de ejecución al empezar la primera grabación.

## Windows (instalador MSIX)
1. `dart run msix:create` (config en `pubspec.yaml:msix_config`).
2. `ffmpeg.exe` junto al instalable o en PATH.
3. Firmar con certificado propio (`vocalis.pfx`).

## Flujo de pantallas
Elegir paciente (caché) → Consentimiento (obligatorio) → Grabar (tareas +
hablante + indicador de nivel) → Resumen (mediana en Hz + nota, rango p5–p95,
histograma, comparación con el rango de referencia por sexo y edad, orientativa)
→ Sincronizar (estados, 409 con acción, recuperar interrumpidas) · Ajustes
(Wi-Fi, retención, PIN).

## Estado de verificación
Ver `CLAUDE.md` §Estado: separa lo **verificado ejecutando** de lo **revisado
leyendo**.
