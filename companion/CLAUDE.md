# Vocalis Companion — guía para agentes

App Flutter (Android + Windows) offline-first. Contrato con el backend:
`../docs/companion-api.md` (no cambiarlo desde acá; si el servidor pide un
campo que no calculamos, se envía `null` y se avisa).

## Alcance (vigente desde 2026-10-09)
- La app entrega del paciente su **altura tonal**: F0 en Hz (YIN en Dart,
  ventana 40 ms, paso 10 ms, umbral 0,15, rango por sexo) **solo sobre tramos
  "paciente"**: `f0_mean_hz, f0_median_hz, f0_p5_hz, f0_p95_hz, f0_min_hz,
  f0_max_hz, voiced_fraction, f0_sd_semitones, f0_sd_hz, f0_histogram,
  f0_contour`.
- Métrica principal: `f0_median_hz` de `conversacion_espontanea`; si no hubo,
  la de todos los tramos del paciente (`tono_global.json`, solo local).
- Nota musical solo para presentación (`lib/core/dsp/nota.dart`): La4 = 440 Hz,
  Do4 = Do central, nombres en español. No se envía al backend.
- **No implementar**: jitter, shimmer, HNR, MPT, intensidad/dB ni medidor con
  cifras. En `acoustics[]` esos campos van `null` (`TaskMetrics.toJson`).
- Sin cambios: transcripción, diarización, audio, ficha, sincronización y emparejamiento.

## Equipos destino
Galaxy A02 (Android 11, armeabi-v7a, 1,9 GB RAM) y una PC con Windows 10. Nada
puede cargar un WAV de sesión entero en memoria: usar `leerRango`/streaming
(`dsp_isolate.dart`) o copia de bytes (`recortarWav`).

## Reglas que no se negocian
1. La grabación no se pierde: bloques WAV de 30 s, la fila de la sesión se
   crea al empezar y las marcas se guardan en `marcas.json`. Recuperación desde
   Sincronizar. Las escrituras de PCM van en serie (`RecorderService._cola`).
2. El audio local no se borra antes de `processed` (estado `synced`). Solo se
   borran copias planas después de verificar su `.enc`, y los temporales de
   descifrado.
3. Audio en reposo cifrado con AES-256-GCM (`lib/data/audio_vault.dart`). Para
   leer cualquier audio local se usa `rutaPlana(...)`, nunca la ruta directa.
4. Android: fuente `VOICE_RECOGNITION` y AGC/NS/AEC en `false`
   (`recorder_service.dart`). Servicio en primer plano de tipo `microphone`.
5. TUS contra Supabase: bloques de 6 MB salvo el último, firma en
   `x-signature`. El `device_token` nunca va a Supabase (`tus_client.dart`).
6. Las APIs de plugins quedan aisladas en `recorder_service.dart` (record),
   `foreground_service.dart` (flutter_foreground_task) y `tareas_fondo.dart`
   (workmanager). Si cambian, se adapta solo ahí.

## Comandos
```bash
flutter pub get && flutter analyze && flutter test
flutter build apk --debug
flutter run            # con el teléfono conectado (adb devices)
```
En esta máquina `flutter analyze` tarda ~1 min y el primer `flutter test`, varios.

## Estado
Ver la sección "Estado de verificación" al final; se actualiza en cada pasada.

## Estado de verificación (pasada 2026-10-09, Flutter 3.47.7 / Dart 3.13.5, Windows 10)

### Verificado ejecutando
- `flutter pub get`: OK.
- `flutter analyze`: **No issues found**.
- `flutter test`: **44 pasan, 5 omitidos** (los 5 casos de Praat esperan WAV
  reales y valores en `test/fixtures/referencias_praat.json`). Cubre YIN con
  tonos sintéticos, métricas de F0 y nulls del payload, nota musical, rango por
  sexo/edad, WAV y recuperación de bloques, store, motor de sync (orden,
  409, backoff, reanudación), TUS (6 MB, `x-signature`, sin device_token) y
  cifrado AES-GCM (ida y vuelta, clave equivocada, manipulación, truncado).
- `flutter build apk --debug`: OK; instalada y abierta en el Galaxy A02
  (`flutter run`, llegó a la pantalla de emparejamiento).
- Backend publicado: `vocalislab.onrender.com/api/companion/health` → ok.
- Supabase Storage acepta `x-signature` en TUS sin `apikey` (probado con
  una firma inválida: responde "Invalid Compact JWS", no "falta API key").

### Revisado leyendo (NO ejecutado)
- Todo lo que depende de un teléfono: grabación real, pantalla apagada,
  segundo plano, servicio en primer plano tipo `microphone` (Android 14+),
  notificación, cierre forzado + recuperación, biometría, compresión
  MediaCodec, cifrado con `cryptography_flutter` nativo, workmanager.
- Subida TUS contra Supabase real. Que Storage acepte el token de
  `create_signed_upload_url` en `x-signature` sale de la doc de Supabase,
  igual que el tamaño de bloque de 6 MB (la doc no dice explícitamente "salvo
  el último"; es lo normal en TUS). Falta una subida real de punta a punta.
- Desactivación de AGC/NS/AEC: leído en `record_android 1.5.2`
  (`PCMReader.kt` crea los efectos con `enabled = false`). Fuente
  `VOICE_RECOGNITION` según el CDD de Android.
- Aceptación de nulls por el servidor: `server_api/companion.py` lee los
  campos con `a.get(...)`; contrato §3 los muestra en `null`.
- Exactitud de F0 contra Praat/SpeechPitch con voces reales: **pendiente**
  (necesita los WAV y los valores de referencia).
