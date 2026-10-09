# Vocalis Companion — Contrato de API v1

Base: `https://vocalislab-api.onrender.com` · Prefijo: `/api/companion`
Decisiones de diseño (conservadoras, documentadas): ver §12.

## 0. Quickstart para el agente Companion (copiar/pegar)

```
BASE=https://vocalislab-api.onrender.com
1) GET  $BASE/api/companion/health                       -> {ok:true} (despierta cold start ~50s; timeout cliente 75s)
2) POST $BASE/api/companion/pair  {code:"ABC123"}        -> {device_token:"..."} (guardar seguro; se muestra 1 vez)
3) POST $BASE/api/companion/sessions  (Bearer token)
    {device_session_id, patient_id, recorded_at, audio_duration_sec,
     audio_codec:"opus", audio_bitrate_kbps:48, dsp_version:"companion-dsp/1.0",
     device_info:{...}, consent_recorded:true,
     segments:[{task_type,speaker,start_sec,end_sec}],
     acoustics:[{task_type, f0_mean_hz, ..., f0_histogram, f0_contour, dsp_version}],
     clips:[{task_type, duration_sec}] }                  -> {session_id, status}
4) POST $BASE/api/companion/uploads (Bearer)
    {device_session_id, kind:"session_audio"|"clip", task_type?, mime, size_bytes}
    -> {upload_url, path, expires_in:3600}
   Subir con TUS reanudable contra upload_url (cabeceras Tus-Resumable: 1.0.0,
   Upload-Length, Upload-Metadata). Clips WAV: uno por llamada con su task_type.
5) POST $BASE/api/companion/uploads/confirm (Bearer) {device_session_id, kind, task_type?}
   -> {status:"uploaded"} (encola procesamiento)
6) Poll GET $BASE/api/companion/sessions/{id} (Bearer) hasta status processed|error
   (backoff 5s,15s,30s,60s; timeout total 30 min).
```

## 1. Autenticación y emparejamiento

- La web (profesional) genera en UI un **código de un solo uso, 6 caracteres, vence 10 min**:
  `POST /api/companion/pairing-code` (usa `google_id` como el resto de la app) → `{code, expires_at}`.
- Companion: `POST /api/companion/pair {code, device_name}` → `{device_token}` (solo se muestra/entrega 1 vez).
- En base **solo se guarda el hash SHA-256** del token (`companion_devices.token_hash`).
- Todo acceso Companion usa `Authorization: Bearer <device_token>`. Token revocado/inexistente → `401`. Dispositivo de otro profesional accediendo a un paciente ajeno → `403` (el `patient_id` debe existir; el `profesional_google_id` del device manda).
- Gestión en UI: `GET /api/companion/devices` (lista + `last_seen_at`), `DELETE /api/companion/devices/{id}` (revoca). Todo acceso a audio queda en `audio_access_log`.
- Sin JWT de Supabase: coherente con el resto de la plataforma (el backend valida con service_role).

## 2. Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/api/companion/health` | no | `{ok:true, queue:{queued,processing}}`. Liviano; úsalo para despertar cold start. |
| POST | `/api/companion/pair` | no (código) | Canjea pairing code → `device_token`. Código se marca usado. |
| POST | `/api/companion/uploads` | Bearer | Firma URL de subida. Valida mime/tamaño/cuota. |
| POST | `/api/companion/uploads/confirm` | Bearer | Verifica archivo completo → `uploaded` + encola job. |
| POST | `/api/companion/sessions` | Bearer | Crea/actualiza sesión (**idempotente** por `device_session_id`). |
| GET | `/api/companion/sessions?patient_id=` | Bearer | Lista sesiones del paciente (verifica pertenencia). |
| GET | `/api/companion/sessions/{id}` | Bearer | Detalle + segmentos + acústica + transcripciones + draft + estado job. |
| GET | `/api/companion/sessions/{id}/audio-url` | Bearer | URL firmada 15 min del audio (+ log). `?clip=<clip_id>` para clips. |
| GET | `/api/companion/referencias?sexo=&edad=` | Bearer | Rango aplicable (con override del paciente si existe). |
| GET | `/api/companion/progreso?patient_id=` | Bearer | Serie `voice_progress` (nº sesión, baseline = sesión 1). |
| GET/PUT | `/api/companion/anamnesis-drafts/{session_id}` | google_id* | Leer / editar borrador. |
| POST | `/api/companion/anamnesis-drafts/{session_id}/aprobar` | google_id* | Vuelca a ficha `anamnesis` vigente. |
| POST | `/api/companion/anamnesis-drafts/{session_id}/descartar` | google_id* | Marca `discarded`. |
| POST | `/api/companion/informes/sesion` | google_id* | PDF de la sesión (firma configurable). |
| POST | `/api/companion/informes/evolucion` | google_id* | PDF de evolución con gráfico. |
| GET | `/api/companion/almacenamiento` | google_id* | `{used_bytes, quota_bytes, sessions_count}`. |
| POST | `/api/companion/mantenimiento/purgar` | google_id* | Body `{session_ids[], confirmar:true}`. Borra archivos, conserva métricas. |
| GET/DELETE | `/api/companion/devices`, `/api/companion/devices/{id}` | google_id* | Lista / revoca dispositivos. |
| POST | `/api/companion/pairing-code` | google_id* | Genera código 10 min. |

