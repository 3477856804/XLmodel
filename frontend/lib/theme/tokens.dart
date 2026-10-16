/// Apple-aligned design tokens for XiaoLing.
///
/// These tokens complement (not replace) the existing XlSpace / XlRadius / etc.
/// in theme.dart. Pages can migrate gradually by referencing [XlAppleSpace],
/// [XlAppleRadius], [XlMaterial], etc.
///
/// See APPLE_DESIGN_SPEC.md §2 for source of each value.
library;

import 'dart:math' as math;
import 'package:flutter/material.dart';

// ---------------------------------------------------------------------------
// §2.4  Spacing scale (4pt base grid)
// ---------------------------------------------------------------------------

class XlAppleSpace {
  XlAppleSpace._();
  static const double s0 = 0;
  static const double s2 = 2;
  static const double s4 = 4;
  static const double s8 = 8;
  static const double s12 = 12;
  static const double s16 = 16;
  static const double s20 = 20;
  static const double s24 = 24;
  static const double s32 = 32;
  static const double s40 = 40;
  static const double s48 = 48;
  static const double s64 = 64;
}

// ---------------------------------------------------------------------------
// §2.5  Corner radius scale + continuous-corner approximation
// ---------------------------------------------------------------------------

class XlAppleRadius {
  XlAppleRadius._();
  static const double none = 0;
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 28;

  /// Capsule = height / 2. Use with [BorderRadius.circular(h / 2)].
  static double capsule(double height) => height / 2;
}

/// Continuous-corner (squircle / superellipse) approximation.
///
/// Apple uses continuous curvature everywhere. True superellipse requires a
/// custom [ShapeBorder] or [ClipPath]; this helper provides a pragmatic
/// approximation that is visually close at UI scale: we inflate the radius
/// by ~18 % so the circular arc looks more like a squircle.
///
/// For pixel-perfect results, wrap the widget in [XlContinuousCornerClip].
class XlContinuousRadius {
  XlContinuousRadius._();

  /// Inflate a logical radius to approximate continuous curvature.
  static double approximate(double r) => r * 1.18;

  static BorderRadius circular(double r) =>
      BorderRadius.circular(approximate(r));
}

/// ClipPath that clips its child with a true superellipse (squircle) corner.
///
/// Uses the equation |x/a|^n + |y/b|^n = 1 with n ≈ 5 (Apple hardware uses
/// n in 4–6 range). Expensive — prefer [XlContinuousRadius.circular] for
/// most cases and reserve this for hero elements.
class XlContinuousCornerClip extends StatelessWidget {
  final double radius;
  final double exponent;
  final Widget child;

  const XlContinuousCornerClip({
    super.key,
    required this.radius,
    required this.child,
    this.exponent = 5.0,
  });

  @override
  Widget build(BuildContext context) =>
      ClipPath(clipper: _SuperellipseClipper(radius, exponent), child: child);
}

class _SuperellipseClipper extends CustomClipper<Path> {
  final double radius;
  final double exponent;
  _SuperellipseClipper(this.radius, this.exponent);

  @override
  Path getClip(Size size) {
    final path = Path();
    final r = radius.clamp(0.0, math.min(size.width, size.height) / 2);
    if (r <= 0) {
      path.addRect(Rect.fromLTWH(0, 0, size.width, size.height));
      return path;
    }
    final n = exponent;
    // Sample the superellipse curve at each corner.
    const steps = 24;
    // Top-right corner
    final cx = size.width - r;
    final cy = r;
    path.moveTo(size.width, r);
    for (int i = 0; i <= steps; i++) {
      final theta = (i / steps) * (math.pi / 2);
      final dx = r * math.pow(math.cos(theta), 2 / n).toDouble();
      final dy = r * math.pow(math.sin(theta), 2 / n).toDouble();
      path.lineTo(cx + dx, cy - dy);
    }
    // Top-left corner
    final cx2 = r;
    final cy2 = r;
    for (int i = 0; i <= steps; i++) {
      final theta = (math.pi / 2) + (i / steps) * (math.pi / 2);
      final dx = r * math.pow(math.cos(theta), 2 / n).toDouble();
      final dy = r * math.pow(math.sin(theta), 2 / n).toDouble();
      path.lineTo(cx2 + dx, cy2 - dy);
    }
    // Bottom-left corner
    final cx3 = r;
    final cy3 = size.height - r;
    for (int i = 0; i <= steps; i++) {
      final theta = math.pi + (i / steps) * (math.pi / 2);
      final dx = r * math.pow(math.cos(theta), 2 / n).toDouble();
      final dy = r * math.pow(math.sin(theta), 2 / n).toDouble();
      path.lineTo(cx3 + dx, cy3 - dy);
    }
    // Bottom-right corner
    final cx4 = size.width - r;
    final cy4 = size.height - r;
    for (int i = 0; i <= steps; i++) {
      final theta = (3 * math.pi / 2) + (i / steps) * (math.pi / 2);
      final dx = r * math.pow(math.cos(theta), 2 / n).toDouble();
      final dy = r * math.pow(math.sin(theta), 2 / n).toDouble();
      path.lineTo(cx4 + dx, cy4 - dy);
    }
    path.close();
    return path;
  }

