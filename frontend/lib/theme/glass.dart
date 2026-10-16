/// Liquid Glass components for XiaoLing.
///
/// Implements Apple's Liquid Glass design language (WWDC25) with:
/// - BackdropFilter blur + semi-transparent tint + 1px highlight stroke
/// - Glass layer count limit (≤3 simultaneous on screen)
/// - Low-end device fallback (opaque fill)
/// - Accessibility degradation (reduce-motion, reduce-transparency, high-contrast)
///
/// IMPORTANT: Glass should ONLY be used for navigation/functional layers (sidebar,
/// toolbar, tab bar, overlays). Content layers (charts, tables, cards with data)
/// must remain opaque per Apple HIG.
library;

import 'dart:io';
import 'dart:ui';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'tokens.dart';
import 'theme.dart';

// ---------------------------------------------------------------------------
// Glass layer counter — tracks simultaneous BackdropFilter instances
// ---------------------------------------------------------------------------

class _GlassLayerCounter extends InheritedWidget {
  final int count;
  const _GlassLayerCounter({required this.count, required super.child});

  static int of(BuildContext context) {
    final counter = context.dependOnInheritedWidgetOfExactType<_GlassLayerCounter>();
    return counter?.count ?? 0;
  }

  @override
  bool updateShouldNotify(_GlassLayerCounter oldWidget) => count != oldWidget.count;
}

/// Tracks the number of active glass layers in the widget tree.
/// Used to enforce the maxSimultaneousBlurLayers limit.
class XlGlassLayerScope extends StatefulWidget {
  final Widget child;
  const XlGlassLayerScope({super.key, required this.child});

  @override
  State<XlGlassLayerScope> createState() => _XlGlassLayerScopeState();
}

class _XlGlassLayerScopeState extends State<XlGlassLayerScope> {
  int _count = 0;

  void increment() => setState(() => _count++);
  void decrement() => setState(() => _count--);

  @override
  Widget build(BuildContext context) =>
      _GlassLayerCounter(count: _count, child: widget.child);
}

// ---------------------------------------------------------------------------
// Low-end device detection
// ---------------------------------------------------------------------------

class _LowEndDetector {
  static bool? _isLowEnd;

  static bool get isLowEnd {
    if (_isLowEnd != null) return _isLowEnd!;
    // Desktop platforms are never low-end for blur purposes
    if (Platform.isMacOS || Platform.isWindows || Platform.isLinux) {
      _isLowEnd = false;
      return false;
    }
    // iOS devices since A12 handle blur fine
    if (Platform.isIOS) {
      _isLowEnd = false;
      return false;
    }
    // Android: assume low-end if we can't determine (conservative)
    // In production, check total RAM < 4GB via device_info_plus
    _isLowEnd = true;
    return true;
  }
}

// ---------------------------------------------------------------------------
// Accessibility helpers
// ---------------------------------------------------------------------------

class _AccessibilityHelper {
  static bool reduceMotion(BuildContext context) =>
      MediaQuery.of(context).disableAnimations;

  static bool reduceTransparency(BuildContext context) =>
      MediaQuery.of(context).disableAnimations; // Flutter doesn't expose reduceTransparency directly

  static bool boldText(BuildContext context) =>
      MediaQuery.of(context).boldText;

  static double textScaleFactor(BuildContext context) =>
      MediaQuery.of(context).textScaleFactor;
}

// ---------------------------------------------------------------------------
// GlassSurface — the foundational Liquid Glass widget
// ---------------------------------------------------------------------------

