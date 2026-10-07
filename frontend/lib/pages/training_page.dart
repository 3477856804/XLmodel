import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;

class TrainingPage extends StatefulWidget {
  const TrainingPage({super.key});
  @override
  State<TrainingPage> createState() => _TrainingPageState();
}

class _TrainingPageState extends State<TrainingPage> with TickerProviderStateMixin {
  pb.TrainingStatusReply? _data;
  pb.GrowthStatusReply? _growth;
  bool _loading = true;
  String? _error;
  late AnimationController _enterCtrl;
  late AnimationController _radarCtrl;
  late AnimationController _pulseCtrl;
  late Animation<double> _enterAnim;
  late Animation<double> _radarAnim;
  final List<_LogLine> _logs = [];
  final ScrollController _logScroll = ScrollController();
  int _selectedPreset = 1;
  bool _autoScroll = true;
  final _lrCtrl = TextEditingController(text: '0.0002');
  final _bsCtrl = TextEditingController(text: '4');
  final _rankCtrl = TextEditingController(text: '8');
  final _stepsCtrl = TextEditingController(text: '100');
  bool _trainingActive = false;
  bool _stopRequested = false;
  int _rtStep = 0;
  int _rtTotalSteps = 0;
  double _rtLoss = 0.0;
  List<pb.TrainingHistoryEntry> _history = [];

  static const _presets = <_Preset>[
    _Preset('轻量', 'r=4 · 3 epochs', 'pink', Icons.bolt_rounded, 0.30),
    _Preset('均衡', 'r=8 · 5 epochs', 'gold', Icons.tune_rounded, 0.55),
    _Preset('深度', 'r=16 · 10 epochs', 'violet', Icons.auto_awesome_rounded, 0.85),
  ];

