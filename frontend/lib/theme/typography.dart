/// Apple-aligned typography for XiaoLing.
///
/// Implements §4 of APPLE_DESIGN_SPEC.md:
/// - Font fallback chain (Inter → Noto Sans CJK → system)
/// - Platform-aware text styles (iOS/macOS vs other)
/// - CJK-aware line height and letter spacing
/// - Dynamic Type support (text scale clamping)
library;

import 'package:flutter/material.dart';
import 'dart:io' show Platform;

// ---------------------------------------------------------------------------
// §4.1  Font fallback chain
// ---------------------------------------------------------------------------

class XlFontFamily {
  XlFontFamily._();

  /// Primary font family with fallback chain.
  ///
  /// SF Pro cannot be distributed with non-Apple apps, so we use Inter as
  /// primary and rely on system fonts for CJK.
  ///
  /// 「primary」是**文本**光学尺寸（Inter 的 opsz=14 实例）：字怀更开、
  /// 字距更松，适合 17pt 上下的正文与小标题。
  static const String primary = 'Inter';

  /// Display optical size, matching Apple's *dynamic optical sizes*: SF Pro
  /// 会随字号自动从 Text 切到 Display。HIG 明确说「动态光学尺寸下你不需要
  /// 手动挑离散光学尺寸」，所以 Flutter 侧必须自己做这件事 —— 我们的字体
  /// 是**预实例化**的静态字重（可变字体在四端的插值行为不一致），只能按
  /// 字号在两个 family 之间切。
  ///
  /// 阈值取 22pt：SF 的 Text/Display 分界约在 20pt。这里没有真机渲染可比对
  /// （沙箱无 Flutter SDK），取 22 是留一点保守余量 —— 宁可少用 Display，
  /// 也不要在中等字号上让字距突然变紧。改动这一阈值需要人眼在真机上复核。
  static const String display = 'InterDisplay';

  /// HIG 的字号→光学尺寸分界。
  static const double displayMinSize = 22;

  /// Pick the optical size for [size] (logical pixels / pt).
  static String forSize(double size) =>
      (size.isFinite && size >= displayMinSize) ? display : primary;

  /// HIG「Tracking values」SF Pro 表，单位 pt，按字号取最近一档。
  ///
  /// Apple 的系统字体**随字号动态调整 tracking**：小字号正值（松）、
  /// 12–23pt 负值（紧）、24pt 以上回到正值且越大越松。
  /// 以前大标题直接吃了 XlLetterSpacing.tighter（−1.2），和 HIG 在 48pt
  /// 该给的 +0.35 **符号相反** —— 大字号挤在一起，是「不像苹果」最明显一处。
  ///
  /// 表值抄自 developer.apple.com 的 iOS/iPadOS·macOS 通用 tracking 表
  /// （两张表在这些字号上数值相同）。只做最近邻，不插值：插值在这里
  /// 是假精度，没有人会逐 pt 核对。
  static const List<(int, double)> _higTracking = [
    (6, 0.24),
    (7, 0.23),
    (8, 0.21),
    (9, 0.17),
    (10, 0.12),
    (11, 0.06),
    (12, 0.0),
    (13, -0.08),
    (14, -0.15),
    (15, -0.23),
    (16, -0.31),
    (17, -0.43),
    (18, -0.44),
    (19, -0.45),
    (20, -0.45),
    (21, -0.36),
    (22, -0.26),
    (23, -0.10),
    (24, 0.07),
    (25, 0.15),
    (26, 0.22),
    (27, 0.29),
    (28, 0.38),
    (29, 0.40),
    (30, 0.40),
    (31, 0.39),
    (32, 0.41),
    (33, 0.40),
    (34, 0.40),
    (35, 0.38),
    (36, 0.37),
    (37, 0.36),
    (38, 0.37),
    (39, 0.38),
    (40, 0.37),
    (41, 0.36),
    (42, 0.37),
    (43, 0.38),
    (44, 0.37),
    (45, 0.35),
    (46, 0.36),
    (47, 0.37),
    (48, 0.35),
    (49, 0.33),
    (50, 0.34),
    (52, 0.33),
    (54, 0.32),
    (56, 0.30),
    (58, 0.28),
    (60, 0.26),
    (64, 0.22),
    (68, 0.17),
    (72, 0.14),
    (76, 0.07),
    (80, 0.0),
    (96, 0.0),
  ];

