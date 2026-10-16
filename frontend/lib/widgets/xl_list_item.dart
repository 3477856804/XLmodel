/// Apple-style list item for XiaoLing.
///
/// Implements §5.6 of APPLE_DESIGN_SPEC.md:
/// - Leading icon + title + subtitle + trailing widget
/// - 44pt minimum height (touch target)
/// - Hover/tap highlight with pink tint
/// - Separator line (inset from leading edge)
/// - Glass morphism optional background
library;

import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../theme/motion.dart';

class XlListItem extends StatefulWidget {
  final Widget? leading;
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool selected;
  final bool showSeparator;
  final double separatorInset;
  final EdgeInsetsGeometry? contentPadding;

  const XlListItem({
    super.key,
    this.leading,
    required this.title,
    this.subtitle,
    this.trailing,
    this.onTap,
    this.selected = false,
    this.showSeparator = true,
    this.separatorInset = 56,
    this.contentPadding,
  });

  @override
  State<XlListItem> createState() => _XlListItemState();
}

class _XlListItemState extends State<XlListItem> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final isDesktop =
        MediaQuery.of(context).size.width >= XlBreakpoint.desktopSm;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: widget.onTap,
            onHover: isDesktop
                ? (hovering) => setState(() => _isHovered = hovering)
                : null,
            borderRadius: BorderRadius.circular(XlRadius.sm),
            splashColor: p.pink.withOpacity(0.08),
            highlightColor: p.pink.withOpacity(0.04),
            child: AnimatedContainer(
              duration: XlDuration.fast,
              curve: XlCurve.easeOut,
              constraints: const BoxConstraints(minHeight: 44),
              padding: widget.contentPadding ??
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: widget.selected
                    ? p.pink.withOpacity(p.isDark ? 0.12 : 0.08)
                    : _isHovered
                        ? p.pink.withOpacity(0.04)
                        : Colors.transparent,
                borderRadius: BorderRadius.circular(XlRadius.sm),
              ),
              child: Row(
                children: [
                  if (widget.leading != null) ...[
                    widget.leading!,
                    const SizedBox(width: 12),
                  ],
                  Expanded(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.title,
                          style: TextStyle(
                            fontSize: XlFont.body,
                            fontWeight: widget.selected
                                ? FontWeight.w600
                                : FontWeight.w400,
                            color: widget.selected ? p.pink : p.text1,
                          ),
                        ),
                        if (widget.subtitle != null) ...[
                          const SizedBox(height: 2),
                          Text(
                            widget.subtitle!,
                            style: TextStyle(
                              fontSize: XlFont.caption,
                              color: p.text3,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  if (widget.trailing != null) ...[
                    const SizedBox(width: 8),
                    widget.trailing!,
                  ],
                ],
              ),
            ),
          ),
        ),
        if (widget.showSeparator)
          Padding(
            padding: EdgeInsets.only(left: widget.separatorInset),
            child: Container(
              height: 0.5,
              color: p.divider,
            ),
          ),
      ],
    );
  }
}

/// Section header for list groups.
class XlListSectionHeader extends StatelessWidget {
  final String title;
  final EdgeInsetsGeometry? padding;

  const XlListSectionHeader({
    super.key,
    required this.title,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Padding(
      padding: padding ?? const EdgeInsets.fromLTRB(16, 24, 16, 8),
      child: Text(
        title.toUpperCase(),
        style: TextStyle(
          fontSize: XlFont.label,
          fontWeight: FontWeight.w700,
          color: p.text3,
          letterSpacing: XlLetterSpacing.wider,
        ),
      ),
    );
  }
}
