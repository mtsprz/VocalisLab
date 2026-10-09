# Pedido al agente web — endpoint de pacientes para Vocalis Companion (1 página)

## Contexto
Vocalis Companion (app Flutter offline-first) necesita descargar la **lista mínima
de pacientes** para elegir al paciente sin internet. El endpoint actual
`GET /api/pacientes` no sirve: no acepta `Authorization: Bearer` de dispositivo,
devuelve filas completas con datos sensibles (DNI, email, teléfono, notas) y no
soporta sincronización delta. **No lo modificamos**: se pide una ruta nueva bajo
`/api/companion` con el mismo modelo de auth del resto del contrato.

## Ruta propuesta
`GET /api/companion/pacientes`

- **Auth**: `Authorization: Bearer <device_token>` (igual que el resto de
  `/api/companion/*`). Sin token válido → `401`. Solo pacientes del
  `profesional_google_id` del dispositivo (como en `GET /sessions`).
- **Query**: `?q=<texto>` (búsqueda por nombre, opcional), `?limit=<n>` (default 200,
  máx 1000), `?updated_since=<ISO8601>` (delta para la caché offline; solo filas
  con `updated_at >= updated_since`, incluyendo bajas lógicas).
- **Respuesta 200**:
```json
{
  "ok": true,
  "pacientes": [
    {"id": "uuid", "nombre_abreviado": "María G.",
     "sexo_referencia": "femenino", "fecha_nacimiento": "1990-04-12",
     "updated_at": "2026-10-01T12:00:00Z", "activo": true}
  ]
}
```
- **Campos prohibidos en esta ruta**: dni, email, teléfono, ocupación, notas,
  derivador, diagnósticos. Solo lo mínimo para identificar + referencia de F0.
- **Errores**: `{ok:false}` con `401` (token), `403` (revocado), `502` (base).

## Notas de implementación (sugeridas, coherentes con `companion.py`)
1. Reutilizar `_device_from_bearer()` y el filtro
   `profesional_google_id == device.profesional_google_id`.
2. `nombre_abreviado`: nombre + inicial del apellido (criterio ya usado en el
   PWA web, `utils/pwa.ts:nombreAbreviado`).
3. `pacientes` ya tiene `updated_at` con trigger (`vocalislab_schema_v2.sql`);
   si falta, `ORDER BY updated_at NULLS LAST` igual funciona para full sync.
4. `activo=false` se incluye con su flag para purgar la caché del dispositivo.

## Mientras tanto (lado Companion)
La app avanza con `PatientRepository` abstracto + `MockPatientRepository`
(seed local) y `RemotePatientRepository` ya escrito contra **esta ruta
propuesta** pero desactivado detrás de `AppConfig.remotePatientsEnabled=false`.
Al agregar el endpoint, basta flippear el flag: sin cambios de UI.
