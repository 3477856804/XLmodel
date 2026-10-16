/// Apple-style dialog for XiaoLing.
///
/// Implements §5.8 of APPLE_DESIGN_SPEC.md:
/// - Glass morphism background with BackdropFilter
/// - Continuous corner (squircle approximation)
/// - Title + content + action buttons layout
/// - 280pt minimum width, 400pt maximum width
/// - Smooth scale + fade animation
library;

import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../theme/tokens.dart';
import '../theme/glass.dart';
import '../theme/motion.dart';
import 'xl_button.dart';

class XlDialog extends StatelessWidget {
  final String? title;
  final Widget? content;
  final String? message;
  final List<XlDialogAction> actions;
  final bool dismissible;

  const XlDialog({
    super.key,
    this.title,
    this.content,
    this.message,
    this.actions = const [],
    this.dismissible = true,
  });

  /// Show a dialog using the Apple style.
  static Future<T?> show<T>({
    required BuildContext context,
    String? title,
    Widget? content,
    String? message,
    List<XlDialogAction> actions = const [],
    bool dismissible = true,
  }) {
    return showDialog<T>(
      context: context,
      barrierDismissible: dismissible,
      barrierColor: XlPalette.of(context).scrim,
      builder: (context) => XlDialog(
        title: title,
        content: content,
        message: message,
        actions: actions,
        dismissible: dismissible,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minWidth: 280, maxWidth: 400),
          child: GlassSurface(
            material: XlGlassMaterial.chrome,
            // GlassSurface.borderRadius 的类型是 double（内部自行构造 BorderRadius），
            // 不能传 BorderRadius.circular(...)，否则编译不过。
            borderRadius: XlRadius.xl,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (title != null) ...[
                    Text(
                      title!,
                      style: TextStyle(
                        fontSize: XlFont.h5,
                        fontWeight: FontWeight.w700,
                        color: p.text1,
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                  if (message != null) ...[
                    Text(
                      message!,
                      style: TextStyle(
                        fontSize: XlFont.body,
                        color: p.text2,
                        height: XlLineHeight.normal,
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],
                  if (content != null) ...[
                    content!,
                    const SizedBox(height: 16),
                  ],
                  if (actions.isNotEmpty)
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        for (int i = 0; i < actions.length; i++) ...[
                          if (i > 0) const SizedBox(width: 8),
                          _buildActionButton(context, actions[i]),
                        ],
                      ],
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildActionButton(BuildContext context, XlDialogAction action) {
    // 按钮族（XlFilledButton / XlTintedButton / XlPlainButton）的必填参数名是
    // `text`，强调色参数名是 `accentColor`——此前这里写成 label/color，
    // 与组件签名不符，导致整个前端编译失败。
    if (action.isDefault) {
      return XlFilledButton(
        onPressed: action.onPressed,
        text: action.label,
        size: XlButtonSize.small,
      );
    } else if (action.isDestructive) {
      return XlTintedButton(
        onPressed: action.onPressed,
        text: action.label,
        accentColor: XlPalette.of(context).red,
        size: XlButtonSize.small,
      );
    } else {
      return XlPlainButton(
        onPressed: action.onPressed,
        text: action.label,
        size: XlButtonSize.small,
      );
    }
  }
}

/// Action button for XlDialog.
class XlDialogAction {
  final String label;
  final VoidCallback? onPressed;
  final bool isDefault;
  final bool isDestructive;

  const XlDialogAction({
    required this.label,
    this.onPressed,
    this.isDefault = false,
    this.isDestructive = false,
  });

  /// Convenience: cancel action.
  factory XlDialogAction.cancel(BuildContext context, {String label = '取消'}) {
    return XlDialogAction(
      label: label,
      onPressed: () => Navigator.of(context).pop(),
    );
  }

  /// Convenience: confirm action.
  factory XlDialogAction.confirm(String label, VoidCallback? onPressed) {
    return XlDialogAction(
      label: label,
      onPressed: onPressed,
      isDefault: true,
    );
  }

  /// Convenience: destructive action.
  factory XlDialogAction.destruct(String label, VoidCallback? onPressed) {
    return XlDialogAction(
      label: label,
      onPressed: onPressed,
      isDestructive: true,
    );
  }
}

/// Show a simple confirmation dialog.
Future<bool?> showXlConfirmDialog({
  required BuildContext context,
  required String title,
  required String message,
  String confirmLabel = '确认',
  String cancelLabel = '取消',
  bool isDestructive = false,
}) {
  return XlDialog.show<bool>(
    context: context,
    title: title,
    message: message,
    actions: [
      XlDialogAction.cancel(context, label: cancelLabel),
      isDestructive
          ? XlDialogAction.destruct(
              confirmLabel, () => Navigator.of(context).pop(true))
          : XlDialogAction.confirm(
              confirmLabel, () => Navigator.of(context).pop(true)),
    ],
  );
}
