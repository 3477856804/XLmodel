/// Loss chart widget for training visualization.
///
/// Implements §5.10 of APPLE_DESIGN_SPEC.md:
/// - Custom painter for loss curve visualization
/// - Support for training loss points and evaluation loss points
/// - Hover/tooltip interaction (desktop)
/// - Reduce-motion support (no animation)
/// - Opaque container (content layer, NOT glass)
///
/// API:
/// ```dart
/// XlLossChart(
///   points: [0.5, 0.4, 0.35, 0.3, ...], // training loss
///   evalPoints: [null, null, 0.45, null, null, 0.38, ...], // eval loss (sparse)
///   labelBuilder: (index) => 'Step ${index + 1}',
///   height: 200,
/// )
/// ```
library;

import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/theme.dart';

class XlLossChart extends StatefulWidget {
  /// Training loss points (dense, one per step).
  final List<double> points;

  /// Evaluation loss points (sparse, null where no eval occurred).
  final List<double?> evalPoints;

  /// Builder for point labels (shown in tooltip).
  final String Function(int index)? labelBuilder;

  /// Chart height.
  final double height;

  /// Accent color for training loss line.
  final Color? lineColor;

  /// Accent color for eval loss line.
  final Color? evalLineColor;

  /// Whether to animate on data change.
  final bool animate;

  const XlLossChart({
    super.key,
    required this.points,
    this.evalPoints = const [],
    this.labelBuilder,
    this.height = 200,
    this.lineColor,
    this.evalLineColor,
    this.animate = true,
  });

  @override
  State<XlLossChart> createState() => _XlLossChartState();
}

