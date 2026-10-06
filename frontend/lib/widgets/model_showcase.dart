import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import '../theme/theme.dart';

class ModelShowcase extends StatefulWidget {
  final String? modelPath;
  final double width;
  final double height;
  final String characterName;
  final String? subtitle;
  final bool showControls;
  final bool autoRotateDefault;
  final bool circularFrame;
  final VoidCallback? onRefresh;
  const ModelShowcase({
    super.key,
    this.modelPath,
    this.width = 300,
    this.height = 300,
    this.characterName = '小凌',
    this.subtitle,
    this.showControls = true,
    this.autoRotateDefault = true,
    this.circularFrame = true,
    this.onRefresh,
  });

  @override
  State<ModelShowcase> createState() => _ModelShowcaseState();
}

class _ModelShowcaseState extends State<ModelShowcase> with TickerProviderStateMixin {
  String? _currentPath;
  bool _hasError = false;
  bool _loading = true;
  bool _autoRotate = true;
  bool _cameraControls = true;
  bool _showSettings = false;
  double _exposure = 1.15;
  double _shadow = 0.55;
  double _zoom = 1.0;
  int _cameraPreset = 0;
  late AnimationController _pulseCtrl;
  late AnimationController _ringCtrl;
  late AnimationController _loadCtrl;
  late AnimationController _fadeCtrl;
  late Animation<double> _fadeAnim;
  Timer? _loadTimer;

  static const _cameraPresets = <String>['正面', '左侧', '右侧', '背面', '俯视'];

  @override
  void initState() {
    super.initState();
    _currentPath = widget.modelPath;
    _autoRotate = widget.autoRotateDefault;
    _pulseCtrl = AnimationController(duration: const Duration(seconds: 4), vsync: this)..repeat();
    _ringCtrl = AnimationController(duration: const Duration(seconds: 12), vsync: this)..repeat();
    _loadCtrl = AnimationController(duration: const Duration(milliseconds: 1400), vsync: this);
    _fadeCtrl = AnimationController(duration: const Duration(milliseconds: 600), vsync: this);
    _fadeAnim = CurvedAnimation(parent: _fadeCtrl, curve: XlCurve.easeOut);
    _fadeCtrl.forward();
    _startLoading();
  }

  @override
  void didUpdateWidget(ModelShowcase old) {
    super.didUpdateWidget(old);
    if (widget.modelPath != old.modelPath) {
      setState(() {
        _currentPath = widget.modelPath;
        _hasError = false;
        _loading = true;
      });
      _startLoading();
    }
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    _ringCtrl.dispose();
    _loadCtrl.dispose();
    _fadeCtrl.dispose();
    _loadTimer?.cancel();
    super.dispose();
  }

  void _startLoading() {
    _loadTimer?.cancel();
    _loadCtrl.forward(from: 0);
    _loadTimer = Timer(const Duration(milliseconds: 1400), () {
      if (mounted && _loading) setState(() => _loading = false);
    });
  }

  void _retry() {
    setState(() {
      _hasError = false;
      _loading = true;
    });
    _startLoading();
    widget.onRefresh?.call();
  }

