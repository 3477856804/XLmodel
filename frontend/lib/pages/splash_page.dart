import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../services/local_store.dart';
import '../main.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;

class SplashPage extends StatefulWidget {
  final VoidCallback onToggleTheme;
  const SplashPage({super.key, required this.onToggleTheme});
  @override
  State<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends State<SplashPage> with TickerProviderStateMixin {
  late AnimationController _pulseCtrl;
  late AnimationController _progressCtrl;
  late AnimationController _fadeCtrl;
  late AnimationController _rotateCtrl;
  late AnimationController _ringCtrl;
  late AnimationController _floatCtrl;
  late AnimationController _textCtrl;
  late AnimationController _shimmerCtrl;
  late Animation<double> _scaleAnim;
  late Animation<double> _glowAnim;
  late Animation<double> _progressAnim;
  late Animation<double> _rotateAnim;
  late Animation<double> _textAnim;

  static const List<String> _loadStages = ['初始化引擎…', '连接后端…', '加载模型…', '准备就绪'];
  Timer? _stageTimer;
  int _stageIdx = 0;
  bool _showVersion = false;

  // ---- 运行时环境自举（GPU→CUDA 版 torch / 无 GPU→CPU 版，就绪才进主页）----
  // 后端 env:status 回报的状态机：idle→detecting→downloading→
  // installing→ready|error。下载态带真实进度（percent/bytes/speed）。
  String? _envPhase;                  // 后端阶段文案（null=还没到这一步）
  double? _envPercent;                // 0~1 真实下载进度
  String? _envError;                  // 非空 = 停在本页展示错误与操作按钮
  Map<String, dynamic>? _envInfo;     // 最近一次 env:status 全量详情
  int _envFail = 0;                   // 查询连续失败计数（后端未起时容忍几次）

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);
    _progressCtrl = AnimationController(
      duration: const Duration(milliseconds: 2400),
      vsync: this,
    );
    _fadeCtrl = AnimationController(
      duration: const Duration(milliseconds: 700),
      vsync: this,
    );
    _rotateCtrl = AnimationController(
      duration: const Duration(milliseconds: 4000),
      vsync: this,
    )..repeat(reverse: true);
    _ringCtrl = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat();
    _floatCtrl = AnimationController(
      duration: const Duration(milliseconds: 6000),
      vsync: this,
    )..repeat();
    _textCtrl = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _shimmerCtrl = AnimationController(
      duration: const Duration(milliseconds: 1800),
      vsync: this,
    )..repeat();
    _scaleAnim = Tween<double>(begin: 0.94, end: 1.05).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );
    _glowAnim = Tween<double>(begin: 0.55, end: 1.0).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );
    _progressAnim = CurvedAnimation(parent: _progressCtrl, curve: XlCurve.easeOut);
    _rotateAnim = Tween<double>(begin: -0.05, end: 0.05).animate(
      CurvedAnimation(parent: _rotateCtrl, curve: Curves.easeInOut),
    );
    _textAnim = CurvedAnimation(parent: _textCtrl, curve: Curves.easeOut);
    _fadeCtrl.forward();
    _progressCtrl.forward();
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) _textCtrl.forward();
    });
    Future.delayed(const Duration(milliseconds: 1000), () {
      if (mounted) setState(() => _showVersion = true);
    });
    _go();
  }

  Future<void> _go() async {
    await Future.delayed(const Duration(milliseconds: 500));
    if (!mounted) return;

    setState(() => _stageIdx = 1);
    pb.StatusReply? st;
    try {
      st = await XlClient.stub.status(
        opt: const XlCallOptions(timeout: Duration(seconds: 5), silent: true),
      );
    } catch (_) {
      st = null;
    }
    if (!mounted) return;

    // 运行时环境自举：检测 GPU → 按需下载对应版本 PyTorch（GPU 版或
    // CPU 版）→ 就绪后才继续。下载中是真实进度；失败则停在本页，
    // 展示错误与「重试 / 改用 CPU 版」按钮，绝不带病进主页。
    final envOk = await _ensureRuntimeEnv();
    if (!envOk) return;
    if (!mounted) return;

    setState(() => _stageIdx = 2);
    final modelReady = st != null && st.model.isNotEmpty;
    await Future.delayed(Duration(milliseconds: modelReady ? 300 : 500));
    if (!mounted) return;

    setState(() => _stageIdx = 3);
    await Future.delayed(const Duration(milliseconds: 300));
    if (!mounted) return;

    await _fadeCtrl.reverse();
    if (mounted) {
      Navigator.pushReplacement(
        context,
        PageRouteBuilder(
          transitionDuration: const Duration(milliseconds: 400),
          pageBuilder: (_, __, ___) => HomeShell(onToggleTheme: widget.onToggleTheme),
          transitionsBuilder: (_, anim, __, child) => FadeTransition(opacity: anim, child: child),
        ),
      );
    }
  }

  /// 轮询后端 env:status，直到运行环境就绪。
  /// 返回 true = 可以继续启动流程；false = 失败（已展示错误与操作按钮）。
  Future<bool> _ensureRuntimeEnv() async {
    if (Platform.environment['FLUTTER_TEST'] == '1') return true;
    while (true) {
      if (!mounted) return false;
      try {
        final out = await XlClient.stub.commandOutput(
          'env:status',
          opt: const XlCallOptions(
              timeout: Duration(seconds: 12), silent: true),
        );
        final st = json.decode(out) as Map<String, dynamic>;
        final state = (st['state'] ?? 'idle').toString();
        if (state == 'ready') {
          setState(() {
            _envPhase = '运行环境就绪';
            _envPercent = 1.0;
            _envError = null;
            _envInfo = st;
          });
          return true;
        }
        if (state == 'error') {
          setState(() {
            _envError = (st['error'] ?? '运行环境初始化失败').toString();
            _envInfo = st;
          });
          return false;
        }
        setState(() {
          _envInfo = st;
          _envPhase = (st['phase'] ?? '正在初始化运行环境…').toString();
          final p = st['percent'];
          _envPercent = (p is num) ? p.toDouble().clamp(0.0, 1.0) : null;
        });
      } catch (e) {
        // 后端可能还没完全起来（Process 刚 spawn）：容忍几次再报错
        _envFail++;
        if (_envFail >= 6) {
          setState(() => _envError = '无法查询运行环境状态：$e');
          return false;
        }
      }
      await Future.delayed(const Duration(milliseconds: 900));
    }
  }

  Future<void> _envAction(String cmd) async {
    setState(() {
      _envError = null;
      _envPhase = cmd == 'env:use-cpu' ? '正在切换到 CPU 版 PyTorch…' : '正在重试…';
      _envPercent = null;
    });
    _envFail = 0;
    try {
      await XlClient.stub.commandOutput(cmd,
          opt: const XlCallOptions(
              timeout: Duration(seconds: 10), silent: true));
    } catch (_) {}
    final ok = await _ensureRuntimeEnv();
    if (ok && mounted) _go();   // 就绪后继续原本被中断的启动流程
  }

  String _fmtBytes(num? b) {
    if (b == null || b <= 0) return '';
    final v = b.toDouble();
    if (v < 1024) return '${v.toStringAsFixed(0)}B';
    if (v < 1024 * 1024) return '${(v / 1024).toStringAsFixed(1)}KB';
    if (v < 1024 * 1024 * 1024) return '${(v / 1048576).toStringAsFixed(1)}MB';
    return '${(v / 1073741824).toStringAsFixed(2)}GB';
  }

  /// 下载详情行：已下载/总量 · 速度 · 当前 wheel 名
  String _envDetail() {
    final st = _envInfo;
    if (st == null) return '';
    final parts = <String>[];
    final done = (st['bytes_done'] as num?)?.toDouble() ?? 0;
    final total = (st['bytes_total'] as num?)?.toDouble() ?? 0;
    if (total > 0) parts.add('${_fmtBytes(done)} / ${_fmtBytes(total)}');
    final speed = (st['speed_bps'] as num?)?.toDouble() ?? 0;
    if (speed > 1024) parts.add('${_fmtBytes(speed)}/s');
    final wheels = st['wheels'];
    if (wheels is List) {
      for (final w in wheels) {
        if (w is Map && (w['done'] ?? 0) < (w['size'] ?? 0)) {
          parts.add('${w['name'] ?? ''}');
          break;
        }
      }
    }
    return parts.join('  ·  ');
  }

  /// 环境初始化失败卡片：说明 + 重试 +（GPU 档时）改用 CPU 版。
  Widget _buildEnvErrorCard(XlPalette p) {
    final isGpu = _envInfo?['flavor'] == 'gpu';
    return Container(
      margin: const EdgeInsets.only(top: 22),
      padding: const EdgeInsets.all(16),
      constraints: const BoxConstraints(maxWidth: 340),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(Icons.cloud_off_rounded, size: 18, color: p.red),
              const SizedBox(width: 8),
              Text(
                '运行环境初始化失败',
                style: TextStyle(
                    color: p.text1,
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            _envError!,
            style: TextStyle(color: p.text2, fontSize: XlFont.caption, height: 1.6),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              ElevatedButton.icon(
                onPressed: () => _envAction('env:retry'),
                icon: const Icon(Icons.refresh_rounded, size: 16),
                label: const Text('重试'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: p.pink,
                  foregroundColor: p.btnInk,
                  textStyle: const TextStyle(
                      fontSize: XlFont.label, fontWeight: FontWeight.w700),
                ),
              ),
              if (isGpu)
                OutlinedButton.icon(
                  onPressed: () => _envAction('env:use-cpu'),
                  icon: const Icon(Icons.memory_rounded, size: 16),
                  label: const Text('改用 CPU 版'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: p.text1,
                    side: BorderSide(color: p.text3.withOpacity(0.5)),
                    textStyle: const TextStyle(
                        fontSize: XlFont.label, fontWeight: FontWeight.w600),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            '首次运行需下载 PyTorch（${isGpu ? 'GPU 版约 3~5GB' : 'CPU 版约 200MB'}），'
            '下载完成后自动进入，请保持网络畅通。',
            style: TextStyle(color: p.text3, fontSize: XlFont.caption, height: 1.5),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    _progressCtrl.dispose();
    _fadeCtrl.dispose();
    _rotateCtrl.dispose();
    _ringCtrl.dispose();
    _floatCtrl.dispose();
    _textCtrl.dispose();
    _shimmerCtrl.dispose();
    _stageTimer?.cancel();
    super.dispose();
  }

  Widget _floatingOrb(double baseX, double baseY, double size, Color color, double phase) {
    return AnimatedBuilder(
      animation: _floatCtrl,
      builder: (_, __) {
        final t = _floatCtrl.value * 2 * math.pi + phase;
        final dx = math.sin(t) * 14;
        final dy = math.cos(t * 0.8) * 18;
        return Positioned(
          left: baseX + dx,
          top: baseY + dy,
          child: Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [color.withOpacity(0.14), color.withOpacity(0.0)],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _glowRing(double delay) {
    return AnimatedBuilder(
      animation: _ringCtrl,
      builder: (_, __) {
        final t = XlEffects.enabled ? (_ringCtrl.value + delay) % 1.0 : 0.0;
        final scale = 0.8 + t * 1.6;
        final opacity = (1 - t) * 0.5;
        return Transform.scale(
          scale: scale,
          child: Opacity(
            opacity: opacity,
            child: Container(
              width: 124,
              height: 124,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: Theme.of(context).extension<XlPalette>()!.pink.withOpacity(0.6),
                  width: 1.5,
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Scaffold(
      backgroundColor: p.bg,
      body: FadeTransition(
        opacity: _fadeCtrl,
        child: Stack(
          children: [
            Positioned.fill(
              child: AppTheme.aurora(context, child: const SizedBox.shrink()),
            ),
            _floatingOrb(60, 120, 160, p.pink, 0),
            _floatingOrb(220, 380, 140, p.gold, 1.5),
            _floatingOrb(100, 500, 180, p.pink2, 3.0),
            Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: 180,
                    height: 180,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        _glowRing(0.0),
                        _glowRing(0.4),
                        AnimatedBuilder(
                          animation: _pulseCtrl,
                          builder: (_, __) {
                            return Transform.rotate(
                              angle: _rotateAnim.value,
                              child: Transform.scale(
                                scale: XlEffects.enabled ? _scaleAnim.value : 1.0,
                                child: Container(
                                  width: 124,
                                  height: 124,
                                  decoration: BoxDecoration(
                                    gradient: p.gradBrand,
                                    shape: BoxShape.circle,
                                    border: Border.all(
                                      color: Colors.white.withOpacity(p.isDark ? 0.40 : 0.55),
                                      width: 3,
                                    ),
                                    boxShadow: [
                                      ...p.raised,
                                      BoxShadow(
                                        color: p.pink.withOpacity(0.5 * (XlEffects.enabled ? _glowAnim.value : 1.0)),
                                        blurRadius: 34,
                                        spreadRadius: -4,
                                      ),
                                    ],
                                  ),
                                  child: Icon(Icons.favorite_rounded, size: 54, color: p.btnInk),
                                ),
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 42),
                  FadeTransition(
                    opacity: _textAnim,
                    child: Column(
                      children: [
                        Text(
                          '晓灵',
                          style: TextStyle(
                            fontSize: 42,
                            fontWeight: FontWeight.w800,
                            color: p.text1,
                            letterSpacing: 10,
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          'XiaoLing AI Companion',
                          style: TextStyle(
                            fontSize: 13,
                            color: p.gold,
                            letterSpacing: 4,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 54),
                  // 运行时环境自举期间用后端回报的真实进度；其余阶段
                  // 仍是原有的固定动画（纯视觉，不假装是真实进度）。
                  SizedBox(
                    width: 220,
                    height: 14,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        Container(
                          width: 220,
                          height: 12,
                          padding: const EdgeInsets.all(2),
                          decoration: AppTheme.sunkenSm(context, r: XlRadius.pill),
                          child: AnimatedBuilder(
                            animation: _progressAnim,
                            builder: (_, __) {
                              final v = _envPercent ??
                                  _progressAnim.value.clamp(0.0, 1.0);
                              return Align(
                                alignment: Alignment.centerLeft,
                                child: FractionallySizedBox(
                                  widthFactor: v.clamp(0.0, 1.0),
                                  child: Container(
                                    decoration: BoxDecoration(
                                      gradient: p.gradBrand,
                                      borderRadius: BorderRadius.circular(XlRadius.pill),
                                      boxShadow: [
                                        BoxShadow(
                                          color: p.pink.withOpacity(0.45),
                                          blurRadius: 8,
                                          spreadRadius: -2,
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        ),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(XlRadius.pill),
                          child: AnimatedBuilder(
                            animation: _shimmerCtrl,
                            builder: (_, __) {
                              final t = _shimmerCtrl.value;
                              return Align(
                                alignment: Alignment.centerLeft,
                                child: FractionallySizedBox(
                                  widthFactor: 220 / 220,
                                  child: Container(
                                    height: 12,
                                    decoration: BoxDecoration(
                                      gradient: LinearGradient(
                                        begin: Alignment(-1.0 + t * 2.5, 0),
                                        end: Alignment(-0.4 + t * 2.5, 0),
                                        colors: [
                                          Colors.white.withOpacity(0),
                                          Colors.white.withOpacity(0.35),
                                          Colors.white.withOpacity(0),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  // env 自举期间显示后端真实阶段文案（含下载详情），
                  // 就绪或失败后交回原有的固定阶段串。
                  SizedBox(
                    height: 20,
                    child: AnimatedSwitcher(
                      duration: const Duration(milliseconds: 350),
                      transitionBuilder: (child, anim) => FadeTransition(opacity: anim, child: child),
                      child: Text(
                        (_envPhase != null && _envError == null && _stageIdx <= 1)
                            ? _envPhase!
                            : _loadStages[_stageIdx],
                        key: ValueKey((_envPhase != null && _envError == null && _stageIdx <= 1)
                            ? _envPhase
                            : _stageIdx),
                        style: TextStyle(
                          fontSize: XlFont.label,
                          color: p.text3,
                          fontWeight: FontWeight.w600,
                          letterSpacing: XlLetterSpacing.wider,
                        ),
                      ),
                    ),
                  ),
                  // 下载详情：已下载/总量 · 速度 · 当前 wheel
                  if (_envPhase != null && _envError == null && _envDetail().isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(
                        _envDetail(),
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: XlFont.caption,
                          color: p.text3,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  // 失败态：错误详情 + 重试 / 改用 CPU 版。绝不带病进主页。
                  if (_envError != null)
                    _buildEnvErrorCard(p),
                ],
              ),
            ),
            Positioned(
              bottom: 28,
              left: 0,
              right: 0,
              child: AnimatedOpacity(
                opacity: _showVersion ? 1.0 : 0.0,
                duration: const Duration(milliseconds: 600),
                child: Text(
                  'v0.0.1',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.gold,
                    fontWeight: FontWeight.w700,
                    letterSpacing: XlLetterSpacing.wider,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
