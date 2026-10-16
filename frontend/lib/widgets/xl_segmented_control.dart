/// Apple-style segmented control for XiaoLing.
///
/// Implements §5.9 of APPLE_DESIGN_SPEC.md:
/// - Pill-shaped container with glass background
/// - Animated selection indicator (sliding pill)
/// - 28pt height, 12pt horizontal padding per segment
/// - Smooth animation between segments
library;

import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../theme/motion.dart';

class XlSegmentedControl extends StatelessWidget {
  final List<String> segments;
  final int selectedIndex;
  final ValueChanged<int> onSegmentChanged;
  final double height;

  const XlSegmentedControl({
    super.key,
    required this.segments,
    required this.selectedIndex,
    required this.onSegmentChanged,
    this.height = 28,
  });

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);

    return Container(
      height: height,
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: p.edge, width: 1),
      ),
      // Overlay the segment buttons
      // 说明：这里原先重复写了两遍滑块的 AnimatedAlign ——
      // 一次作为 Container 的 child、一次又在下面的 Stack 里，
      // 于是同一个 Container 出现两个 `child:` 具名参数（编译错误
      // duplicate_named_argument）。滑块本身已由 Stack 内那份承担，
      // 故删除外层这份重复实现。
      child: Stack(
        children: [
          // Sliding indicator (rendered above via the AnimatedAlign)
          AnimatedAlign(
            duration: XlDuration.fast,
            curve: XlCurve.easeOut,
            alignment: Alignment(
              segments.length <= 1
                  ? 0
                  : (selectedIndex / (segments.length - 1) * 2 - 1),
              0,
            ),
            child: Container(
              height: height - 4,
              width: (MediaQuery.of(context).size.width / segments.length)
                  .clamp(60.0, 200.0),
              decoration: BoxDecoration(
                gradient: p.btnFace,
                borderRadius: BorderRadius.circular(XlRadius.pill),
                boxShadow: p.raisedXxs,
              ),
            ),
          ),
          // Segment buttons
          Row(
            children: List.generate(segments.length, (index) {
              final selected = index == selectedIndex;
              return Expanded(
                child: GestureDetector(
                  onTap: () => onSegmentChanged(index),
                  behavior: HitTestBehavior.opaque,
                  child: Container(
                    height: height,
                    alignment: Alignment.center,
                    child: Text(
                      segments[index],
                      style: TextStyle(
                        fontSize: XlFont.caption,
                        fontWeight:
                            selected ? FontWeight.w700 : FontWeight.w500,
                        color: selected ? p.btnInk : p.text2,
                      ),
                    ),
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}

/// Simpler segmented control with fixed-width segments.
class XlSegmentedControlFixed extends StatelessWidget {
  final List<String> segments;
  final int selectedIndex;
  final ValueChanged<int> onSegmentChanged;
  final double segmentWidth;
  final double height;

  const XlSegmentedControlFixed({
    super.key,
    required this.segments,
    required this.selectedIndex,
    required this.onSegmentChanged,
    this.segmentWidth = 80,
    this.height = 28,
  });

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final totalWidth = segmentWidth * segments.length;

    return SizedBox(
      width: totalWidth,
      height: height,
      child: Stack(
        children: [
          // Background
          Container(
            decoration: BoxDecoration(
              color: p.surfaceLo,
              borderRadius: BorderRadius.circular(XlRadius.pill),
              border: Border.all(color: p.edge, width: 1),
            ),
          ),
          // Animated selection indicator
          AnimatedPositioned(
            duration: XlDuration.fast,
            curve: XlCurve.easeOut,
            left: selectedIndex * segmentWidth + 2,
            top: 2,
            bottom: 2,
            width: segmentWidth - 4,
            child: Container(
              decoration: BoxDecoration(
                gradient: p.btnFace,
                borderRadius: BorderRadius.circular(XlRadius.pill),
                boxShadow: p.raisedXxs,
              ),
            ),
          ),
          // Segment buttons
          Row(
            children: List.generate(segments.length, (index) {
              final selected = index == selectedIndex;
              return SizedBox(
                width: segmentWidth,
                height: height,
                child: GestureDetector(
                  onTap: () => onSegmentChanged(index),
                  behavior: HitTestBehavior.opaque,
                  child: Container(
                    alignment: Alignment.center,
                    child: Text(
                      segments[index],
                      style: TextStyle(
                        fontSize: XlFont.caption,
                        fontWeight:
                            selected ? FontWeight.w700 : FontWeight.w500,
                        color: selected ? p.btnInk : p.text2,
                      ),
                    ),
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}
