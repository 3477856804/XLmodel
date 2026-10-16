import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;
import '../services/local_store.dart';
import '../widgets/xl_loss_chart.dart';

class TrainingPage extends StatefulWidget {
  const TrainingPage({super.key});
  @override
  State<TrainingPage> createState() => _TrainingPageState();
}

class _TrainingPageState extends State<TrainingPage>
    with TickerProviderStateMixin {
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
  bool _cancelRequested = false;
  String _cancelReason = '';
  int _rtStep = 0;
  int _rtTotalSteps = 0;
  double _rtLoss = 0.0;
  String? _trainError;
  // 后端元数据（training:status / :env / :adapter / :history）——
  // 界面所有「是不是真训练、跑在哪、写到哪」的判断只能来自这里，
  // 拿不到就显示「未获取」，绝不在前端推断。
  Map<String, dynamic>? _trainStatus;
  Map<String, dynamic>? _trainEnv;
  Map<String, dynamic>? _adapterInfo;
  List<Map<String, dynamic>> _historyRecords = [];
  String? _metaError;
  final List<double> _lossPoints = [];
  final List<double?> _evalPoints = [];
  // 图表用不可变快照：_lossPoints 每步都在变，直接把它包成 unmodifiable 会让
  // XlLossChart 每次 build 都认为是新数据、重启动画。只在点数真的变了时换引用。
  List<double> _chartPoints = const [];
  List<double?> _chartEval = const [];
  List<pb.TrainingHistoryEntry> _history = [];
  final List<_SavedPreset> _savedPresets = [];
  final TextEditingController _presetNameCtrl = TextEditingController();

  static const _presets = <_Preset>[
    _Preset('轻量', 'r=4 · 3 epochs', 'pink', Icons.bolt_rounded, 0.30),
    _Preset('均衡', 'r=8 · 5 epochs', 'gold', Icons.tune_rounded, 0.55),
    _Preset(
        '深度', 'r=16 · 10 epochs', 'violet', Icons.auto_awesome_rounded, 0.85),
  ];

  List<_Milestone> _buildMilestones() {
    final inter = _growth?.totalInteractions ?? 0;
    final gen = _growth?.currentGeneration ?? 0;
    final rows = _historyRows;
    final trained = rows.any((r) => r['ok'] == true || r['real'] == true) ||
        (rows.isEmpty ? _history.isNotEmpty : false);
    return <_Milestone>[
      _Milestone('首次对话', inter > 0 ? '已完成' : '未开始', inter > 0, 'pink'),
      _Milestone('累计 10 轮对话', inter >= 10 ? '已达成' : '$inter / 10', inter >= 10,
          'gold'),
      _Milestone('首次微调', trained ? '已完成' : '未触发', trained, 'violet'),
      _Milestone('进化第 2 代', gen >= 2 ? '已达成' : '$gen 代', gen >= 2, 'green'),
    ];
  }

  Timer? _statusTicker;
  bool _metaBusy = false;

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(
        duration: const Duration(milliseconds: 900), vsync: this);
    _radarCtrl = AnimationController(
        duration: const Duration(milliseconds: 1100), vsync: this);
    _pulseCtrl = XlEffects.bindAmbient(
        AnimationController(duration: const Duration(seconds: 4), vsync: this));
    _enterAnim = CurvedAnimation(parent: _enterCtrl, curve: XlCurve.easeOut);
    _radarAnim = CurvedAnimation(parent: _radarCtrl, curve: XlCurve.easeOut);
    _enterCtrl.forward();
    _loadPresets();
    _load();
  }

  @override
  void dispose() {
    _statusTicker?.cancel();
    _enterCtrl.dispose();
    _radarCtrl.dispose();
    _pulseCtrl.dispose();
    _logScroll.dispose();
    _lrCtrl.dispose();
    _bsCtrl.dispose();
    _rankCtrl.dispose();
    _stepsCtrl.dispose();
    _presetNameCtrl.dispose();
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
      final h = await XlClient.stub
          .safe(() => XlClient.stub.getTrainingHistory(pb.Empty()));
      if (!mounted) return;
      setState(() {
        _data = r;
        _growth = g;
        _history = h?.entries.toList() ?? [];
        _loading = false;
      });
      _radarCtrl.forward(from: 0);
      // 元数据（是否真训练 / 设备 / 适配器落点 / 取消状态）走 training: 指令族。
      // 失败不把整页变错误屏：卡片自己显示「未获取」。
      unawaited(_loadMeta());
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  /// 从后端取训练元数据。cancel_requested / kind / adapter_dir 只有这里有真值，
  /// 前端不许自己推断「是不是演练」「停没停」。
  /// [light] 只取 status 快照（训练中的定时轮询用，避免每 2 秒扫一遍磁盘目录）。
  Future<void> _loadMeta({bool light = false}) async {
    if (_metaBusy) return;
    _metaBusy = true;
    try {
      final status = await XlClient.stub.safe(() => XlClient.stub
          .command('training:status', opt: const XlCallOptions(silent: true)));
      Map<String, dynamic>? env, ad;
      List<Map<String, dynamic>> recs = const [];
      if (!light) {
        env = _json((await XlClient.stub.safe(() => XlClient.stub.command(
                'training:env',
                opt: const XlCallOptions(silent: true))))
            ?.output);
        ad = _json((await XlClient.stub.safe(() => XlClient.stub.command(
                'training:adapter',
                opt: const XlCallOptions(silent: true))))
            ?.output);
        recs = _jsonList(
            (await XlClient.stub.safe(() => XlClient.stub.command(
                    'training:history 20',
                    opt: const XlCallOptions(silent: true))))
                ?.output,
            'records');
      }
      if (!mounted) return;
      setState(() {
        _trainStatus = _json(status?.output);
        if (!light) {
          _trainEnv = env;
          _adapterInfo = ad;
          _historyRecords = recs;
        }
        if (_trainStatus == null && _trainEnv == null && _adapterInfo == null) {
          _metaError = '后端未返回训练元数据（training: 指令族不可用）';
        } else {
          _metaError = null;
        }
        _cancelRequested = _trainStatus?['cancel_requested'] == true;
        final r = _trainStatus?['cancel_reason'];
        if (r is String && r.isNotEmpty) _cancelReason = r;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _metaError = '训练元数据读取失败：$e');
    } finally {
      _metaBusy = false;
    }
  }

  /// 训练期间定时轮询后端快照：即使前端断流/重进页面，进度与取消状态也不会丢。
  void _syncStatusTicker() {
    if (_trainingActive) {
      _statusTicker ??= Timer.periodic(const Duration(seconds: 2), (_) {
        unawaited(_loadMeta(light: true));
      });
    } else {
      _statusTicker?.cancel();
      _statusTicker = null;
    }
  }

  Map<String, dynamic>? _json(String? raw) {
    final d = _jsonRaw(raw);
    return (d != null && d['ok'] == true) ? d : null;
  }

  /// 不要求 ok==true 的解码：失败响应里的 reason / error 同样是真话，
  /// 比如「当前没有正在运行的训练任务」，不能因为 ok=false 就丢掉。
  Map<String, dynamic>? _jsonRaw(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    try {
      final d = jsonDecode(raw);
      return d is Map ? Map<String, dynamic>.from(d) : null;
    } catch (_) {
      return null;
    }
  }

  List<Map<String, dynamic>> _jsonList(String? raw, String key) {
    final rows = _json(raw)?[key];
    if (rows is! List) return const [];
    return rows
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }

  String _metaText(Object? v, {String fallback = '未获取'}) {
    if (v == null) return fallback;
    final s = v.toString().trim();
    return s.isEmpty ? fallback : s;
  }

  void _loadPresets() async {
    final data = await LocalStore.readJson('training_presets.json');
    final list = data['presets'];
    if (!mounted) return;
    if (list is List) {
      setState(() {
        _savedPresets.clear();
        for (final e in list) {
          if (e is Map) {
            _savedPresets.add(_SavedPreset(
              name: (e['name'] ?? '').toString(),
              lr: (e['lr'] is num) ? (e['lr'] as num).toDouble() : 0.0002,
              bs: (e['bs'] is num) ? (e['bs'] as num).toInt() : 4,
              rank: (e['rank'] is num) ? (e['rank'] as num).toInt() : 8,
              steps: (e['steps'] is num) ? (e['steps'] as num).toInt() : 100,
            ));
          }
        }
      });
    }
  }

  Future<void> _persistPresets() async {
    await LocalStore.writeJson('training_presets.json', {
      'presets': _savedPresets
          .map((s) => {
                'name': s.name,
                'lr': s.lr,
                'bs': s.bs,
                'rank': s.rank,
                'steps': s.steps
              })
          .toList(),
    });
  }

  Color _colorOf(XlPalette p, String key) {
    switch (key) {
      case 'pink':
        return p.pink;
      case 'gold':
        return p.gold;
      case 'violet':
        return p.violet;
      case 'green':
        return p.green;
      case 'red':
        return p.red;
      case 'blue':
        return p.blue;
      default:
        return p.pink;
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    if (_loading) return _loadingView(p);
    if (_data == null) return _errorView(p);
    return Stack(
      children: [
        Positioned.fill(
            child: AppTheme.aurora(context, child: const SizedBox.shrink())),
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
    final isMobile = MediaQuery.of(context).size.width < 600;
    final hPad = isMobile ? 16.0 : 26.0;
    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(hPad, 6, hPad, 30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _stagger(0, _heroRow(p)),
          const SizedBox(height: 22),
          _stagger(1, _statusBanner(p)),
          const SizedBox(height: 20),
          _stagger(2, _paramsCard(p)),
          const SizedBox(height: 20),
          _stagger(3, _savedPresetsCard(p)),
          const SizedBox(height: 20),
          _stagger(4, LayoutBuilder(
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
          _stagger(6, _envCard(p)),
          const SizedBox(height: 20),
          _stagger(7, _historyCard(p)),
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
        final t = Interval(start, end, curve: Curves.easeOut)
            .transform(_enterAnim.value);
        return Opacity(
          opacity: t,
          child: Transform.translate(
              offset: Offset(0, (1 - t) * 18), child: child),
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
        final t = XlEffects.enabled ? _pulseCtrl.value : 0.0;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: color.withOpacity(p.isDark ? 0.14 : 0.10),
            borderRadius: BorderRadius.circular(XlRadius.pill),
            border: Border.all(color: color.withOpacity(0.32), width: 1),
            boxShadow: training
                ? [
                    BoxShadow(
                        color: color.withOpacity(0.25 + t * 0.15),
                        blurRadius: 12,
                        spreadRadius: -2)
                  ]
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
    final isMobile = MediaQuery.of(context).size.width < 600;
    return Container(
      padding: EdgeInsets.all(isMobile ? 16 : 20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              AnimatedBuilder(
                animation: _pulseCtrl,
                builder: (_, __) {
                  final t = XlEffects.enabled ? _pulseCtrl.value : 0.0;
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
                          gradient: LinearGradient(
                              colors: [color, color.withOpacity(0.75)]),
                          shape: BoxShape.circle,
                          border: Border.all(
                              color: Colors.white
                                  .withOpacity(p.isDark ? 0.32 : 0.48),
                              width: 1.5),
                          boxShadow: [
                            ...p.raisedXs,
                            BoxShadow(
                                color: color.withOpacity(0.4),
                                blurRadius: 18,
                                spreadRadius: -4)
                          ],
                        ),
                        child: Icon(
                          training
                              ? Icons.auto_awesome_rounded
                              : Icons.pause_rounded,
                          color: p.btnInk,
                          size: 20,
                        ),
                      ),
                    ],
                  );
                },
              ),
              SizedBox(width: isMobile ? 12 : 18),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(training ? '正在训练' : '等待指令',
                              style: TextStyle(
                                fontSize: XlFont.h6,
                                fontWeight: FontWeight.w800,
                                color: p.text1,
                                letterSpacing: XlLetterSpacing.normal,
                              )),
                        ),
                        const SizedBox(width: 8),
                        _tinyChip(p, training ? 'ACTIVE' : 'STANDBY', color),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(_data!.displayStatus,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: XlFont.caption,
                          color: p.text2,
                          fontWeight: FontWeight.w500,
                          letterSpacing: XlLetterSpacing.wide,
                        )),
                  ],
                ),
              ),
              if (!isMobile) ...[
                const Spacer(),
                AnimatedSwitcher(
                  duration: XlDuration.normal,
                  transitionBuilder: (child, anim) => ScaleTransition(
                    scale: anim,
                    child: RotationTransition(
                        turns: Tween(begin: 0.85, end: 1.0).animate(anim),
                        child: child),
                  ),
                  child: _trainingActive
                      ? _stopBtn(p, key: const ValueKey('stop'))
                      : (_data!.isTraining
                          ? _epochIndicator(p, key: const ValueKey('epoch'))
                          : _startBtn(p, key: const ValueKey('start'))),
                ),
              ],
            ],
          ),
          if (isMobile) ...[
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: AnimatedSwitcher(
                duration: XlDuration.normal,
                transitionBuilder: (child, anim) =>
                    FadeTransition(opacity: anim, child: child),
                child: _trainingActive
                    ? Center(child: _stopBtn(p, key: const ValueKey('stop')))
                    : (_data!.isTraining
                        ? Center(
                            child: _epochIndicator(p,
                                key: const ValueKey('epoch')))
                        : Center(
                            child: _startBtn(p, key: const ValueKey('start')))),
              ),
            ),
          ],
          if (_trainingActive) ...[
            const SizedBox(height: 16),
            if (_trainError != null)
              _trainErrorCard(p)
            else ...[
              _liveStatusBadge(p),
              const SizedBox(height: 10),
              _rtProgress(p),
              _liveLossPanel(p),
            ],
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
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
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

  /// 实时状态徽标：内容全部来自后端 training:status / training:env。
  ///
  /// 旧版这里是个写死的「演练模式（不产生真实权重）」标记，靠匹配 status
  /// 里的 `[演练]` 前缀点亮——trainer 早就不再有演练分支了，所以那个标记
  /// 永远不亮，反而把「这次训练到底真不真」这个关键信息变成前端口头声明。
  /// 现在改为如实展示后端给出的 kind / device / 取消状态，取不到就说取不到。
  Widget _liveStatusBadge(XlPalette p) {
    String text;
    String colorKey;
    IconData icon;
    if (_cancelRequested) {
      text =
          '正在取消（当前 step 结束后退出）${_cancelReason.isEmpty ? "" : " · ${_cancelReason}"}';
      colorKey = 'red';
      icon = Icons.stop_circle_outlined;
    } else if (_trainStatus == null) {
      text = '后端状态未获取（training:status 不可用）';
      colorKey = 'gold';
      icon = Icons.help_outline_rounded;
    } else {
      final kind = (_trainStatus?['kind'] ?? '').toString();
      final kindLabel = {
        'init': '准备中',
        'info': '环境就绪',
        'progress': '训练中',
        'eval': '验证中',
        'done': '已结束',
        'error': '失败',
      }[kind];
      final bits = <String>[
        if (kindLabel != null) kindLabel else '状态未知',
        if (_trainStatus?['real'] == true) '真实权重' else '未确认训练',
      ];
      // 后端读取消状态失败时会带 cancel_state_error：此时 cancel_requested
      // 恒为 False，不能让它看起来像「没人在取消」，要点明这一项没确认。
      final cse = _trainStatus?['cancel_state_error'];
      if (cse is String && cse.isNotEmpty) bits.add('取消状态未确认');
      final dev = _trainEnv?['device'];
      if (dev is String && dev.isNotEmpty) bits.add('device=$dev');
      final quant = _trainEnv?['bitsandbytes'];
      if (quant is String && quant.isNotEmpty) bits.add('QLoRA');
      text = bits.join(' · ');
      final failed = kind == 'error' || _trainStatus?['error'] != null;
      colorKey = failed ? 'red' : (kind == 'done' ? 'green' : 'pink');
      icon = failed ? Icons.error_outline_rounded : Icons.insights_rounded;
    }
    final color = _colorOf(p, colorKey);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(XlRadius.sm),
        border: Border.all(color: color.withOpacity(0.45), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Flexible(
            child: Text(text,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: color,
                  fontWeight: FontWeight.w800,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ),
        ],
      ),
    );
  }

  Widget _trainErrorCard(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.screen(context, r: XlRadius.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.error_outline_rounded, size: 18, color: p.pink),
              const SizedBox(width: 8),
              Text('训练无法启动',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    color: p.pink,
                    fontWeight: FontWeight.w800,
                  )),
            ],
          ),
          const SizedBox(height: 10),
          Text(_trainError ?? '',
              style: TextStyle(
                fontSize: XlFont.label,
                color: p.text2,
                fontWeight: FontWeight.w600,
                height: 1.5,
              )),
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

  /// 预计耗时：只有后端实测过（训练历史里的 metadata.sec_per_step）才给数字。
  /// 旧代码是 steps * 0.6 秒写死的，跟真实设备/数据量无关，属于编出来的承诺。
  String _estimateLabel(int steps) {
    final sps = _measuredSecPerStep;
    if (sps == null) return '首次训练：暂无实测耗时';
    final secs = steps * sps;
    if (secs < 60) return '按上次实测约 ${secs.toStringAsFixed(0)} 秒';
    return '按上次实测约 ${(secs / 60).toStringAsFixed(1)} 分钟';
  }

  double? get _measuredSecPerStep {
    // _historyRecords 已按「新→旧」返回（training:history 里 [::-1]）
    for (final r in _historyRecords) {
      final meta = r['metadata'];
      if (meta is! Map) continue;
      final v = meta['sec_per_step'];
      if (v is num && v > 0) return v.toDouble();
    }
    return null;
  }

  Widget _startBtn(XlPalette p, {Key? key}) {
    final steps = int.tryParse(_stepsCtrl.text.trim()) ?? 100;
    final est = _estimateLabel(steps);
    // 前置校验：训练栈（torch/transformers/peft）缺失时不再假装能开始。
    // 打包版未内置 torch，点击后只会走到 trainer 的 ImportError 分支，
    // 而那句「请 pip install」在打包态没有 pip 可执行 —— 在这里就把
    // 真实原因说清楚，让用户知道该换源码模式而不是反复重点。
    String? blocked;
    final env = _trainEnv;
    if (env != null) {
      final missing = <String>[];
      for (final k in const ['torch', 'transformers', 'peft']) {
        final v = env[k]?.toString();
        if (v == null || v.isEmpty || v == 'None') missing.add(k);
      }
      if (missing.isNotEmpty) {
        blocked = env['frozen'] == true
            ? '当前为打包版，未内置 PyTorch 训练栈（缺少：${missing.join('、')}），'
                  '且产物内没有 pip 无法在线补装。请使用源码模式运行 python main.py，'
                  '或改用内置训练栈的完整版后端。'
            : '训练栈未安装（缺少：${missing.join('、')}）。'
                  '请先在设置页「依赖自愈」安装（torch 档需显式确认），'
                  '或运行 python main.py --install-deps torch force。';
      }
    }
    return Column(
      key: key,
      crossAxisAlignment: CrossAxisAlignment.end,
      mainAxisSize: MainAxisSize.min,
      children: [
        _Pressable(
          onTap: blocked == null
              ? _startTraining
              : () => setState(() => _trainError = blocked),
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
        Text(est,
            style: TextStyle(
              fontSize: XlFont.micro,
              color: _measuredSecPerStep == null ? p.text3 : p.gold,
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
          border: Border.all(
              color: Colors.white.withOpacity(p.isDark ? 0.32 : 0.22),
              width: 1),
          boxShadow: [
            ...p.raisedXs,
            BoxShadow(
                color: p.red.withOpacity(0.35),
                blurRadius: 12,
                spreadRadius: -2)
          ],
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

  /// 后端 server 按事件类型给 status 加前缀：[准备] / [环境] / [验证] / [完成]。
  /// proto 的 TrainingProgress 只有 step/total/loss/status 四个字段（约定不改
  /// proto），所以 kind 只能从前缀还原；eval loss 同样只能从文案里取。
  /// 取不到就返回 null，绝不猜。
  static const _kindByPrefix = <String, String>{
    '[准备]': 'init',
    '[环境]': 'info',
    '[验证]': 'eval',
    '[告警]': 'warning',
    '[完成]': 'done',
  };

  static String _kindOf(String status) {
    for (final e in _kindByPrefix.entries) {
      if (status.startsWith(e.key)) return e.value;
    }
    return 'progress';
  }

  static double? _evalLossOf(String status) {
    final m = RegExp(r'验证\s*loss\s*=\s*(\d+(?:\.\d+)?)').firstMatch(status);
    return m == null ? null : double.tryParse(m.group(1)!);
  }

  Future<void> _startTraining() async {
    if (_trainingActive) return;
    final lr = double.tryParse(_lrCtrl.text.trim()) ?? 0.0002;
    final bs = int.tryParse(_bsCtrl.text.trim()) ?? 4;
    final rank = int.tryParse(_rankCtrl.text.trim()) ?? 8;
    final steps = int.tryParse(_stepsCtrl.text.trim()) ?? 100;
    setState(() {
      _trainingActive = true;
      _rtStep = 0;
      _rtTotalSteps = steps;
      _rtLoss = 0.0;
      _cancelRequested = false;
      _cancelReason = '';
      _trainError = null;
      _lossPoints.clear();
      _evalPoints.clear();
      _chartPoints = const [];
      _chartEval = const [];
      _logs.add(_LogLine(
          '[start] 初始化 LoRA 适配器 · lr=$lr bs=$bs r=$rank steps=$steps',
          _LogLevel.warn));
      _logs.add(_LogLine(
          '[preset] ${_presets[_selectedPreset].desc}', _LogLevel.dim));
    });
    _syncStatusTicker();
    _scrollLogBottom();
    var sawDone = false;
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
        // 页面被关掉时停止刷新 UI；后端仍在按自己的节奏跑（要真停得点停止）。
        if (!mounted) break;
        final status = p.status;
        if (status.startsWith('error:') || status.startsWith('failed:')) {
          final msg = status.substring(status.indexOf(':') + 1).trim();
          setState(() {
            _trainError = msg;
            _logs.add(_LogLine('[error] $msg', _LogLevel.error));
          });
          _scrollLogBottom();
          break;
        }
        final kind = _kindOf(status);
        if (kind == 'done') sawDone = true;
        final evalLoss = kind == 'eval' ? _evalLossOf(status) : null;
        setState(() {
          _rtStep = p.step;
          _rtTotalSteps = p.totalSteps <= 0 ? steps : p.totalSteps;
          _rtLoss = p.loss;
          // 曲线点只在真实数值事件上采集：准备/环境事件没有 loss 含义；
          // done 事件只是把最后一个 step 的 loss 重发一遍，不再追加。
          if ((kind == 'progress' || kind == 'eval') && p.loss > 0) {
            if (kind == 'progress') _lossPoints.add(p.loss);
            if (kind == 'eval' && evalLoss != null) {
              // eval 的 x 轴对齐到当前 step（points 下标），中间补 null
              while (_evalPoints.length < _lossPoints.length - 1) {
                _evalPoints.add(null);
              }
              _evalPoints.add(evalLoss);
            }
          }
          // 非 step 事件（准备/环境/完成）一律如实打日志，不再靠 substring 猜
          if (kind != 'progress') {
            _logs.add(_LogLine(
                status, kind == 'done' ? _LogLevel.ok : _LogLevel.dim));
          } else if (p.step % 10 == 0 || p.step == _rtTotalSteps) {
            _logs.add(_LogLine(
                '[step] ${p.step}/${p.totalSteps} loss=${p.loss.toStringAsFixed(3)}',
                _LogLevel.info));
          }
          // 只有数值事件才换图表快照引用；done/info 等事件重绘会让曲线动画
          // 白白重启（快照引用相同 → XlLossChart 的 didUpdateWidget 不触发）。
          if (kind == 'progress' || kind == 'eval') {
            _chartPoints = List<double>.unmodifiable(_lossPoints);
            _chartEval = List<double?>.unmodifiable(_evalPoints);
          }
        });
        _scrollLogBottom();
      }
    } catch (e) {
      if (mounted) {
        setState(() => _logs.add(_LogLine('[error] $e', _LogLevel.error)));
        _scrollLogBottom();
      }
    } finally {
      // 流结束（完成 / 取消 / 报错 / 断开）都要停掉轮询，避免后台空转
      _statusTicker?.cancel();
      _statusTicker = null;
      if (mounted) {
        setState(() {
          _trainingActive = false;
          if (_trainError == null && !sawDone) {
            _logs.add(
                _LogLine('[warn] 训练流提前结束（未收到完成事件，进度以训练记录为准）', _LogLevel.warn));
          }
        });
        _scrollLogBottom();
        _load();
      }
    }
  }

  /// 真的通知后端停：training:cancel 让 trainer 在当前 step 结束时退出并落盘。
  /// 旧实现只置了一个本地布尔，gRPC 生成器继续跑，CPU 照烧——那是假停止。
  Future<void> _cancelOnBackend() async {
    try {
      final r = await XlClient.stub.command(
        'training:cancel 用户在界面点了停止',
        opt: const XlCallOptions(timeout: Duration(seconds: 8)),
      );
      final d = _jsonRaw(r.output) ?? const {'ok': false, 'reason': ''};
      final ok = d['ok'] == true;
      final reason = (d['reason'] ?? d['error'] ?? '').toString();
      final n = (d['cancelled'] as num?)?.toInt();
      if (!mounted) return;
      setState(() {
        _cancelRequested = ok;
        if (reason.isNotEmpty) _cancelReason = reason;
        _logs.add(_LogLine(
            '${ok ? "[stop]" : "[stop-fail]"} $reason'
            '${(ok && n != null) ? "（登记 $n 个训练任务）" : ""}',
            ok ? _LogLevel.warn : _LogLevel.error));
      });
      _scrollLogBottom();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        // 后端没停成，前端不许装作停了——回到「可再次点停止」状态
        _cancelRequested = false;
        _logs.add(_LogLine('[stop-fail] 取消请求发送失败：$e（训练继续）', _LogLevel.error));
      });
      _scrollLogBottom();
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
                            gradient: LinearGradient(
                                colors: [p.red, p.red.withOpacity(0.85)]),
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
    if (_cancelRequested) return;
    // 先让后端真停（trainer 跑完当前 step 退出并落盘），流自己会结束。
    setState(() => _cancelRequested = true);
    _logs.add(_LogLine('[stop] 已请求后端停止，等待当前 step 结束', _LogLevel.warn));
    _scrollLogBottom();
    await _cancelOnBackend();
    await _loadMeta();
  }

  /// API 接入设置入口：打开对话框，关闭后刷新训练元数据。
  Future<void> _openApiSettings() async {
    await showDialog<void>(
      context: context,
      barrierColor: XlPalette.of(context).scrim,
      builder: (_) => const _ApiSettingsDialog(),
    );
    if (mounted) unawaited(_loadMeta());
  }

  Future<void> _saveCurrentPreset() async {
    _presetNameCtrl.text = '';
    final p = XlPalette.of(context);
    final name = await showDialog<String>(
      context: context,
      barrierColor: p.scrim,
      builder: (ctx) {
        final pp = XlPalette.of(ctx);
        return Dialog(
          backgroundColor: Colors.transparent,
          elevation: 0,
          child: Container(
            width: 360,
            padding: const EdgeInsets.all(22),
            decoration: AppTheme.neuLg(ctx, r: XlRadius.xxxl),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('保存参数预设',
                    style: TextStyle(
                      fontSize: XlFont.h6,
                      fontWeight: FontWeight.w800,
                      color: pp.text1,
                    )),
                const SizedBox(height: 12),
                Container(
                  decoration: AppTheme.sunkenXs(ctx, r: XlRadius.md),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
                  child: TextField(
                    controller: _presetNameCtrl,
                    autofocus: true,
                    style: TextStyle(
                        fontSize: XlFont.bodySm,
                        color: pp.text1,
                        fontWeight: FontWeight.w700),
                    decoration: InputDecoration(
                      border: InputBorder.none,
                      isDense: true,
                      hintText: '例如: 日常微调',
                      hintStyle:
                          TextStyle(fontSize: XlFont.bodySm, color: pp.decor),
                      contentPadding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                Row(children: [
                  Expanded(
                    child: _Pressable(
                      onTap: () => Navigator.pop(ctx),
                      scale: 0.95,
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 11),
                        decoration: AppTheme.ghost(ctx, r: XlRadius.pill),
                        child: Center(
                          child: Text('取消',
                              style: TextStyle(
                                  fontSize: XlFont.captionSm,
                                  fontWeight: FontWeight.w800,
                                  color: pp.text1)),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _Pressable(
                      scale: 0.95,
                      onTap: () =>
                          Navigator.pop(ctx, _presetNameCtrl.text.trim()),
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 11),
                        decoration: AppTheme.btn(ctx, r: XlRadius.pill),
                        child: Center(
                          child: Text('保存',
                              style: TextStyle(
                                  fontSize: XlFont.captionSm,
                                  fontWeight: FontWeight.w800,
                                  color: pp.btnInk)),
                        ),
                      ),
                    ),
                  ),
                ]),
              ],
            ),
          ),
        );
      },
    );
    if (name == null || name.isEmpty) return;
    setState(() {
      _savedPresets.add(_SavedPreset(
        name: name,
        lr: double.tryParse(_lrCtrl.text.trim()) ?? 0.0002,
        bs: int.tryParse(_bsCtrl.text.trim()) ?? 4,
        rank: int.tryParse(_rankCtrl.text.trim()) ?? 8,
        steps: int.tryParse(_stepsCtrl.text.trim()) ?? 100,
      ));
    });
    _persistPresets();
  }

  void _applySavedPreset(_SavedPreset s) {
    setState(() {
      _lrCtrl.text = s.lr.toString();
      _bsCtrl.text = s.bs.toString();
      _rankCtrl.text = s.rank.toString();
      _stepsCtrl.text = s.steps.toString();
    });
    final p = XlPalette.of(context);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      behavior: SnackBarBehavior.floating,
      backgroundColor: p.surface,
      elevation: 0,
      duration: const Duration(milliseconds: 1100),
      content: Text('已载入预设: ${s.name}',
          style: TextStyle(
              color: p.text1,
              fontSize: XlFont.captionSm,
              fontWeight: FontWeight.w700)),
    ));
  }

  Widget _savedPresetsCard(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text('我的参数预设',
                style: TextStyle(
                  fontSize: XlFont.h6,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                  letterSpacing: XlLetterSpacing.normal,
                )),
            const Spacer(),
            _Pressable(
              scale: 0.92,
              onTap: _trainingActive ? null : _saveCurrentPreset,
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                decoration: AppTheme.btn(context, r: XlRadius.pill),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(Icons.bookmark_add_rounded, size: 13, color: p.btnInk),
                  const SizedBox(width: 6),
                  Text('保存当前',
                      style: TextStyle(
                        fontSize: XlFont.label,
                        fontWeight: FontWeight.w800,
                        color: p.btnInk,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                ]),
              ),
            ),
          ]),
          const SizedBox(height: 14),
          if (_savedPresets.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text('尚未保存预设，调整参数后点击"保存当前"',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    color: p.decor,
                    fontWeight: FontWeight.w500,
                  )),
            )
          else
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: _savedPresets.map((s) {
                return _Pressable(
                  scale: 0.95,
                  onTap: _trainingActive ? null : () => _applySavedPreset(s),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 10),
                    decoration: AppTheme.accentSoft(context, r: XlRadius.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Row(mainAxisSize: MainAxisSize.min, children: [
                          Icon(Icons.bookmark_rounded, size: 13, color: p.pink),
                          const SizedBox(width: 6),
                          Text(s.name,
                              style: TextStyle(
                                fontSize: XlFont.captionSm,
                                color: p.text1,
                                fontWeight: FontWeight.w800,
                              )),
                          const SizedBox(width: 8),
                          _Pressable(
                            scale: 0.9,
                            onTap: () =>
                                setState(() => _savedPresets.remove(s)),
                            child: Icon(Icons.close_rounded,
                                size: 12, color: p.text3),
                          ),
                        ]),
                        const SizedBox(height: 4),
                        Text(
                            'lr=${s.lr} bs=${s.bs} r=${s.rank} steps=${s.steps}',
                            style: TextStyle(
                              fontSize: XlFont.micro,
                              color: p.gold,
                              fontWeight: FontWeight.w700,
                              fontFeatures: const [
                                FontFeature.tabularFigures()
                              ],
                              letterSpacing: XlLetterSpacing.wider,
                            )),
                      ],
                    ),
                  ),
                );
              }).toList(),
            ),
        ],
      ),
    );
  }

  Widget _liveLossPanel(XlPalette p) {
    // 用快照引用（_chartPoints）而不是现场 List.unmodifiable(_lossPoints)：
    // 后者每次 build 都造新对象，XlLossChart 会误判「数据变了」而重启动画。
    final hasCurve = _chartPoints.length >= 2;
    return Container(
      margin: const EdgeInsets.only(top: 14),
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.screen(context, r: XlRadius.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text('Loss 实时曲线',
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.text3,
                  fontWeight: FontWeight.w800,
                  letterSpacing: XlLetterSpacing.wider,
                )),
            const Spacer(),
            if (_evalPoints.any((e) => e != null)) ...[
              _legendDot(p.violet),
              Text(' train', style: _legendStyle(p)),
              const SizedBox(width: 8),
              _legendDot(p.gold),
              Text(' eval', style: _legendStyle(p)),
              const SizedBox(width: 10),
            ],
            _LiveLossEta(
                step: _rtStep,
                total: _rtTotalSteps,
                active: _trainingActive,
                palette: p),
          ]),
          const SizedBox(height: 10),
          // 共享组件（原页面里的私有 _LiveLossChart 只能画单线、不支持验证集，
          // 已删除）：points 是真实采集到的每步 loss，取不到就不画线。
          hasCurve
              ? XlLossChart(
                  points: _chartPoints,
                  evalPoints: _chartEval,
                  height: 150,
                  lineColor: p.violet,
                  evalLineColor: p.gold,
                  labelBuilder: (i) => 'Step ${i + 1}',
                )
              : Container(
                  height: 72,
                  alignment: Alignment.center,
                  child: Text(
                      _lossPoints.isEmpty
                          ? '暂无 Loss 数据（等待第一个真实 step）'
                          : '采集 Loss 数据中…',
                      style: TextStyle(
                        fontSize: XlFont.micro,
                        color: p.decor,
                        fontWeight: FontWeight.w600,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                ),
        ],
      ),
    );
  }

  Widget _legendDot(Color c) => Container(
        width: 7,
        height: 7,
        decoration: BoxDecoration(color: c, shape: BoxShape.circle),
      );

  TextStyle _legendStyle(XlPalette p) => TextStyle(
        fontSize: XlFont.micro,
        color: p.text3,
        fontWeight: FontWeight.w700,
      );

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
            child:
                Text(dims.isEmpty ? '暂无数据' : '综合得分 ${_data!.avgDimensionLabel}',
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
      padding:
          EdgeInsets.only(bottom: i == _data!.dimensions.length - 1 ? 0 : 18),
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
                      gradient: LinearGradient(
                          colors: [color.withOpacity(0.8), color]),
                      borderRadius: BorderRadius.circular(99),
                      boxShadow: [
                        BoxShadow(
                            color: color.withOpacity(0.4),
                            blurRadius: 8,
                            spreadRadius: -2)
                      ],
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
              padding:
                  EdgeInsets.only(bottom: i == _presets.length - 1 ? 0 : 10),
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
                  color: selected
                      ? color
                      : p.shDark.withOpacity(p.isDark ? 0.32 : 0.14),
                  width: 1.5,
                ),
              ),
              child: selected
                  ? Icon(Icons.check_rounded,
                      size: 13, color: p.btnInk)
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
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: _autoScroll
                        ? p.pink.withOpacity(p.isDark ? 0.14 : 0.10)
                        : p.surfaceLo,
                    borderRadius: BorderRadius.circular(XlRadius.pill),
                    border: Border.all(
                      color:
                          _autoScroll ? p.pink.withOpacity(0.30) : p.edgeSoft,
                      width: 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        _autoScroll
                            ? Icons.vertical_align_bottom_rounded
                            : Icons.pause_rounded,
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
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: p.surfaceLo,
                    borderRadius: BorderRadius.circular(XlRadius.pill),
                    border: Border.all(color: p.edgeSoft, width: 1),
                  ),
                  child: Icon(Icons.cleaning_services_outlined,
                      size: 10, color: p.text3),
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
                    child: Text('[idle] 等待训练开始...',
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
      case _LogLevel.info:
        return p.text2;
      case _LogLevel.dim:
        return p.decor;
      case _LogLevel.ok:
        return p.green;
      case _LogLevel.warn:
        return p.gold;
      case _LogLevel.error:
        return p.red;
    }
  }

  Widget _milestonesCard(XlPalette p) {
    final milestones = _buildMilestones();
    final done = milestones.where((m) => m.done).length;
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
              Text('$done/${milestones.length}',
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
          for (int i = 0; i < milestones.length; i++)
            Padding(
              padding:
                  EdgeInsets.only(bottom: i == milestones.length - 1 ? 0 : 12),
              child: _milestoneRow(p, milestones[i]),
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
            gradient: m.done
                ? LinearGradient(colors: [color, color.withOpacity(0.7)])
                : null,
            color: m.done ? null : p.surfaceLo,
            shape: BoxShape.circle,
            border: Border.all(
              color: m.done
                  ? Colors.white.withOpacity(p.isDark ? 0.32 : 0.48)
                  : p.shDark.withOpacity(p.isDark ? 0.30 : 0.13),
              width: 1,
            ),
            boxShadow: m.done
                ? [
                    ...p.raisedXxs,
                    BoxShadow(
                        color: color.withOpacity(0.35),
                        blurRadius: 12,
                        spreadRadius: -2)
                  ]
                : p.sunkenXxs,
          ),
          child: Icon(
            m.done ? Icons.check_rounded : Icons.lock_outline_rounded,
            size: 14,
            color: m.done ? (p.btnInk) : p.decor,
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
            color: m.done
                ? color.withOpacity(p.isDark ? 0.14 : 0.10)
                : p.surfaceLo,
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
    final lrLabel = _formatLr(_lrCtrl.text.trim());
    final bsLabel = _bsCtrl.text.trim().isEmpty ? '未配置' : _bsCtrl.text.trim();
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
          _metricRow(p, '当前 Epoch', '$cur', '/$total', p.pink,
              cur / total.clamp(1, 999)),
          const SizedBox(height: 14),
          _metricRow(
              p, '训练进度', '${(pct * 100).toStringAsFixed(0)}', '%', p.gold, pct),
          const SizedBox(height: 14),
          _metricRow(p, 'Loss 值', loss == 0 ? '—' : loss.toStringAsFixed(4), '',
              p.violet, _data!.lossQuality),
          const SizedBox(height: 14),
          _metricRow(p, '学习率', lrLabel, '', p.green, 0.0),
          const SizedBox(height: 14),
          _metricRow(p, '批次大小', bsLabel, '', p.blue, 0.0),
        ],
      ),
    );
  }

  String _formatLr(String raw) {
    if (raw.isEmpty) return '未配置';
    final v = double.tryParse(raw);
    if (v == null || v <= 0) return '未配置';
    if (v >= 0.001) return v.toStringAsFixed(4);
    return v
        .toStringAsExponential(0)
        .replaceAll('e-0', 'e-')
        .replaceAll('e+0', 'e');
  }

  Widget _metricRow(XlPalette p, String label, String value, String unit,
      Color color, double progress) {
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

  Widget _neuProgress(XlPalette p, double value,
      {double height = 5, Color? color, bool shimmer = false}) {
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
                  boxShadow: [
                    BoxShadow(
                        color: c.withOpacity(0.35),
                        blurRadius: 8,
                        spreadRadius: -2)
                  ],
                ),
              ),
              if (shimmer && XlEffects.enabled) _ShimmerSweep(anim: _pulseCtrl),
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
    final isMobile = MediaQuery.of(context).size.width < 600;
    return Container(
      padding: EdgeInsets.all(isMobile ? 16 : 20),
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
          textStyle:
              TextStyle(fontSize: XlFont.micro, color: p.text2, height: 1.4),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: [
              Container(
                  width: 6,
                  height: 6,
                  decoration: AppTheme.glowDot(f.color, size: 6)),
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

  /// 训练环境与产物：全部读 training:env / training:adapter。
  ///
  /// 之前页面完全没这块，用户看不出「训练依赖到底装没装、基座可不可用、
  /// 适配器有没有真的写出来」，只能在训练失败后靠猜。这里把后端已经算好
  /// 的真值摆出来；取不到就明确写「未获取」，不做任何本地推断。
  Widget _envCard(XlPalette p) {
    final env = _trainEnv;
    final ad = _adapterInfo;
    final deps = <String, String?>{
      'torch': env?['torch']?.toString(),
      'transformers': env?['transformers']?.toString(),
      'peft': env?['peft']?.toString(),
      'accelerate': env?['accelerate']?.toString(),
      'bitsandbytes': env?['bitsandbytes']?.toString(),
    };
    final baseOk = env?['trainable_base_ok'] == true;
    final latestOk = ad?['lora_latest_exists'] == true;
    final weightBytes = ad?['weight_files'];
    final totalBytes = (weightBytes is List)
        ? weightBytes
            .whereType<Map>()
            .fold<int>(0, (s, e) => s + ((e['bytes'] as num?)?.toInt() ?? 0))
        : 0;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('训练环境与产物',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              _tinyChip(p, env == null ? '未知' : (baseOk ? '可训练' : '缺基座'),
                  env == null ? p.text3 : (baseOk ? p.green : p.red)),
            ],
          ),
          const SizedBox(height: 4),
          Text('训练依赖、基座与适配器落点的真实状态',
              style: TextStyle(
                fontSize: XlFont.label,
                color: p.text3,
                fontWeight: FontWeight.w500,
                letterSpacing: XlLetterSpacing.wider,
              )),
          if (_metaError != null) ...[
            const SizedBox(height: 10),
            Text(_metaError!,
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.red,
                  fontWeight: FontWeight.w700,
                )),
          ],
          // frozen 横幅：与设置页同款。写清楚两件事 ——
          // ① 打包版没有内置训练栈、也没有 pip，微调请走源码模式；
          // ② API 配置不参与微调启动，只服务蒸馏老师端与连通性测试
          //    （此前的产品预期缺口：「配好 API 就能训练」并不成立）。
          if (env?['frozen'] == true) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: p.gold.withOpacity(0.10),
                borderRadius: BorderRadius.circular(XlRadius.md),
                border: Border.all(color: p.gold.withOpacity(0.35)),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline_rounded, size: 16, color: p.gold),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      '当前为打包模式（frozen）：未内置 PyTorch 训练栈，且无法在线安装。'
                      '微调训练请使用源码模式运行 python main.py，或改用完整版后端；'
                      'API 配置仅用于蒸馏老师端与连通性测试，不参与微调启动。',
                      style: TextStyle(
                        fontSize: XlFont.label,
                        color: p.gold,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final e in deps.entries) _depChip(p, e.key, e.value),
            ],
          ),
          const SizedBox(height: 14),
          _envRow(p, '设备', _metaText(env?['device'])),
          _envRow(
              p,
              '可训练基座',
              env == null
                  ? '未获取'
                  : (baseOk
                      ? _metaText(env['trainable_base'])
                      : '不可用：${_metaText(env['trainable_base_reason'], fallback: "未知原因")}')),
          _envRow(
              p, '适配器目录', ad == null ? '未获取' : _metaText(ad['adapter_dir'])),
          _envRow(p, 'lora_latest',
              ad == null ? '未获取' : (latestOk ? '已产出' : '尚未产出（还没成功训练）')),
          _envRow(
              p,
              '权重体积',
              ad == null
                  ? '未获取'
                  : (totalBytes > 0
                      ? '${(totalBytes / 1024 / 1024).toStringAsFixed(2)} MB'
                      : '无权重文件')),
          _envRow(p, 'target_modules', _joinList(ad?['target_modules'])),
          _envRow(
              p,
              'rank / alpha',
              ad == null
                  ? '未获取'
                  : '${_metaText(ad['r'], fallback: '?')} / ${_metaText(ad['lora_alpha'], fallback: '?')}'),
          _envRow(p, '可续训', _resumeLine(ad)),
          const SizedBox(height: 16),
          // API 接入设置（OpenAI 兼容端点）：入口按钮 + 独立对话框。
          _Pressable(
            onTap: _openApiSettings,
            scale: 0.98,
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 11),
              decoration: AppTheme.ghost(context, r: XlRadius.pill),
              child: Center(
                child: Text('API 接入设置',
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                    )),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// 「可续训」这一行只转述后端给的事实：会不会真的续（resumable）、续哪个
  /// 检查点、不能续的原因。前端不自己从 checkpoints 列表推断 —— 之前正是这种
  /// 「看 state 有步数就显示可续训」让界面与 trainer 当场打架。
  String _resumeLine(dynamic ad) {
    if (ad == null) return '未获取';
    final ok = ad['resumable'] == true;
    final gs = _metaText(ad['global_step'], fallback: '?');
    final used = _metaText(ad['resume_would_use'], fallback: '检查点');
    final head = ok ? '可（从 $used 续，global_step=$gs）' : '否';
    final parts = <String>[
      '$head · 检查点 ${_joinList(ad['checkpoints'])}',
      if (!ok) _metaText(ad['resume_blocked_reason'], fallback: ''),
      _metaText(ad['resume_hint'], fallback: ''),
    ].where((s) => s.isNotEmpty).toList();
    return parts.join('\n');
  }

  Widget _depChip(XlPalette p, String name, String? version) {
    final ok = version != null && version.isNotEmpty && version != 'None';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: (ok ? p.green : p.red).withOpacity(ok ? 0.10 : 0.08),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(
            color: (ok ? p.green : p.red).withOpacity(0.28), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(ok ? Icons.check_rounded : Icons.unpublished_rounded,
              size: 11, color: ok ? p.green : p.red),
          const SizedBox(width: 5),
          Text('$name ${ok ? version : '未安装'}',
              style: TextStyle(
                fontSize: XlFont.micro,
                fontWeight: FontWeight.w800,
                color: ok ? p.green : p.red,
                letterSpacing: XlLetterSpacing.wide,
              )),
        ],
      ),
    );
  }

  Widget _envRow(XlPalette p, String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 96,
            child: Text(label,
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.text3,
                  fontWeight: FontWeight.w700,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ),
          Expanded(
            child: Text(value,
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: value == '未获取' ? p.decor : p.text1,
                  fontWeight: FontWeight.w600,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          ),
        ],
      ),
    );
  }

  String _joinList(Object? v, {String dashWhenEmpty = '未获取'}) {
    if (v == null) return dashWhenEmpty;
    if (v is List)
      return v.isEmpty ? '—' : v.map((e) => e.toString()).join(', ');
    final s = v.toString().trim();
    return s.isEmpty ? '—' : s;
  }

  /// 训练历史行：优先用 training:history 的完整记录（含 ok/real/device/
  /// metadata/取消原因），proto 的 GetTrainingHistory 只有 4 个字段，
  /// 够判断的一律以 JSON 记录为准；JSON 拿不到时才退回 proto 条目。
  List<Map<String, dynamic>> get _historyRows {
    if (_historyRecords.isNotEmpty) return _historyRecords;
    return _history
        .map((e) => <String, dynamic>{
              'timestamp': e.timestamp,
              'steps': e.steps,
              'final_loss': e.finalLoss,
              'loss_curve': e.lossCurve.toList(),
              '_proto_only': true,
            })
        .toList();
  }

  Widget _historyCard(XlPalette p) {
    final rows = _historyRows;
    final failed = rows.where((r) => r['ok'] == false).length;
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
              Text('${rows.length} 次',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w800,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            _historyRows.isEmpty
                ? '历次微调的 loss 收敛曲线'
                : (failed == 0
                    ? '历次微调的 loss 收敛曲线（含失败与中断记录）'
                    : '历次微调记录 · 其中 $failed 次未成功产出适配器'),
            style: TextStyle(
              fontSize: XlFont.label,
              color: p.text3,
              fontWeight: FontWeight.w500,
              letterSpacing: XlLetterSpacing.wider,
            ),
          ),
          const SizedBox(height: 16),
          if (rows.isEmpty)
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
            for (var i = 0; i < rows.length; i++)
              Padding(
                padding: EdgeInsets.only(bottom: i == rows.length - 1 ? 0 : 14),
                child: _historyTile(p, rows[i]),
              ),
        ],
      ),
    );
  }

  Widget _historyTile(XlPalette p, Map<String, dynamic> r) {
    final ts = (r['timestamp'] as num?)?.toInt() ?? 0;
    final ms = ts > 1000000000000 ? ts : ts * 1000;
    final dt = DateTime.fromMillisecondsSinceEpoch(ms);
    final curve = (r['loss_curve'] is List)
        ? (r['loss_curve'] as List)
            .whereType<num>()
            .map((e) => e.toDouble())
            .toList()
        : const <double>[];
    final ok = r['ok'] != false;
    final real = r['real'] == true;
    final meta = (r['metadata'] is Map)
        ? Map<String, dynamic>.from(r['metadata'] as Map)
        : const <String, dynamic>{};
    final cancelled =
        meta['cancel_reason'] != null || meta['cancelled_at'] != null;
    final steps = (r['steps'] as num?)?.toInt() ?? 0;
    final finalLoss = (r['final_loss'] as num?)?.toDouble();
    final avgLoss =
        (r['avg_loss'] is num) ? (r['avg_loss'] as num).toDouble() : null;
    final accent = ok ? (cancelled ? p.gold : p.green) : p.red;
    final statusText = !ok
        ? '未成功：${_metaText(r['reason'], fallback: '原因未记录')}'
        : (cancelled
            ? '中断于第 ${_metaText(meta['cancelled_at'], fallback: "?")} 步'
            : '已完成');
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
                Row(
                  children: [
                    Text(
                        '${dt.month}/${dt.day} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}',
                        style: TextStyle(
                          fontSize: XlFont.captionSm,
                          color: p.text1,
                          fontWeight: FontWeight.w800,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                    const SizedBox(width: 6),
                    // 徽标来自记录本身（real / ok / 取消），不再用「曲线是平的」
                    // 这种猜测来判断演练。
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(
                        color: accent.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        !ok
                            ? '失败'
                            : (!real ? '未产出权重' : (cancelled ? '中断' : '真权重')),
                        style: TextStyle(
                          fontSize: 10,
                          color: accent,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                    '步数 $steps · 最终 Loss ${finalLoss == null ? '—' : finalLoss.toStringAsFixed(3)}'
                    '${avgLoss == null ? '' : ' · 均 Loss ${avgLoss.toStringAsFixed(3)}'}',
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text3,
                      fontWeight: FontWeight.w600,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
                const SizedBox(height: 3),
                Text(
                  [
                    statusText,
                    _metaText(r['device'], fallback: ''),
                    if (r['lora_rank'] != null) 'r=${r['lora_rank']}',
                    if (r['batch_size'] != null) 'bs=${r['batch_size']}',
                    if (meta['prompt_mask'] != null)
                      'mask=${meta['prompt_mask']}',
                    if (meta['elapsed_sec'] != null) '${meta['elapsed_sec']}s',
                  ].where((s) => s.toString().isNotEmpty).join(' · '),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    color: p.decor,
                    fontWeight: FontWeight.w600,
                    letterSpacing: XlLetterSpacing.wide,
                  ),
                ),
                if (r['_proto_only'] == true)
                  Text('仅概要字段（training:history 未提供明细）',
                      style: TextStyle(fontSize: XlFont.micro, color: p.decor)),
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
                      child: Text('无曲线数据',
                          style: TextStyle(
                              fontSize: XlFont.label, color: p.decor)),
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
              Expanded(
                  child: _skeleton(p,
                      width: double.infinity, height: 220, radius: 22)),
              const SizedBox(width: 18),
              Expanded(
                  flex: 2,
                  child: _skeleton(p,
                      width: double.infinity, height: 220, radius: 22)),
            ],
          ),
          const SizedBox(height: 20),
          _skeleton(p, width: double.infinity, height: 120, radius: 22),
        ],
      ),
    );
  }

  Widget _skeleton(XlPalette p,
      {required double width, required double height, double radius = 16}) {
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
          final t = XlEffects.enabled ? _pulseCtrl.value : 0.0;
          final dx = (t * 2.2 - 0.6) * w;
          return Stack(children: [
            Positioned(
              left: dx.clamp(-w * 0.6, w),
              top: 0,
              bottom: 0,
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
            // 把真实错误带出来：原来这里只有一句「请确认 backend 已启动」，
            // 超时/权限/序列化之类的问题全被吞成同一个提示。
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 420),
                  child: Text(_error!,
                      maxLines: 4,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: XlFont.micro,
                        color: p.red,
                        fontWeight: FontWeight.w600,
                        fontFamily: 'monospace',
                      )),
                ),
              ),
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
                padding:
                    const EdgeInsets.symmetric(horizontal: 26, vertical: 12),
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
        final pp =
            Offset(center.dx + r * math.cos(a), center.dy + r * math.sin(a));
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
      final pp = Offset(
          center.dx + maxR * math.cos(a), center.dy + maxR * math.sin(a));
      canvas.drawLine(center, pp, ringPaint);
    }

    final dataPath = Path();
    for (var i = 0; i < n; i++) {
      final a = -math.pi / 2 + 2 * math.pi * i / n;
      final v = dims[i].ratio * progress;
      final r = maxR * v;
      final pp =
          Offset(center.dx + r * math.cos(a), center.dy + r * math.sin(a));
      if (i == 0) {
        dataPath.moveTo(pp.dx, pp.dy);
      } else {
        dataPath.lineTo(pp.dx, pp.dy);
      }
    }
    dataPath.close();

    final fillPaint = Paint()
      ..shader = RadialGradient(
        colors: [
          palette.pink.withOpacity(0.32),
          palette.pink.withOpacity(0.08)
        ],
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
      final pp =
          Offset(center.dx + r * math.cos(a), center.dy + r * math.sin(a));
      canvas.drawCircle(pp, 6, Paint()..color = palette.pink.withOpacity(0.25));
      canvas.drawCircle(pp, 4, Paint()..color = palette.gold);
      canvas.drawCircle(pp, 2, Paint()..color = palette.bg);
    }

    final labelPainter = TextPainter(textDirection: TextDirection.ltr);
    for (var i = 0; i < n; i++) {
      final a = -math.pi / 2 + 2 * math.pi * i / n;
      final lr = maxR + 22;
      final pp =
          Offset(center.dx + lr * math.cos(a), center.dy + lr * math.sin(a));
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
  _LossCurvePainter(
      {required this.points, required this.palette, this.progress = 1.0});

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2) return;
    final count =
        (points.length * progress).clamp(2.0, points.length.toDouble()).round();
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
    final lastY = size.height -
        4 -
        ((pts.last - minV) / (maxV - minV)) * (size.height - 8);
    canvas.drawCircle(
        Offset(size.width * (pts.length - 1) / (points.length - 1), lastY),
        2.5,
        Paint()..color = palette.gold);
  }

  @override
  bool shouldRepaint(covariant _LossCurvePainter old) =>
      old.points != points ||
      old.palette != palette ||
      old.progress != progress;
}