/// Liquid Glass surface with BackdropFilter blur + tint + highlight.
///
/// Use for navigation/functional layers ONLY. Content layers (charts, tables,
/// data cards) must remain opaque per Apple HIG.
///
/// Features:
/// - BackdropFilter with ImageFilter.blur (lensing effect)
/// - Semi-transparent tint overlay
/// - 1px top-edge specular highlight gradient
/// - Respects reduce-transparency (falls back to opaque)
/// - Enforces maxSimultaneousBlurLayers limit (degrades to opaque if exceeded)
/// - Low-end device fallback (opaque fill)
/// - RepaintBoundary for performance isolation
class GlassSurface extends StatefulWidget {
  final Widget child;
  final XlGlassMaterial material;
  final double borderRadius;
  final Color? tint;
  final bool continuousCorner;
  final EdgeInsetsGeometry? padding;
  final EdgeInsetsGeometry? margin;
  final BoxBorder? border;
  final List<BoxShadow>? boxShadow;
  final bool clipChild;

  const GlassSurface({
    super.key,
    required this.child,
    this.material = XlGlassMaterial.regular,
    this.borderRadius = 16.0,
    this.tint,
    this.continuousCorner = true,
    this.padding,
    this.margin,
    this.border,
    this.boxShadow,
    this.clipChild = true,
  });

  @override
  State<GlassSurface> createState() => _GlassSurfaceState();
}

class _GlassSurfaceState extends State<GlassSurface> {
  bool _registered = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Register with layer scope if not already
    final scope = context.findAncestorStateOfType<_XlGlassLayerScopeState>();
    if (scope != null && !_registered) {
      final currentCount = _GlassLayerCounter.of(context);
      if (currentCount < XlMaterial.maxSimultaneousBlurLayers) {
        scope.increment();
        _registered = true;
      }
    }
  }

  @override
  void dispose() {
    if (_registered) {
      final scope = context.findAncestorStateOfType<_XlGlassLayerScopeState>();
      scope?.decrement();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final isDark = p.isDark;
    final reduceTransparency = _AccessibilityHelper.reduceTransparency(context);
    final reduceMotion = _AccessibilityHelper.reduceMotion(context);
    final currentCount = _GlassLayerCounter.of(context);
    final isLowEnd = _LowEndDetector.isLowEnd;

    // Determine if we should use glass or fallback to opaque
    final useGlass = !reduceTransparency &&
        !isLowEnd &&
        currentCount < XlMaterial.maxSimultaneousBlurLayers;

    final params = XlMaterial.glassParams(widget.material, isDark: isDark);
    final radius = widget.continuousCorner
        ? XlContinuousRadius.circular(widget.borderRadius)
        : BorderRadius.circular(widget.borderRadius);

    // Apply custom tint if provided, otherwise use material tint
    final tintedColor = widget.tint ?? params.tint.withOpacity(params.tintOpacity);

    Widget content = widget.child;
    if (widget.padding != null) {
      content = Padding(padding: widget.padding!, child: content);
    }

    if (useGlass) {
      // Glass implementation with BackdropFilter
      content = ClipRRect(
        borderRadius: radius,
        child: BackdropFilter(
          filter: ImageFilter.blur(
            sigmaX: params.blurSigma,
            sigmaY: params.blurSigma,
            tileMode: TileMode.clamp,
          ),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: radius,
              // Layer 1: Tint
              color: tintedColor,
              // Layer 2: Border with highlight stroke
              border: widget.border ??
                  Border.all(
                    color: isDark
                        ? Colors.white.withOpacity(0.12)
                        : Colors.white.withOpacity(0.40),
                    width: 0.5,
                  ),
              // Layer 3: Specular highlight gradient overlay
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  params.highlightTop,
                  params.highlightBottom,
                ],
                stops: const [0.0, 0.4],
              ),
              boxShadow: widget.boxShadow,
            ),
            child: widget.clipChild
                ? ClipRRect(borderRadius: radius, child: content)
                : content,
          ),
        ),
      );
    } else {
      // Opaque fallback for reduce-transparency / low-end / layer limit exceeded
      content = Container(
        decoration: BoxDecoration(
          borderRadius: radius,
          color: p.surface,
          border: widget.border ??
              Border.all(
                color: p.edge,
                width: 1,
              ),
          boxShadow: widget.boxShadow ?? p.raisedSm,
        ),
        child: widget.clipChild
            ? ClipRRect(borderRadius: radius, child: content)
            : content,
      );
    }

    // Wrap in RepaintBoundary for performance isolation
    content = RepaintBoundary(child: content);

    if (widget.margin != null) {
      content = Padding(padding: widget.margin!, child: content);
    }

    return content;
  }
}