  /// tracking for [size] per the HIG table above.
  static double trackingFor(double size) {
    if (!size.isFinite) return 0.0;
    var best = _higTracking.first;
    var bestD = (size - best.$1).abs();
    for (final e in _higTracking) {
      final d = (size - e.$1).abs();
      if (d < bestD) {
        bestD = d;
        best = e;
      }
    }
    return best.$2;
  }

  /// Monospace font family.
  ///
  /// 以前写的是 'JetBrains Mono'，而 pubspec 里没有该字体、四端也不保证
  /// 装了它 —— 一个从没生效过的假声明（全仓库 24 处代码实际用的是
  /// 'monospace'）。改成与那些调用点同一个值，落到系统的等宽回落上。
  static const String mono = 'monospace';

  /// Fallback chain per platform.
  ///
  /// Order matters: Flutter tries each in sequence until it finds a glyph.
  static List<String> get fallback {
    if (Platform.isMacOS || Platform.isIOS) {
      // Apple platforms: SF Pro is available
      return [
        '.AppleSystemUIFont', // iOS/macOS system (SF Pro)
        'Inter',
        'Noto Sans SC', // Simplified Chinese
        'Noto Sans TC', // Traditional Chinese
        'Noto Sans JP', // Japanese
        'Noto Sans KR', // Korean
        'sans-serif',
      ];
    } else if (Platform.isWindows) {
      return [
        'Inter',
        'Segoe UI', // Windows system
        'Microsoft YaHei', // Windows Chinese
        'Noto Sans SC',
        'Noto Sans TC',
        'sans-serif',
      ];
    } else if (Platform.isAndroid) {
      return [
        'Inter',
        'Roboto', // Android system
        'Noto Sans SC',
        'Noto Sans TC',
        'Noto Sans JP',
        'sans-serif',
      ];
    } else {
      // Linux
      return [
        'Inter',
        'Ubuntu', // GNOME default
        'Cantarell', // GNOME alt
        'Noto Sans SC',
        'Noto Sans TC',
        'sans-serif',
      ];
    }
  }
}

// ---------------------------------------------------------------------------
// §4.2  Text style builder
// ---------------------------------------------------------------------------

class XlTextStyles {
  XlTextStyles._();

  /// Build a text style with proper font family, fallback, and CJK adjustments.
  ///
  /// [size] in logical pixels (pt on iOS/macOS).
  /// [weight] font weight (avoid Ultralight/Thin/Light per Apple HIG).
  /// [height] line height as multiple of font size (null = system default).
  /// [letterSpacing] letter spacing in logical pixels.
  /// [isCJK] if true, applies CJK-specific adjustments (no positive letter-spacing).
  static TextStyle build({
    required double size,
    FontWeight weight = FontWeight.w400,
    double? height,
    double? letterSpacing,
    bool isCJK = false,
    Color? color,
  }) {
    // 没显式给字距时，按 HIG 的 tracking 表随字号取值（以前是 null，
    // 等于完全交给字体默认 kerning，大字号与小字号一个松紧度）。
    final spacing = letterSpacing ?? XlFontFamily.trackingFor(size);
    // CJK text should not have positive letter-spacing (looks unnatural)
    final adjustedSpacing = isCJK && spacing > 0 ? 0.0 : spacing;

    // HIG「动态光学尺寸」：SF Pro 会随字号自动在 Text/Display 之间插值。
    // 我们的 Inter 是预先实例化好的两套静态字重，所以这里显式按字号选族。
    final family = XlFontFamily.forSize(size);
    // Display 缺字时先回落到同字重的 Text 族（而不是直接掉到系统字体），
    // 保证一整段文字的观感一致。
    final chain = family == XlFontFamily.display
        ? [XlFontFamily.primary, ...XlFontFamily.fallback]
        : XlFontFamily.fallback;

    return TextStyle(
      fontFamily: family,
      fontFamilyFallback: chain,
      fontSize: size,
      fontWeight: weight,
      height: height,
      letterSpacing: adjustedSpacing,
      color: color,
    );
  }

  /// Monospace text style for code.
  static TextStyle mono({
    required double size,
    FontWeight weight = FontWeight.w400,
    double? height,
    Color? color,
  }) {
    return TextStyle(
      fontFamily: XlFontFamily.mono,
      fontFamilyFallback: ['SF Mono', 'Consolas', 'monospace'],
      fontSize: size,
      fontWeight: weight,
      height: height,
      color: color,
    );
  }
}