class _XlLossChartState extends State<XlLossChart>
    with SingleTickerProviderStateMixin {
  late AnimationController _animCtrl;
  late Animation<double> _anim;
  int? _hoveredIndex;

  @override
  void initState() {
    super.initState();
    _animCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _anim = CurvedAnimation(
      parent: _animCtrl,
      curve: XlCurve.easeOut,
    );
    if (widget.animate) {
      _animCtrl.forward();
    } else {
      _animCtrl.value = 1.0;
    }
  }

  @override
  void didUpdateWidget(XlLossChart oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.points != oldWidget.points ||
        widget.evalPoints != oldWidget.evalPoints) {
      if (widget.animate) {
        _animCtrl.forward(from: 0.0);
      }
    }
  }

  @override
  void dispose() {
    _animCtrl.dispose();
    super.dispose();
  }

  void _onHover(int? index) {
    setState(() => _hoveredIndex = index);
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final isDark = p.isDark;
    final reduceMotion = MediaQuery.of(context).disableAnimations;

    // Resolve colors
    final lineColor = widget.lineColor ?? p.pink;
    final evalLineColor = widget.evalLineColor ?? p.gold;

    // Chart container (opaque, NOT glass — content layer)
    return Container(
      height: widget.height,
      decoration: BoxDecoration(
        color: p.screen,
        borderRadius: BorderRadius.circular(XlRadius.md),
        border: Border.all(
          color: p.shDark.withOpacity(isDark ? 0.40 : 0.18),
          width: 1,
        ),
        boxShadow: p.sunkenDeep,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(XlRadius.md),
        child: AnimatedBuilder(
          animation: _anim,
          builder: (context, child) {
            return CustomPaint(
              painter: _LossChartPainter(
                points: widget.points,
                evalPoints: widget.evalPoints,
                lineColor: lineColor,
                evalLineColor: evalLineColor,
                gridColor: p.divider.withOpacity(0.5),
                progress: reduceMotion ? 1.0 : _anim.value,
                hoveredIndex: _hoveredIndex,
                isDark: isDark,
              ),
              child: child,
            );
          },
          child: MouseRegion(
            onHover: (event) {
              final box = context.findRenderObject() as RenderBox?;
              if (box == null) return;
              final n = widget.points.length;
              // 点数 < 2 时 (n-1) 为 0，旧的除法会算出 NaN/inf；空数据直接不命中。
              if (n < 2) {
                _onHover(n == 1 ? 0 : null);
                return;
              }
              final rect = _chartRect(box.size.width, box.size.height);
              final local = box.globalToLocal(event.position);
              if (local.dx < rect.left - 6 || local.dx > rect.right + 6) {
                _onHover(null);
                return;
              }
              final ratio = (local.dx - rect.left) / rect.width;
              _onHover((ratio * (n - 1)).round().clamp(0, n - 1));
            },
            onExit: (_) => _onHover(null),
            child: LayoutBuilder(
              builder: (context, c) => Stack(
                children: [
                  // Tooltip：位置按「绘图区比例」算并夹在画布内。
                  // 旧写法 `40 + (idx/(n-1) * (size.width-40)) - 40` 用了
                  // context.size!（可能为 null 直接崩），且没做越界夹取，
                  // 靠右侧的点会把气泡顶出屏幕。
                  if (_hoveredIndex != null &&
                      _hoveredIndex! < widget.points.length &&
                      widget.points.length > 1)
                    Positioned(
                      left: (_chartLeft(c.maxWidth) +
                              _hoveredIndex! /
                                  (widget.points.length - 1) *
                                  _chartWidth(c.maxWidth) -
                              64)
                          .clamp(4.0, math.max(4.0, c.maxWidth - 140)),
                      top: 4,
                      child: _Tooltip(
                        label: widget.labelBuilder?.call(_hoveredIndex!) ??
                            'Step ${_hoveredIndex! + 1}',
                        value: widget.points[_hoveredIndex!],
                        evalValue: _hoveredIndex! < widget.evalPoints.length
                            ? widget.evalPoints[_hoveredIndex!]
                            : null,
                        isDark: isDark,
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

/// 绘图区几何（左轴标签留白 + 上下留白）。painter 与 hover 命中测试共用，
/// 避免两处各写一份 padding 数字导致鼠标点和曲线错位。
const double _kLeftPad = 40, _kRightPad = 16, _kTopPad = 16, _kBottomPad = 32;

double _chartLeft(double width) => _kLeftPad;
double _chartWidth(double width) =>
    math.max(1.0, width - _kLeftPad - _kRightPad);
double _chartHeight(double height) =>
    math.max(1.0, height - _kTopPad - _kBottomPad);
Rect _chartRect(double width, double height) => Rect.fromLTRB(
      _kLeftPad,
      _kTopPad,
      _kLeftPad + _chartWidth(width),
      _kTopPad + _chartHeight(height),
    );

class _Tooltip extends StatelessWidget {
  final String label;
  final double value;
  final double? evalValue;
  final bool isDark;

  const _Tooltip({
    required this.label,
    required this.value,
    this.evalValue,
    required this.isDark,
  });

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: isDark ? p.surfaceHi : p.surface,
        borderRadius: BorderRadius.circular(XlRadius.sm),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedXs,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: p.text2,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            'Loss: ${value.toStringAsFixed(4)}',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: p.text1,
            ),
          ),
          if (evalValue != null) ...[
            const SizedBox(height: 1),
            Text(
              'Eval: ${evalValue!.toStringAsFixed(4)}',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: p.gold,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _LossChartPainter extends CustomPainter {
  final List<double> points;
  final List<double?> evalPoints;
  final Color lineColor;
  final Color evalLineColor;
  final Color gridColor;
  final double progress;
  final int? hoveredIndex;
  final bool isDark;

  _LossChartPainter({
    required this.points,
    required this.evalPoints,
    required this.lineColor,
    required this.evalLineColor,
    required this.gridColor,
    required this.progress,
    this.hoveredIndex,
    required this.isDark,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty) return;

    // 绘图区几何与 hover 命中测试共用同一套常量，避免两边各写一份 padding
    // 造成鼠标点和曲线错位。
    final chartRect = _chartRect(size.width, size.height);

    // progress 之前只是传进来没用过，动画等于白跑：现在按 progress 截断点数，
    // 让曲线是真的「长出来」，而不是整条线瞬间出现。
    final shown = progress >= 0.999
        ? points.length
        : math.max(
            points.length <= 1 ? 1 : 2, (points.length * progress).ceil());
    final visible = points.sublist(0, shown.clamp(1, points.length));

    // Find min/max for Y axis（用全量数据定标，避免动画过程中纵轴跳动）
    final allValues = [...points, ...evalPoints.whereType<double>()];
    if (allValues.isEmpty) return;
    final minValue = allValues.reduce(math.min);
    final maxValue = allValues.reduce(math.max);
    final valueRange = maxValue - minValue;
    // 单点或全同值时 range=0，除零会让所有 y 变成 NaN；给个保底区间。
    final half =
        valueRange > 0 ? valueRange * 0.1 : (maxValue.abs() * 0.05 + 0.05);
    final yMin = minValue - half;
    final yMax = maxValue + half;

    // Draw grid lines
    _drawGrid(canvas, chartRect, yMin, yMax);

    // Draw training loss line（span 固定为总点数，动画时 x 轴不缩放）
    _drawLine(canvas, chartRect, visible, lineColor, yMin, yMax,
        isDashed: false, span: points.length);

    // Draw eval loss points at their real step positions.
    // 不能用 whereType 压缩后再画——那会把稀疏的 eval 点连成一条连续线，
    // x 轴就和训练 step 对不上了。这里按下标定位，只在非空点之间连线。
    if (evalPoints.any((e) => e != null)) {
      _drawSparseLine(canvas, chartRect, evalPoints, evalLineColor, yMin, yMax,
          math.max(points.length, evalPoints.length));
    }

    // Draw hover indicator
    if (hoveredIndex != null && hoveredIndex! < points.length) {
      _drawHoverIndicator(
          canvas, chartRect, hoveredIndex!, points[hoveredIndex!], yMin, yMax);
    }
  }

  void _drawGrid(Canvas canvas, Rect rect, double yMin, double yMax) {
    final paint = Paint()
      ..color = gridColor
      ..strokeWidth = 1;

    // Horizontal grid lines (5 lines)
    for (int i = 0; i <= 4; i++) {
      final y = rect.top + (rect.height * i / 4);
      canvas.drawLine(Offset(rect.left, y), Offset(rect.right, y), paint);

      // Y axis labels
      final value = yMax - (yMax - yMin) * i / 4;
      final textPainter = TextPainter(
        text: TextSpan(
          text: value.toStringAsFixed(2),
          style: TextStyle(
            fontSize: 10,
            color: gridColor,
            fontWeight: FontWeight.w500,
          ),
        ),
        textDirection: TextDirection.ltr,
      );
      textPainter.layout();
      textPainter.paint(
        canvas,
        Offset(rect.left - textPainter.width - 8, y - textPainter.height / 2),
      );
    }
  }

  /// x 方向按 [span]（总点数）定位，values 只是其中已显示的前缀——
  /// 这样动画/增量采集时曲线不会左右伸缩跳动。
  void _drawLine(
    Canvas canvas,
    Rect rect,
    List<double> values,
    Color color,
    double yMin,
    double yMax, {
    required bool isDashed,
    int? span,
  }) {
    if (values.isEmpty) return;

    final paint = Paint()
      ..color = color
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final total = math.max(1, span ?? values.length);
    final path = Path();
    final stepX = rect.width / (total - 1).clamp(1, double.infinity);

    for (int i = 0; i < values.length; i++) {
      final x = rect.left + stepX * i;
      final normalizedY = (values[i] - yMin) / (yMax - yMin);
      final y = rect.bottom - normalizedY * rect.height;

      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }

    if (isDashed) {
      final dashedPath = Path();
      final metrics = path.computeMetrics();
      for (final metric in metrics) {
        var distance = 0.0;
        while (distance < metric.length) {
          final end = (distance + 6).clamp(0.0, metric.length);
          dashedPath.addPath(metric.extractPath(distance, end), Offset.zero);
          distance += 10; // 6 dash, 4 gap
        }
      }
      canvas.drawPath(dashedPath, paint);
    } else {
      canvas.drawPath(path, paint);
    }

    // Draw area fill（收口到最后一个已画点的 x，不是 rect.right —
    // 否则动画进行中会出现一条从曲线末端直接拉到右边界的大三角）
    if (!isDashed && values.length >= 2) {
      final lastX = rect.left + stepX * (values.length - 1);
      final fillPath = Path.from(path)
        ..lineTo(lastX, rect.bottom)
        ..lineTo(rect.left, rect.bottom)
        ..close();

      final fillPaint = Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            color.withOpacity(0.15),
            color.withOpacity(0.0),
          ],
        ).createShader(rect);

      canvas.drawPath(fillPath, fillPaint);
    }
  }

  /// 稀疏线：values[i] 对应第 i 个 step，null 表示该步没有验证值。
  /// 只在相邻的非空点之间连线，并给每个非空点画一个小圆点。
  void _drawSparseLine(
    Canvas canvas,
    Rect rect,
    List<double?> values,
    Color color,
    double yMin,
    double yMax,
    int span,
  ) {
    final total = math.max(1, span);
    final stepX = rect.width / (total - 1).clamp(1, double.infinity);
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    double? lastX, lastY;
    for (int i = 0; i < values.length; i++) {
      final v = values[i];
      if (v == null) continue;
      final x = rect.left + stepX * i;
      final y = rect.bottom - ((v - yMin) / (yMax - yMin)) * rect.height;
      canvas.drawCircle(Offset(x, y), 3, Paint()..color = color);
      if (lastX != null && lastY != null) {
        final seg = Path()
          ..moveTo(lastX, lastY)
          ..lineTo(x, y);
        final dashed = Path();
        var d = 0.0;
        for (final m in seg.computeMetrics()) {
          while (d < m.length) {
            dashed.addPath(
                m.extractPath(d, (d + 6).clamp(0.0, m.length)), Offset.zero);
            d += 10;
          }
        }
        canvas.drawPath(dashed, paint);
      }
      lastX = x;
      lastY = y;
    }
  }

  void _drawHoverIndicator(
    Canvas canvas,
    Rect rect,
    int index,
    double value,
    double yMin,
    double yMax,
  ) {
    final stepX = rect.width / (points.length - 1).clamp(1, double.infinity);
    final x = rect.left + stepX * index;
    final normalizedY = (value - yMin) / (yMax - yMin);
    final y = rect.bottom - normalizedY * rect.height;

    // Vertical line
    final linePaint = Paint()
      ..color = lineColor.withOpacity(0.3)
      ..strokeWidth = 1;
    canvas.drawLine(Offset(x, rect.top), Offset(x, rect.bottom), linePaint);

    // Dot
    final dotPaint = Paint()
      ..color = lineColor
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(x, y), 5, dotPaint);

    final borderPaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    canvas.drawCircle(Offset(x, y), 5, borderPaint);
  }

  @override
  bool shouldRepaint(_LossChartPainter oldDelegate) {
    return oldDelegate.points != points ||
        oldDelegate.evalPoints != evalPoints ||
        oldDelegate.progress != progress ||
        oldDelegate.hoveredIndex != hoveredIndex;
  }
}
