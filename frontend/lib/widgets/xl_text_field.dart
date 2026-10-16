/// Apple-style input field for XiaoLing.
///
/// Implements §5.5 of APPLE_DESIGN_SPEC.md:
/// - Glass morphism container with BackdropFilter
/// - 36pt height, 12pt horizontal padding
/// - Focus ring animation (pink glow)
/// - Error state with red border
/// - Disabled state with reduced opacity
/// - Accessible: 44pt touch target, semantic labels
library;

import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../theme/tokens.dart';
import '../theme/glass.dart';

class XlTextField extends StatefulWidget {
  final TextEditingController? controller;
  final FocusNode? focusNode;
  final String? hintText;
  final String? labelText;
  final String? errorText;
  final bool obscureText;
  final bool enabled;
  final int maxLines;
  final int? maxLength;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final Widget? prefixIcon;
  final Widget? suffixIcon;
  final EdgeInsetsGeometry? contentPadding;
  final bool useGlass;

  const XlTextField({
    super.key,
    this.controller,
    this.focusNode,
    this.hintText,
    this.labelText,
    this.errorText,
    this.obscureText = false,
    this.enabled = true,
    this.maxLines = 1,
    this.maxLength,
    this.keyboardType,
    this.textInputAction,
    this.onChanged,
    this.onSubmitted,
    this.prefixIcon,
    this.suffixIcon,
    this.contentPadding,
    this.useGlass = true,
  });

  @override
  State<XlTextField> createState() => _XlTextFieldState();
}

class _XlTextFieldState extends State<XlTextField> {
  late FocusNode _focusNode;
  bool _isFocused = false;

  @override
  void initState() {
    super.initState();
    _focusNode = widget.focusNode ?? FocusNode();
    _focusNode.addListener(_onFocusChange);
  }

  @override
  void dispose() {
    if (widget.focusNode == null) {
      _focusNode.dispose();
    }
    super.dispose();
  }

  void _onFocusChange() {
    setState(() {
      _isFocused = _focusNode.hasFocus;
    });
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final hasError = widget.errorText != null;

    // Determine border color based on state
    Color borderColor;
    if (hasError) {
      borderColor = p.red;
    } else if (_isFocused) {
      borderColor = p.pink;
    } else {
      borderColor = p.edge;
    }

    // Build the input decoration
    final decoration = InputDecoration(
      hintText: widget.hintText,
      labelText: widget.labelText,
      errorText: widget.errorText,
      hintStyle: TextStyle(color: p.text3, fontSize: XlFont.body),
      labelStyle: TextStyle(
        color: _isFocused ? p.pink : p.text2,
        fontSize: XlFont.body,
        fontWeight: _isFocused ? FontWeight.w600 : FontWeight.w400,
      ),
      errorStyle: TextStyle(color: p.red, fontSize: XlFont.caption),
      prefixIcon: widget.prefixIcon,
      suffixIcon: widget.suffixIcon,
      contentPadding: widget.contentPadding ??
          const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      filled: false,
      border: InputBorder.none,
      enabledBorder: InputBorder.none,
      focusedBorder: InputBorder.none,
      errorBorder: InputBorder.none,
      focusedErrorBorder: InputBorder.none,
      isDense: true,
    );

    // Build the container (glass or opaque)
    Widget container;
    if (widget.useGlass && !hasError) {
      // Glass morphism container
      container = GlassSurface(
        material: XlGlassMaterial.regular,
        // GlassSurface.borderRadius 是 double，不能传 BorderRadius。
        borderRadius: XlRadius.md,
        border: Border.all(
          color: borderColor,
          width: _isFocused ? 1.5 : 1.0,
        ),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 36),
          child: TextField(
            controller: widget.controller,
            focusNode: _focusNode,
            obscureText: widget.obscureText,
            enabled: widget.enabled,
            maxLines: widget.maxLines,
            maxLength: widget.maxLength,
            keyboardType: widget.keyboardType,
            textInputAction: widget.textInputAction,
            onChanged: widget.onChanged,
            onSubmitted: widget.onSubmitted,
            decoration: decoration,
            style: TextStyle(
              color: widget.enabled ? p.text1 : p.text3,
              fontSize: XlFont.body,
            ),
            cursorColor: p.pink,
          ),
        ),
      );
    } else {
      // Opaque container (for error state or when glass disabled)
      container = Container(
        constraints: const BoxConstraints(minHeight: 36),
        decoration: BoxDecoration(
          color: widget.enabled ? p.surface : p.surfaceLo,
          borderRadius: BorderRadius.circular(XlRadius.md),
          border: Border.all(
            color: borderColor,
            width: _isFocused ? 1.5 : 1.0,
          ),
        ),
        child: TextField(
          controller: widget.controller,
          focusNode: _focusNode,
          obscureText: widget.obscureText,
          enabled: widget.enabled,
          maxLines: widget.maxLines,
          maxLength: widget.maxLength,
          keyboardType: widget.keyboardType,
          textInputAction: widget.textInputAction,
          onChanged: widget.onChanged,
          onSubmitted: widget.onSubmitted,
          decoration: decoration,
          style: TextStyle(
            color: widget.enabled ? p.text1 : p.text3,
            fontSize: XlFont.body,
          ),
          cursorColor: hasError ? p.red : p.pink,
        ),
      );
    }

    // Wrap in focus glow effect
    if (_isFocused && !hasError) {
      container = Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(XlRadius.md),
          boxShadow: [
            BoxShadow(
              color: p.pink.withOpacity(0.3),
              blurRadius: 8,
              spreadRadius: 0,
            ),
          ],
        ),
        child: container,
      );
    }

    // Ensure 44pt touch target (§6.2)
    return Semantics(
      textField: true,
      label: widget.labelText ?? widget.hintText ?? '输入框',
      enabled: widget.enabled,
      child: SizedBox(
        height: widget.maxLines == 1 ? 44 : null,
        child: container,
      ),
    );
  }
}

/// Convenience constructor for search fields.
class XlSearchField extends StatelessWidget {
  final TextEditingController? controller;
  final FocusNode? focusNode;
  final String? hintText;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;

  const XlSearchField({
    super.key,
    this.controller,
    this.focusNode,
    this.hintText = '搜索...',
    this.onChanged,
    this.onSubmitted,
  });

  @override
  Widget build(BuildContext context) {
    return XlTextField(
      controller: controller,
      focusNode: focusNode,
      hintText: hintText,
      onChanged: onChanged,
      onSubmitted: onSubmitted,
      prefixIcon: Icon(Icons.search_rounded,
          size: 18, color: XlPalette.of(context).text3),
      textInputAction: TextInputAction.search,
    );
  }
}