  static const _milestones = <_Milestone>[
    _Milestone('第一次对话', '完成', true, 'pink'),
    _Milestone('累计 10 轮', '已达成', true, 'gold'),
    _Milestone('首次微调', '待触发', false, 'violet'),
    _Milestone('关系升级', '未解锁', false, 'green'),
  ];

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 900), vsync: this);
    _radarCtrl = AnimationController(duration: const Duration(milliseconds: 1100), vsync: this);
    _pulseCtrl = AnimationController(duration: const Duration(seconds: 4), vsync: this)..repeat();
    _enterAnim = CurvedAnimation(parent: _enterCtrl, curve: XlCurve.easeOut);
    _radarAnim = CurvedAnimation(parent: _radarCtrl, curve: XlCurve.easeOut);
    _enterCtrl.forward();
    _load();
  }

  @override
  void dispose() {
    _enterCtrl.dispose();
    _radarCtrl.dispose();
    _pulseCtrl.dispose();
    _logScroll.dispose();
    _lrCtrl.dispose();
    _bsCtrl.dispose();
    _rankCtrl.dispose();
    _stepsCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await XlClient.stub.training();
      final g = await XlClient.stub.safe(() => XlClient.stub.growth());
      final h = await XlClient.stub.safe(() => XlClient.stub.getTrainingHistory(pb.Empty()));
      if (!mounted) return;
      setState(() {
        _data = r;
        _growth = g;
        _history = h?.entries.toList() ?? [];
        _loading = false;
      });
      _radarCtrl.forward(from: 0);
      _seedLogs(r);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  void _seedLogs(pb.TrainingStatusReply r) {
    _logs
      ..clear()
      ..add(_LogLine('[ready] 训练引擎已就绪', _LogLevel.info))
      ..add(_LogLine('[model] 冻结主干权重，注入低秩矩阵', _LogLevel.info))
      ..add(_LogLine('[data] 数据集: 128 条 · 序列长度 512', _LogLevel.dim))
      ..add(_LogLine('[device] 设备: CPU · 精度: fp32', _LogLevel.dim))
      ..add(_LogLine(
        r.isTraining ? '[state] 训练中 · ${r.statusText}' : '[state] 待机 · 等待指令',
        r.isTraining ? _LogLevel.warn : _LogLevel.info,
      ));
    if (r.currentEpoch > 0) {
      _logs.add(_LogLine('[epoch] 已完成 ${r.epochLabel} 轮', _LogLevel.ok));
    }
    if (r.loss > 0) {
      _logs.add(_LogLine('[loss] 当前 ${r.lossLabel}', _LogLevel.ok));
    }
  }

  Color _colorOf(XlPalette p, String key) {
    switch (key) {
      case 'pink': return p.pink;
      case 'gold': return p.gold;
      case 'violet': return p.violet;
      case 'green': return p.green;
      case 'red': return p.red;
      case 'blue': return p.blue;
      default: return p.pink;
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    if (_loading) return _loadingView(p);
    if (_data == null) return _errorView(p);
    return Stack(
      children: [
        Positioned.fill(child: AppTheme.aurora(context, child: const SizedBox.shrink())),
        AnimatedBuilder(
          animation: _enterAnim,
          builder: (_, __) => Opacity(
            opacity: _enterAnim.value,
            child: Transform.translate(
              offset: Offset(0, (1 - _enterAnim.value) * 16),
              child: _body(p),
            ),
          ),
        ),
      ],
    );
  }

  Widget _body(XlPalette p) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _stagger(0, _heroRow(p)),
          const SizedBox(height: 22),
          _stagger(1, _statusBanner(p)),
          const SizedBox(height: 20),
          _stagger(2, _paramsCard(p)),
          const SizedBox(height: 20),
          _stagger(3, LayoutBuilder(
            builder: (context, c) {
              final stacked = c.maxWidth < 1000;
              if (stacked) {
                return Column(
                  children: [
                    _radarCard(p),
                    const SizedBox(height: 18),
                    _dimensionsCard(p),
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 4, child: _radarCard(p)),
                  const SizedBox(width: 18),
                  Expanded(flex: 5, child: _dimensionsCard(p)),
                ],
              );
            },
          )),
          const SizedBox(height: 20),
          _stagger(4, LayoutBuilder(
            builder: (context, c) {
              final stacked = c.maxWidth < 1000;
              if (stacked) {
                return Column(
                  children: [
                    _presetCard(p),
                    const SizedBox(height: 18),
                    _logCard(p),
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 3, child: _presetCard(p)),
                  const SizedBox(width: 18),
                  Expanded(flex: 5, child: _logCard(p)),
                ],
              );
            },
          )),
          const SizedBox(height: 20),
          _stagger(5, LayoutBuilder(
            builder: (context, c) {
              final stacked = c.maxWidth < 900;
              if (stacked) {
                return Column(
                  children: [
                    _milestonesCard(p),
                    const SizedBox(height: 18),
                    _statsCard(p),
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 4, child: _milestonesCard(p)),
                  const SizedBox(width: 18),
                  Expanded(flex: 3, child: _statsCard(p)),
                ],
              );
            },
          )),
          const SizedBox(height: 20),
          _stagger(6, _historyCard(p)),
        ],
      ),
    );
  }

  Widget _stagger(int index, Widget child) {
    final start = (index * 0.08).clamp(0.0, 0.72);
    final end = (start + 0.5).clamp(0.0, 1.0);
    return AnimatedBuilder(
      animation: _enterAnim,
      builder: (_, __) {
        final t = Interval(start, end, curve: Curves.easeOut).transform(_enterAnim.value);
        return Opacity(
          opacity: t,
          child: Transform.translate(offset: Offset(0, (1 - t) * 18), child: child),
        );
      },
    );
  }

  Widget _heroRow(XlPalette p) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text('能力训练',
                      style: TextStyle(
                        fontSize: XlFont.h2,
                        fontWeight: FontWeight.w800,
                        color: p.text1,
                        letterSpacing: XlLetterSpacing.normal,
                      )),
                  const SizedBox(width: 12),
                  _trainingBadge(p),
                ],
              ),
              const SizedBox(height: 6),
              Text('五维能力 · LoRA 微调 · 让模型越来越像她',
                  style: TextStyle(
                    fontSize: XlFont.caption,
                    color: p.text2,
                    fontWeight: FontWeight.w500,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
            ],
          ),
        ),
        const SizedBox(width: 16),
        _refreshBtn(p),
      ],
    );
  }

  Widget _trainingBadge(XlPalette p) {
    final training = _data?.isTraining ?? false;
    final color = training ? p.green : p.gold;
    return AnimatedBuilder(
      animation: _pulseCtrl,
      builder: (_, __) {
        final t = _pulseCtrl.value;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: color.withOpacity(p.isDark ? 0.14 : 0.10),
            borderRadius: BorderRadius.circular(XlRadius.pill),
            border: Border.all(color: color.withOpacity(0.32), width: 1),
            boxShadow: training
                ? [BoxShadow(color: color.withOpacity(0.25 + t * 0.15), blurRadius: 12, spreadRadius: -2)]
                : null,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: AppTheme.glowDot(color, size: 6),
              ),
              const SizedBox(width: 6),
              Text(training ? 'TRAINING' : 'IDLE',
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w800,
                    color: color,
                    letterSpacing: XlLetterSpacing.ultra,
                  )),
            ],
          ),
        );
      },
    );
  }

  Widget _refreshBtn(XlPalette p) {
    return _Pressable(
      onTap: _load,
      child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: AppTheme.neuXs(context, r: XlRadius.lg),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.refresh_rounded, size: 15, color: p.pink),
              const SizedBox(width: 8),
              Text('刷新',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w700,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
        ),
      );
  }

  Widget _statusBanner(XlPalette p) {
    final training = _data!.isTraining || _trainingActive;
    final color = training ? p.green : p.gold;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              AnimatedBuilder(
                animation: _pulseCtrl,
                builder: (_, __) {
                  final t = _pulseCtrl.value;
                  return Stack(
                    alignment: Alignment.center,
                    children: [
                      Container(
                        width: 48 + t * 12,
                        height: 48 + t * 12,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: color.withOpacity((1 - t) * 0.20),
                        ),
                      ),
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(colors: [color, color.withOpacity(0.75)]),
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.32 : 0.48), width: 1.5),
                          boxShadow: [...p.raisedXs, BoxShadow(color: color.withOpacity(0.4), blurRadius: 18, spreadRadius: -4)],
                        ),
                        child: Icon(
                          training ? Icons.auto_awesome_rounded : Icons.pause_rounded,
                          color: p.isDark ? p.btnInk : Colors.white,
                          size: 20,
                        ),
                      ),
                    ],
                  );
                },
              ),
              const SizedBox(width: 18),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(training ? '正在训练' : '等待指令',
                            style: TextStyle(
                              fontSize: XlFont.h6,
                              fontWeight: FontWeight.w800,
                              color: p.text1,
                              letterSpacing: XlLetterSpacing.normal,
                            )),
                        const SizedBox(width: 10),
                        _tinyChip(p, training ? 'ACTIVE' : 'STANDBY', color),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(_data!.displayStatus,
                        style: TextStyle(
                          fontSize: XlFont.caption,
                          color: p.text2,
                          fontWeight: FontWeight.w500,
                          letterSpacing: XlLetterSpacing.wide,
                        )),
                  ],
                ),
              ),
              const Spacer(),
              AnimatedSwitcher(
                duration: XlDuration.normal,
                transitionBuilder: (child, anim) => ScaleTransition(
                  scale: anim,
                  child: RotationTransition(turns: Tween(begin: 0.85, end: 1.0).animate(anim), child: child),
                ),
                child: _trainingActive
                    ? _stopBtn(p, key: const ValueKey('stop'))
                    : (_data!.isTraining ? _epochIndicator(p, key: const ValueKey('epoch')) : _startBtn(p, key: const ValueKey('start'))),
              ),
            ],
          ),
          if (_trainingActive) ...[
            const SizedBox(height: 16),
            _rtProgress(p),
          ],
        ],
      ),
    );
  }

  Widget _rtProgress(XlPalette p) {
    final total = _rtTotalSteps <= 0 ? 1 : _rtTotalSteps;
    final pct = (_rtStep / total).clamp(0.0, 1.0);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.screen(context, r: XlRadius.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('Step',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w700,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
              const SizedBox(width: 8),
              Text('$_rtStep',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    color: p.pink,
                    fontWeight: FontWeight.w800,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  )),
              Text('/$_rtTotalSteps',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    color: p.text3,
                    fontWeight: FontWeight.w700,
                  )),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: AppTheme.sunkenXs(context, r: XlRadius.sm),
                child: TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0.0, end: _rtLoss),
                  duration: const Duration(milliseconds: 300),
                  curve: XlCurve.standard,
                  builder: (_, v, __) => Text('Loss ${v.toStringAsFixed(3)}',
                      style: TextStyle(
                        fontSize: XlFont.captionSm,
                        color: p.violet,
                        fontWeight: FontWeight.w800,
                        fontFeatures: const [FontFeature.tabularFigures()],
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _neuProgress(p, pct, height: 6, shimmer: _trainingActive),
          const SizedBox(height: 6),
          Align(
            alignment: Alignment.centerRight,
            child: Text('${(pct * 100).toStringAsFixed(1)}%',
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.gold,
                  fontWeight: FontWeight.w800,
                  fontFeatures: const [FontFeature.tabularFigures()],
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ),
        ],
      ),
    );
  }

  Widget _epochIndicator(XlPalette p, {Key? key}) {
    final pct = _data!.progressRatio;
    return Column(
      key: key,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Row(
          children: [
            Text('Epoch ',
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.text3,
                  fontWeight: FontWeight.w700,
                  letterSpacing: XlLetterSpacing.wider,
                )),
            Text('${_data!.currentEpoch}',
                style: TextStyle(
                  fontSize: XlFont.h6,
                  color: p.pink,
                  fontWeight: FontWeight.w800,
                  fontFeatures: const [FontFeature.tabularFigures()],
                )),
            Text('/${_data!.totalEpochs}',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text3,
                  fontWeight: FontWeight.w700,
                )),
          ],
        ),
        const SizedBox(height: 6),
        SizedBox(
          width: 120,
          child: _neuProgress(p, pct, height: 5),
        ),
      ],
    );
  }

  Widget _startBtn(XlPalette p, {Key? key}) {
    final steps = int.tryParse(_stepsCtrl.text.trim()) ?? 100;
    final estMin = (steps * 0.6 / 60).ceil().clamp(1, 999);
    return Column(
      key: key,
      crossAxisAlignment: CrossAxisAlignment.end,
      mainAxisSize: MainAxisSize.min,
      children: [
        _Pressable(
          onTap: _startTraining,
          child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 13),
              decoration: AppTheme.btn(context, r: XlRadius.pill),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.play_arrow_rounded, size: 16, color: p.btnInk),
                  const SizedBox(width: 8),
                  Text('开始训练',
                      style: TextStyle(
                        fontSize: XlFont.captionSm,
                        fontWeight: FontWeight.w800,
                        color: p.btnInk,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                ],
              ),
            ),
          ),
        const SizedBox(height: 6),
        Text('预计约 $estMin 分钟',
            style: TextStyle(
              fontSize: XlFont.micro,
              color: p.gold,
              fontWeight: FontWeight.w700,
              letterSpacing: XlLetterSpacing.wider,
            )),
      ],
    );
  }

  Widget _stopBtn(XlPalette p, {Key? key}) {
    return _Pressable(
      key: key,
      onTap: _requestStop,
      child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 13),
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [p.red, p.red.withOpacity(0.8)]),
            borderRadius: BorderRadius.circular(XlRadius.pill),
            border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.32 : 0.22), width: 1),
            boxShadow: [...p.raisedXs, BoxShadow(color: p.red.withOpacity(0.35), blurRadius: 12, spreadRadius: -2)],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.stop_rounded, size: 15, color: p.btnInk),
              const SizedBox(width: 8),
              Text('停止',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: p.btnInk,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
        ),
      );
  }

  Future<void> _startTraining() async {
    if (_trainingActive) return;
    final lr = double.tryParse(_lrCtrl.text.trim()) ?? 0.0002;
    final bs = int.tryParse(_bsCtrl.text.trim()) ?? 4;
    final rank = int.tryParse(_rankCtrl.text.trim()) ?? 8;
    final steps = int.tryParse(_stepsCtrl.text.trim()) ?? 100;
    _stopRequested = false;
    setState(() {
      _trainingActive = true;
      _rtStep = 0;
      _rtTotalSteps = steps;
      _rtLoss = 0.0;
      _logs.add(_LogLine('[start] 初始化 LoRA 适配器 · lr=$lr bs=$bs r=$rank steps=$steps', _LogLevel.warn));
      _logs.add(_LogLine('[preset] ${_presets[_selectedPreset].desc}', _LogLevel.dim));
    });
    _scrollLogBottom();
    try {
      final req = pb.TrainingRequest(
        learningRate: lr,
        batchSize: bs,
        loraRank: rank,
        steps: steps,
        datasetName: 'default',
      );
      final stream = XlClient.stub.startTraining(req);
      await for (final p in stream) {
        if (!mounted || _stopRequested) break;
        setState(() {
          _rtStep = p.step;
          _rtTotalSteps = p.totalSteps <= 0 ? steps : p.totalSteps;
          _rtLoss = p.loss;
        });
        if (p.step % 10 == 0 || p.step == _rtTotalSteps) {
          _logs.add(_LogLine('[step] ${p.step}/${p.totalSteps} loss=${p.loss.toStringAsFixed(3)}', _LogLevel.info));
          _scrollLogBottom();
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _logs.add(_LogLine('[error] $e', _LogLevel.error)));
        _scrollLogBottom();
      }
    } finally {
      if (mounted) {
        setState(() {
          _trainingActive = false;
          _logs.add(_LogLine('[done] 训练流程结束', _LogLevel.ok));
        });
        _scrollLogBottom();
        _load();
      }
    }
  }

  Future<void> _requestStop() async {
    if (!_trainingActive) return;
    final confirmed = await showDialog<bool>(
      context: context,
      barrierColor: XlPalette.of(context).scrim,
      builder: (ctx) {
        final p = XlPalette.of(ctx);
        return Dialog(
          backgroundColor: Colors.transparent,
          elevation: 0,
          child: Container(
            width: 380,
            padding: const EdgeInsets.all(24),
            decoration: AppTheme.neuLg(ctx, r: XlRadius.xxxl),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('中断训练',
                    style: TextStyle(
                      fontSize: XlFont.h5,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                    )),
                const SizedBox(height: 6),
                Text('确定要中断当前训练吗？已训练的进度将被记录',
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.text2,
                      fontWeight: FontWeight.w500,
                      height: XlLineHeight.relaxed,
                    )),
                const SizedBox(height: 22),
                Row(
                  children: [
                    Expanded(
                      child: _Pressable(
                        onTap: () => Navigator.pop(ctx, false),
                        scale: 0.95,
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          decoration: AppTheme.ghost(ctx, r: XlRadius.pill),
                          child: Center(
                            child: Text('继续训练',
                                style: TextStyle(
                                  fontSize: XlFont.captionSm,
                                  fontWeight: FontWeight.w800,
                                  color: p.text1,
                                )),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _Pressable(
                        scale: 0.95,
                        onTap: () => Navigator.pop(ctx, true),
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          decoration: BoxDecoration(
                            gradient: LinearGradient(colors: [p.red, p.red.withOpacity(0.85)]),
                            borderRadius: BorderRadius.circular(XlRadius.pill),
                          ),
                          child: Center(
                            child: Text('中断',
                                style: TextStyle(
                                  fontSize: XlFont.captionSm,
                                  fontWeight: FontWeight.w800,
                                  color: p.btnInk,
                                )),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
    if (confirmed != true) return;
    setState(() => _stopRequested = true);
    _logs.add(_LogLine('[stop] 收到停止指令，结束当前轮次', _LogLevel.warn));
    _scrollLogBottom();
  }

  void _scrollLogBottom() {
    if (!_autoScroll) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_logScroll.hasClients) {
        _logScroll.animateTo(
          _logScroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 240),
          curve: XlCurve.easeOut,
        );
      }
    });
  }

  Widget _radarCard(XlPalette p) {
    final dims = _data!.dimensions;
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('五维能力',
                        style: TextStyle(
                          fontSize: XlFont.h6,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.normal,
                        )),
                    const SizedBox(height: 3),
                    Text('综合评估模型能力分布',
                        style: TextStyle(
                          fontSize: XlFont.label,
                          color: p.text3,
                          fontWeight: FontWeight.w500,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                  ],
                ),
              ),
              _tinyChip(p, '${dims.length} 维', p.violet),
            ],
          ),
          const SizedBox(height: 18),
          AspectRatio(
            aspectRatio: 1,
            child: AnimatedBuilder(
              animation: _radarAnim,
              builder: (_, __) => CustomPaint(
                painter: _RadarPainter(
                  dims: dims,
                  palette: p,
                  progress: _radarAnim.value,
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Center(
            child: Text(dims.isEmpty ? '暂无数据' : '综合得分 ${_data!.avgDimensionLabel}',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text2,
                  fontWeight: FontWeight.w700,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ),
        ],
      ),
    );
  }

  Widget _dimensionsCard(XlPalette p) {
    final dims = _data!.dimensions;
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('详细数值',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              Text('${dims.length} 项',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w700,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
          const SizedBox(height: 18),
          if (dims.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 30),
              child: Center(
                child: Text('暂无维度数据',
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.text3,
                      fontWeight: FontWeight.w500,
                    )),
              ),
            )
          else
            for (int i = 0; i < dims.length; i++) _dimRow(p, dims[i], i),
        ],
      ),
    );
  }

  Widget _dimRow(XlPalette p, pb.TrainingDimension d, int i) {
    final colors = [p.pink, p.gold, p.violet, p.green, p.blue];
    final color = colors[i % colors.length];
    return Padding(
      padding: EdgeInsets.only(bottom: i == _data!.dimensions.length - 1 ? 0 : 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: AppTheme.glowDot(color, size: 8),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(d.displayName,
                    style: TextStyle(
                      fontSize: XlFont.caption,
                      fontWeight: FontWeight.w700,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
              ),
              _tierChip(p, d.tier, color),
              const SizedBox(width: 10),
              Text(d.normalized.toStringAsFixed(1),
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: color,
                    fontFeatures: const [FontFeature.tabularFigures()],
                    height: 1.0,
                  )),
              const SizedBox(width: 2),
              Text('%',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w700,
                    color: p.text3,
                  )),
            ],
          ),
          const SizedBox(height: 8),
          Stack(
            children: [
              Container(
                height: 8,
                decoration: BoxDecoration(
                  color: p.surfaceLo,
                  borderRadius: BorderRadius.circular(99),
                  boxShadow: p.sunkenXxs,
                ),
              ),
              TweenAnimationBuilder<double>(
                duration: Duration(milliseconds: 500 + i * 100),
                curve: XlCurve.easeOut,
                tween: Tween(begin: 0.0, end: d.ratio),
                builder: (_, v, __) => FractionallySizedBox(
                  widthFactor: v,
                  child: Container(
                    height: 8,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(colors: [color.withOpacity(0.8), color]),
                      borderRadius: BorderRadius.circular(99),
                      boxShadow: [BoxShadow(color: color.withOpacity(0.4), blurRadius: 8, spreadRadius: -2)],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _presetCard(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('训练预设',
              style: TextStyle(
                fontSize: XlFont.h6,
                fontWeight: FontWeight.w800,
                color: p.text1,
                letterSpacing: XlLetterSpacing.normal,
              )),
          const SizedBox(height: 4),
          Text('选择适配你硬件的档位',
              style: TextStyle(
                fontSize: XlFont.label,
                color: p.text3,
                fontWeight: FontWeight.w500,
                letterSpacing: XlLetterSpacing.wider,
              )),
          const SizedBox(height: 16),
          for (int i = 0; i < _presets.length; i++)
            Padding(
              padding: EdgeInsets.only(bottom: i == _presets.length - 1 ? 0 : 10),
              child: _presetTile(p, _presets[i], i),
            ),
        ],
      ),
    );
  }

  Widget _presetTile(XlPalette p, _Preset preset, int i) {
    final selected = _selectedPreset == i;
    final color = _colorOf(p, preset.color);
    return _Pressable(
      onTap: () => setState(() => _selectedPreset = i),
      child: AnimatedContainer(
          duration: XlDuration.fast,
          curve: XlCurve.standard,
          padding: const EdgeInsets.all(14),
          decoration: selected
              ? AppTheme.sunkenSm(context, r: XlRadius.md)
              : AppTheme.neuXs(context, r: XlRadius.md),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                  borderRadius: BorderRadius.circular(XlRadius.sm),
                  border: Border.all(color: color.withOpacity(0.28), width: 1),
                ),
                child: Icon(preset.icon, size: 16, color: color),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(preset.name,
                        style: TextStyle(
                          fontSize: XlFont.caption,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.wide,
                        )),
                    const SizedBox(height: 2),
                    Text(preset.desc,
                        style: TextStyle(
                          fontSize: XlFont.label,
                          color: p.text3,
                          fontWeight: FontWeight.w500,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                  ],
                ),
              ),
              AnimatedContainer(
                duration: XlDuration.fast,
                width: 20,
                height: 20,
                decoration: BoxDecoration(
                  color: selected ? color : Colors.transparent,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: selected ? color : p.shDark.withOpacity(p.isDark ? 0.32 : 0.14),
                    width: 1.5,
                  ),
                ),
                child: selected
                    ? Icon(Icons.check_rounded, size: 13, color: p.isDark ? p.btnInk : Colors.white)
                    : null,
              ),
            ],
          ),
        ),
      );
  }

  Widget _logCard(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('训练日志',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              _Pressable(
                onTap: () => setState(() => _autoScroll = !_autoScroll),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: _autoScroll ? p.pink.withOpacity(p.isDark ? 0.14 : 0.10) : p.surfaceLo,
                    borderRadius: BorderRadius.circular(XlRadius.pill),
                    border: Border.all(
                      color: _autoScroll ? p.pink.withOpacity(0.30) : p.edgeSoft,
                      width: 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        _autoScroll ? Icons.vertical_align_bottom_rounded : Icons.pause_rounded,
                        size: 10,
                        color: _autoScroll ? p.pink : p.text3,
                      ),
                      const SizedBox(width: 4),
                      Text(_autoScroll ? 'AUTO' : 'PAUSED',
                          style: TextStyle(
                            fontSize: XlFont.micro,
                            fontWeight: FontWeight.w800,
                            color: _autoScroll ? p.pink : p.text3,
                            letterSpacing: XlLetterSpacing.ultra,
                          )),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 8),
              _Pressable(
                onTap: () => setState(() => _logs.clear()),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: p.surfaceLo,
                    borderRadius: BorderRadius.circular(XlRadius.pill),
                    border: Border.all(color: p.edgeSoft, width: 1),
                  ),
                  child: Icon(Icons.cleaning_services_outlined, size: 10, color: p.text3),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Container(
            height: 220,
            decoration: AppTheme.screen(context, r: XlRadius.md),
            padding: const EdgeInsets.all(14),
            child: _logs.isEmpty
                ? Center(
                    child: Text('[empty] 暂无日志输出',
                        style: TextStyle(
                          fontSize: XlFont.label,
                          color: p.decor,
                          fontFamily: 'monospace',
                          fontWeight: FontWeight.w500,
                        )),
                  )
                : ListView.builder(
                    controller: _logScroll,
                    padding: EdgeInsets.zero,
                    itemCount: _logs.length,
                    itemBuilder: (_, i) {
                      final line = _logs[i];
                      return _LogEntrance(
                        child: Padding(
                          padding: const EdgeInsets.only(bottom: 5),
                          child: Text(
                            line.text,
                            style: TextStyle(
                              fontFamily: 'monospace',
                              fontSize: XlFont.label,
                              height: XlLineHeight.relaxed,
                              color: _logColor(p, line.level),
                              fontWeight: FontWeight.w500,
                              letterSpacing: XlLetterSpacing.wide,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Color _logColor(XlPalette p, _LogLevel level) {
    switch (level) {
      case _LogLevel.info: return p.text2;
      case _LogLevel.dim: return p.decor;
      case _LogLevel.ok: return p.green;
      case _LogLevel.warn: return p.gold;
      case _LogLevel.error: return p.red;
    }
  }

  Widget _milestonesCard(XlPalette p) {
    final unlocked = _growth != null;
    final done = _milestones.where((m) => m.done).length + (unlocked ? 1 : 0);
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('训练里程碑',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              Text('$done/${_milestones.length}',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w800,
                    letterSpacing: XlLetterSpacing.wider,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  )),
            ],
          ),
          const SizedBox(height: 16),
          for (int i = 0; i < _milestones.length; i++)
            Padding(
              padding: EdgeInsets.only(bottom: i == _milestones.length - 1 ? 0 : 12),
              child: _milestoneRow(p, _milestones[i]),
            ),
        ],
      ),
    );
  }

  Widget _milestoneRow(XlPalette p, _Milestone m) {
    final color = _colorOf(p, m.color);
    return Row(
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            gradient: m.done ? LinearGradient(colors: [color, color.withOpacity(0.7)]) : null,
            color: m.done ? null : p.surfaceLo,
            shape: BoxShape.circle,
            border: Border.all(
              color: m.done
                  ? Colors.white.withOpacity(p.isDark ? 0.32 : 0.48)
                  : p.shDark.withOpacity(p.isDark ? 0.30 : 0.13),
              width: 1,
            ),
            boxShadow: m.done
                ? [...p.raisedXxs, BoxShadow(color: color.withOpacity(0.35), blurRadius: 12, spreadRadius: -2)]
                : p.sunkenXxs,
          ),
          child: Icon(
            m.done ? Icons.check_rounded : Icons.lock_outline_rounded,
            size: 14,
            color: m.done ? (p.isDark ? p.btnInk : Colors.white) : p.decor,
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Text(m.name,
              style: TextStyle(
                fontSize: XlFont.captionSm,
                fontWeight: m.done ? FontWeight.w700 : FontWeight.w500,
                color: m.done ? p.text1 : p.text2,
                letterSpacing: XlLetterSpacing.wide,
              )),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: m.done ? color.withOpacity(p.isDark ? 0.14 : 0.10) : p.surfaceLo,
            borderRadius: BorderRadius.circular(XlRadius.pill),
            border: Border.all(
              color: m.done ? color.withOpacity(0.30) : p.edgeSoft,
              width: 1,
            ),
          ),
          child: Text(m.status,
              style: TextStyle(
                fontSize: XlFont.micro,
                fontWeight: FontWeight.w800,
                color: m.done ? color : p.text3,
                letterSpacing: XlLetterSpacing.wider,
              )),
        ),
      ],
    );
  }

  Widget _statsCard(XlPalette p) {
    final cur = _data!.currentEpoch;
    final total = _data!.totalEpochs == 0 ? 1 : _data!.totalEpochs;
    final loss = _data!.loss;
    final pct = _data!.progressRatio;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('训练指标',
              style: TextStyle(
                fontSize: XlFont.h6,
                fontWeight: FontWeight.w800,
                color: p.text1,
                letterSpacing: XlLetterSpacing.normal,
              )),
          const SizedBox(height: 16),
          _metricRow(p, '当前 Epoch', '$cur', '/$total', p.pink, cur / total.clamp(1, 999)),
          const SizedBox(height: 14),
          _metricRow(p, '训练进度', '${(pct * 100).toStringAsFixed(0)}', '%', p.gold, pct),
          const SizedBox(height: 14),
          _metricRow(p, 'Loss 值', loss == 0 ? '—' : loss.toStringAsFixed(4), '', p.violet, _data!.lossQuality),
          const SizedBox(height: 14),
          _metricRow(p, '学习率', '2e-4', '', p.green, 0.6),
          const SizedBox(height: 14),
          _metricRow(p, '批次大小', '4', '', p.blue, 0.4),
        ],
      ),
    );
  }

  Widget _metricRow(XlPalette p, String label, String value, String unit, Color color, double progress) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(label,
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.text3,
                  fontWeight: FontWeight.w700,
                  letterSpacing: XlLetterSpacing.wider,
                )),
            const Spacer(),
            Text(value,
                style: TextStyle(
                  fontSize: XlFont.caption,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                  fontFeatures: const [FontFeature.tabularFigures()],
                )),
            if (unit.isNotEmpty)
              Text(unit,
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w700,
                    color: p.text3,
                  )),
          ],
        ),
        const SizedBox(height: 6),
        _neuProgress(p, progress, height: 4, color: color),
      ],
    );
  }

  Widget _neuProgress(XlPalette p, double value, {double height = 5, Color? color, bool shimmer = false}) {
    final c = color ?? p.pink;
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(99),
        boxShadow: p.sunkenXxs,
      ),
      child: FractionallySizedBox(
        alignment: Alignment.centerLeft,
        widthFactor: value.clamp(0.0, 1.0),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: Stack(
            fit: StackFit.expand,
            children: [
              Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: [c.withOpacity(0.7), c]),
                  borderRadius: BorderRadius.circular(99),
                  boxShadow: [BoxShadow(color: c.withOpacity(0.35), blurRadius: 8, spreadRadius: -2)],
                ),
              ),
              if (shimmer) _ShimmerSweep(anim: _pulseCtrl),
            ],
          ),
        ),
      ),
    );
  }

  Widget _tinyChip(XlPalette p, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(p.isDark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: color.withOpacity(0.28), width: 1),
      ),
      child: Text(text,
          style: TextStyle(
            fontSize: XlFont.micro,
            fontWeight: FontWeight.w800,
            color: color,
            letterSpacing: XlLetterSpacing.ultra,
          )),
    );
  }

  Widget _tierChip(XlPalette p, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(p.isDark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.xs),
        border: Border.all(color: color.withOpacity(0.28), width: 1),
      ),
      child: Text(text,
          style: TextStyle(
            fontSize: XlFont.micro,
            fontWeight: FontWeight.w800,
            color: color,
            letterSpacing: XlLetterSpacing.wider,
          )),
    );
  }

  Widget _paramsCard(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('训练参数',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              _tinyChip(p, 'LoRA', p.pink),
            ],
          ),
          const SizedBox(height: 4),
          Text('自定义本次微调的超参数',
              style: TextStyle(
                fontSize: XlFont.label,
                color: p.text3,
                fontWeight: FontWeight.w500,
                letterSpacing: XlLetterSpacing.wider,
              )),
          const SizedBox(height: 16),
          LayoutBuilder(
            builder: (context, c) {
              final wide = c.maxWidth > 620;
              final fields = [
                _ParamField('学习率', '0.0002', _lrCtrl, p.pink),
                _ParamField('Batch Size', '4', _bsCtrl, p.gold),
                _ParamField('LoRA Rank', '8', _rankCtrl, p.violet),
                _ParamField('训练步数', '100', _stepsCtrl, p.green),
              ];
              if (wide) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (var i = 0; i < fields.length; i++) ...[
                      Expanded(child: _paramField(p, fields[i])),
                      if (i != fields.length - 1) const SizedBox(width: 12),
                    ],
                  ],
                );
              }
              return Column(
                children: [
                  for (var i = 0; i < fields.length; i++) ...[
                    _paramField(p, fields[i]),
                    if (i != fields.length - 1) const SizedBox(height: 12),
                  ],
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  String _paramTip(String label) {
    switch (label) {
      case '学习率':
        return '控制权重更新步长，推荐 1e-4 ~ 5e-4，过大易震荡';
      case 'Batch Size':
        return '单次迭代样本数，显存不足时调小，推荐 4 ~ 16';
      case 'LoRA Rank':
        return '低秩矩阵维度，越大拟合越强，推荐 4 ~ 16';
      case '训练步数':
        return '总训练迭代次数，推荐 50 ~ 200';
      default:
        return '';
    }
  }

  Widget _paramField(XlPalette p, _ParamField f) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Tooltip(
          message: _paramTip(f.label),
          preferBelow: false,
          decoration: BoxDecoration(
            color: p.surface,
            borderRadius: BorderRadius.circular(XlRadius.sm),
            border: Border.all(color: p.edgeSoft),
          ),
          textStyle: TextStyle(fontSize: XlFont.micro, color: p.text2, height: 1.4),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: [
              Container(width: 6, height: 6, decoration: AppTheme.glowDot(f.color, size: 6)),
              const SizedBox(width: 6),
              Text(f.label,
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w700,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
        ),
        const SizedBox(height: 6),
        Container(
          decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
          child: TextField(
            controller: f.controller,
            enabled: !_trainingActive,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            style: TextStyle(
              fontSize: XlFont.caption,
              color: p.text1,
              fontWeight: FontWeight.w800,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
            decoration: InputDecoration(
              hintText: f.hint,
              hintStyle: TextStyle(fontSize: XlFont.caption, color: p.decor),
              border: InputBorder.none,
              isDense: true,
              contentPadding: const EdgeInsets.symmetric(vertical: 10),
            ),
          ),
        ),
      ],
    );
  }

  Widget _historyCard(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('训练历史',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              Text('${_history.length} 次',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w800,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
          const SizedBox(height: 4),
          Text('历次微调的 loss 收敛曲线',
              style: TextStyle(
                fontSize: XlFont.label,
                color: p.text3,
                fontWeight: FontWeight.w500,
                letterSpacing: XlLetterSpacing.wider,
              )),
          const SizedBox(height: 16),
          if (_history.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Center(
                child: Text('暂无训练记录',
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.decor,
                      fontWeight: FontWeight.w500,
                    )),
              ),
            )
          else
            for (var i = 0; i < _history.length; i++)
              Padding(
                padding: EdgeInsets.only(bottom: i == _history.length - 1 ? 0 : 14),
                child: _historyTile(p, _history[i]),
              ),
        ],
      ),
    );
  }

  Widget _historyTile(XlPalette p, pb.TrainingHistoryEntry e) {
    final ts = e.timestamp.toInt();
    final ms = ts > 1000000000000 ? ts : ts * 1000;
    final dt = DateTime.fromMillisecondsSinceEpoch(ms);
    final curve = e.lossCurve.toList();
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.sunkenSm(context, r: XlRadius.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            flex: 3,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${dt.month}/${dt.day} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}',
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.text1,
                      fontWeight: FontWeight.w800,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
                const SizedBox(height: 4),
                Text('步数 ${e.steps} · 最终 Loss ${e.finalLoss.toStringAsFixed(3)}',
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text3,
                      fontWeight: FontWeight.w600,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            flex: 4,
            child: Container(
              height: 44,
              decoration: AppTheme.screen(context, r: XlRadius.sm),
              padding: const EdgeInsets.all(4),
              child: curve.length >= 2
                  ? _AnimatedLossCurve(points: curve, palette: p)
                  : Center(
                      child: Text('—',
                          style: TextStyle(fontSize: XlFont.label, color: p.decor)),
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _loadingView(XlPalette p) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _skeleton(p, width: 140, height: 30, radius: 10),
              const SizedBox(width: 12),
              _skeleton(p, width: 70, height: 22, radius: 99),
            ],
          ),
          const SizedBox(height: 22),
          _skeleton(p, width: double.infinity, height: 96, radius: 22),
          const SizedBox(height: 20),
          _skeleton(p, width: double.infinity, height: 150, radius: 22),
          const SizedBox(height: 20),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: _skeleton(p, width: double.infinity, height: 220, radius: 22)),
              const SizedBox(width: 18),
              Expanded(flex: 2, child: _skeleton(p, width: double.infinity, height: 220, radius: 22)),
            ],
          ),
          const SizedBox(height: 20),
          _skeleton(p, width: double.infinity, height: 120, radius: 22),
        ],
      ),
    );
  }

  Widget _skeleton(XlPalette p, {required double width, required double height, double radius = 16}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: p.surfaceLo,
          borderRadius: BorderRadius.circular(radius),
          boxShadow: p.sunkenSm,
        ),
        child: _shimmerLayer(p),
      ),
    );
  }

  Widget _shimmerLayer(XlPalette p) {
    return AnimatedBuilder(
      animation: _pulseCtrl,
      builder: (_, __) {
        return LayoutBuilder(builder: (ctx, c) {
          final w = c.maxWidth;
          final dx = (_pulseCtrl.value * 2.2 - 0.6) * w;
          return Stack(children: [
            Positioned(
              left: dx.clamp(-w * 0.6, w),
              top: 0, bottom: 0,
              width: w * 0.4,
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: [
                    Colors.white.withOpacity(0.0),
                    Colors.white.withOpacity(p.isDark ? 0.06 : 0.18),
                    Colors.white.withOpacity(0.0),
                  ]),
                ),
              ),
            ),
          ]);
        });
      },
    );
  }

  Widget _errorView(XlPalette p) {
    return Center(
      child: Container(
        padding: const EdgeInsets.all(36),
        margin: const EdgeInsets.all(40),
        decoration: AppTheme.neu(context, r: XlRadius.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 62,
              height: 62,
              decoration: BoxDecoration(
                color: p.red.withOpacity(p.isDark ? 0.14 : 0.10),
                shape: BoxShape.circle,
                border: Border.all(color: p.red.withOpacity(0.32), width: 1),
              ),
              child: Icon(Icons.cloud_off_rounded, size: 26, color: p.red),
            ),
            const SizedBox(height: 18),
            Text('后端未连接',
                style: TextStyle(
                  fontSize: XlFont.h6,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                )),
            const SizedBox(height: 6),
            Text('请确认 backend 已启动',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text2,
                  fontWeight: FontWeight.w500,
                )),
            const SizedBox(height: 20),
            _Pressable(
              onTap: _load,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 12),
                decoration: AppTheme.btn(context, r: XlRadius.pill),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.refresh_rounded, size: 15, color: p.btnInk),
                    const SizedBox(width: 8),
                    Text('重试连接',
                        style: TextStyle(
                          fontSize: XlFont.captionSm,
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
    );
  }
}