  @override
  bool shouldReclip(_SuperellipseClipper old) =>
      old.radius != radius || old.exponent != exponent;
}

// ---------------------------------------------------------------------------
// §2.3  Material tokens (Liquid Glass layers)
// ---------------------------------------------------------------------------

enum XlGlassMaterial {
  ultraThin,
  thin,
  regular,
  thick,
  chrome,
}

/// Resolved parameters for a glass material layer.
class XlGlassParams {
  final double blurSigma;
  final Color tint;
  final double tintOpacity;
  final Color highlightTop;
  final Color highlightBottom;

  const XlGlassParams({
    required this.blurSigma,
    required this.tint,
    required this.tintOpacity,
    required this.highlightTop,
    required this.highlightBottom,
  });
}

class XlMaterial {
  XlMaterial._();

  // §2.6 blur sigmas
  static const double blurUltraThin = 8;
  static const double blurThin = 12;
  static const double blurRegular = 20;
  static const double blurThick = 30;
  static const double blurChrome = 24;

  // §2.6 highlight stroke
  static const double highlightStrokeWidth = 1.0;

  // §2.6 performance cap
  static const int maxSimultaneousBlurLayers = 3;

  /// Resolve a glass material to concrete parameters for the given brightness.
  static XlGlassParams glassParams(
    XlGlassMaterial mat, {
    required bool isDark,
  }) {
    switch (mat) {
      case XlGlassMaterial.ultraThin:
        return XlGlassParams(
          blurSigma: blurUltraThin,
          tint: isDark ? const Color(0xFF000000) : const Color(0xFFFFFFFF),
          tintOpacity: isDark ? 0.05 : 0.08,
          highlightTop:
              Colors.white.withOpacity(isDark ? 0.08 : 0.18),
          highlightBottom: Colors.white.withOpacity(0.0),
        );
      case XlGlassMaterial.thin:
        return XlGlassParams(
          blurSigma: blurThin,
          tint: isDark ? const Color(0xFF000000) : const Color(0xFFFFFFFF),
          tintOpacity: isDark ? 0.10 : 0.12,
          highlightTop:
              Colors.white.withOpacity(isDark ? 0.10 : 0.20),
          highlightBottom: Colors.white.withOpacity(0.0),
        );
      case XlGlassMaterial.regular:
        return XlGlassParams(
          blurSigma: blurRegular,
          tint: isDark ? const Color(0xFF000000) : const Color(0xFFFFFFFF),
          tintOpacity: isDark ? 0.20 : 0.25,
          highlightTop:
              Colors.white.withOpacity(isDark ? 0.12 : 0.25),
          highlightBottom: Colors.white.withOpacity(0.0),
        );
      case XlGlassMaterial.thick:
        return XlGlassParams(
          blurSigma: blurThick,
          tint: isDark ? const Color(0xFF000000) : const Color(0xFFFFFFFF),
          tintOpacity: isDark ? 0.35 : 0.40,
          highlightTop:
              Colors.white.withOpacity(isDark ? 0.14 : 0.30),
          highlightBottom: Colors.white.withOpacity(0.0),
        );
      case XlGlassMaterial.chrome:
        return XlGlassParams(
          blurSigma: blurChrome,
          tint: isDark ? const Color(0xFF000000) : const Color(0xFFFFFFFF),
          tintOpacity: isDark ? 0.25 : 0.30,
          highlightTop:
              Colors.white.withOpacity(isDark ? 0.12 : 0.22),
          highlightBottom: Colors.white.withOpacity(0.0),
        );
    }
  }

