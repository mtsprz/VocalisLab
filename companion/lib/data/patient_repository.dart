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

/// Caché local de pacientes (funciona sin internet). Se llena con
/// GET /api/companion/pacientes al vincular y cada vez que se abre la lista
/// con conexión ([MockPatientRepository.sincronizar]). Sin seed de demo: un
/// paciente inventado no existe en el servidor y la sesión no sincronizaría.
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
    return rows.map(PacienteMin.fromMap).toList();
  }

  /// Reemplaza la caché por la lista del servidor (solo pacientes activos).
  /// Si [descargar] falla (sin red), la caché queda como estaba.
  Future<int> sincronizar(Future<List<Map<String, dynamic>>> Function() descargar) async {
    final remotos = await descargar();
    final activos = [
      for (final m in remotos)
        if (m['activo'] != false) PacienteMin.fromMap(m),
    ];
    await db.transaction((tx) async {
      await tx.delete('patients_cache');
      for (final p in activos) {
        await tx.insert('patients_cache', {
          'id': p.id,
          'nombre_abreviado': p.nombreAbreviado,
          'sexo_referencia': p.sexoReferencia,
          'fecha_nacimiento': p.fechaNacimiento,
          'updated_at': DateTime.now().toIso8601String(),
        },);
      }
    });
    return activos.length;
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
          conflictAlgorithm: ConflictAlgorithm.replace,);
    }
    await b.commit(noResult: true);
  }
}