\* `google_id` = mismo modelo de confianza que el resto de la app (parámetro `user_id`).
Errores: `{ok:false, error:"..."}` con HTTP 400 (payload), 401 (token), 403 (ajeno/revocado),
404 (inexistente), 409 (conflicto de estado), 413 (tamaño), 422 (métrica inválida), 507 (cuota).

## 3. Payload `POST /api/companion/sessions` (ejemplo)

```json
{
  "device_session_id": "pixel8-20261009-093012-a1b2",
  "patient_id": "uuid-del-paciente",
  "recorded_at": "2026-10-09T09:30:12-03:00",
  "audio_duration_sec": 2700.5,
  "audio_codec": "opus",
  "audio_bitrate_kbps": 48,
  "dsp_version": "companion-dsp/1.0",
  "device_info": {"modelo": "Pixel 8", "so": "Android 15", "microfono": "interno",
                  "distancia_cm": 15, "calibracion_db": null},
  "consent_recorded": true,
  "segments": [
    {"task_type": "vocal_sostenida_a", "speaker": "paciente", "start_sec": 12.0, "end_sec": 24.5},
    {"task_type": "conversacion_espontanea", "speaker": "paciente", "start_sec": 120.0, "end_sec": 480.0},
    {"task_type": "conversacion_espontanea", "speaker": "fonoaudiologo", "start_sec": 480.0, "end_sec": 540.0}
  ],
  "acoustics": [
    {"task_type": "vocal_sostenida_a", "f0_mean_hz": 212.4, "f0_median_hz": 211.0,
     "f0_sd_hz": 3.1, "f0_sd_semitones": 0.25, "f0_p5_hz": 205.0, "f0_p95_hz": 219.0,
     "f0_min_hz": 198.0, "f0_max_hz": 226.0, "voiced_fraction": 0.97,
     "intensity_mean_db": -18.5, "intensity_sd_db": 2.1, "mpt_sec": 18.2,
     "jitter_pct": 0.42, "shimmer_pct": 2.1, "hnr_db": 21.5,
     "f0_histogram": {"ref_hz": 211.0, "bins": {"-2": 3, "-1": 40, "0": 120, "1": 35, "2": 2}},
     "f0_contour": [0, 0, 209.1, 210.4, 211.2],
     "dsp_version": "companion-dsp/1.0"},
    {"task_type": "conversacion_espontanea", "f0_mean_hz": 198.0, "f0_median_hz": 196.5,
     "f0_sd_hz": 28.0, "f0_sd_semitones": 2.4, "f0_p5_hz": 150.0, "f0_p95_hz": 250.0,
     "f0_min_hz": 120.0, "f0_max_hz": 310.0, "voiced_fraction": 0.62,
     "intensity_mean_db": -22.0, "intensity_sd_db": 5.4,
     "mpt_sec": null, "jitter_pct": null, "shimmer_pct": null, "hnr_db": null,
     "f0_histogram": {"ref_hz": 196.5, "bins": {"-6": 12, "-5": 30}},
     "f0_contour": [0, 190.2, 0, 201.0],
     "dsp_version": "companion-dsp/1.0"}
  ]
}
```

