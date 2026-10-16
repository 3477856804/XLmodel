/// Apple-aligned button components for XiaoLing.
///
/// Implements §5.4 of APPLE_DESIGN_SPEC.md:
/// - Filled button (primary CTA)
/// - Tinted button (secondary)
/// - Glass button (tertiary, uses Liquid Glass)
/// - Plain button (borderless, text-only)
///
/// All buttons support:
/// - Hover effects (desktop only)
/// - Reduce-motion support
/// - 44pt minimum touch target (iOS)
/// - Capsule border radius
library;

import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../theme/tokens.dart';
import '../theme/glass.dart';
import '../theme/motion.dart';

// ---------------------------------------------------------------------------
// Base button style
// ---------------------------------------------------------------------------

enum XlButtonStyle {
  filled,
  tinted,
  glass,
  plain,
}

enum XlButtonSize {
  small,
  medium,
  large,
}

// ---------------------------------------------------------------------------
// XlButton — unified button component
// ---------------------------------------------------------------------------

class XlButton extends StatefulWidget {
  final String text;
  final VoidCallback? onPressed;
  final XlButtonStyle style;
  final XlButtonSize size;
  final IconData? icon;
  final Color? accentColor;
  final bool expand;

  const XlButton({
    super.key,
    required this.text,
    this.onPressed,
    this.style = XlButtonStyle.filled,
    this.size = XlButtonSize.medium,
    this.icon,
    this.accentColor,
    this.expand = false,
  });

  @override
  State<XlButton> createState() => _XlButtonState();
}

