import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import 'package:sqflite/sqflite.dart';

import 'data/secure_store.dart';
import 'data/session_store.dart';
import 'data/patient_repository.dart';
import 'sync/api_client.dart';
import 'sync/sync_engine.dart';
import 'sync/tus_client.dart';
import 'ui/theme.dart';
import 'ui/pairing_screen.dart';
import 'ui/patient_screen.dart';
import 'ui/consent_screen.dart';
import 'ui/recording_screen.dart';
import 'ui/summary_screen.dart';
import 'ui/sync_screen.dart';
import 'ui/settings_screen.dart';

/// Dependencias compartidas (v1: holder simple, sin DI framework).
class Deps {
  final Database db;
  late final SessionStore store;
  late final MockPatientRepository pacientes;
  final SecureStore secure = SecureStore();
  late final ApiClient api;
  late final SyncEngine sync;

  Deps({required this.db}) {
    store = SessionStore(db);
    pacientes = MockPatientRepository(db);
    api = ApiClient(secure: secure);
    sync = SyncEngine(
      api: api,
      tus: TusClient(),
      store: store,
      leerToken: secure.readDeviceToken,
    );
  }
}

class CompanionApp extends StatelessWidget {
  final Database db;

  const CompanionApp({super.key, required this.db});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Vocalis Companion',
      theme: ClinicaTheme.light,
      home: PuertaAuth(deps: Deps(db: db)),
      debugShowCheckedModeBanner: false,
    );
  }
}

/// Puerta 1: PIN o biometría (si hay PIN configurado).
class PuertaAuth extends StatefulWidget {
  final Deps deps;
  const PuertaAuth({super.key, required this.deps});

  @override
  State<PuertaAuth> createState() => _PuertaAuthState();
}

class _PuertaAuthState extends State<PuertaAuth> {
  bool? _bloqueado;
  final _pin = TextEditingController();
  String? _error;

  @override
  void initState() {
    super.initState();
    widget.deps.secure.hasPin().then((h) => setState(() => _bloqueado = h));
  }

  Future<void> _bio() async {
    try {
      final ok = await LocalAuthentication().authenticate(
        localizedReason: 'Desbloquear Vocalis Companion',
        options: const AuthenticationOptions(biometricOnly: true),
      );
      if (ok && mounted) setState(() => _bloqueado = false);
    } catch (_) {
      setState(() => _error = 'Biometría no disponible, usá el PIN');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_bloqueado == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_bloqueado == false) return PuertaPairing(deps: widget.deps);
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('Vocalis Companion', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _bio,
              icon: const Icon(Icons.fingerprint),
              label: const Text('Desbloquear con biometría'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _pin,
              obscureText: true,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'o PIN', border: OutlineInputBorder()),
            ),
            if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: () async {
                if (await widget.deps.secure.checkPin(_pin.text)) {
                  setState(() => _bloqueado = false);
                } else {
                  setState(() => _error = 'PIN incorrecto');
                }
              },
              child: const Text('Abrir con PIN'),
            ),
          ]),
        ),
      ),
    );
  }
}

/// Puerta 2: emparejamiento (si no hay token).
class PuertaPairing extends StatefulWidget {
  final Deps deps;
  const PuertaPairing({super.key, required this.deps});

  @override
  State<PuertaPairing> createState() => _PuertaPairingState();
}

class _PuertaPairingState extends State<PuertaPairing> {
  bool? _listo;

  @override
  void initState() {
    super.initState();
    widget.deps.secure.readDeviceToken().then((t) {
      setState(() => _listo = (t != null && t.isNotEmpty));
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_listo == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!_listo!) {
      return PairingScreen(
        deps: widget.deps,
        onListo: () => setState(() => _listo = true),
      );
    }
    return HomeTabs(deps: widget.deps);
  }
}

class HomeTabs extends StatefulWidget {
  final Deps deps;
  const HomeTabs({super.key, required this.deps});

  @override
  State<HomeTabs> createState() => _HomeTabsState();
}

class _HomeTabsState extends State<HomeTabs> {
  int _i = 0;
  String? _pacienteId;
  bool _consent = false;

  @override
  Widget build(BuildContext context) {
    final pantallas = [
      _FlujoGrabacion(
        deps: widget.deps,
        pacienteId: _pacienteId,
        onPaciente: (id) => setState(() => _pacienteId = id),
        consent: _consent,
        onConsent: (v) => setState(() => _consent = v),
      ),
      SyncScreen(deps: widget.deps),
      SettingsScreen(deps: widget.deps),
    ];
    return Scaffold(
      body: SafeArea(child: pantallas[_i]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _i,
        onDestinationSelected: (v) => setState(() => _i = v),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.mic, size: 30), label: 'Grabar'),
          NavigationDestination(icon: Icon(Icons.cloud_upload, size: 30), label: 'Sincronizar'),
          NavigationDestination(icon: Icon(Icons.settings, size: 30), label: 'Ajustes'),
        ],
      ),
    );
  }
}

/// Flujo guiado: paciente → consentimiento → grabación.
class _FlujoGrabacion extends StatefulWidget {
  final Deps deps;
  final String? pacienteId;
  final ValueChanged<String?> onPaciente;
  final bool consent;
  final ValueChanged<bool> onConsent;

  const _FlujoGrabacion({
    required this.deps,
    required this.pacienteId,
    required this.onPaciente,
    required this.consent,
    required this.onConsent,
  });

  @override
  State<_FlujoGrabacion> createState() => _FlujoGrabacionState();
}

class _FlujoGrabacionState extends State<_FlujoGrabacion> {
  int _paso = 0;
  String? _resumenId;

  @override
  Widget build(BuildContext context) {
    if (_resumenId != null) {
      return SummaryScreen(
        deps: widget.deps,
        deviceSessionId: _resumenId!,
        pacienteId: widget.pacienteId ?? '',
        onVolver: () => setState(() {
          _resumenId = null;
          _paso = 0;
          widget.onPaciente(null);
        }),
      );
    }
    if (widget.pacienteId == null) {
      return PatientScreen(deps: widget.deps, onSelect: widget.onPaciente);
    }
    if (_paso == 0) {
      return ConsentScreen(
        deps: widget.deps,
        pacienteId: widget.pacienteId!,
        consent: widget.consent,
        onConsent: widget.onConsent,
        onSeguir: () => setState(() => _paso = 1),
        onCambiarPaciente: () => widget.onPaciente(null),
      );
    }
    return RecordingScreen(
      deps: widget.deps,
      pacienteId: widget.pacienteId!,
      consent: widget.consent,
      onTerminar: (dsid) => setState(() => _resumenId = dsid),
    );
  }
}