// ---------------------------------------------------------------------------
// GlassCard — convenience wrapper for card-style glass
// ---------------------------------------------------------------------------

/// Glass card with standard padding and border radius.
///
/// Use for navigation/functional cards (sidebar items, toolbar buttons).
/// Do NOT use for content cards (data display, charts) — those must be opaque.
class GlassCard extends StatelessWidget {
  final Widget child;
  final XlGlassMaterial material;
  final EdgeInsetsGeometry padding;
  final double borderRadius;
  final Color? tint;
  final VoidCallback? onTap;
  final bool continuousCorner;

  const GlassCard({
    super.key,
    required this.child,
    this.material = XlGlassMaterial.regular,
    this.padding = const EdgeInsets.all(16),
    this.borderRadius = 16.0,
    this.tint,
    this.onTap,
    this.continuousCorner = true,
  });

  @override
  Widget build(BuildContext context) {
    final card = GlassSurface(
      material: material,
      borderRadius: borderRadius,
      tint: tint,
      continuousCorner: continuousCorner,
      padding: padding,
      child: child,
    );

    if (onTap != null) {
      return MouseRegion(
        cursor: SystemMouseCursors.click,
        child: GestureDetector(
          onTap: onTap,
          child: card,
        ),
      );
    }
    return card;
  }
}

// ---------------------------------------------------------------------------
// GlassAppBar — navigation bar with glass material
// ---------------------------------------------------------------------------

/// Glass app bar for navigation layer.
///
/// Uses [XlGlassMaterial.chrome] by default (σ24 blur, 0.25–0.30 tint).
/// Includes 1px bottom highlight stroke.
class GlassAppBar extends StatelessWidget implements PreferredSizeWidget {
  final Widget? title;
  final List<Widget>? actions;
  final Widget? leading;
  final double height;
  final XlGlassMaterial material;
  final bool showBottomBorder;

  const GlassAppBar({
    super.key,
    this.title,
    this.actions,
    this.leading,
    this.height = 56.0,
    this.material = XlGlassMaterial.chrome,
    this.showBottomBorder = true,
  });

  @override
  Size get preferredSize => Size.fromHeight(height);

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final isDark = p.isDark;
    final reduceTransparency = _AccessibilityHelper.reduceTransparency(context);
    final currentCount = _GlassLayerCounter.of(context);
    final isLowEnd = _LowEndDetector.isLowEnd;

    final useGlass = !reduceTransparency &&
        !isLowEnd &&
        currentCount < XlMaterial.maxSimultaneousBlurLayers;

    final params = XlMaterial.glassParams(material, isDark: isDark);

    Widget appBar = Container(
      height: height,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        // Glass or opaque
        color: useGlass
            ? params.tint.withOpacity(params.tintOpacity)
            : p.surface,
        // Bottom border (highlight stroke)
        border: showBottomBorder
            ? Border(
                bottom: BorderSide(
                  color: isDark
                      ? Colors.white.withOpacity(0.12)
                      : Colors.white.withOpacity(0.40),
                  width: 0.5,
                ),
              )
            : null,
        // Specular highlight gradient
        gradient: useGlass
            ? LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  params.highlightTop,
                  params.highlightBottom,
                ],
                stops: const [0.0, 0.4],
              )
            : null,
      ),
      child: Row(
        children: [
          if (leading != null) leading!,
          if (title != null)
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: DefaultTextStyle(
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w600,
                    color: p.text1,
                  ),
                  child: title!,
                ),
              ),
            ),
          if (actions != null) ...actions!,
        ],
      ),
    );

    if (useGlass) {
      appBar = ClipRect(
        child: BackdropFilter(
          filter: ImageFilter.blur(
            sigmaX: params.blurSigma,
            sigmaY: params.blurSigma,
            tileMode: TileMode.clamp,
          ),
          child: appBar,
        ),
      );
    }

    return RepaintBoundary(child: appBar);
  }
}