class _RadarPainter extends CustomPainter {
  final List<pb.TrainingDimension> dims;
  final XlPalette palette;
  final double progress;
  _RadarPainter({
    required this.dims,
    required this.palette,
    required this.progress,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final maxR = size.width / 2 - 32;
    final n = dims.length;
    if (n == 0) return;

    final ringPaint = Paint()
      ..color = palette.text2.withOpacity(0.16)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;

    final ringPaintHi = Paint()
      ..color = palette.text2.withOpacity(0.24)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;

    for (var ring = 1; ring <= 5; ring++) {
      final r = maxR * ring / 5;
      final path = Path();
      for (var i = 0; i < n; i++) {
        final a = -math.pi / 2 + 2 * math.pi * i / n;
        final pp = Offset(center.dx + r * math.cos(a), center.dy + r * math.sin(a));
        if (i == 0) {
          path.moveTo(pp.dx, pp.dy);
        } else {
          path.lineTo(pp.dx, pp.dy);
        }
      }
      path.close();
      canvas.drawPath(path, ring == 5 ? ringPaintHi : ringPaint);
    }

    for (var i = 0; i < n; i++) {
      final a = -math.pi / 2 + 2 * math.pi * i / n;
      final pp = Offset(center.dx + maxR * math.cos(a), center.dy + maxR * math.sin(a));
      canvas.drawLine(center, pp, ringPaint);
    }

    final dataPath = Path();
    for (var i = 0; i < n; i++) {
      final a = -math.pi / 2 + 2 * math.pi * i / n;
      final v = dims[i].ratio * progress;
      final r = maxR * v;
      final pp = Offset(center.dx + r * math.cos(a), center.dy + r * math.sin(a));
      if (i == 0) {
        dataPath.moveTo(pp.dx, pp.dy);
      } else {
        dataPath.lineTo(pp.dx, pp.dy);
      }
    }
    dataPath.close();

    final fillPaint = Paint()
      ..shader = RadialGradient(
        colors: [palette.pink.withOpacity(0.32), palette.pink.withOpacity(0.08)],
      ).createShader(Rect.fromCircle(center: center, radius: maxR));

    final strokePaint = Paint()
      ..color = palette.pink
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeJoin = StrokeJoin.round;

    canvas.drawPath(dataPath, fillPaint);
    canvas.drawPath(dataPath, strokePaint);

    for (var i = 0; i < n; i++) {
      final a = -math.pi / 2 + 2 * math.pi * i / n;
      final v = dims[i].ratio * progress;
      final r = maxR * v;
      final pp = Offset(center.dx + r * math.cos(a), center.dy + r * math.sin(a));
      canvas.drawCircle(pp, 6, Paint()..color = palette.pink.withOpacity(0.25));
      canvas.drawCircle(pp, 4, Paint()..color = palette.gold);
      canvas.drawCircle(pp, 2, Paint()..color = palette.bg);
    }

    final labelPainter = TextPainter(textDirection: TextDirection.ltr);
    for (var i = 0; i < n; i++) {
      final a = -math.pi / 2 + 2 * math.pi * i / n;
      final lr = maxR + 22;
      final pp = Offset(center.dx + lr * math.cos(a), center.dy + lr * math.sin(a));
      labelPainter.text = TextSpan(
        text: dims[i].displayName,
        style: TextStyle(
          fontSize: 11,
          color: palette.text1,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.4,
        ),
      );
      labelPainter.layout();
      labelPainter.paint(
        canvas,
        Offset(pp.dx - labelPainter.width / 2, pp.dy - labelPainter.height / 2),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _RadarPainter old) =>
      old.dims != dims || old.palette != palette || old.progress != progress;
}

enum _LogLevel { info, dim, ok, warn, error }

class _LogLine {
  final String text;
  final _LogLevel level;
  const _LogLine(this.text, this.level);
}

class _Preset {
  final String name;
  final String desc;
  final String color;
  final IconData icon;
  final double intensity;
  const _Preset(this.name, this.desc, this.color, this.icon, this.intensity);
}

class _Milestone {
  final String name;
  final String status;
  final bool done;
  final String color;
  const _Milestone(this.name, this.status, this.done, this.color);
}

class _ParamField {
  final String label;
  final String hint;
  final TextEditingController controller;
  final Color color;
  const _ParamField(this.label, this.hint, this.controller, this.color);
}

class _LossCurvePainter extends CustomPainter {
  final List<double> points;
  final XlPalette palette;
  final double progress;
  _LossCurvePainter({required this.points, required this.palette, this.progress = 1.0});

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2) return;
    final count = (points.length * progress).clamp(2.0, points.length.toDouble()).round();
    final pts = points.sublist(0, count);
    var minV = pts.reduce(math.min);
    var maxV = pts.reduce(math.max);
    if ((maxV - minV).abs() < 0.001) {
      maxV = minV + 1.0;
    }
    final path = Path();
    for (var i = 0; i < pts.length; i++) {
      final x = size.width * i / (points.length - 1);
      final v = (pts[i] - minV) / (maxV - minV);
      final y = size.height - 4 - v * (size.height - 8);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    final stroke = Paint()
      ..color = palette.pink
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..strokeJoin = StrokeJoin.round
      ..strokeCap = StrokeCap.round;
    canvas.drawPath(path, stroke);
    final lastY = size.height - 4 - ((pts.last - minV) / (maxV - minV)) * (size.height - 8);
    canvas.drawCircle(Offset(size.width * (pts.length - 1) / (points.length - 1), lastY), 2.5, Paint()..color = palette.gold);
  }

  @override
  bool shouldRepaint(covariant _LossCurvePainter old) =>
      old.points != points || old.palette != palette || old.progress != progress;
}

class _AnimatedLossCurve extends StatefulWidget {
  final List<double> points;
  final XlPalette palette;
  const _AnimatedLossCurve({required this.points, required this.palette});
  @override
  State<_AnimatedLossCurve> createState() => _AnimatedLossCurveState();
}

class _AnimatedLossCurveState extends State<_AnimatedLossCurve> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 800),
  )..forward();
  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) => CustomPaint(
        painter: _LossCurvePainter(
          points: widget.points,
          palette: widget.palette,
          progress: CurvedAnimation(parent: _c, curve: XlCurve.easeOut).value,
        ),
      ),
    );
  }
}

