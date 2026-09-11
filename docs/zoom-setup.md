# Zoom en VocalisLab Pro — Guía de configuración

> **Importante (2026):** Zoom deprecó el SDK Key/Secret legacy (migración
> enforced desde el 27/06/2026). La firma del Meeting SDK ahora usa
> **Client ID + Client Secret** de una **General App** con Meeting SDK habilitado.
> El código ya firma así: `ZOOM_SDK_KEY` = Client ID, `ZOOM_SDK_SECRET` = Client Secret.

La teleconsulta usa dos piezas (dos apps distintas en
**Zoom App Marketplace**, misma cuenta del consultorio):

## 1. App Server-to-Server OAuth (crear salas desde la agenda) — la que ya tenés

1. Marketplace → **Develop** → **Build App** → **Server-to-Server OAuth** → Create.
2. Nombre: `VocalisLab Pro`. Copiá **Account ID**, **Client ID**, **Client Secret**.
3. En **Scopes** agregá: `meeting:write`, `meeting:read`, `user:read`.
4. **Activate** la app.

En **Render → Environment** del backend:
- `ZOOM_ACCOUNT_ID`
- `ZOOM_CLIENT_ID`
- `ZOOM_CLIENT_SECRET`

## 2. App General App + Meeting SDK (video embebido “Atender aquí embebido”)

Elegí **General App** en tu pantalla (es la opción correcta: el tipo
“Meeting SDK” separado ya no aparece; ahora vive dentro de General App):

1. Marketplace → **Develop** → **Build App** → **General App** → Create
   (nombre: `VocalisLab Embedded`).
2. En la app, andá a **Features → Embed** y activá **Meeting SDK** (toggle ON).
3. En **Basic Information → App Credentials** copiá el **Client ID** y el
   **Client Secret** (usá las credenciales de *development* mientras probás;
   las de *production* cuando publiques).
4. En **Render → Environment**:
   - `ZOOM_SDK_KEY` = Client ID de esta General App
   - `ZOOM_SDK_SECRET` = Client Secret de esta General App
5. **NO** pegues acá las credenciales de la app Server-to-Server (eso da el
   error 3712 “Signature is invalid”). Cada app tiene sus propias credenciales.

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
