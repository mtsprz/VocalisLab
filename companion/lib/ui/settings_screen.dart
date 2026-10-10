import 'package:flutter/material.dart';

import '../app.dart';
import '../data/settings_store.dart';

/// Ajustes: red, retención local, PIN y cierre de sesión.
class SettingsScreen extends StatefulWidget {
  final Deps deps;
  const SettingsScreen({super.key, required this.deps});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  AppSettings _s = AppSettings();
  final _ret = TextEditingController();
  final _pin = TextEditingController();
  String? _msg;
  bool _tienePin = false;

  @override
  void initState() {
    super.initState();
    AppSettings.load().then((s) {
      if (!mounted) return;
      setState(() {
        _s = s;
        _ret.text = '${s.localRetentionDays}';
      });
    });
    widget.deps.secure.hasPin().then((h) {
      if (mounted) setState(() => _tienePin = h);
    });
  }

  Future<void> _guardar() async {
    _s.localRetentionDays = int.tryParse(_ret.text) ?? 30;
    await _s.save();
    if (mounted) setState(() => _msg = 'Ajustes guardados ✓');
  }

  @override
  Widget build(BuildContext context) {
    return ListView(padding: const EdgeInsets.all(20), children: [
      const Text('Ajustes', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
      const SizedBox(height: 12),
      SwitchListTile(
        value: _s.wifiOnly,
        onChanged: (v) => setState(() => _s.wifiOnly = v),
        title: const Text('Sincronizar solo con Wi-Fi', style: TextStyle(fontSize: 18)),
      ),
      const SizedBox(height: 8),
      const Text('Retención local tras SYNCED (días)', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
      TextField(
        controller: _ret,
        keyboardType: TextInputType.number,
        style: const TextStyle(fontSize: 18),
        decoration: const InputDecoration(
            border: OutlineInputBorder(), hintText: '30', helperText: 'Nunca se borra antes de processed + estos días',),
      ),
      const SizedBox(height: 12),
      ElevatedButton(onPressed: _guardar, child: const Text('Guardar ajustes')),
      const SizedBox(height: 20),
      const Text('PIN de apertura', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
      Text(_tienePin ? 'PIN configurado ✓ (o biometría)' : 'Sin PIN: la app abre directo',
          style: const TextStyle(fontSize: 16),),
      Row(children: [
        Expanded(
          child: TextField(
            controller: _pin,
            obscureText: true,
            keyboardType: TextInputType.number,
            style: const TextStyle(fontSize: 18),
            decoration: const InputDecoration(border: OutlineInputBorder(), hintText: 'Nuevo PIN'),
          ),
        ),
        const SizedBox(width: 8),
        ElevatedButton(
          onPressed: () async {
            if (_pin.text.length < 4) {
              setState(() => _msg = 'PIN de al menos 4 dígitos');
              return;
            }
            await widget.deps.secure.setPin(_pin.text);
            setState(() {
              _tienePin = true;
              _msg = 'PIN configurado ✓';
            });
          },
          child: const Text('Fijar PIN'),
        ),
      ],),
      if (_msg != null) ...[
        const SizedBox(height: 8),
        Text(_msg!, style: const TextStyle(fontSize: 16)),
      ],
      const SizedBox(height: 20),
      OutlinedButton.icon(
        onPressed: () async {
          await widget.deps.secure.clearDeviceToken();
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Dispositivo desvinculado. Reiniciá la app para re-emparejar.')),);
          }
        },
        icon: const Icon(Icons.link_off),
        label: const Text('Desvincular dispositivo', style: TextStyle(fontSize: 17)),
      ),
    ],);
  }
}
