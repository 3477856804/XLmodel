import 'dart:ui';
import 'package:flutter/material.dart';

/// 小凌 · 液态玻璃主题（粉+黑+金）
class AppTheme {
  // 主粉色系
  static const Color primaryPink = Color(0xFFE85A8A);
  static const Color lightPink = Color(0xFFFF9FBE);
  static const Color deepPink = Color(0xFFC2185B);

  // 金色点缀
  static const Color gold = Color(0xFFD4AF37);
  static const Color goldLight = Color(0xFFF0D060);
  static const Color goldPale = Color(0xFFF5E6B8);

  // 深色（文字/点缀）
  static const Color ink = Color(0xFF1A1015);
  static const Color inkSoft = Color(0xFF3D2B35);
  static const Color soft = Color(0xFFFFE0EA);
  static const Color gradientStart = Color(0xFFFF7AA2);
  static const Color gradientEnd = Color(0xFFE85A8A);

  // 文字
  static const Color textPrimary = Color(0xFF2D1B2E);
  static const Color textSecondary = Color(0xFF7A5F6E);
  static const Color textLight = Color(0xFFAB8FA0);
  static const Color textOnGlass = Color(0xFF3D2030);

  // 背景极光色（用于透毛玻璃后面的彩色光斑）
  static const Color auroraPink = Color(0xFFFFC2D9);
  static const Color auroraRose = Color(0xFFFF9EB8);
  static const Color auroraPeach = Color(0xFFFFD4B8);
  static const Color auroraGold = Color(0xFFFCE8B2);
  static const Color auroraLavender = Color(0xFFE8D4F0);
  static const Color bgBase = Color(0xFFFFF5F8);

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      primaryColor: primaryPink,
      scaffoldBackgroundColor: Colors.transparent,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryPink,
        primary: primaryPink,
        secondary: gold,
      ),
      textTheme: const TextTheme(
        headlineLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.w800, color: textPrimary, letterSpacing: -0.5),
        headlineMedium: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: textPrimary, letterSpacing: -0.3),
        titleLarge: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: textPrimary),
        bodyLarge: TextStyle(fontSize: 15, color: textPrimary, height: 1.5),
        bodyMedium: TextStyle(fontSize: 13.5, color: textSecondary, height: 1.5),
        bodySmall: TextStyle(fontSize: 12, color: textLight),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryPink,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          elevation: 0,
        ),
      ),
    );
  }

  /// 极光渐变背景：多层彩色光斑 + 基底色
  static Widget auroraBackground({required Widget child}) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFF5F8), Color(0xFFFDE8F0), Color(0xFFFBE0E8)],
          stops: [0.0, 0.5, 1.0],
        ),
      ),
      child: Stack(
        children: [
          // 左上粉色光斑
          Positioned(
            top: -80, left: -60,
            child: _blob(auroraPink, 280, 0.55),
          ),
          // 右上金色光斑
          Positioned(
            top: 40, right: -80,
            child: _blob(auroraGold, 220, 0.45),
          ),
          // 左下玫瑰光斑
          Positioned(
            bottom: -60, left: -40,
            child: _blob(auroraRose, 260, 0.4),
          ),
          // 右下薰衣草光斑
          Positioned(
            bottom: 80, right: -60,
            child: _blob(auroraLavender, 200, 0.35),
          ),
          // 中部桃色光斑
          Positioned(
            top: 200, left: 80,
            child: _blob(auroraPeach, 160, 0.3),
          ),
          child,
        ],
      ),
    );
  }

  static Widget _blob(Color color, double size, double opacity) {
    return Container(
      width: size, height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [color.withOpacity(opacity), color.withOpacity(0.0)],
        ),
      ),
    );
  }

  /// 玻璃卡片：BackdropFilter 真模糊 + 半透明白底 + 金色细边
  static Widget glassCard({
    required Widget child,
    EdgeInsetsGeometry padding = const EdgeInsets.all(18),
    double borderRadius = 22,
    double blur = 24,
  }) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.55),
            borderRadius: BorderRadius.circular(borderRadius),
            border: Border.all(
              color: Colors.white.withOpacity(0.6),
              width: 1.2,
            ),
            boxShadow: [
              BoxShadow(
                color: primaryPink.withOpacity(0.08),
                blurRadius: 24,
                offset: const Offset(0, 8),
              ),
              BoxShadow(
                color: Colors.black.withOpacity(0.04),
                blurRadius: 8,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: child,
        ),
      ),
    );
  }

  /// 玻璃卡片（BoxDecoration 版本，用于 Container.decoration）
  static BoxDecoration get glassDecoration => BoxDecoration(
        color: Colors.white.withOpacity(0.55),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.white.withOpacity(0.6), width: 1.2),
        boxShadow: [
          BoxShadow(
            color: primaryPink.withOpacity(0.08),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ],
      );

  /// 渐变按钮装饰
  static BoxDecoration get gradientButton => BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFFF9FBE), Color(0xFFE85A8A)],
        ),
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: primaryPink.withOpacity(0.3),
            blurRadius: 12, offset: const Offset(0, 4),
          ),
        ],
      );

  /// 简单渐变背景（splash 用）
  static BoxDecoration get gradientBackground => const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFFF5F8), Color(0xFFFDE8F0), Color(0xFFFBE0E8)],
        ),
      );

  /// 玻璃按钮（渐变粉金）
  static BoxDecoration get glassButton => BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFF9FBE), Color(0xFFE85A8A)],
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withOpacity(0.4), width: 1),
        boxShadow: [
          BoxShadow(
            color: primaryPink.withOpacity(0.35),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      );

  /// 玻璃输入框
  static InputDecoration glassInput({
    required String hint,
    IconData? prefix,
  }) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: textLight, fontSize: 14),
      prefixIcon: prefix != null ? Icon(prefix, color: textLight, size: 20) : null,
      filled: true,
      fillColor: Colors.white.withOpacity(0.5),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: Colors.white.withOpacity(0.5)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: primaryPink, width: 1.5),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    );
  }
}
