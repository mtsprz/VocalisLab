import 'package:sqflite/sqflite.dart';

/// Paciente mínimo para uso offline (sin diagnósticos ni datos clínicos).
class PacienteMin {
  final String id;
  final String nombreAbreviado;
  final String sexoReferencia;
  final String fechaNacimiento;

  const PacienteMin({
    required this.id,
    required this.nombreAbreviado,
    this.sexoReferencia = '',
    this.fechaNacimiento = '',
  });

  factory PacienteMin.fromMap(Map<String, dynamic> m) => PacienteMin(
        id: '${m['id']}',
        nombreAbreviado: '${m['nombre_abreviado'] ?? ''}',
        sexoReferencia: '${m['sexo_referencia'] ?? ''}',
        fechaNacimiento: '${m['fecha_nacimiento'] ?? ''}',
      );
}

/// Repositorio mockeable. Hoy: caché local + seed de desarrollo.
/// Cuando el backend agregue GET /api/companion/pacientes
/// (docs/pedido-endpoint-pacientes-companion.md), se activa
/// RemotePatientRepository con AppConfig.remotePatientsEnabled.
abstract class PatientRepository {
  Future<List<PacienteMin>> listar();
  Future<void> guardarCache(List<PacienteMin> lista);
}

class MockPatientRepository implements PatientRepository {
  final Database db;

  MockPatientRepository(this.db);

  @override
  Future<List<PacienteMin>> listar() async {
    final rows = await db.query('patients_cache', orderBy: 'nombre_abreviado');
    if (rows.isNotEmpty) return rows.map(PacienteMin.fromMap).toList();
    // Seed de desarrollo (se reemplaza con la primera sincronización real).
    return const [
      PacienteMin(id: 'demo-1', nombreAbreviado: 'Demo A.', sexoReferencia: 'femenino'),
      PacienteMin(id: 'demo-2', nombreAbreviado: 'Demo B.', sexoReferencia: 'masculino'),
    ];
  }

  @override
  Future<void> guardarCache(List<PacienteMin> lista) async {
    final b = db.batch();
    for (final p in lista) {
      b.insert(
          'patients_cache',
          {
            'id': p.id,
            'nombre_abreviado': p.nombreAbreviado,
            'sexo_referencia': p.sexoReferencia,
            'fecha_nacimiento': p.fechaNacimiento,
            'updated_at': DateTime.now().toIso8601String(),
          },
          conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await b.commit(noResult: true);
  }
}