Respuesta: `{ok:true, session_id:"uuid", status:"uploaded", job:{status:"queued"}}`.
Reenviar el mismo `device_session_id` → `200` con el mismo `session_id` (upsert, sin duplicar).

## 4. Contrato de métricas (unidades y fórmulas)

- Frecuencias en **Hz** (float). Tiempos en **segundos**. `voiced_fraction` 0–1.
- **dB = dBFS relativo** (negativos, ej. −18.5). Solo son absolutos si `device_info.calibracion_db` no es null (se indica en UI/PDF).
- `f0_sd_semitones` = **SD sobre la serie por trama** `st_i = 12·log2(f_i / f0_median)` (solo tramas sonoras).
- `f0_histogram`: `{ref_hz, bins:{semitono:int: conteo}}`, bins de **1 semitono** relativos a `ref_hz` (= mediana informada).
- `f0_contour`: array diezmado a **~20 Hz**, `0` = tramo sordo.
- `jitter_pct / shimmer_pct / hnr_db / mpt_sec`: **solo `vocal_sostenida_a`**; en el resto van `null` (el servidor los ignora si vienen).
- `dsp_version` obligatorio en sesión y en cada fila de acústica.
- **Validación del servidor** (nunca sobrescribe): recalcula media/mediana/SD/percentiles desde histograma+contorno; tolerancias: media/mediana ±3 %, percentiles ±1 semitono, SD ±10 %. Discrepancia mayor → `validada=false` (visible en UI) y se conservan los valores del Companion.

## 5. Archivos y límites (Supabase gratis: 50 MB/archivo, 1 GB total)

- Sesión: **audio comprimido Opus/AAC 32–64 kbps** (registro clínico + transcripción). 45 min ≈ **11–22 MB**.
- Clips: **WAV PCM 16 kHz mono 16-bit ≈10 s ≈ 0,3 MB c/u** (revisión jitter/shimmer/HNR). El WAV completo queda solo en el dispositivo.
- Mimes aceptados: `audio/mp4, audio/x-m4a, audio/mpeg, audio/wav, audio/x-wav, audio/webm, audio/ogg`.
- **Rechazar > 45 MB** por archivo; si hace falta, el cliente divide en partes numeradas (`part_index/part_total` en `uploads`, el servidor concatena al confirmar — implementado en Fase 2).
- Cuota: `STORAGE_QUOTA_BYTES` (default 1 GB). Estimación: **≈45–90 sesiones de 45 min por GB** + clips. `GET /almacenamiento` expone el uso en la UI.
- ⚠️ Decisión documentada: **recalcular jitter/shimmer/HNR desde el comprimido NO es válido** (solo F0, con tolerancia). Las métricas oficiales son las locales sobre PCM.

## 6. Subida (TUS reanudable, separada de la metadata)

1. `POST /uploads` → `{upload_url, path, expires_in:3600}`. Path: `companion-audio-vault/{patient_id}/{device_session_id}.m4a` (clips: `.../clips/{task_type}.wav`).
2. Subir con cliente TUS contra `upload_url` (`Tus-Resumable: 1.0.0`, `Upload-Length`, `Upload-Metadata`). Reanuda solo: mismo `path`.
3. `POST /uploads/confirm` verifica existencia+tamaño → `status=uploaded` + encola job (`processing_jobs`, `queued`).
- Subida interrumpida: la sesión queda sin audio confirmado; reintentar confirm describe `{"ok":false, "error":"audio incompleto: X/Y bytes"}` (test Fase 5).

## 7. Estados, reintentos y timeouts

