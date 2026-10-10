import 'package:flutter/material.dart';

import '../app.dart';

/// Paso 2: consentimiento obligatorio. Sin tilde no se puede grabar ni
/// sincronizar (el servidor rechaza `processed` sin consent_recorded=true).
class ConsentScreen extends StatelessWidget {
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
          value: consent,
          onChanged: (v) => onConsent(v ?? false),
          title: const Text('Consentimiento verbal registrado',
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold),),
          controlAffinity: ListTileControlAffinity.leading,
          contentPadding: EdgeInsets.zero,
        ),
        const Spacer(),
        ElevatedButton(
          onPressed: consent ? onSeguir : null,
          child: const Text('Continuar'),
        ),
        const SizedBox(height: 10),
        TextButton(onPressed: onCambiarPaciente, child: const Text('Cambiar paciente')),
      ],),
    );
  }
}