// ---------------------------------------------------------------------------
// §4.2  TextTheme mapping (Apple text styles → Flutter)
// ---------------------------------------------------------------------------

class XlAppleTextTheme {
  XlAppleTextTheme._();

  /// Build a complete TextTheme with Apple-aligned text styles.
  ///
  /// Uses iOS text style sizes (Dynamic Type compatible).
  /// For macOS, sizes are smaller (see spec §2.7 macOS table).
  static TextTheme build({
    required Color text1,
    required Color text2,
    required Color text3,
    required Color text4,
    bool isMacOS = false,
    bool isCJK = false,
  }) {
    if (isMacOS) {
      return _macOSTextTheme(text1, text2, text3, text4, isCJK);
    } else {
      return _iosTextTheme(text1, text2, text3, text4, isCJK);
    }
  }

  /// iOS / iPadOS text styles (Dynamic Type — Large default).
  static TextTheme _iosTextTheme(
    Color text1,
    Color text2,
    Color text3,
    Color text4,
    bool isCJK,
  ) {
    return TextTheme(
      // Large Title: 34pt Regular
      displayLarge: XlTextStyles.build(
        size: 34,
        weight: FontWeight.w400,
        height: 1.21,
        letterSpacing: 0.37,
        color: text1,
        isCJK: isCJK,
      ),
      // Title 1: 28pt Regular
      headlineLarge: XlTextStyles.build(
        size: 28,
        weight: FontWeight.w400,
        height: 1.21,
        letterSpacing: 0.36,
        color: text1,
        isCJK: isCJK,
      ),
      // Title 2: 22pt Regular
      headlineMedium: XlTextStyles.build(
        size: 22,
        weight: FontWeight.w400,
        height: 1.27,
        letterSpacing: 0.35,
        color: text1,
        isCJK: isCJK,
      ),
      // Title 3: 20pt Regular
      headlineSmall: XlTextStyles.build(
        size: 20,
        weight: FontWeight.w400,
        height: 1.25,
        letterSpacing: 0.38,
        color: text1,
        isCJK: isCJK,
      ),
      // Headline: 17pt Semibold
      titleLarge: XlTextStyles.build(
        size: 17,
        weight: FontWeight.w600,
        height: 1.29,
        letterSpacing: -0.43,
        color: text1,
        isCJK: isCJK,
      ),
      // Body: 17pt Regular
      bodyLarge: XlTextStyles.build(
        size: 17,
        weight: FontWeight.w400,
        height: 1.29,
        letterSpacing: -0.43,
        color: text1,
        isCJK: isCJK,
      ),
      // Callout: 16pt Regular
      bodyMedium: XlTextStyles.build(
        size: 16,
        weight: FontWeight.w400,
        height: 1.31,
        letterSpacing: -0.32,
        color: text2,
        isCJK: isCJK,
      ),
      // Subheadline: 15pt Regular
      bodySmall: XlTextStyles.build(
        size: 15,
        weight: FontWeight.w400,
        height: 1.33,
        letterSpacing: -0.24,
        color: text2,
        isCJK: isCJK,
      ),
      // Footnote: 13pt Regular
      labelLarge: XlTextStyles.build(
        size: 13,
        weight: FontWeight.w400,
        height: 1.38,
        letterSpacing: -0.08,
        color: text3,
        isCJK: isCJK,
      ),
      // Caption 1: 12pt Regular
      labelMedium: XlTextStyles.build(
        size: 12,
        weight: FontWeight.w400,
        height: 1.33,
        letterSpacing: 0.0,
        color: text3,
        isCJK: isCJK,
      ),
      // Caption 2: 11pt Regular
      labelSmall: XlTextStyles.build(
        size: 11,
        weight: FontWeight.w400,
        height: 1.18,
        letterSpacing: 0.07,
        color: text4,
        isCJK: isCJK,
      ),
    );
  }