- Sesión: `uploaded → processing → processed | error`. Job: `queued → processing → done | error` (`attempts`, `next_retry_at` backoff 1/5/15 min, máx 5 intentos).
- Al boot: jobs `processing` con `lease_at` vencido (>10 min sin heartbeat) vuelven a `queued` (supervivencia a reinicios). Un job a la vez.
- Cliente: timeout 75 s (cold start Render ~50 s), backoff 5/15/30/60 s, poll de estado hasta 30 min. `GET /health` para despertar.
- Transcripción: trozos <20 MB cortados en límites de tarea (o silencios), Whisper secuencial con offsets, reintento por trozo (3×). ffmpeg disponible en Docker Render (verificado en `Dockerfile`); fallback documentado si falta.
- Diarización = alineación de segmentos transcriptos a ventanas `session_segments` (sin pyannote: pesado para free).
- **Consentimiento**: sin `consent_recorded=true` la sesión **no** pasa a `processed` (queda `error` con `error_detail` + endpoint de reproceso). Visible en la tarjeta.
- IA borrador: `AI_PROVIDER=groq|gemini` (default `gemini`), `AI_MODEL` (default `gemini-2.0-flash`, el confirmado en repo). `AI_EXTERNAL_AUDIO_ENABLED=false` desactiva envío de audio a proveedores (solo métricas/segmentos/transcripción local o manual). Riesgo: Groq declara no entrenar con API data en planes pagos; Gemini API no usa datos para entrenamiento según términos vigentes — **verificar al contratar**; si no es configurable, el interruptor existe para eso.

## 8. Telegram (solo saliente por defecto)

- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_NOTIFY_CHAT_ID`. Al `processed`: `🔔 Sesión procesada — MG (f) · 09/10 · ver ficha: <url>/?paciente=<id>`. **Nunca** nombre completo ni datos clínicos.
- Inbound implementado pero **apagado**: `TELEGRAM_INBOUND_ENABLED=false`; al activar, `POST /api/telegram/webhook` (secret `TELEGRAM_WEBHOOK_SECRET`) acepta audios <20 MB → sesión `tg:{file_unique_id}` + mismo pipeline.

## 9. Retención y auditoría

- `AUDIO_RETENTION_DAYS=3650` (10 años). **Purga nunca automática**: solo `POST /mantenimiento/purgar` con `confirmar:true` (doble confirmación en UI). Borra archivos, **conserva** métricas, transcripción y access log.
- `audio_access_log`: cada URL firmada y cada acceso relevante (actor = device name o google_id, acción, fecha).

## 10. PWA y grabador de emergencia (web)

- `manifest.webmanifest` + `sw.js`: shell offline tras primera visita; lista mínima en `localStorage` (`vocalislab_pacientes_min`, TTL 7 días, **solo id, nombre abreviado, sexo_referencia, fecha_nacimiento**; se borra al logout; sin diagnósticos).
- Grabador: bloques MediaRecorder 30 s → IndexedDB, `persist()`, Wake Lock, constraints sin AGC/ruido/eco (como `AnalisisModule`); sync al volver red vía `POST /api/companion/sesiones-web` (multipart directo ≤45 MB, auth `google_id` como el resto de la app); borrado local **solo** tras confirmación del servidor.

## 11. Informe PDF

Firma `PROFESIONAL_NOMBRE` (default `Matías Perez`) + `PROFESIONAL_MATRICULA` (default `M.P. 7276`); **nunca** "especialista en voz". Incluye: datos de sesión (fecha, duración, códec/bitrate, dsp), métricas por tarea con referencia usada (sexo+edad), gráfico de evolución, banda de referencia y aclaración **"valores orientativos, requieren criterio clínico"**.

## 12. Decisiones conservadoras registradas

1. Profesional único con `profesional_google_id` en tablas → multi = solo usuarios+policies.
2. RLS permisiva + enforcement en backend (service_role bypasea RLS; documentado, no simulado).
3. Sin dependencias nuevas: gráficos SVG propios, wrapper IndexedDB propio, TUS del lado Companion (el backend solo firma URLs).
4. Troceo por ventanas de tarea (usa datos que ya manda el Companion) antes que detección de silencios.
5. `voice_progress` filtra `status='processed'`; baseline = `session_number=1`.
6. `reference_ranges.sexo_referencia='ninex'` para niñez 4–10 (evita colisión con check `sexo` de pacientes); el override por paciente (`f0_ref_min/max_hz`) tiene prioridad; si no hay rango aplicable, semáforo en gris "sin referencia".
