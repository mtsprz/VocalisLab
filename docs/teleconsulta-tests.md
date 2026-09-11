# Teleconsulta — Checklist de pruebas obligatorias

> No marcar como terminada hasta probar end-to-end en producción con
> credenciales reales de Zoom + Google. Marcar [x] a medida que se prueba.

## Agenda y sincronización
- [ ] Crear turno presencial (sin Meet/Zoom, solo Supabase)
- [ ] Crear turno virtual con Google Calendar + Meet (ver evento en calendar.google.com)
- [ ] Crear turno virtual con sala Zoom automática (ver reunión en Zoom + `zoom_join_url` en tarjeta)
- [ ] Editar turno (fecha/hora/modalidad) → verifica Supabase + evento Google actualizado + Zoom reprogramado
- [ ] Cancelar turno → verificado: evento Google y reunión Zoom tratados + `zoom_status= cancelada`
- [ ] Reprogramar turno → PATCH Zoom + PATCH Google + mismos IDs (`google_event_id`, `zoom_meeting_id` conservados)
- [ ] Sincronizar Google Calendar (botón recargar agenda, eventos importados visibles)

## Sala y firma
- [ ] Crear reunión Zoom vía `POST /api/teleconsulta/zoom/create` → join URL válida
- [ ] Obtener join URL y abrirla (entra a la sala real)
- [ ] Generar firma SDK (`POST /api/teleconsulta/zoom/signature`, rol 1 y rol 0)
- [ ] Entrar como profesional (video embebido “Atender aquí embebido”)
- [ ] Activar/desactivar micrófono y cámara desde el embebido
- [ ] Compartir pantalla (botón nativo del SDK embebido)
- [ ] Cambiar dispositivo de audio (selector + placa USB detectada)

## Clínica en sesión
- [ ] Panel lateral: ficha, motivo, objetivos, notas → Guardar notas (`POST notes`)
- [ ] Material terapéutico: seleccionar ejercicio, presentar consigna en pantalla completa
- [ ] Registrar duración + observaciones + marcar realizado
- [ ] Asociar ejercicios al cuadernillo (llega con los IDs precargados)
- [ ] Pitch en vivo: Hz + nota + teclado + indicador de confiabilidad
- [ ] Confirmar F0 de sesión (solo guarda si el profesional confirma)
- [ ] Accesos rápidos: anamnesis / escalas / Praat sin perder la sesión

## Finalización
- [ ] Resumen editable + guardar + finalizar (`POST end`, turno → completado)
- [ ] Generar cuadernillo desde la sesión
- [ ] Exportar PDF del informe
- [ ] Enviar por correo (con confirmación, PDF adjuntado manualmente)
- [ ] Compartir por WhatsApp (con confirmación, sin auto-envío)

## Errores y bordes
- [ ] Error de credenciales Zoom (sin env vars → mensaje claro, app no rompe)
- [ ] Error de token Google expirado (401 → re-login, reintentar)
- [ ] Error de red (mensajes visibles, reintento manual)
- [ ] Doble clic en crear sala → una sola reunión (idempotencia por `zoom_meeting_id`)
- [ ] Reunión expirada/eliminada en Zoom (404 tolerado, estado local coherente)
- [ ] Paciente no autorizado (403 sin user_id válido)
- [ ] Profesional sin permisos (403)

## Notas de entorno
- Requiere en Render: `ZOOM_ACCOUNT_ID/CLIENT_ID/CLIENT_SECRET`, `ZOOM_SDK_KEY/SECRET`,
  `GOOGLE_CLIENT_ID/SECRET`, `SUPABASE_URL/SERVICE_KEY`, `GROQ_API_KEY`.
- Requiere en Supabase (SQL Editor): columnas `zoom_*`, `teleconsulta_provider`,
  `fecha_sincronizacion`, `ultima_error_sincronizacion` + tabla `sesiones_teleconsulta`
  (todo en `supabase/vocalislab_schema_v2.sql`).
- Verificación rápida: `GET /api/teleconsulta/config` → ambos `true`;
  `GET /api/debug/status` → `write_probe` todo `insert_ok: true`.