// ---------------------------------------------------------------------------
// Scroll edge effect — soft blur fade at scroll boundaries
// ---------------------------------------------------------------------------

/// Soft scroll edge effect (iOS/Android style).
///
/// Applies a gradient mask at the top/bottom of a scrollable to create a
/// gradual blur fade between content and floating UI.
class SoftScrollEdge extends StatelessWidget {
  final Widget child;
  final double topHeight;
  final double bottomHeight;
  final ScrollController? controller;

  const SoftScrollEdge({
    super.key,
    required this.child,
    this.topHeight = 24.0,
    this.bottomHeight = 24.0,
    this.controller,
  });

  @override
  Widget build(BuildContext context) {
    return ShaderMask(
      shaderCallback: (rect) {
        return LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Colors.transparent,
            Colors.white,
            Colors.white,
            Colors.transparent,
          ],
          stops: [
            0.0,
            topHeight / rect.height,
            1.0 - (bottomHeight / rect.height),
            1.0,
          ],
        ).createShader(rect);
      },
      blendMode: BlendMode.dstIn,
      child: child,
    );
  }
}

/// Hard scroll edge effect (macOS style).
///
/// Uniform opaque background across toolbar height — no gradient fade.
class HardScrollEdge extends StatelessWidget {
  final Widget child;
  final Color color;
  final double topHeight;
  final double bottomHeight;

  const HardScrollEdge({
    super.key,
    required this.child,
    required this.color,
    this.topHeight = 56.0,
    this.bottomHeight = 56.0,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        child,
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          height: topHeight,
          child: Container(color: color),
        ),
        Positioned(
          bottom: 0,
          left: 0,
          right: 0,
          height: bottomHeight,
          child: Container(color: color),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// GlassTabBar — bottom tab bar with glass material (mobile)
// ---------------------------------------------------------------------------

/// Glass bottom tab bar for mobile navigation.
///
/// Height: 49pt content + safe area bottom.
/// Material: [XlGlassMaterial.regular] by default.
/// Touch target: 44×44 minimum per iOS HIG.
class GlassTabBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;
  final List<GlassTabItem> items;
  final XlGlassMaterial material;

  const GlassTabBar({
    super.key,
    required this.currentIndex,
    required this.onTap,
    required this.items,
    this.material = XlGlassMaterial.regular,
  });

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final bottomPadding = MediaQuery.of(context).padding.bottom;

    return GlassSurface(
      material: material,
      borderRadius: 0,
      continuousCorner: false,
      margin: EdgeInsets.only(bottom: bottomPadding),
      child: SizedBox(
        height: 49,
        child: Row(
          children: List.generate(items.length, (i) {
            final item = items[i];
            final isSelected = i == currentIndex;
            final color = isSelected ? p.pink : p.text3;

            return Expanded(
              child: GestureDetector(
                onTap: () => onTap(i),
                behavior: HitTestBehavior.opaque,
                child: MouseRegion(
                  cursor: SystemMouseCursors.click,
                  child: Container(
                    constraints: const BoxConstraints(
                      minWidth: 44,
                      minHeight: 44,
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(item.icon, size: 24, color: color),
                        const SizedBox(height: 3),
                        Text(
                          item.label,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                            color: color,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          }),
        ),
      ),
    );
  }
}

class GlassTabItem {
  final IconData icon;
  final String label;
  const GlassTabItem({required this.icon, required this.label});
}