class _AnimatedLossCurve extends StatefulWidget {
  final List<double> points;
  final XlPalette palette;
  const _AnimatedLossCurve({required this.points, required this.palette});
  @override
  State<_AnimatedLossCurve> createState() => _AnimatedLossCurveState();
}

class _AnimatedLossCurveState extends State<_AnimatedLossCurve>
    with SingleTickerProviderStateMixin {
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

class _SavedPreset {
  final String name;
  final double lr;
  final int bs;
  final int rank;
  final int steps;
  const _SavedPreset({
    required this.name,
    required this.lr,
    required this.bs,
    required this.rank,
    required this.steps,
  });
}

class _LiveLossEta extends StatefulWidget {
  final int step;
  final int total;
  final bool active;
  final XlPalette palette;
  const _LiveLossEta({
    required this.step,
    required this.total,
    required this.active,
    required this.palette,
  });
  @override
  State<_LiveLossEta> createState() => _LiveLossEtaState();
}

class _LiveLossEtaState extends State<_LiveLossEta> {
  DateTime? _startAt;
  int _baseStep = 0;
  Duration _remaining = Duration.zero;
  Timer? _ticker;

  @override
  void didUpdateWidget(_LiveLossEta old) {
    super.didUpdateWidget(old);
    if (widget.active && _startAt == null) {
      _startAt = DateTime.now();
      _baseStep = widget.step;
      _ticker = Timer.periodic(const Duration(seconds: 1), (_) => _recalc());
    }
    if (!widget.active && _startAt != null) {
      _ticker?.cancel();
      _ticker = null;
      _startAt = null;
      _remaining = Duration.zero;
    }
  }

  void _recalc() {
    if (!mounted || _startAt == null) return;
    final elapsed = DateTime.now().difference(_startAt!);
    final done = (widget.step - _baseStep).clamp(1, 1 << 30);
    final perStep = elapsed.inMilliseconds / done;
    final left = (widget.total - widget.step).clamp(0, 1 << 30);
    setState(
        () => _remaining = Duration(milliseconds: (perStep * left).round()));
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  String _fmt(Duration d) {
    if (d.inHours > 0) return '${d.inHours}h ${d.inMinutes % 60}m';
    if (d.inMinutes > 0) return '${d.inMinutes}m ${d.inSeconds % 60}s';
    return '${d.inSeconds}s';
  }

  @override
  Widget build(BuildContext context) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.timelapse_rounded, size: 12, color: widget.palette.gold),
      const SizedBox(width: 5),
      Text(widget.active ? '预计剩余 ${_fmt(_remaining)}' : '待开始',
          style: TextStyle(
            fontSize: XlFont.micro,
            color: widget.palette.gold,
            fontWeight: FontWeight.w800,
            fontFeatures: const [FontFeature.tabularFigures()],
            letterSpacing: XlLetterSpacing.wider,
          )),
    ]);
  }
}

