import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../app.dart';
import '../sync/sincronizar.dart';

/// Paso 2: consentimiento obligatorio. Sin tilde no se puede grabar ni
/// sincronizar (el servidor rechaza `processed` sin consent_recorded=true).
/// Desde acá también se importa un audio ya grabado con otro programa.
class ConsentScreen extends StatefulWidget {
  final Deps deps;
  final String pacienteId;
  final bool consent;
  final ValueChanged<bool> onConsent;
  final VoidCallback onSeguir;
  final VoidCallback onCambiarPaciente;

  const ConsentScreen({
    super.key,
    required this.deps,
    required this.pacienteId,
    required this.consent,
    required this.onConsent,
    required this.onSeguir,
    required this.onCambiarPaciente,
  });

  @override
  State<ConsentScreen> createState() => _ConsentScreenState();
}

class _ConsentScreenState extends State<ConsentScreen> {
  bool _importando = false;
  String? _msg;

  Future<void> _importar() async {
    setState(() => _msg = null);
    final res = await FilePicker.platform.pickFiles(
      dialogTitle: 'Elegí la grabación de la sesión',
      type: FileType.custom,
      allowedExtensions: extensionesImportables,
    );
    final ruta = res?.files.single.path;
    if (ruta == null) return;
    setState(() => _importando = true);
    try {
      await importarArchivo(
        widget.deps,
        origen: ruta,
        pacienteId: widget.pacienteId,
        consentimiento: widget.consent,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        duration: Duration(seconds: 6),
        content: Text('Audio importado ✓ Se sube y se analiza solo (transcripción, voces y '
            'altura tonal). Lo vas a ver en VocalisLab en unos minutos.'),
      ),);
      widget.onCambiarPaciente();
    } catch (e) {
      if (mounted) setState(() => _msg = 'No se pudo importar: $e');
    } finally {
      if (mounted) setState(() => _importando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Consentimiento', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        const Text(
          'Confirmo que el paciente aceptó la grabación de la sesión '
          'para su ficha clínica, incluyendo el análisis de su voz.',
          style: TextStyle(fontSize: 18),
        ),
        const SizedBox(height: 16),
        CheckboxListTile(
          value: widget.consent,
          onChanged: (v) => widget.onConsent(v ?? false),
          title: const Text('Consentimiento verbal registrado',
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold),),
          controlAffinity: ListTileControlAffinity.leading,
          contentPadding: EdgeInsets.zero,
        ),
        if (_msg != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(_msg!, style: TextStyle(fontSize: 15, color: Theme.of(context).colorScheme.error)),
          ),
        const Spacer(),
        ElevatedButton.icon(
          onPressed: widget.consent && !_importando ? widget.onSeguir : null,
          icon: const Icon(Icons.mic, size: 28),
          label: const Text('Grabar sesión'),
        ),
        const SizedBox(height: 10),
        OutlinedButton.icon(
          onPressed: widget.consent && !_importando ? _importar : null,
          icon: _importando
              ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5))
              : const Icon(Icons.upload_file, size: 26),
          label: Text(_importando ? 'Importando…' : 'Importar audio ya grabado',
              style: const TextStyle(fontSize: 18),),
          style: OutlinedButton.styleFrom(minimumSize: const Size(220, 56)),
        ),
        const SizedBox(height: 4),
        Text('Grabadora de Windows, celular u otra app (m4a, mp3, wav…)',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 14, color: Theme.of(context).colorScheme.onSurfaceVariant),),
        const SizedBox(height: 10),
        TextButton(onPressed: widget.onCambiarPaciente, child: const Text('Cambiar paciente')),
      ],),
    );
  }
}
