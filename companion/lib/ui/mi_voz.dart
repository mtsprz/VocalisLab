import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../core/audio/recorder_service.dart';
import '../core/audio/wav.dart';
import '../core/dsp/dsp_isolate.dart';
import '../core/dsp/modelo_huella.dart';
import '../core/dsp/nota.dart';
import '../data/settings_store.dart';

/// Ajustes → "Mi voz": 15 s leyendo en voz alta → perfil de tono del
/// fonoaudiólogo/a (mediana Hz + dispersión). Se usa para separar
/// automáticamente su voz de la del paciente. El audio se borra al terminar.
class MiVozCard extends StatefulWidget {
  const MiVozCard({super.key});

  @override
  State<MiVozCard> createState() => _MiVozCardState();
}

class _MiVozCardState extends State<MiVozCard> {
  static const _segundos = 15;
  AppSettings _s = AppSettings();
  final _rec = RecorderService();
  bool _grabando = false;
  bool _analizando = false;
  int _resta = _segundos;
  Timer? _timer;
  String? _msg;

  @override
  void initState() {
    super.initState();
    AppSettings.load().then((s) {
      if (mounted) setState(() => _s = s);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _rec.dispose();
    super.dispose();
  }

  Future<void> _grabar() async {
    if (!await _rec.tienePermiso()) {
      setState(() => _msg = 'Sin permiso de micrófono');
      return;
    }
    final dir = p.join((await getTemporaryDirectory()).path, 'mi_voz');
    final d = Directory(dir);
    if (await d.exists()) await d.delete(recursive: true);
    await _rec.iniciar(dir);
    setState(() {
      _grabando = true;
      _resta = _segundos;
      _msg = null;
    });
    _timer = Timer.periodic(const Duration(seconds: 1), (t) async {
      if (!mounted) return;
      setState(() => _resta--);
      if (_resta <= 0) {
        t.cancel();
        await _terminar(dir);
      }
    });
  }

  Future<void> _terminar(String dir) async {
    await _rec.detener();
    setState(() {
      _grabando = false;
      _analizando = true;
    });
    try {
      final bloques = await recuperarBloques(Directory(dir));
      if (bloques.isEmpty) throw Exception('No se grabó audio');
      final wav = p.join(dir, 'mi_voz.wav');
      await concatenarBloques(bloques, wav);
      final perfil = await analizarPerfilVozEnIsolate(wav, modeloHuella: await rutaModeloHuella());
      if (perfil == null) {
        setState(() => _msg = 'No se escuchó suficiente voz. Probá de nuevo, leyendo en voz alta.');
      } else {
        _s.vozFonoHz = (perfil['mediana_hz'] as num).toDouble();
        _s.vozFonoSdSt = (perfil['sd_st'] as num).toDouble();
        _s.vozFonoHuella = perfil['huella'] as Float32List?;
        _s.vozFonoModelo = _s.vozFonoHuella == null ? null : idModeloHuella;
        await _s.save();
        setState(() => _msg = _s.vozFonoHuella == null
            ? 'Listo (solo tono: no se pudo calcular la huella vocal)'
            : 'Listo ✓ (tono + huella vocal)',);
      }
    } catch (e) {
      setState(() => _msg = 'No se pudo analizar: $e');
    } finally {
      try {
        await Directory(dir).delete(recursive: true);
      } catch (_) {}
      if (mounted) setState(() => _analizando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final hz = _s.vozFonoHz;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Mi voz (fonoaudiólogo/a)', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
      Text(
        hz == null
            ? 'Sin grabar. La app la usa para separar automáticamente tu voz de la del paciente.'
            : 'Guardada: ${alturaTonal(hz)}${_s.vozFonoHuella != null ? ' + huella vocal' : ''}. '
                'Se usa para separar tu voz de la del paciente.',
        style: const TextStyle(fontSize: 16),
      ),
      const SizedBox(height: 8),
      if (_grabando)
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            'Leé en voz alta, con tu voz habitual de sesión ($_resta s):\n\n'
            '"Buenos días. Hoy vamos a trabajar la respiración y la voz. '
            'Contame cómo estuviste esta semana, si sentiste cansancio al hablar '
            'o algún cambio en la voz. Vamos a empezar con unos ejercicios suaves."',
            style: const TextStyle(fontSize: 17),
          ),
        )
      else
        ElevatedButton.icon(
          onPressed: _analizando ? null : _grabar,
          icon: const Icon(Icons.record_voice_over),
          label: Text(_analizando
              ? 'Analizando…'
              : (hz == null ? 'Grabar mi voz (15 s)' : 'Volver a grabar mi voz'),),
        ),
      if (_msg != null) Text(_msg!, style: const TextStyle(fontSize: 16)),
    ],);
  }
}
