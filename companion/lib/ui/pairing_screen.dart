import 'dart:io' show Platform;

import 'package:flutter/material.dart';

import '../app.dart';
import '../sync/pairing.dart';

/// Vinculación con VocalisLab (una sola vez, necesita internet ese momento).
/// Principal: "Entrar con Google". Respaldo: código generado en la web.
class PairingScreen extends StatefulWidget {
  final Deps deps;
  final VoidCallback onListo;

  const PairingScreen({super.key, required this.deps, required this.onListo});

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  final _code = TextEditingController();
  bool _busy = false;
  bool _conCodigo = false;
  String? _error;

  String get _nombreEquipo => Platform.isWindows ? 'PC Windows' : 'Teléfono Android';

  Future<void> _vincular(Future<void> Function() accion) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await accion();
      // Con la vinculación hecha, bajar los pacientes para usarlos offline.
      try {
        await widget.deps.pacientes.sincronizar(widget.deps.api.pacientes);
      } catch (_) {}
      widget.onListo();
    } catch (e) {
      setState(() => _error = '$e'.replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _google() => _vincular(() => emparejarConGoogle(
        api: widget.deps.api,
        secure: widget.deps.secure,
        deviceName: _nombreEquipo,
      ),);

  Future<void> _codigo() async {
    if (_code.text.trim().length < 4) {
      setState(() => _error = 'Ingresá el código de 6 caracteres');
      return;
    }
    await _vincular(() => emparejar(
          api: widget.deps.api,
          secure: widget.deps.secure,
          code: _code.text,
          deviceName: _nombreEquipo,
        ),);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Vincular con VocalisLab')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.link, size: 64, color: Color(0xFF5C7A57)),
            const SizedBox(height: 16),
            const Text(
              'Se hace una sola vez y necesita internet ese momento. Después la app '
              'sigue vinculada aunque no haya conexión.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 17),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _busy ? null : _google,
              icon: const Icon(Icons.account_circle, size: 28),
              label: Text(_busy ? 'Vinculando…' : 'Entrar con Google'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 16)),
            ],
            const SizedBox(height: 24),
            TextButton(
              onPressed: () => setState(() => _conCodigo = !_conCodigo),
              child: const Text('Tengo un código de la web', style: TextStyle(fontSize: 16)),
            ),
            if (_conCodigo) ...[
              TextField(
                controller: _code,
                textCapitalization: TextCapitalization.characters,
                maxLength: 8,
                style: const TextStyle(fontSize: 26, letterSpacing: 6),
                textAlign: TextAlign.center,
                decoration: const InputDecoration(labelText: 'Código', border: OutlineInputBorder()),
              ),
              OutlinedButton(
                onPressed: _busy ? null : _codigo,
                child: const Text('Vincular con código'),
              ),
            ],
          ],),
        ),
      ),
    );
  }
}
