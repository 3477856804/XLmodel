/// Motion utilities for XiaoLing.
///
/// Implements §2.8 of APPLE_DESIGN_SPEC.md:
/// - Reduce-motion support
/// - Spring animations
/// - Duration/curve helpers
library;

import 'package:flutter/material.dart';
import 'tokens.dart';

// ---------------------------------------------------------------------------
// Motion helpers
// ---------------------------------------------------------------------------

class XlMotion {
  XlMotion._();

  /// Resolve a duration respecting reduce-motion preference.
  static Duration resolve(Duration d, BuildContext context) {
    final reduceMotion = MediaQuery.of(context).disableAnimations;
    return XlAppleMotion.resolve(d, reduceMotion: reduceMotion);
  }

  /// Resolve a curve respecting reduce-motion preference.
  static Curve resolveCurve(Curve c, BuildContext context) {
    final reduceMotion = MediaQuery.of(context).disableAnimations;
    return XlAppleMotion.resolveCurve(c, reduceMotion: reduceMotion);
  }

  /// Create an animation controller with reduce-motion support.
  static AnimationController controller({
    required TickerProvider vsync,
    required Duration duration,
    BuildContext? context,
  }) {
    final resolvedDuration = context != null
        ? resolve(duration, context)
        : duration;
    return AnimationController(
      vsync: vsync,
      duration: resolvedDuration,
    );
  }

  /// Create a spring animation with reduce-motion support.
  ///
  /// When reduce-motion is active, falls back to easeOut curve.
  /// Otherwise uses a spring-like cubic curve approximation.
  static Animation<double> spring({
    required AnimationController controller,
    required double begin,
    required double end,
    BuildContext? context,
  }) {
    final reduceMotion = context != null
        ? MediaQuery.of(context).disableAnimations
        : false;

    if (reduceMotion) {
      // Use ease-out instead of spring
      return Tween<double>(begin: begin, end: end).animate(
        CurvedAnimation(
          parent: controller,
          curve: XlAppleMotion.easeOutCurve,
        ),
      );
    } else {
      // Approximate spring with overshoot cubic curve
      return Tween<double>(begin: begin, end: end).animate(
        CurvedAnimation(
          parent: controller,
          curve: const Cubic(0.34, 1.20, 0.64, 1.0), // spring overshoot
        ),
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Hover effect helper (desktop only)
// ---------------------------------------------------------------------------

class XlHoverEffect extends StatefulWidget {
  final Widget child;
  final Color? hoverColor;
  final double scale;
  final Duration duration;
  final VoidCallback? onTap;

  const XlHoverEffect({
    super.key,
    required this.child,
    this.hoverColor,
    this.scale = 1.0,
    this.duration = const Duration(milliseconds: 150),
    this.onTap,
  });

  @override
  State<XlHoverEffect> createState() => _XlHoverEffectState();
}

class _XlHoverEffectState extends State<XlHoverEffect> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final supportsHover = Theme.of(context).platform == TargetPlatform.macOS ||
        Theme.of(context).platform == TargetPlatform.windows ||
        Theme.of(context).platform == TargetPlatform.linux;

    if (!supportsHover) {
      return widget.child;
    }

    Widget content = AnimatedScale(
      scale: _isHovered ? widget.scale : 1.0,
      duration: widget.duration,
      child: AnimatedContainer(
        duration: widget.duration,
        decoration: BoxDecoration(
          color: _isHovered ? widget.hoverColor : Colors.transparent,
        ),
        child: widget.child,
      ),
    );

    if (widget.onTap != null) {
      content = GestureDetector(
        onTap: widget.onTap,
        child: content,
      );
    }

    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      cursor: widget.onTap != null
          ? SystemMouseCursors.click
          : SystemMouseCursors.basic,
      child: content,
    );
  }
}