class _Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  const _Pressable({super.key, required this.child, this.onTap, this.scale = 0.96});
  @override
  State<_Pressable> createState() => _PressableState();
}

class _PressableState extends State<_Pressable> {
  bool _down = false;
  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: (_) => setState(() => _down = true),
      onPointerUp: (_) => setState(() => _down = false),
      onPointerCancel: (_) => setState(() => _down = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedScale(
          scale: _down ? widget.scale : 1.0,
          duration: XlDuration.micro,
          curve: XlCurve.standard,
          child: widget.child,
        ),
      ),
    );
  }
}

class _ShimmerSweep extends StatelessWidget {
  final Animation<double> anim;
  const _ShimmerSweep({required this.anim});
  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: anim,
      builder: (_, __) {
        return LayoutBuilder(builder: (ctx, c) {
          final w = c.maxWidth;
          final dx = (anim.value * 2.2 - 0.5) * w;
          return Stack(children: [
            Positioned(
              left: dx.clamp(-w * 0.5, w),
              top: 0, bottom: 0,
              width: w * 0.35,
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: [
                    Colors.white.withOpacity(0.0),
                    Colors.white.withOpacity(0.35),
                    Colors.white.withOpacity(0.0),
                  ]),
                ),
              ),
            ),
          ]);
        });
      },
    );
  }
}

class _LogEntrance extends StatefulWidget {
  final Widget child;
  const _LogEntrance({required this.child});
  @override
  State<_LogEntrance> createState() => _LogEntranceState();
}

class _LogEntranceState extends State<_LogEntrance> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 350),
  )..forward();
  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) => Opacity(
        opacity: _c.value,
        child: Transform.translate(
          offset: Offset(0, (1 - _c.value) * 8),
          child: widget.child,
        ),
      ),
    );
  }
}