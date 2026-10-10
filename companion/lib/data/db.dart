import 'dart:io' show Platform;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

/// Base local. En Windows/Linux usa sqflite_common_ffi; en Android/iOS, sqflite.
/// En tests: `openAppDb(pathOverride: inMemoryDatabasePath)` (con ffi).
Future<Database> openAppDb({String? pathOverride}) async {
  if (Platform.isWindows || Platform.isLinux) {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  }
  final path = pathOverride ??
      p.join((await getApplicationDocumentsDirectory()).path, 'vocalis.db');
  return openDatabase(path, version: 1, onCreate: (db, _) async {
    await db.execute('''
      CREATE TABLE patients_cache(
        id TEXT PRIMARY KEY, nombre_abreviado TEXT NOT NULL,
        sexo_referencia TEXT DEFAULT '', fecha_nacimiento TEXT DEFAULT '',
        updated_at TEXT DEFAULT '')''');
    await db.execute('''
      CREATE TABLE sessions(
        device_session_id TEXT PRIMARY KEY, patient_id TEXT NOT NULL,
        recorded_at TEXT DEFAULT '', audio_duration_sec REAL DEFAULT 0,
        audio_codec TEXT DEFAULT '', audio_bitrate_kbps INTEGER DEFAULT 0,
        dsp_version TEXT DEFAULT '', device_info TEXT DEFAULT '{}',
        consent_recorded INTEGER DEFAULT 0,
        status TEXT DEFAULT 'recording',
        server_session_id TEXT DEFAULT '', error_detail TEXT DEFAULT '',
        blocks_dir TEXT DEFAULT '', finalized INTEGER DEFAULT 0,
        created_at TEXT DEFAULT '')''');
    await db.execute('''
      CREATE TABLE segments(
        id INTEGER PRIMARY KEY AUTOINCREMENT, device_session_id TEXT NOT NULL,
        task_type TEXT NOT NULL, speaker TEXT NOT NULL,
        start_sec REAL NOT NULL, end_sec REAL NOT NULL)''');
    await db.execute('''
      CREATE TABLE acoustics(
        device_session_id TEXT NOT NULL, task_type TEXT NOT NULL,
        payload TEXT NOT NULL, validada INTEGER DEFAULT 1,
        PRIMARY KEY (device_session_id, task_type))''');
    await db.execute('''
      CREATE TABLE clips(
        id INTEGER PRIMARY KEY AUTOINCREMENT, device_session_id TEXT NOT NULL,
        task_type TEXT NOT NULL, path TEXT NOT NULL, duration_sec REAL DEFAULT 0)''');
    await db.execute(
        'CREATE INDEX idx_segments_sesion ON segments(device_session_id)',);
  },);
}
