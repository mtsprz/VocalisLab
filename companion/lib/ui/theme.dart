import 'package:flutter/material.dart';

/// Estética clínica cálida: Lino Crema, Verde Salvia, Terracota.
/// Tipografía grande (accesible para uso en consultorio).
class ClinicaTheme {
  static const Color lino = Color(0xFFF7F0EA);
  static const Color salvia = Color(0xFF7D9B76);
  static const Color salviaOscura = Color(0xFF5C7A57);
  static const Color terracota = Color(0xFFC96F4A);
  static const Color tinta = Color(0xFF2E2A26);

  static ThemeData get light {
    final base = ThemeData.light(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: lino,
      colorScheme: const ColorScheme.light(
        primary: salviaOscura,
        secondary: terracota,
        surface: Colors.white,
        onPrimary: Colors.white,
        onSurface: tinta,
      ),
      textTheme: base.textTheme.copyWith(
        displaySmall: base.textTheme.displaySmall?.copyWith(
            fontSize: 28, fontWeight: FontWeight.bold, color: tinta,),
        titleLarge: base.textTheme.titleLarge?.copyWith(
            fontSize: 22, fontWeight: FontWeight.bold, color: tinta,),
        titleMedium: base.textTheme.titleMedium?.copyWith(fontSize: 19, color: tinta),
        bodyLarge: base.textTheme.bodyLarge?.copyWith(fontSize: 18, color: tinta),
        bodyMedium: base.textTheme.bodyMedium?.copyWith(fontSize: 16, color: tinta),
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