  Color _presetColor(XlPalette p, int i) {
    final colors = [p.pink, p.gold, p.violet, p.green, p.blue];
    return colors[i % colors.length];
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return AnimatedBuilder(
      animation: _fadeAnim,
      builder: (_, child) => Opacity(
        opacity: _fadeAnim.value,
        child: Transform.scale(
          scale: 0.96 + _fadeAnim.value * 0.04,
          child: child,
        ),
      ),
      child: SizedBox(
        width: widget.width,
        height: widget.height + (widget.showControls ? 96 : 0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: widget.width,
              height: widget.height,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  _ambientGlow(p),
                  _outerRing(p),
                  _frame(p),
                  _content(p),
                  _topBadge(p),
                  if (_loading) _loadingOverlay(p),
                  if (_hasError) _errorOverlay(p),
                ],
              ),
            ),
            if (widget.showControls) ...[
              const SizedBox(height: 14),
              _infoStrip(p),
              const SizedBox(height: 10),
              _controlBar(p),
              if (_showSettings) ...[
                const SizedBox(height: 10),
                _settingsPanel(p),
              ],
            ],
          ],
        ),
      ),
    );
  }

  Widget _ambientGlow(XlPalette p) {
    return AnimatedBuilder(
      animation: _pulseCtrl,
      builder: (_, __) {
        final t = _pulseCtrl.value;
        return IgnorePointer(
          child: Stack(
            alignment: Alignment.center,
            children: [
              Container(
                width: widget.width + 30 + t * 22,
                height: widget.width + 30 + t * 22,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: p.pink.withOpacity((1 - t) * 0.14),
                ),
              ),
              Container(
                width: widget.width + 12 + t * 12,
                height: widget.width + 12 + t * 12,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: p.gold.withOpacity((1 - t) * 0.10),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _outerRing(XlPalette p) {
    if (!widget.circularFrame) return const SizedBox.shrink();
    return AnimatedBuilder(
      animation: _ringCtrl,
      builder: (_, __) {
        return IgnorePointer(
          child: Transform.rotate(
            angle: _ringCtrl.value * 2 * math.pi,
            child: CustomPaint(
              size: Size(widget.width + 14, widget.width + 14),
              painter: _RingPainter(
                colors: [
                  p.pink.withOpacity(0.5),
                  p.gold.withOpacity(0.35),
                  p.violet.withOpacity(0.4),
                  p.pink.withOpacity(0.5),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _frame(XlPalette p) {
    return Container(
      width: widget.width,
      height: widget.width,
      decoration: BoxDecoration(
        shape: widget.circularFrame ? BoxShape.circle : BoxShape.rectangle,
        borderRadius: widget.circularFrame ? null : BorderRadius.circular(XlRadius.xxl),
        gradient: p.face,
        border: Border.all(color: p.edge, width: 1),
        boxShadow: [
          ...p.raised,
          BoxShadow(color: p.pink.withOpacity(0.22), blurRadius: 30, spreadRadius: -8),
        ],
      ),
    );
  }

  Widget _content(XlPalette p) {
    final innerSize = widget.width - 24;
    return ClipOval(
      child: Container(
        width: innerSize,
        height: innerSize,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(
            colors: [p.screen, p.surfaceLo, p.surface],
            stops: const [0.0, 0.62, 1.0],
          ),
        ),
        child: Stack(
          alignment: Alignment.center,
          children: [
            _floorShadow(p),
            if (_currentPath != null && !_hasError)
              _modelViewer()
            else
              _placeholder(p),
          ],
        ),
      ),
    );
  }

  Widget _floorShadow(XlPalette p) {
    return Positioned(
      bottom: widget.width * 0.12,
      child: AnimatedBuilder(
        animation: _pulseCtrl,
        builder: (_, __) {
          final t = _pulseCtrl.value;
          return Container(
            width: widget.width * 0.5,
            height: widget.width * 0.08,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(99),
              gradient: RadialGradient(
                colors: [
                  p.pink.withOpacity(0.28 * (0.8 + t * 0.2)),
                  p.pink.withOpacity(0),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _modelViewer() {
    return SizedBox(
      width: widget.width,
      height: widget.width,
      child: Transform.scale(
        scale: _zoom,
        child: ModelViewer(
          src: 'file://$_currentPath',
          alt: '${widget.characterName} 3D 模型',
          ar: false,
          autoRotate: _autoRotate,
          autoRotateDelay: 0,
          rotationPerSecond: '24deg',
          cameraControls: _cameraControls,
          disableZoom: false,
          disableTap: false,
          interactionPrompt: InteractionPrompt.none,
          exposure: _exposure,
          shadowIntensity: _shadow,
          shadowSoftness: 0.9,
          environmentImage: EnvironmentImage.neutral,
          backgroundColor: Colors.transparent,
          onWebViewCreated: (_) {
            if (mounted) setState(() => _loading = false);
          },
          onError: (e) {
            if (mounted) {
              setState(() {
                _hasError = true;
                _loading = false;
              });
            }
          },
        ),
      ),
    );
  }

  Widget _placeholder(XlPalette p) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        AnimatedBuilder(
          animation: _pulseCtrl,
          builder: (_, __) {
            final t = _pulseCtrl.value;
            return Container(
              width: widget.width * 0.32,
              height: widget.width * 0.32,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: p.gradBrand,
                border: Border.all(
                  color: Colors.white.withOpacity(p.dark ? 0.28 + t * 0.14 : 0.42 + t * 0.14),
                  width: 2,
                ),
                boxShadow: [
                  BoxShadow(
                    color: p.pink.withOpacity(0.35 + t * 0.15),
                    blurRadius: 30 + t * 10,
                    spreadRadius: -6,
                  ),
                ],
              ),
              child: Icon(
                Icons.face_6_rounded,
                size: widget.width * 0.14,
                color: p.btnInk,
              ),
            );
          },
        ),
        const SizedBox(height: 14),
        Text(widget.characterName,
            style: TextStyle(
              fontSize: XlFont.h5,
              fontWeight: FontWeight.w800,
              color: p.text1,
              letterSpacing: XlLetterSpacing.normal,
            )),
        const SizedBox(height: 4),
        Text(widget.subtitle ?? '还没有加载模型',
            style: TextStyle(
              fontSize: XlFont.label,
              color: p.text3,
              fontWeight: FontWeight.w600,
              letterSpacing: XlLetterSpacing.wider,
            )),
      ],
    );
  }

  Widget _topBadge(XlPalette p) {
    final status = _hasError
        ? '加载失败'
        : _loading
            ? '加载中'
            : (_autoRotate ? '自动旋转' : '手动模式');
    final color = _hasError
        ? p.red
        : _loading
            ? p.gold
            : (_autoRotate ? p.green : p.pink);
    return Positioned(
      top: 12,
      child: AnimatedOpacity(
        duration: XlDuration.normal,
        opacity: _loading ? 0 : 1,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: p.surface.withOpacity(p.dark ? 0.85 : 0.9),
            borderRadius: BorderRadius.circular(XlRadius.pill),
            border: Border.all(color: color.withOpacity(0.32), width: 1),
            boxShadow: p.raisedXxs,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                  boxShadow: [BoxShadow(color: color.withOpacity(0.6), blurRadius: 6, spreadRadius: -1)],
                ),
              ),
              const SizedBox(width: 6),
              Text(status,
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w800,
                    color: color,
                    letterSpacing: XlLetterSpacing.ultra,
                  )),
            ],
          ),
        ),
      ),
    );
  }

  Widget _loadingOverlay(XlPalette p) {
    return Positioned.fill(
      child: ClipOval(
        child: Container(
          color: p.screen.withOpacity(p.dark ? 0.72 : 0.62),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: widget.width * 0.28,
                  height: widget.width * 0.28,
                  child: AnimatedBuilder(
                    animation: _loadCtrl,
                    builder: (_, __) {
                      return CustomPaint(
                        painter: _LoadRingPainter(
                          progress: _loadCtrl.value,
                          color: p.pink,
                          track: p.surfaceLo,
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 14),
                AnimatedBuilder(
                  animation: _loadCtrl,
                  builder: (_, __) {
                    final pct = (_loadCtrl.value * 100).toInt();
                    return Text('加载中 $pct%',
                        style: TextStyle(
                          fontSize: XlFont.captionSm,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.wider,
                          fontFeatures: const [FontFeature.tabularFigures()],
                        ));
                  },
                ),
                const SizedBox(height: 4),
                Text('正在准备 3D 角色',
                    style: TextStyle(
                      fontSize: XlFont.label,
                      fontWeight: FontWeight.w500,
                      color: p.text3,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _errorOverlay(XlPalette p) {
    return Positioned.fill(
      child: ClipOval(
        child: Container(
          color: p.screen.withOpacity(p.dark ? 0.85 : 0.78),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: widget.width * 0.22,
                  height: widget.width * 0.22,
                  decoration: BoxDecoration(
                    color: p.red.withOpacity(p.dark ? 0.14 : 0.10),
                    shape: BoxShape.circle,
                    border: Border.all(color: p.red.withOpacity(0.32), width: 1),
                  ),
                  child: Icon(
                    Icons.broken_image_outlined,
                    size: widget.width * 0.09,
                    color: p.red,
                  ),
                ),
                const SizedBox(height: 12),
                Text('模型加载失败',
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
                const SizedBox(height: 4),
                Text('检查模型路径是否正确',
                    style: TextStyle(
                      fontSize: XlFont.label,
                      fontWeight: FontWeight.w500,
                      color: p.text3,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
                const SizedBox(height: 14),
                GestureDetector(
                  onTap: _retry,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 9),
                    decoration: AppTheme.btn(context, r: XlRadius.pill),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.refresh_rounded, size: 13, color: p.btnInk),
                        const SizedBox(width: 6),
                        Text('重试',
                            style: TextStyle(
                              fontSize: XlFont.label,
                              fontWeight: FontWeight.w800,
                              color: p.btnInk,
                              letterSpacing: XlLetterSpacing.wider,
                            )),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _infoStrip(XlPalette p) {
    return Container(
      width: widget.width,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: AppTheme.neuXs(context, r: XlRadius.md),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              gradient: p.gradBrand,
              borderRadius: BorderRadius.circular(XlRadius.xs),
              border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.32 : 0.48), width: 1),
              boxShadow: p.raisedXxs,
            ),
            child: Center(
              child: Text(
                widget.characterName.isNotEmpty ? widget.characterName.characters.first : '凌',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  color: p.btnInk,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(widget.characterName,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                const SizedBox(height: 2),
                Text(widget.subtitle ?? '拖拽旋转 · 滚轮缩放',
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      fontWeight: FontWeight.w500,
                      color: p.text3,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ],
            ),
          ),
          _miniTag(p, '${(_zoom * 100).toInt()}%', p.violet),
        ],
      ),
    );
  }

  Widget _miniTag(XlPalette p, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(p.dark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: color.withOpacity(0.28), width: 1),
      ),
      child: Text(text,
          style: TextStyle(
            fontSize: XlFont.micro,
            fontWeight: FontWeight.w800,
            color: color,
            letterSpacing: XlLetterSpacing.wider,
            fontFeatures: const [FontFeature.tabularFigures()],
          )),
    );
  }

  Widget _controlBar(XlPalette p) {
    return Container(
      width: widget.width,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _controlBtn(p, _autoRotate ? Icons.pause_rounded : Icons.play_arrow_rounded,
              _autoRotate ? '暂停' : '旋转', p.pink, () => setState(() => _autoRotate = !_autoRotate)),
          _controlBtn(p, Icons.camera_alt_outlined, '视角', p.gold, _cycleCameraPreset),
          _controlBtn(p, Icons.center_focus_strong_rounded, '复位', p.violet, _resetView),
          _controlBtn(p, _cameraControls ? Icons.pan_tool_alt_rounded : Icons.pan_tool_rounded,
              _cameraControls ? '锁定' : '解锁', p.green, () => setState(() => _cameraControls = !_cameraControls)),
          _controlBtn(p, _showSettings ? Icons.tune_rounded : Icons.tune_outlined,
              '参数', p.blue, () => setState(() => _showSettings = !_showSettings)),
        ],
      ),
    );
  }

  Widget _controlBtn(XlPalette p, IconData icon, String label, Color color, VoidCallback onTap) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(XlRadius.md),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: color.withOpacity(p.dark ? 0.14 : 0.10),
                  borderRadius: BorderRadius.circular(XlRadius.sm),
                  border: Border.all(color: color.withOpacity(0.28), width: 1),
                  boxShadow: [BoxShadow(color: color.withOpacity(0.18), blurRadius: 10, spreadRadius: -3)],
                ),
                child: Icon(icon, size: 15, color: color),
              ),
              const SizedBox(height: 5),
              Text(label,
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w700,
                    color: p.text2,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
        ),
      ),
    );
  }

  Widget _settingsPanel(XlPalette p) {
    return Container(
      width: widget.width,
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neuXs(context, r: XlRadius.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.tune_rounded, size: 13, color: p.pink),
              const SizedBox(width: 6),
              Text('渲染参数',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
              const Spacer(),
              Text(_cameraPresets[_cameraPreset],
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w800,
                    color: p.gold,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
          const SizedBox(height: 12),
          _slider(p, '曝光', _exposure, p.pink, (v) => setState(() => _exposure = v)),
          const SizedBox(height: 10),
          _slider(p, '阴影', _shadow, p.violet, (v) => setState(() => _shadow = v)),
          const SizedBox(height: 10),
          _slider(p, '缩放', _zoom, p.gold, (v) => setState(() => _zoom = v), min: 0.5, max: 1.5),
        ],
      ),
    );
  }

  Widget _slider(XlPalette p, String label, double value, Color color, ValueChanged<double> onChanged, {double min = 0.5, double max = 1.5}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(label,
                style: TextStyle(
                  fontSize: XlFont.micro,
                  fontWeight: FontWeight.w700,
                  color: p.text2,
                  letterSpacing: XlLetterSpacing.wider,
                )),
            const Spacer(),
            Text(value.toStringAsFixed(2),
                style: TextStyle(
                  fontSize: XlFont.micro,
                  fontWeight: FontWeight.w800,
                  color: color,
                  letterSpacing: XlLetterSpacing.wider,
                  fontFeatures: const [FontFeature.tabularFigures()],
                )),
          ],
        ),
        const SizedBox(height: 6),
        LayoutBuilder(
          builder: (context, c) {
            return GestureDetector(
              onHorizontalDragUpdate: (d) {
                final w = c.maxWidth;
                final pos = d.localPosition.dx.clamp(0.0, w);
                final v = min + (pos / w) * (max - min);
                onChanged(v.clamp(min, max));
              },
              onTapDown: (d) {
                final w = c.maxWidth;
                final pos = d.localPosition.dx.clamp(0.0, w);
                final v = min + (pos / w) * (max - min);
                onChanged(v.clamp(min, max));
              },
              child: SizedBox(
                height: 18,
                child: Stack(
                  alignment: Alignment.centerLeft,
                  children: [
                    Container(
                      height: 6,
                      decoration: BoxDecoration(
                        color: p.surfaceLo,
                        borderRadius: BorderRadius.circular(99),
                        boxShadow: p.sunkenXxs,
                      ),
                    ),
                    FractionallySizedBox(
                      widthFactor: ((value - min) / (max - min)).clamp(0.0, 1.0),
                      child: Container(
                        height: 6,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(colors: [color.withOpacity(0.7), color]),
                          borderRadius: BorderRadius.circular(99),
                          boxShadow: [BoxShadow(color: color.withOpacity(0.35), blurRadius: 8, spreadRadius: -2)],
                        ),
                      ),
                    ),
                    Positioned(
                      left: ((value - min) / (max - min)).clamp(0.0, 1.0) * (c.maxWidth - 14),
                      child: Container(
                        width: 14,
                        height: 14,
                        decoration: BoxDecoration(
                          color: p.surfaceHi,
                          shape: BoxShape.circle,
                          border: Border.all(color: color.withOpacity(0.5), width: 1.2),
                          boxShadow: p.raisedXxs,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  void _cycleCameraPreset() {
    setState(() {
      _cameraPreset = (_cameraPreset + 1) % _cameraPresets.length;
      _autoRotate = false;
    });
    HapticFeedback.selectionClick();
  }

  void _resetView() {
    setState(() {
      _cameraPreset = 0;
      _zoom = 1.0;
      _exposure = 1.15;
      _shadow = 0.55;
      _autoRotate = widget.autoRotateDefault;
      _cameraControls = true;
      _hasError = false;
      _loading = true;
    });
    _startLoading();
    HapticFeedback.lightImpact();
  }
}

class _RingPainter extends CustomPainter {
  final List<Color> colors;
  _RingPainter({required this.colors});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 3;
    final rect = Rect.fromCircle(center: center, radius: radius);
    final segs = 90;
    final segAngle = 2 * math.pi / segs;

    for (var i = 0; i < segs; i++) {
      if (i % 4 == 0) continue;
      final a0 = i * segAngle;
      final t = i / segs;
      final color = _lerp4(colors, t);
      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round
        ..color = color.withOpacity(0.35 + 0.45 * (1 - (t - 0.5).abs() * 2));
      canvas.drawArc(rect, a0, segAngle * 0.72, false, paint);
    }

    for (var i = 0; i < 4; i++) {
      final angle = i * math.pi / 2 - math.pi / 2;
      final pos = Offset(
        center.dx + radius * math.cos(angle),
        center.dy + radius * math.sin(angle),
      );
      final c = colors[i % colors.length];
      canvas.drawCircle(pos, 5, Paint()..color = c.withOpacity(0.25));
      canvas.drawCircle(pos, 3, Paint()..color = c);
    }
  }

  Color _lerp4(List<Color> c, double t) {
    final scaled = t * (c.length - 1);
    final i = scaled.floor().clamp(0, c.length - 2);
    final local = scaled - i;
    return Color.lerp(c[i], c[i + 1], local)!;
  }

  @override
  bool shouldRepaint(covariant _RingPainter old) => old.colors != colors;
}

class _LoadRingPainter extends CustomPainter {
  final double progress;
  final Color color;
  final Color track;
  _LoadRingPainter({required this.progress, required this.color, required this.track});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 6;

    final trackPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round
      ..color = track;
    canvas.drawCircle(center, radius, trackPaint);

    final rect = Rect.fromCircle(center: center, radius: radius);
    final sweepPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        colors: [color.withOpacity(0.4), color, color.withOpacity(0.4)],
        stops: const [0.0, 0.5, 1.0],
      ).createShader(rect);
    canvas.drawArc(rect, -math.pi / 2, 2 * math.pi * progress, false, sweepPaint);

    final dotAngle = -math.pi / 2 + 2 * math.pi * progress;
    final dotCenter = Offset(
      center.dx + radius * math.cos(dotAngle),
      center.dy + radius * math.sin(dotAngle),
    );
    canvas.drawCircle(dotCenter, 8, Paint()..color = color.withOpacity(0.25));
    canvas.drawCircle(dotCenter, 5, Paint()..color = color);
  }

  @override
  bool shouldRepaint(covariant _LoadRingPainter old) =>
      old.progress != progress || old.color != color || old.track != track;
}