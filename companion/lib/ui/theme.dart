import 'package:flutter/material.dart';

/// Estética clínica cálida: Lino Crema, Verde Salvia, Terracota.
/// Tipografía grande (accesible para uso en consultorio).
/// Modo noche: mismos acentos sobre un fondo carbón cálido (no negro puro,
/// para no encandilar en consultorio con poca luz).
class ClinicaTheme {
  static const Color lino = Color(0xFFF7F0EA);
  static const Color salvia = Color(0xFF7D9B76);
  static const Color salviaOscura = Color(0xFF5C7A57);
  static const Color terracota = Color(0xFFC96F4A);
  static const Color tinta = Color(0xFF2E2A26);

  static const Color carbon = Color(0xFF1C1A18);
  static const Color carbonSup = Color(0xFF272421);
  static const Color carbonAlto = Color(0xFF34302C);
  static const Color linoTexto = Color(0xFFEDE6DF);
  static const Color salviaClara = Color(0xFF9DBB95);
  static const Color terracotaClara = Color(0xFFE08A66);

  static ThemeData get light => _tema(
        base: ThemeData.light(useMaterial3: true),
        fondo: lino,
        esquema: const ColorScheme.light(
          primary: salviaOscura,
          secondary: terracota,
          surface: Colors.white,
          surfaceContainerHighest: Color(0xFFF7F3EA),
          onPrimary: Colors.white,
          onSurface: tinta,
          onSurfaceVariant: Color(0xFF6B645D),
        ),
        texto: tinta,
      );

  static ThemeData get dark => _tema(
        base: ThemeData.dark(useMaterial3: true),
        fondo: carbon,
        esquema: const ColorScheme.dark(
          primary: salviaClara,
          secondary: terracotaClara,
          surface: carbonSup,
          surfaceContainerHighest: carbonAlto,
          onPrimary: carbon,
          onSecondary: carbon,
          onSurface: linoTexto,
          onSurfaceVariant: Color(0xFFB5ADA5),
        ),
        texto: linoTexto,
      );

  static ThemeData _tema({
    required ThemeData base,
    required Color fondo,
    required ColorScheme esquema,
    required Color texto,
  }) {
    return base.copyWith(
      scaffoldBackgroundColor: fondo,
      colorScheme: esquema,
      cardTheme: CardThemeData(color: esquema.surface),
      textTheme: base.textTheme.copyWith(
        displaySmall: base.textTheme.displaySmall?.copyWith(
            fontSize: 28, fontWeight: FontWeight.bold, color: texto,),
        titleLarge: base.textTheme.titleLarge?.copyWith(
            fontSize: 22, fontWeight: FontWeight.bold, color: texto,),
        titleMedium: base.textTheme.titleMedium?.copyWith(fontSize: 19, color: texto),
        bodyLarge: base.textTheme.bodyLarge?.copyWith(fontSize: 18, color: texto),
        bodyMedium: base.textTheme.bodyMedium?.copyWith(fontSize: 16, color: texto),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          minimumSize: const Size(220, 60),
          textStyle: const TextStyle(fontSize: 19, fontWeight: FontWeight.bold),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      ),
    );
  }
}

/// Tema elegido en Ajustes (se aplica al instante en toda la app).
final ValueNotifier<ThemeMode> temaApp = ValueNotifier(ThemeMode.system);

ThemeMode temaDesde(String t) => switch (t) {
      'claro' => ThemeMode.light,
      'oscuro' => ThemeMode.dark,
      _ => ThemeMode.system,
    };