class _XlButtonState extends State<XlButton> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final isDark = p.isDark;
    final supportsHover = XlPlatformHelper.supportsHover(context);
    final reduceMotion = MediaQuery.of(context).disableAnimations;

    // Resolve size
    final height = switch (widget.size) {
      XlButtonSize.small => 28.0,
      XlButtonSize.medium => 36.0,
      XlButtonSize.large => 44.0,
    };
    final fontSize = switch (widget.size) {
      XlButtonSize.small => 13.0,
      XlButtonSize.medium => 15.0,
      XlButtonSize.large => 17.0,
    };
    final horizontalPadding = switch (widget.size) {
      XlButtonSize.small => 12.0,
      XlButtonSize.medium => 16.0,
      XlButtonSize.large => 20.0,
    };

    // Resolve accent color
    final accent = widget.accentColor ?? p.pink;

    // Build button content
    Widget content = Row(
      mainAxisSize: widget.expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (widget.icon != null) ...[
          Icon(widget.icon, size: fontSize + 2),
          const SizedBox(width: 6),
        ],
        Text(
          widget.text,
          style: TextStyle(
            fontSize: fontSize,
            fontWeight: FontWeight.w600,
            letterSpacing: -0.2,
          ),
        ),
      ],
    );

    // Build button decoration based on style
    Widget button;
    switch (widget.style) {
      case XlButtonStyle.filled:
        button = _buildFilledButton(
            p, isDark, height, horizontalPadding, accent, content);
        break;
      case XlButtonStyle.tinted:
        button = _buildTintedButton(
            p, isDark, height, horizontalPadding, accent, content);
        break;
      case XlButtonStyle.glass:
        button =
            _buildGlassButton(p, isDark, height, horizontalPadding, content);
        break;
      case XlButtonStyle.plain:
        button = _buildPlainButton(
            p, isDark, height, horizontalPadding, accent, content);
        break;
    }

    // Wrap in gesture detector
    button = GestureDetector(
      onTap: widget.onPressed,
      behavior: HitTestBehavior.opaque,
      child: button,
    );

    // Add hover effect (desktop only)
    if (supportsHover && widget.onPressed != null) {
      button = MouseRegion(
        onEnter: (_) => setState(() => _isHovered = true),
        onExit: (_) => setState(() => _isHovered = false),
        cursor: SystemMouseCursors.click,
        child: AnimatedScale(
          scale: _isHovered ? 1.02 : 1.0,
          duration: reduceMotion
              ? XlAppleMotion.reduceMotionMaxDuration
              : XlAppleMotion.fast,
          child: button,
        ),
      );
    }

    // Enforce minimum touch target (44pt)
    return SizedBox(
      height: height.clamp(44.0, double.infinity),
      child: Center(child: button),
    );
  }

  Widget _buildFilledButton(
    XlPalette p,
    bool isDark,
    double height,
    double horizontalPadding,
    Color accent,
    Widget content,
  ) {
    return Container(
      height: height,
      padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [accent, accent.withOpacity(0.85)],
        ),
        borderRadius: BorderRadius.circular(height / 2), // capsule
        border: Border.all(
          color: Colors.white.withOpacity(isDark ? 0.20 : 0.30),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: accent.withOpacity(0.30),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Center(
        child: DefaultTextStyle(
          style: TextStyle(color: p.btnInk),
          child: content,
        ),
      ),
    );
  }

  Widget _buildTintedButton(
    XlPalette p,
    bool isDark,
    double height,
    double horizontalPadding,
    Color accent,
    Widget content,
  ) {
    return Container(
      height: height,
      padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
      decoration: BoxDecoration(
        color: accent.withOpacity(0.12),
        borderRadius: BorderRadius.circular(height / 2),
        border: Border.all(
          color: accent.withOpacity(0.30),
          width: 1,
        ),
      ),
      child: Center(
        child: DefaultTextStyle(
          style: TextStyle(color: accent),
          child: content,
        ),
      ),
    );
  }

  Widget _buildGlassButton(
    XlPalette p,
    bool isDark,
    double height,
    double horizontalPadding,
    Widget content,
  ) {
    return GlassSurface(
      material: XlGlassMaterial.thin,
      borderRadius: height / 2,
      padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
      child: SizedBox(
        height: height,
        child: Center(
          child: DefaultTextStyle(
            style: TextStyle(color: p.text1),
            child: content,
          ),
        ),
      ),
    );
  }

  Widget _buildPlainButton(
    XlPalette p,
    bool isDark,
    double height,
    double horizontalPadding,
    Color accent,
    Widget content,
  ) {
    return Container(
      height: height,
      padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
      decoration: BoxDecoration(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(height / 2),
      ),
      child: Center(
        child: DefaultTextStyle(
          style: TextStyle(color: accent),
          child: content,
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Convenience constructors
// ---------------------------------------------------------------------------

class XlFilledButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final XlButtonSize size;
  final IconData? icon;
  final Color? accentColor;
  final bool expand;

  const XlFilledButton({
    super.key,
    required this.text,
    this.onPressed,
    this.size = XlButtonSize.medium,
    this.icon,
    this.accentColor,
    this.expand = false,
  });

  @override
  Widget build(BuildContext context) => XlButton(
        text: text,
        onPressed: onPressed,
        style: XlButtonStyle.filled,
        size: size,
        icon: icon,
        accentColor: accentColor,
        expand: expand,
      );
}

class XlTintedButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final XlButtonSize size;
  final IconData? icon;
  final Color? accentColor;
  final bool expand;

  const XlTintedButton({
    super.key,
    required this.text,
    this.onPressed,
    this.size = XlButtonSize.medium,
    this.icon,
    this.accentColor,
    this.expand = false,
  });

  @override
  Widget build(BuildContext context) => XlButton(
        text: text,
        onPressed: onPressed,
        style: XlButtonStyle.tinted,
        size: size,
        icon: icon,
        accentColor: accentColor,
        expand: expand,
      );
}

class XlGlassButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final XlButtonSize size;
  final IconData? icon;
  final bool expand;

  const XlGlassButton({
    super.key,
    required this.text,
    this.onPressed,
    this.size = XlButtonSize.medium,
    this.icon,
    this.expand = false,
  });

  @override
  Widget build(BuildContext context) => XlButton(
        text: text,
        onPressed: onPressed,
        style: XlButtonStyle.glass,
        size: size,
        icon: icon,
        expand: expand,
      );
}

class XlPlainButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final XlButtonSize size;
  final IconData? icon;
  final Color? accentColor;
  final bool expand;

  const XlPlainButton({
    super.key,
    required this.text,
    this.onPressed,
    this.size = XlButtonSize.medium,
    this.icon,
    this.accentColor,
    this.expand = false,
  });

  @override
  Widget build(BuildContext context) => XlButton(
        text: text,
        onPressed: onPressed,
        style: XlButtonStyle.plain,
        size: size,
        icon: icon,
        accentColor: accentColor,
        expand: expand,
      );
}
