# Pruebas manuales en el teléfono (Android)

Antes de empezar: APK de depuración instalado (`flutter run` o
`flutter install`), un **paciente de prueba** creado en la web de VocalisLab
(nombre ficticio, sexo y fecha de nacimiento cargados), teléfono con Android 13
o superior si es posible (14+ para validar el servicio de tipo `microphone`).
Anotar para cada prueba: modelo, versión de Android, resultado (OK / FALLA) y
`device_session_id`.

## 1. Emparejamiento
- [ ] Web → Voz y sesiones → Dispositivos → Generar código (vence en 10 min).
- [ ] App → pegar código + nombre del equipo → Emparejar → entra a "Grabar".
- [ ] El token no aparece en ninguna pantalla.
- [ ] El dispositivo figura en la web con `last_seen_at` actualizado tras sincronizar.
- [ ] Código vencido o ya usado → mensaje de error claro, no se empareja.
- [ ] Revocar en la web → la próxima sincronización falla con 401 → Ajustes →
      "Desvincular" → reiniciar la app → pide código otra vez.

## 2. Permisos (primer uso)
- [ ] Al tocar "Iniciar sesión" pide micrófono. Si se deniega: "Sin permiso de micrófono".
- [ ] En Android 13+ pide notificaciones. Con permiso, aparece la notificación
      "Grabando sesión vocal" mientras se graba.

## 3. Grabación de 5 minutos + altura tonal
- [ ] Elegir paciente de prueba → consentimiento → Iniciar.
- [ ] Marcar: Vocal /a/ (paciente, ≥ 10 s) · Lectura · Conversación espontánea
      alternando "Paciente habla" / "Fonoaudiólogo" varias veces.
- [ ] El indicador de nivel se mueve sin mostrar cifras de dB. Al gritar cerca
      del micrófono aparece "¡SATURA!".
- [ ] Cambiar a la pestaña "Sincronizar" y volver: el cronómetro sigue y la
      grabación no se cortó.
- [ ] Detener a los 5:00 → "Midiendo el tono…" → Resumen.
- [ ] El resumen muestra en grande la mediana (Hz) y la nota (ej. "Do#3 · 139 Hz"),
      el rango p5–p95, el histograma, la comparación con el rango para sexo/edad
      con el aviso "orientativo" y la línea de convención de octavas.
- [ ] Ninguna pantalla muestra jitter, shimmer, HNR, MPT ni dB.
- [ ] Comparar la mediana con una app de afinador o con Praat sobre el mismo audio (aprox.).
- [ ] Grabar sin marcar ninguna tarea → el resumen dice "Todos los tramos del
      paciente" y la sesión sincroniza (los turnos van como conversación espontánea).

## 4. Pantalla apagada y app en segundo plano
- [ ] Iniciar grabación → bloquear la pantalla 3 min → desbloquear → el
      cronómetro avanzó ~3 min.
- [ ] Iniciar grabación → Home → abrir otra app 2 min → volver → sigue grabando.
- [ ] Detener y verificar en el resumen que la duración total es la esperada y
      que la mediana tiene sentido (si el audio se cortó, el tono sale con huecos).
- [ ] (Android 14+) Durante la prueba la notificación del servicio sigue
      visible. Sin ella, Android corta el micrófono en segundo plano.

## 5. Cierre forzado y recuperación
- [ ] Iniciar grabación, marcar una tarea, hablar 1-2 min.
- [ ] Ajustes del sistema → Apps → Vocalis Companion → **Forzar detención**
      (o deslizar la app de recientes y matar el proceso).
- [ ] Abrir la app → Sincronizar → la sesión figura como RECORDING con
      "Grabación interrumpida: recuperar".
- [ ] Recuperar → "Sesión recuperada ✓" → pasa a QUEUED.
- [ ] Sincronizar → llega a la ficha con el audio hasta el último bloque de
      30 s (se puede perder como mucho lo que no llegó a escribirse) y con la
      tarea marcada (cerrada en el último guardado de marcas, cada 5 s).
- [ ] Repetir apagando el teléfono (batería) en vez de forzar detención.

## 6. Modo avión (offline-first)
- [ ] Activar modo avión → grabar una sesión de 1-2 min completa → Resumen
      funciona y la comparación con el rango usa la tabla cacheada (si nunca
      hubo conexión, avisa que falta la referencia).
- [ ] Sincronizar en modo avión → queda pendiente, sin cuelgues; la app sigue usable.
- [ ] Desactivar modo avión (Wi-Fi) → Sincronizar → UPLOADING → WATCHING → SYNCED.
- [ ] Con "Solo Wi-Fi" activado y solo datos móviles → no sube ("Sin Wi-Fi").
- [ ] Cortar el Wi-Fi a mitad de una subida → reintenta con backoff y, al
      volver la red, termina (no duplica la sesión en la web).

## 7. Sincronización con el servidor (paciente de prueba)
- [ ] Primera sincronización tras cold start de Render (~50 s): no falla por timeout.
- [ ] En la web, ficha del paciente de prueba: aparece la sesión con segmentos,
      acústica (F0 media/mediana/percentiles/histograma/contorno) y los campos
      jitter/shimmer/HNR/MPT/intensidad vacíos.
- [ ] El audio se reproduce en la web (m4a) y el clip de vocal sostenida también.
- [ ] La transcripción se genera (estado `processed`) y la app marca SYNCED.
- [ ] Reenviar la misma sesión (Sincronizar de nuevo) no duplica nada (idempotencia).
- [ ] Sesión sin consentimiento → ERROR con "Marcar consentimiento y
      reprocesar" → al tocarlo llega a `processed`.
- [ ] En Supabase Storage (`companion-audio-vault/vault/...`) el objeto existe
      con el tamaño correcto. Si la subida TUS falla con 400/401/403, anotar el
      cuerpo del error (ver el riesgo de `x-signature`/`apikey` en el informe).

## 8. Cifrado y retención
- [ ] Con `adb shell run-as com.vocalis.companion ls -R app_flutter/sesiones` (build debug):
      en `sesiones/<id>/` solo hay `*.enc`, `marcas.json`, `tono_global.json`;
      no quedan `sesion.wav` ni `bloques/` después de finalizar.
- [ ] Tras sincronizar, la caché `vocalis_tmp` queda vacía.
- [ ] "Liberar espacio" no borra sesiones que no estén SYNCED.
- [ ] (Destructivo, en un equipo de prueba) Ajustes del sistema → Borrar
      datos de la app con una sesión sin sincronizar → confirmar que se pierde
      (comportamiento documentado en README §Seguridad).