  // §2.10  WCAG contrast helpers
  /// Compute relative luminance per WCAG 2.1.
  static double _luminance(Color c) {
    double linearize(double v) =>
        v <= 0.03928 ? v / 12.92 : math.pow((v + 0.055) / 1.055, 2.4).toDouble();
    return 0.2126 * linearize(c.red / 255) +
        0.7152 * linearize(c.green / 255) +
        0.0722 * linearize(c.blue / 255);
  }

  /// WCAG contrast ratio between two colors.
  static double contrastRatio(Color a, Color b) {
    final la = _luminance(a);
    final lb = _luminance(b);
    final lighter = math.max(la, lb);
    final darker = math.min(la, lb);
    return (lighter + 0.05) / (darker + 0.05);
  }

  /// Check if a foreground meets WCAG AA (4.5:1) against a background.
  static bool meetsAA(Color fg, Color bg) => contrastRatio(fg, bg) >= 4.5;

  /// Check if a foreground meets WCAG AA large-text (3:1) against a background.
  static bool meetsAALarge(Color fg, Color bg) => contrastRatio(fg, bg) >= 3.0;
}

// ---------------------------------------------------------------------------
// §2.8  Motion tokens (aligned with spec)
// ---------------------------------------------------------------------------

class XlAppleMotion {
  XlAppleMotion._();

  // Durations
  static const Duration instant = Duration(milliseconds: 80);
  static const Duration fast = Duration(milliseconds: 150);
  static const Duration normal = Duration(milliseconds: 250);
  static const Duration medium = Duration(milliseconds: 350);
  static const Duration slow = Duration(milliseconds: 500);
  static const Duration deliberate = Duration(milliseconds: 700);

  // Curves
  static const Curve easeOutCurve = Cubic(0.0, 0.0, 0.2, 1.0);
  static const Curve easeInOutCurve = Cubic(0.4, 0.0, 0.2, 1.0);

  /// Spring description for natural feel.
  static const SpringDescription spring = SpringDescription(
    mass: 1,
    stiffness: 180,
    damping: 16,
  );

  /// When reduce-motion is active, cap durations at this.
  static const Duration reduceMotionMaxDuration = Duration(milliseconds: 150);

  /// Resolve a duration respecting reduce-motion preference.
  static Duration resolve(Duration d, {required bool reduceMotion}) {
    if (!reduceMotion) return d;
    return Duration(
      milliseconds: math.min(
        d.inMilliseconds,
        reduceMotionMaxDuration.inMilliseconds,
      ),
    );
  }

  /// Resolve a curve respecting reduce-motion preference.
  static Curve resolveCurve(Curve c, {required bool reduceMotion}) =>
      reduceMotion ? easeOutCurve : c;
}

// ---------------------------------------------------------------------------
// §2.9  Control sizes & touch targets
// ---------------------------------------------------------------------------

class XlControlSize {
  XlControlSize._();
  // macOS sizes
  static const double mini = 16;
  static const double small = 20;
  static const double medium = 28;
  static const double large = 32;
  static const double xLarge = 40;
  // Touch targets
  static const double touchTarget = 44; // iOS minimum
  static const double macTouchTarget = 28; // macOS pointer
}

// ---------------------------------------------------------------------------
// §6  Platform detection helper
// ---------------------------------------------------------------------------

enum XlPlatformCategory { desktop, phone, tablet }

class XlPlatformHelper {
  XlPlatformHelper._();

  static XlPlatformCategory categoryOf(BuildContext context) {
    final p = Theme.of(context).platform;
    final w = MediaQuery.of(context).size.width;
    switch (p) {
      case TargetPlatform.macOS:
      case TargetPlatform.windows:
      case TargetPlatform.linux:
        return XlPlatformCategory.desktop;
      case TargetPlatform.iOS:
        return w >= 600 ? XlPlatformCategory.tablet : XlPlatformCategory.phone;
      case TargetPlatform.android:
        return w >= 600 ? XlPlatformCategory.tablet : XlPlatformCategory.phone;
      case TargetPlatform.fuchsia:
        return XlPlatformCategory.phone;
    }
  }

  static bool isDesktop(BuildContext context) =>
      categoryOf(context) == XlPlatformCategory.desktop;

  static bool isPhone(BuildContext context) =>
      categoryOf(context) == XlPlatformCategory.phone;

  static bool isTablet(BuildContext context) =>
      categoryOf(context) == XlPlatformCategory.tablet;

  /// Whether hover effects should be enabled on this platform.
  static bool supportsHover(BuildContext context) {
    final p = Theme.of(context).platform;
    return p == TargetPlatform.macOS ||
        p == TargetPlatform.windows ||
        p == TargetPlatform.linux;
  }
}
