/**
 * VocalisLab — Importación automática de la agenda y los alumnos de Fonoar.
 *
 * Corre en la cuenta del consultorio (la que recibe el mail "Fonoar: Turnos
 * del DD/MM/AAAA" y a la que comparten la planilla "ALUMNOS DE CANTO"):
 * - Cada hora busca esos mails, los manda a la app (que crea/actualiza
 *   pacientes y turnos sin duplicar) y les pone la etiqueta
 *   "VocalisLab/importado" para no mandarlos de nuevo.
 * - Cada día a la mañana lee la pestaña MATIAS de la planilla de alumnos de
 *   canto y la manda a la app (alumnos, clases de las próximas 4 semanas y
 *   pagos del mes).
 *
 * INSTALACIÓN (una sola vez, ~5 minutos):
 * 1. Entrá a https://script.google.com con la cuenta del consultorio
 *    (la que recibe los mails de Fonoar) → "Nuevo proyecto".
 * 2. Borrá lo que aparece y pegá TODO este archivo. Guardá (Ctrl+S) con el
 *    nombre "VocalisLab agenda Fonoar".
 * 3. (La clave de la app ya viene incluida abajo, en CLAVE_AGENDA. No
 *    compartas este script.)
 * 4. Elegí la función "instalar" arriba y tocá "Ejecutar".
 *    Google pide permisos (leer Gmail y la planilla de Drive, conectarse a
 *    la app): aceptalos. Si ya lo tenías instalado, volvé a ejecutar
 *    "instalar" con este script nuevo para sumar la planilla.
 *    Si aparece "Google no verificó esta app": Configuración avanzada →
 *    "Ir a VocalisLab agenda Fonoar". Es tu propio script.
 * 5. Listo. Para probar ya mismo, ejecutá "importarAgendaFonoar" y mirá el
 *    registro de ejecución (abajo): dice cuántos turnos importó.
 */

const BACKEND = 'https://vocalislab.onrender.com';
const CLAVE_AGENDA = '__CLAVE_AGENDA__';
const BUSQUEDA = 'from:centrofonoar.com.ar subject:"Turnos del" newer_than:10d -label:VocalisLab/importado';
const ETIQUETA = 'VocalisLab/importado';
// Planilla de alumnos de canto: se la busca por nombre en el Drive (o poné
// su ID acá si cambia de nombre). Pestaña con tus alumnos:
const PLANILLA_CANTO_ID = '';
const PLANILLA_CANTO_NOMBRE = 'ALUMNOS DE CANTO';
const PESTANA_CANTO = 'MATIAS';

function importarAgendaFonoar() {
  const clave = PropertiesService.getScriptProperties().getProperty('CLAVE_AGENDA') || CLAVE_AGENDA;
  if (!clave || clave.indexOf('__') === 0) throw new Error('Falta la clave: descargá el script desde la app.');
  const hilos = GmailApp.search(BUSQUEDA, 0, 20);
  if (!hilos.length) {
    console.log('No hay agendas nuevas de Fonoar.');
    return;
  }
  despertarServidor_();
  const etiqueta = GmailApp.getUserLabelByName(ETIQUETA) || GmailApp.createLabel(ETIQUETA);
  hilos.forEach(function (hilo) {
    const mensajes = hilo.getMessages();
    const msg = mensajes[mensajes.length - 1];
    const resp = UrlFetchApp.fetch(BACKEND + '/api/agenda/importar-fonoar/script', {
      method: 'post',
      contentType: 'application/json',
      headers: { 'X-Clave-Agenda': clave },
      payload: JSON.stringify({ html: msg.getBody(), asunto: msg.getSubject() }),
      muteHttpExceptions: true,
    });
    const codigo = resp.getResponseCode();
    let datos = {};
    try { datos = JSON.parse(resp.getContentText()); } catch (e) {}
    if (codigo === 200 && datos.ok) {
      hilo.addLabel(etiqueta);
      console.log(msg.getSubject() + ' → ' + datos.turnos_nuevos + ' turnos nuevos, ' +
                  datos.pacientes_nuevos + ' pacientes nuevos. ' + (datos.avisos || []).join(' | '));
    } else {
      // Sin etiqueta: se reintenta en la próxima hora.
      console.error(msg.getSubject() + ' → error ' + codigo + ': ' + resp.getContentText().slice(0, 300));
    }
  });
}

function importarPlanillaCanto() {
  const clave = PropertiesService.getScriptProperties().getProperty('CLAVE_AGENDA') || CLAVE_AGENDA;
  let planilla = null;
  if (PLANILLA_CANTO_ID) {
    planilla = SpreadsheetApp.openById(PLANILLA_CANTO_ID);
  } else {
    const archivos = DriveApp.searchFiles('title contains "' + PLANILLA_CANTO_NOMBRE +
      '" and mimeType = "application/vnd.google-apps.spreadsheet" and trashed = false');
    let masNuevo = null;
    while (archivos.hasNext()) {
      const f = archivos.next();
      if (!masNuevo || f.getLastUpdated() > masNuevo.getLastUpdated()) masNuevo = f;
    }
    if (!masNuevo) throw new Error('No encontré la planilla "' + PLANILLA_CANTO_NOMBRE + '" en este Drive.');
    planilla = SpreadsheetApp.openById(masNuevo.getId());
  }
  const hoja = planilla.getSheetByName(PESTANA_CANTO);
  if (!hoja) throw new Error('La planilla no tiene la pestaña ' + PESTANA_CANTO + '.');
  despertarServidor_();
  const resp = UrlFetchApp.fetch(BACKEND + '/api/canto/importar-planilla/script', {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-Clave-Agenda': clave },
    payload: JSON.stringify({ filas: hoja.getDataRange().getDisplayValues() }),
    muteHttpExceptions: true,
  });
  console.log('Planilla de canto → ' + resp.getResponseCode() + ': ' + resp.getContentText().slice(0, 300));
}

/** El servidor gratuito duerme tras 15 min sin uso: se lo despierta antes. */
function despertarServidor_() {
  for (let i = 0; i < 4; i++) {
    try {
      const r = UrlFetchApp.fetch(BACKEND + '/api/health', { muteHttpExceptions: true });
      if (r.getResponseCode() === 200) return;
    } catch (e) {}
    Utilities.sleep(20000);
  }
}

/** Ejecutar UNA vez: crea los disparadores (agenda cada hora, planilla cada mañana). */
function instalar() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (['importarAgendaFonoar', 'importarPlanillaCanto'].indexOf(t.getHandlerFunction()) >= 0) {
      ScriptApp.deleteTrigger(t);
    }
  });
  ScriptApp.newTrigger('importarAgendaFonoar').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('importarPlanillaCanto').timeBased().everyDays(1).atHour(7).create();
  console.log('Listo: la agenda de Fonoar se importa cada hora y la planilla de canto cada mañana.');
  importarAgendaFonoar();
  importarPlanillaCanto();
}