class _Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  const _Pressable(
      {super.key, required this.child, this.onTap, this.scale = 0.96});
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
              top: 0,
              bottom: 0,
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

class _LogEntranceState extends State<_LogEntrance>
    with SingleTickerProviderStateMixin {
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

/// API 接入设置对话框（OpenAI 兼容端点）。
///
/// 读写后端 config.training.api_*（training:api 指令族）：
///   - key 后端只回打码值，本对话框也只在用户主动输入时才提交新 key；
///   - 「测试连接」发真实请求，结果如实展示，不伪造成功。
class _ApiSettingsDialog extends StatefulWidget {
  const _ApiSettingsDialog();

  @override
  State<_ApiSettingsDialog> createState() => _ApiSettingsDialogState();
}

class _ApiSettingsDialogState extends State<_ApiSettingsDialog> {
  final _baseCtrl = TextEditingController();
  final _keyCtrl = TextEditingController();
  final _modelCtrl = TextEditingController();
  bool _enabled = false;
  bool _hasKey = false;
  bool _busy = false;
  String? _msg;
  bool _msgOk = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _baseCtrl.dispose();
    _keyCtrl.dispose();
    _modelCtrl.dispose();
    super.dispose();
  }

  Future<Map<String, dynamic>?> _api(String arg) async {
    final cmd = arg.isEmpty ? 'training:api' : 'training:api $arg';
    final r = await XlClient.stub.safe(
        () => XlClient.stub.command(cmd, opt: const XlCallOptions(silent: true)));
    final out = r?.output;
    if (out == null || out.isEmpty) return null;
    try {
      final v = jsonDecode(out);
      return v is Map<String, dynamic> ? v : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> _load() async {
    final d = await _api('');
    if (!mounted || d == null) return;
    setState(() {
      _enabled = d['enabled'] == true;
      _baseCtrl.text = (d['base'] ?? '').toString();
      _modelCtrl.text = (d['model'] ?? '').toString();
      _hasKey = d['has_key'] == true;
    });
  }

  Future<void> _send(String arg, {String? okText}) async {
    setState(() {
      _busy = true;
      _msg = null;
    });
    final d = await _api(arg);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _msgOk = d?['ok'] == true;
      _msg = _msgOk ? (okText ?? '已完成') : '失败：${d?['error'] ?? '后端无响应'}';
      if (_msgOk && arg == 'key') {
        _keyCtrl.clear();
        _hasKey = d?['has_key'] == true;
      }
    });
  }

  Future<void> _saveAll() async {
    // 依次写 base / model / key（key 留空 = 不改动）。中途失败即停。
    await _send('base ${_baseCtrl.text.trim()}', okText: '端点已保存');
    if (!mounted || !_msgOk) return;
    await _send('model ${_modelCtrl.text.trim()}', okText: '模型名已保存');
    if (!mounted || !_msgOk) return;
    final key = _keyCtrl.text.trim();
    if (key.isNotEmpty) await _send('key $key', okText: '密钥已保存');
  }

  Future<void> _toggle(bool v) async {
    setState(() => _enabled = v);
    await _send(v ? 'on' : 'off', okText: v ? '已启用' : '已停用');
  }

  Future<void> _test() async {
    setState(() {
      _busy = true;
      _msg = '正在测试连接…';
      _msgOk = false;
    });
    final d = await _api('test');
    if (!mounted) return;
    setState(() {
      _busy = false;
      _msgOk = d?['ok'] == true;
      _msg = _msgOk
          ? '连接成功：${d?['model'] ?? '?'} · ${d?['latency_ms'] ?? '?'} ms'
          : '失败：${d?['error'] ?? '后端无响应'}';
    });
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Dialog(
      backgroundColor: Colors.transparent,
      elevation: 0,
      child: Container(
        width: 440,
        padding: const EdgeInsets.all(24),
        decoration: AppTheme.neuLg(context, r: XlRadius.xxxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Text('API 接入设置',
                  style: TextStyle(
                      fontSize: XlFont.h6,
                      fontWeight: FontWeight.w800,
                      color: p.text1)),
              const Spacer(),
              Text(_enabled ? '已启用' : '未启用',
                  style: TextStyle(
                      fontSize: XlFont.label,
                      fontWeight: FontWeight.w700,
                      color: _enabled ? p.green : p.text3)),
              const SizedBox(width: 8),
              SizedBox(
                height: 22,
                child: Switch(value: _enabled, onChanged: _busy ? null : _toggle),
              ),
            ]),
            const SizedBox(height: 4),
            Text('OpenAI 兼容端点（LM Studio / vLLM / 云端推理），'
                    '配置由后端持久化，密钥只打码回显',
                style: TextStyle(
                    fontSize: XlFont.captionSm, color: p.text3)),
            const SizedBox(height: 14),
            _field(p, '端点 Base URL', _baseCtrl, 'http://127.0.0.1:1234/v1'),
            const SizedBox(height: 10),
            _field(p, '模型名', _modelCtrl, '例如 qwen2.5-7b-instruct'),
            const SizedBox(height: 10),
            _field(p, _hasKey ? '密钥（已有，留空=不改动）' : '密钥（可留空）',
                _keyCtrl, 'sk-...', obscure: true),
            if (_msg != null) ...[
              const SizedBox(height: 10),
              Text(_msg!,
                  style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w700,
                      color: _msgOk ? p.green : p.red)),
            ],
            const SizedBox(height: 18),
            Row(children: [
              Expanded(
                child: _Pressable(
                  onTap: _busy ? null : _test,
                  scale: 0.95,
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 11),
                    decoration: AppTheme.ghost(context, r: XlRadius.pill),
                    child: Center(
                        child: Text('测试连接',
                            style: TextStyle(
                                fontSize: XlFont.captionSm,
                                fontWeight: FontWeight.w800,
                                color: p.text1))),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _Pressable(
                  onTap: _busy ? null : _saveAll,
                  scale: 0.95,
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 11),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                          colors: [p.green, p.green.withOpacity(0.85)]),
                      borderRadius: BorderRadius.circular(XlRadius.pill),
                    ),
                    child: Center(
                        child: Text('保存',
                            style: TextStyle(
                                fontSize: XlFont.captionSm,
                                fontWeight: FontWeight.w800,
                                color: p.btnInk))),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              _Pressable(
                onTap: () => Navigator.pop(context),
                scale: 0.95,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(vertical: 11, horizontal: 16),
                  decoration: AppTheme.ghost(context, r: XlRadius.pill),
                  child: Text('关闭',
                      style: TextStyle(
                          fontSize: XlFont.captionSm,
                          fontWeight: FontWeight.w800,
                          color: p.text2)),
                ),
              ),
            ]),
          ],
        ),
      ),
    );
  }

  Widget _field(XlPalette p, String label, TextEditingController ctrl,
      String hint, {bool obscure = false}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: TextStyle(
                fontSize: XlFont.label,
                fontWeight: FontWeight.w700,
                color: p.text2)),
        const SizedBox(height: 4),
        Container(
          decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
          child: TextField(
            controller: ctrl,
            obscureText: obscure,
            style: TextStyle(
                fontSize: XlFont.bodySm,
                color: p.text1,
                fontWeight: FontWeight.w700),
            decoration: InputDecoration(
              border: InputBorder.none,
              isDense: true,
              hintText: hint,
              hintStyle: TextStyle(fontSize: XlFont.bodySm, color: p.decor),
              contentPadding: const EdgeInsets.symmetric(vertical: 10),
            ),
          ),
        ),
      ],
    );
  }
}