  /// macOS text styles (no Dynamic Type).
  static TextTheme _macOSTextTheme(
    Color text1,
    Color text2,
    Color text3,
    Color text4,
    bool isCJK,
  ) {
    return TextTheme(
      // Large Title: 26pt Regular
      displayLarge: XlTextStyles.build(
        size: 26,
        weight: FontWeight.w400,
        height: 1.23,
        letterSpacing: 0.0,
        color: text1,
        isCJK: isCJK,
      ),
      // Title 1: 22pt Regular
      headlineLarge: XlTextStyles.build(
        size: 22,
        weight: FontWeight.w400,
        height: 1.18,
        letterSpacing: 0.0,
        color: text1,
        isCJK: isCJK,
      ),
      // Title 2: 17pt Regular
      headlineMedium: XlTextStyles.build(
        size: 17,
        weight: FontWeight.w400,
        height: 1.29,
        letterSpacing: 0.0,
        color: text1,
        isCJK: isCJK,
      ),
      // Title 3: 15pt Semibold
      headlineSmall: XlTextStyles.build(
        size: 15,
        weight: FontWeight.w600,
        height: 1.33,
        letterSpacing: 0.0,
        color: text1,
        isCJK: isCJK,
      ),
      // Headline: 13pt Bold
      titleLarge: XlTextStyles.build(
        size: 13,
        weight: FontWeight.w700,
        height: 1.23,
        letterSpacing: 0.0,
        color: text1,
        isCJK: isCJK,
      ),
      // Body: 13pt Regular
      bodyLarge: XlTextStyles.build(
        size: 13,
        weight: FontWeight.w400,
        height: 1.23,
        letterSpacing: 0.0,
        color: text1,
        isCJK: isCJK,
      ),
      // Callout: 12pt Regular
      bodyMedium: XlTextStyles.build(
        size: 12,
        weight: FontWeight.w400,
        height: 1.25,
        letterSpacing: 0.0,
        color: text2,
        isCJK: isCJK,
      ),
      // Subheadline: 11pt Regular
      bodySmall: XlTextStyles.build(
        size: 11,
        weight: FontWeight.w400,
        height: 1.27,
        letterSpacing: 0.0,
        color: text2,
        isCJK: isCJK,
      ),
      // Footnote: 10pt Regular
      labelLarge: XlTextStyles.build(
        size: 10,
        weight: FontWeight.w400,
        height: 1.30,
        letterSpacing: 0.0,
        color: text3,
        isCJK: isCJK,
      ),
      // Caption 1: 10pt Regular
      labelMedium: XlTextStyles.build(
        size: 10,
        weight: FontWeight.w400,
        height: 1.30,
        letterSpacing: 0.0,
        color: text3,
        isCJK: isCJK,
      ),
      // Caption 2: 10pt Medium
      labelSmall: XlTextStyles.build(
        size: 10,
        weight: FontWeight.w500,
        height: 1.30,
        letterSpacing: 0.0,
        color: text4,
        isCJK: isCJK,
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// §4.3  Dynamic Type support (text scale clamping)
// ---------------------------------------------------------------------------

class XlDynamicType {
  XlDynamicType._();

  /// Clamp text scale factor to a reasonable range.
  ///
  /// Apple allows up to AX5 (~3x) but UI may break. We clamp to 0.85x–1.5x
  /// to balance accessibility with layout stability.
  static TextScaler clamp(
    TextScaler scaler, {
    double min = 0.85,
    double max = 1.5,
  }) {
    final scale = scaler.scale(1.0).clamp(min, max);
    return TextScaler.linear(scale);
  }

  /// Apply clamped text scale to a MediaQuery.
  static MediaQueryData applyToMediaQuery(
    MediaQueryData media, {
    double min = 0.85,
    double max = 1.5,
  }) {
    return media.copyWith(
      textScaler: clamp(media.textScaler, min: min, max: max),
    );
  }
}

// ---------------------------------------------------------------------------
// CJK detection helper
// ---------------------------------------------------------------------------

class XlCJKHelper {
  XlCJKHelper._();

  /// Check if a string contains CJK characters.
  static bool containsCJK(String text) {
    // CJK Unified Ideographs: U+4E00 to U+9FFF
    // CJK Extension A: U+3400 to U+4DBF
    // Hiragana: U+3040 to U+309F
    // Katakana: U+30A0 to U+30FF
    // Hangul: U+AC00 to U+D7AF
    final cjkRegex = RegExp(
      r'[\u4E00-\u9FFF\u3400-\u4DBF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]',
    );
    return cjkRegex.hasMatch(text);
  }

  /// Check if the current locale is CJK.
  static bool isCJKLocale(Locale? locale) {
    if (locale == null) return false;
    return locale.languageCode == 'zh' ||
        locale.languageCode == 'ja' ||
        locale.languageCode == 'ko';
  }
}
