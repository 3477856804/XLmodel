/// Apple-style toast/HUD (Head-Up Display) for XiaoLing.
///
/// Implements §5.7 of APPLE_DESIGN_SPEC.md:
/// - Transient overlay that auto-dismisses
/// - Glass morphism background
/// - Icon + message layout
/// - Smooth fade + slide animation
/// - Stacks at top-center of screen
/// - Maximum 3 simultaneous toasts
library;

import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../theme/tokens.dart';
import '../theme/glass.dart';
import '../theme/motion.dart';

/// Global toast overlay manager.
class XlToastManager {
  XlToastManager._();
  static final XlToastManager instance = XlToastManager._();

  final List<_ToastEntry> _toasts = [];
  static const int maxToasts = 3;

  VoidCallback? _onChanged;

  void _notify() => _onChanged?.call();

  /// Show a toast message.
  void show({
    required String message,
    IconData? icon,
    XlToastType type = XlToastType.info,
    Duration duration = const Duration(seconds: 2),
  }) {
    // Remove oldest if at max
    if (_toasts.length >= maxToasts) {
      _toasts.removeAt(0);
    }

    final entry = _ToastEntry(
      message: message,
      icon: icon ?? _defaultIcon(type),
      type: type,
      duration: duration,
    );
    _toasts.add(entry);
    _notify();

    // Auto-dismiss
    Timer(duration + const Duration(milliseconds: 300), () {
      _toasts.remove(entry);
      _notify();
    });
  }

  /// Show a success toast.
  void success(String message) => show(
        message: message,
        icon: Icons.check_circle_rounded,
        type: XlToastType.success,
      );

  /// Show an error toast.
  void error(String message) => show(
        message: message,
        icon: Icons.error_rounded,
        type: XlToastType.error,
      );

  /// Show a warning toast.
  void warning(String message) => show(
        message: message,
        icon: Icons.warning_rounded,
        type: XlToastType.warning,
      );

  /// Show an info toast.
  void info(String message) => show(
        message: message,
        icon: Icons.info_rounded,
        type: XlToastType.info,
      );

  IconData _defaultIcon(XlToastType type) {
    switch (type) {
      case XlToastType.success:
        return Icons.check_circle_rounded;
      case XlToastType.error:
        return Icons.error_rounded;
      case XlToastType.warning:
        return Icons.warning_rounded;
      case XlToastType.info:
        return Icons.info_rounded;
    }
  }
}

enum XlToastType { success, error, warning, info }

class _ToastEntry {
  final String message;
  final IconData icon;
  final XlToastType type;
  final Duration duration;

  _ToastEntry({
    required this.message,
    required this.icon,
    required this.type,
    required this.duration,
  });
}

/// Widget that displays the toast overlay. Place at the root of your app.
class XlToastOverlay extends StatefulWidget {
  final Widget child;

  const XlToastOverlay({super.key, required this.child});

  @override
  State<XlToastOverlay> createState() => _XlToastOverlayState();
}

class _XlToastOverlayState extends State<XlToastOverlay> {
  @override
  void initState() {
    super.initState();
    XlToastManager.instance._onChanged = _onToastChanged;
  }

  @override
  void dispose() {
    XlToastManager.instance._onChanged = null;
    super.dispose();
  }

  void _onToastChanged() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final toasts = XlToastManager.instance._toasts;

    return Stack(
      children: [
        widget.child,
        if (toasts.isNotEmpty)
          Positioned(
            top: MediaQuery.of(context).padding.top + 16,
            left: 0,
            right: 0,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children:
                  toasts.map((entry) => _ToastWidget(entry: entry)).toList(),
            ),
          ),
      ],
    );
  }
}

class _ToastWidget extends StatefulWidget {
  final _ToastEntry entry;

  const _ToastWidget({required this.entry});

  @override
  State<_ToastWidget> createState() => _ToastWidgetState();
}

class _ToastWidgetState extends State<_ToastWidget>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _opacity;
  late Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: XlDuration.normal,
      vsync: this,
    );
    _opacity = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _controller, curve: XlCurve.easeOut),
    );
    _slide = Tween<Offset>(
      begin: const Offset(0, -0.3),
      end: Offset.zero,
    ).animate(
      CurvedAnimation(parent: _controller, curve: XlCurve.easeOut),
    );
    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Color _iconColor(XlToastType type, XlPalette p) {
    switch (type) {
      case XlToastType.success:
        return p.green;
      case XlToastType.error:
        return p.red;
      case XlToastType.warning:
        return p.gold;
      case XlToastType.info:
        return p.blue;
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 4),
      child: SlideTransition(
        position: _slide,
        child: FadeTransition(
          opacity: _opacity,
          child: GlassSurface(
            material: XlGlassMaterial.chrome,
            // GlassSurface.borderRadius 是 double，不能传 BorderRadius。
            borderRadius: XlRadius.lg,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    widget.entry.icon,
                    size: 18,
                    color: _iconColor(widget.entry.type, p),
                  ),
                  const SizedBox(width: 8),
                  Flexible(
                    child: Text(
                      widget.entry.message,
                      style: TextStyle(
                        fontSize: XlFont.bodySm,
                        fontWeight: FontWeight.w500,
                        color: p.text1,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Convenience function to show a toast from anywhere.
void xlShowToast(String message, {XlToastType type = XlToastType.info}) {
  XlToastManager.instance.show(message: message, type: type);
}
