import 'package:flutter/material.dart';

/// 小凌粉色少女风主题
class AppTheme {
  // 主粉色系
  static const Color primaryPink = Color(0xFFD4385C);
  static const Color lightPink = Color(0xFFFF7AA2);
  static const Color gradientStart = Color(0xFFFF7AA2);
  static const Color gradientEnd = Color(0xFFE85A8A);

  // 背景渐变
  static const Color bgStart = Color(0xFFFFF7F9);
  static const Color bgMiddle = Color(0xFFFDE8EF);
  static const Color bgEnd = Color(0xFFFBDCE6);

  // 卡片玻璃质感
  static const Color glassBg = Color(0x33FFFFFF);
  static const Color glassBorder = Color(0x44FFFFFF);

  // 文字
  static const Color textPrimary = Color(0xFF2D1B2E);
  static const Color textSecondary = Color(0xFF6B5566);
  static const Color textLight = Color(0xFF9B8B99);

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      primaryColor: primaryPink,
      scaffoldBackgroundColor: Colors.transparent,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryPink,
        primary: primaryPink,
        secondary: lightPink,
      ),
      textTheme: const TextTheme(
        headlineLarge: TextStyle(
          fontSize: 32,
          fontWeight: FontWeight.bold,
          color: textPrimary,
        ),
        headlineMedium: TextStyle(
          fontSize: 24,
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
        bodyLarge: TextStyle(
          fontSize: 16,
          color: textPrimary,
        ),
        bodyMedium: TextStyle(
          fontSize: 14,
          color: textSecondary,
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryPink,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          elevation: 4,
        ),
      ),
      cardTheme: CardTheme(
        color: Colors.white.withOpacity(0.7),
        elevation: 8,
        shadowColor: primaryPink.withOpacity(0.3),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
      ),
    );
  }

  /// 渐变背景装饰
  static BoxDecoration get gradientBackground {
    return const BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [bgStart, bgMiddle, bgEnd],
        stops: [0.0, 0.5, 1.0],
      ),
    );
  }

  /// 粉色渐变按钮
  static BoxDecoration get pinkGradientButton {
    return BoxDecoration(
      gradient: const LinearGradient(
        colors: [gradientStart, gradientEnd],
      ),
      borderRadius: BorderRadius.circular(16),
      boxShadow: [
        BoxShadow(
          color: primaryPink.withOpacity(0.4),
          blurRadius: 12,
          offset: const Offset(0, 4),
        ),
      ],
    );
  }

  /// 玻璃卡片
  static BoxDecoration get glassCard {
    return BoxDecoration(
      color: glassBg,
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: glassBorder, width: 1),
      boxShadow: [
        BoxShadow(
          color: Colors.black.withOpacity(0.05),
          blurRadius: 20,
          offset: const Offset(0, 8),
        ),
      ],
    );
  }
}
