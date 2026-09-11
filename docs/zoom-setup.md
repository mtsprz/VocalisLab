# Zoom en VocalisLab Pro — Guía de configuración

La teleconsulta usa dos piezas de Zoom (ambas se crean en
**Zoom App Marketplace** con la misma cuenta de Zoom del consultorio):

## 1. App Server-to-Server OAuth (crear salas desde la agenda)

1. Entrá a https://marketplace.zoom.us → **Develop** → **Build App** → **Server-to-Server OAuth** → Create.
2. Nombre: `VocalisLab Pro`. Copiá **Account ID**, **Client ID**, **Client Secret**.
3. En **Scopes** agregá: `meeting:write`, `meeting:read`, `user:read`.
4. **Activate** la app.

En **Render → Environment** del backend:
- `ZOOM_ACCOUNT_ID`
- `ZOOM_CLIENT_ID`
- `ZOOM_CLIENT_SECRET`

Con esto, el botón **“Crear sala Zoom”** de cada turno genera la reunión
(waiting room, video host/participante, audio bidireccional) y guarda
ID/clave/enlace en el turno.

## 2. App Meeting SDK (video embebido “Atender aquí embebido”)

1. En Marketplace → **Build App** → **Meeting SDK** → Create.
2. Copiá **SDK Key** y **SDK Secret**.
3. En **Render → Environment**:
   - `ZOOM_SDK_KEY`
   - `ZOOM_SDK_SECRET`
4. El frontend ya trae `@zoom/meetingsdk` (Component View, patrón oficial
   `zoom/meetingsdk-web-sample` → `Components/`). La firma se genera en
   `POST /api/teleconsulta/zoom-signature` (terapeuta role 1).

Sin estas variables, la app **no se rompe**: muestra la guía de setup y
permite igual agendar + compartir enlaces.

## 3. Audio profesional (importante clínico)

El Meeting SDK **web no permite forzar por código** el modo “Sonido Original”
(eso solo existe en el Video SDK nativo vía `stream.startAudio`). Por eso la
app muestra la **guía obligatoria** antes de unirse:

- Auriculares + ambiente silencioso.
- Zoom → Configuración → Audio → **“Sonido original para músicos”** ON.
- Supresión de ruido y cancelación de eco OFF (cortan SOVTE, fricativas
  /s/ /z/ /f/, falsete y cambios bruscos de intensidad).
- Placa USB si está disponible.

## 4. Columnas de Supabase (correr una vez en SQL Editor)

```sql
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS zoom_meeting_id TEXT;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS zoom_password TEXT;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS zoom_join_url TEXT;
```

## Verificación rápida

- `GET /api/teleconsulta/config` → `{"s2s_configured": true, "sdk_configured": true}`
- Crear sala desde una tarjeta de turno → aparece enlace + ID + clave.
- Botón **“Atender aquí embebido”** → video dentro de VocalisLab con notas al lado.
