import 'dart:convert';
import 'package:sqflite/sqflite.dart';

/// Estados locales (no confundir con los del servidor).
/// recording → ready → queued → uploading → confirming → watching → synced
/// error (con error_detail). watching = esperando `processed` del servidor.
class SessionStore {
  final Database db;

  SessionStore(this.db);

  Future<void> crear(Map<String, dynamic> fila) async {
    await db.insert('sessions', fila,
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<Map<String, dynamic>?> leer(String deviceSessionId) async {
    final r = await db.query('sessions',
        where: 'device_session_id = ?', whereArgs: [deviceSessionId], limit: 1);
    return r.isEmpty ? null : r.first;
  }

  Future<List<Map<String, dynamic>>> pendientes() async {
    return db.query('sessions',
        where: "status IN ('ready','queued','uploading','confirming','watching','error')",
        orderBy: 'created_at');
  }

  /// Sesiones sin finalizar (cierre forzado): con bloques en disco.
  Future<List<Map<String, dynamic>>> incompletas() async {
    return db.query('sessions',
        where: "status IN ('recording') OR (status = 'ready' AND finalized = 0)");
  }

  Future<void> estado(String id, String status, {String error = ''}) async {
    await db.update('sessions', {'status': status, 'error_detail': error},
        where: 'device_session_id = ?', whereArgs: [id]);
  }

  Future<void> guardarSegmentos(String id, List<Map<String, dynamic>> segs) async {
    await db.delete('segments', where: 'device_session_id = ?', whereArgs: [id]);
    final b = db.batch();
    for (final s in segs) {
      b.insert('segments', {
        'device_session_id': id,
        'task_type': s['task_type'],
        'speaker': s['speaker'],
        'start_sec': s['start_sec'],
        'end_sec': s['end_sec'],
      });
    }
    await b.commit(noResult: true);
  }

  Future<List<Map<String, dynamic>>> segmentos(String id) =>
      db.query('segments', where: 'device_session_id = ?', whereArgs: [id], orderBy: 'start_sec');

  Future<void> guardarAcustica(String id, String task, Map<String, dynamic> payload) async {
    await db.insert(
        'acoustics',
        {'device_session_id': id, 'task_type': task, 'payload': jsonEncode(payload), 'validada': 1},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<List<Map<String, dynamic>>> acustica(String id) =>
      db.query('acoustics', where: 'device_session_id = ?', whereArgs: [id]);

  Future<void> agregarClip(String id, String task, String path, double dur) async {
    await db.insert('clips',
        {'device_session_id': id, 'task_type': task, 'path': path, 'duration_sec': dur});
  }

  Future<List<Map<String, dynamic>>> clips(String id) =>
      db.query('clips', where: 'device_session_id = ?', whereArgs: [id]);

  Future<void> guardarServidor(String id, String serverId) async {
    await db.update('sessions', {'server_session_id': serverId},
        where: 'device_session_id = ?', whereArgs: [id]);
  }

  /// Arma el payload exacto del contrato POST /sessions desde la base local.
  Future<Map<String, dynamic>> payloadParaServidor(String id) async {
    final ses = await leer(id);
    if (ses == null) throw Exception('Sesión inexistente en base local');
    final segs = await segmentos(id);
    final acs = await acustica(id);
    final cl = await clips(id);
    return {
      'device_session_id': id,
      'patient_id': ses['patient_id'],
      'recorded_at': ses['recorded_at'],
      'audio_duration_sec': ses['audio_duration_sec'],
      'audio_codec': ses['audio_codec'],
      'audio_bitrate_kbps': ses['audio_bitrate_kbps'],
      'dsp_version': ses['dsp_version'],
      'device_info': jsonDecode('${ses['device_info'] ?? '{}'}'),
      'consent_recorded': (ses['consent_recorded'] ?? 0) == 1,
      'segments': [
        for (final s in segs)
          {
            'task_type': s['task_type'],
            'speaker': s['speaker'],
            'start_sec': s['start_sec'],
            'end_sec': s['end_sec'],
          }
      ],
      'acoustics': [
        for (final a in acs) (jsonDecode('${a['payload']}') as Map<String, dynamic>)
          ..['task_type'] = a['task_type'],
      ],
      'clips': [
        for (final c in cl)
          {'task_type': c['task_type'], 'duration_sec': c['duration_sec']},
      ],
    };
  }

  Future<void> borrarSesionLocal(String id) async {
    for (final t in ['clips', 'acoustics', 'segments', 'sessions']) {
      await db.delete(t, where: 'device_session_id = ?', whereArgs: [id]);
    }
  }
}
