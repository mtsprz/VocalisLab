/**
 * VocalisLab — Importación automática de la agenda de Fonoar.
 *
 * Corre en la cuenta de Gmail del consultorio (la que recibe el mail
 * "Fonoar: Turnos del DD/MM/AAAA"). Cada hora busca esos mails, los manda a
 * la app (que crea/actualiza pacientes y turnos sin duplicar) y les pone la
 * etiqueta "VocalisLab/importado" para no mandarlos de nuevo.
 *
 * INSTALACIÓN (una sola vez, ~5 minutos):
 * 1. Entrá a https://script.google.com con la cuenta del consultorio
 *    (la que recibe los mails de Fonoar) → "Nuevo proyecto".
 * 2. Borrá lo que aparece y pegá TODO este archivo. Guardá (Ctrl+S) con el
 *    nombre "VocalisLab agenda Fonoar".
 * 3. (La clave de la app ya viene incluida abajo, en CLAVE_AGENDA. No
 *    compartas este script.)
 * 4. Elegí la función "instalar" arriba y tocá "Ejecutar".
 *    Google pide permisos (leer Gmail, conectarse a la app): aceptalos.
 *    Si aparece "Google no verificó esta app": Configuración avanzada →
 *    "Ir a VocalisLab agenda Fonoar". Es tu propio script.
 * 5. Listo. Para probar ya mismo, ejecutá "importarAgendaFonoar" y mirá el
 *    registro de ejecución (abajo): dice cuántos turnos importó.
 */

const BACKEND = 'https://vocalislab.onrender.com';
const CLAVE_AGENDA = '__CLAVE_AGENDA__';
const BUSQUEDA = 'from:centrofonoar.com.ar subject:"Turnos del" newer_than:10d -label:VocalisLab/importado';
const ETIQUETA = 'VocalisLab/importado';

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

/** Ejecutar UNA vez: crea el disparador que corre la importación cada hora. */
function instalar() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'importarAgendaFonoar') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('importarAgendaFonoar').timeBased().everyHours(1).create();
  console.log('Listo: la agenda de Fonoar se importa sola cada hora.');
  importarAgendaFonoar();
}
