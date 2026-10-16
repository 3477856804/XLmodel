import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;
import '../services/local_store.dart';

class GrowthPage extends StatefulWidget {
  const GrowthPage({super.key});
  @override
  State<GrowthPage> createState() => _GrowthPageState();
}

class _GrowthPageState extends State<GrowthPage> with TickerProviderStateMixin {
  pb.GrowthStatusReply? _data;
  pb.TrainingStatusReply? _training;

  /// 后端真值（ExecuteCommand + JSON，不改 proto）。
  /// 以前这些数值全部在 Dart 里写死：关系五档的固定文案、固定「第 3 级」、
  /// 时间线每个节点固定用 DateTime.now()。现在一律读后端，后端改了前端跟着变。
  Map<String, dynamic> _persona = const {};
  List<Map<String, dynamic>> _activity = const [];
  Map<String, dynamic> _daily = const {};
  Map<String, dynamic> _first = const {};
  String? _metaError;

  /// 成长运维真值（growth:status，只读）。此前暂停/回滚/GC/清库只有后端 API，
  /// 前端连状态都看不到；现在这条指令返回的就是 should_train 实际读到的值，
  /// 包括 paused、rank、以及「现在到底能不能练」的阻塞原因列表。
  Map<String, dynamic>? _ops;
  String? _opsError;
  bool _opsBusy = false;

  bool _loading = true;
  String? _error;
  late AnimationController _enterCtrl;
  late AnimationController _radialCtrl;
  late AnimationController _pulseCtrl;
  late AnimationController _timelineCtrl;
  late Animation<double> _enterAnim;
  late Animation<double> _radialAnim;
  late Animation<double> _timelineAnim;
  int _rangeIndex = 1;
  int _dailyGoal = 20;

  static const _ranges = <String>['7 天', '30 天', '全部'];

  /// 三档对应向后端要多少天的活动量；「全部」用足够大的窗口截到 366 天上限
  static const _rangeDays = <int>[7, 30, 366];

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(
        duration: const Duration(milliseconds: 900), vsync: this);
    _radialCtrl = AnimationController(
        duration: const Duration(milliseconds: 900), vsync: this);
    _pulseCtrl = XlEffects.bindAmbient(
        AnimationController(duration: const Duration(seconds: 4), vsync: this));
    _timelineCtrl = AnimationController(
        duration: const Duration(milliseconds: 1200), vsync: this);
    _enterAnim = CurvedAnimation(parent: _enterCtrl, curve: XlCurve.easeOut);
    _radialAnim = CurvedAnimation(parent: _radialCtrl, curve: XlCurve.spring);
    _timelineAnim =
        CurvedAnimation(parent: _timelineCtrl, curve: XlCurve.easeOut);
    _enterCtrl.forward();
    _loadDailyGoal();
    _load();
  }

  @override
  void dispose() {
    _enterCtrl.dispose();
    _radialCtrl.dispose();
    _pulseCtrl.dispose();
    _timelineCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await XlClient.stub.growth();
      final t = await XlClient.stub.safe(() => XlClient.stub.training());
      if (!mounted) return;
      setState(() {
        _data = r;
        _training = t;
        _loading = false;
      });
      _radialCtrl.forward(from: 0);
      _timelineCtrl.forward(from: 0);
      // 元数据失败不影响主页面（等级卡/时间线会退化成「后端未提供」占位），
      // 所以单独 catch，不把整页变成错误屏。
      unawaited(_loadMeta());
      unawaited(_loadOps());
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  /// 拉取关系档位 / 情绪来源 / 按天活动量 / 今日进度（全部来自后端真值）。
  Future<void> _loadMeta() async {
    final days = _rangeDays[_rangeIndex];
    try {
      final persona = await XlClient.stub.safe(() => XlClient.stub
          .command('growth:persona', opt: const XlCallOptions(silent: true)));
      final act = await XlClient.stub.safe(() => XlClient.stub.command(
          'growth:timeline $days',
          opt: const XlCallOptions(silent: true)));
      final daily = await XlClient.stub.safe(() => XlClient.stub
          .command('growth:daily', opt: const XlCallOptions(silent: true)));
      final first = await XlClient.stub.safe(() => XlClient.stub
          .command('growth:first', opt: const XlCallOptions(silent: true)));
      if (!mounted) return;
      setState(() {
        _persona = _json(persona?.output) ?? const {};
        _activity = _jsonList(act?.output, 'activity');
        _daily = _json(daily?.output) ?? const {};
        _first = _json(first?.output) ?? const {};
        _metaError = (_persona.isEmpty && _activity.isEmpty)
            ? '后端未返回成长元数据（growth: 指令族不可用）'
            : null;
        // 后端的每日目标是权威值；本地缓存只在后端没给时兜底
        final g = _daily['goal'];
        if (g is num) _dailyGoal = g.toInt();
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _metaError = '成长元数据读取失败：$e');
    }
  }

  Map<String, dynamic>? _json(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    try {
      final d = jsonDecode(raw);
      return (d is Map && d['ok'] == true)
          ? Map<String, dynamic>.from(d)
          : null;
    } catch (_) {
      return null;
    }
  }

  List<Map<String, dynamic>> _jsonList(String? raw, String key) {
    final d = _json(raw);
    final rows = d?[key];
    if (rows is! List) return const [];
    return rows
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }

  Future<void> _loadDailyGoal() async {
    final data = await LocalStore.readJson('growth_settings.json');
    final v = data['daily_goal'];
    if (v is num) {
      if (!mounted) return;
      setState(() => _dailyGoal = v.toInt());
    }
  }

  Future<void> _persistDailyGoal(int value) async {
    await LocalStore.writeJson('growth_settings.json', {'daily_goal': value});
    try {
      // 后端才是每日目标的权威存储（growth:daily 读的就是它）；
      // 只写本地 JSON 的话，重启/换设备后后端和前端各说一套。
      final raw = await XlClient.stub.command('growth:goal $value',
          opt: const XlCallOptions(silent: true));
      final d = _json(raw.output);
      if (d == null) {
        if (!mounted) return;
        setState(() => _metaError = '每日目标已存本地，但后端写入失败');
      } else if (d['goal'] is num) {
        if (!mounted) return;
        setState(() {
          _daily = d;
          _dailyGoal = (d['goal'] as num).toInt();
        });
      }
    } catch (e) {
      debugPrint('操作失败: $e');
    }
  }

  void _adjustDailyGoal(int delta) {
    final next = (_dailyGoal + delta).clamp(5, 100);
    if (next == _dailyGoal) return;
    setState(() => _dailyGoal = next);
    _persistDailyGoal(next);
  }

  // -------------------------------------------------------------- 成长运维
  // 暂停/恢复/状态/回滚/GC/清库此前只有后端 Python API，前端连状态都读不到。
  // 后端已接成 growth:pause|resume|status|rollback|gc|purge，这里补上入口。
  // 与后端同一套约定：**默认只读或演练，破坏性动作必须显式 confirm**。
  // 所以面板打开时只会看到「会删多少、够不够格回滚」，绝不可能一点就掉数据。

  /// 与 `_json` 的区别：`_json` 只在 ok==true 时返回，错误信息会被丢掉；
  /// 运维指令需要把 `error` 原样显示给用户，所以这里不管 ok 与否都解出来。
  Map<String, dynamic> _decode(String? raw) {
    if (raw == null || raw.isEmpty) return <String, dynamic>{};
    try {
      final d = jsonDecode(raw);
      // 一定要拷成可变 map：调用方会往里补 _task_id，
      // 而 const {} / 常量 map 写进去就是运行时 UnsupportedError。
      return d is Map ? Map<String, dynamic>.from(d) : <String, dynamic>{};
    } catch (_) {
      return <String, dynamic>{};
    }
  }

  Future<Map<String, dynamic>> _opsCmd(String cmd) async {
    final r = await XlClient.stub.command(
        cmd, opt: const XlCallOptions(silent: true, timeout: Duration(seconds: 25)));
    return _decode(r.output);
  }

  /// confirm 类指令返回的是后台任务（task_id + poll），不是结果本身。
  /// 这里轮询到终态再取 result；超时就把 task_id 如实报出来，不假装成功。
  Future<Map<String, dynamic>> _awaitTask(Map<String, dynamic> started) async {
    final id = (started['task_id'] ?? '').toString();
    if (id.isEmpty) return started;
    for (var i = 0; i < 60; i++) {
      await Future.delayed(const Duration(milliseconds: 500));
      final st = _decode((await XlClient.stub.command('agent:task status $id',
              opt: const XlCallOptions(silent: true)))
          .output);
      if (st['ok'] != true) return st;
      if ((st['status'] ?? '') != 'running') {
        final res = _decode((await XlClient.stub.command('agent:task result $id',
                opt: const XlCallOptions(silent: true)))
            .output);
        res['_task_id'] = id;
        return res;
      }
    }
    return {
      'ok': false,
      'pending': true,
      'task_id': id,
      'error': '任务仍在进行（$id），稍后可用 agent:task result $id 查看结果'
    };
  }

  void _toast(bool ok, String msg) {
    if (!mounted) return;
    final p = XlPalette.of(context);
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(milliseconds: 2600),
        content: Row(
          children: [
            Icon(ok ? Icons.check_circle_outline_rounded
                     : Icons.error_outline_rounded,
                size: 16, color: ok ? p.green : p.red),
            const SizedBox(width: 8),
            Expanded(
              child: Text(msg,
                  style: TextStyle(
                      fontWeight: FontWeight.w600, color: p.text1)),
            ),
          ],
        ),
      ));
  }

  Future<void> _loadOps() async {
    try {
      final d = await _opsCmd('growth:status');
      if (!mounted) return;
      if (d['ok'] != true) {
        setState(() {
          _ops = null;
          _opsError =
              d['error']?.toString() ?? '后端未返回成长运维状态（growth:status 不可用）';
        });
        return;
      }
      setState(() {
        _ops = d;
        _opsError = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _ops = null;
        _opsError = '成长运维状态读取失败：$e';
      });
    }
  }

  Future<void> _reloadGrowth() async {
    final r = await XlClient.stub
        .safe(() => XlClient.stub.growth(opt: const XlCallOptions(silent: true)));
    if (!mounted || r == null) return;
    setState(() => _data = r);
  }

  Future<void> _toggleGrowthPause() async {
    if (_opsBusy) return;
    final paused = _ops?['paused'] == true || (_data?.paused ?? false);
    setState(() => _opsBusy = true);
    try {
      final d = await _opsCmd(
          paused ? 'growth:resume' : 'growth:pause 用户在成长页暂停');
      final ok = d['ok'] == true;
      _toast(ok, ok
          ? '${paused ? '已恢复成长：' : '已暂停成长：'}${d['note'] ?? ''}'
          : '操作失败：${d['error'] ?? '后端未回应'}');
    } catch (e) {
      _toast(false, '操作失败：$e');
    }
    if (!mounted) return;
    setState(() => _opsBusy = false);
    await _loadOps();
    await _reloadGrowth();
  }

  Future<void> _showOpsSheet() async {
    if (!mounted) return;
    final p = XlPalette.of(context);
    await showDialog<void>(
      context: context,
      barrierColor: p.scrim,
      builder: (ctx) => _GrowthOpsDialog(
        ops: _ops,
        command: _opsCmd,
        awaitTask: _awaitTask,
        onBusyChanged: (b) {
          if (mounted) setState(() => _opsBusy = b);
        },
      ),
    );
    await _loadOps();
    await _reloadGrowth();
  }

  Future<void> _exportGrowthData() async {
    final g = _data;
    if (g == null) return;
    try {
      final docs = await getApplicationDocumentsDirectory();
      final now = DateTime.now();
      final stamp = '${now.year}${_two(now.month)}${_two(now.day)}';
      final rows = <List<String>>[
        ['metric', 'value'],
        ['displayRank', g.displayRank],
        ['displayStage', g.displayStage],
        ['displayEmotion', g.displayEmotion],
        ['totalInteractions', '${g.totalInteractions}'],
        ['currentGeneration', '${g.currentGeneration}'],
        ['totalGenerations', '${g.totalGenerations}'],
        ['normalizedProgress', g.normalizedProgress.toStringAsFixed(2)],
        ['emotionIntensity', (_emotionIntensity?.toStringAsFixed(2)) ?? 'null'],
      ];
      final csv = rows.map((r) => r.map((c) => '"$c"').join(',')).join('\n');
      final csvFile = File(p.join(docs.path, 'growth_$stamp.csv'));
      await csvFile.writeAsString(csv);
      final jsonFile = File(p.join(docs.path, 'growth_$stamp.json'));
      await jsonFile.writeAsString(const JsonEncoder.withIndent('  ').convert({
        'rank': g.displayRank,
        'stage': g.displayStage,
        'emotion': g.displayEmotion,
        'interactions': g.totalInteractions,
        'generation': '${g.currentGeneration}/${g.totalGenerations}',
        'progress': g.normalizedProgress,
        'exportedAt': now.toIso8601String(),
      }));
      if (!mounted) return;
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(SnackBar(
          behavior: SnackBarBehavior.floating,
          duration: const Duration(milliseconds: 2000),
          content: Text('成长数据已导出（growth_$stamp）',
              style: const TextStyle(fontWeight: FontWeight.w600)),
        ));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(SnackBar(content: Text('导出失败：$e')));
    }
  }

  Widget _dailyGoalCard(XlPalette p) {
    final g = _data!;
    // 今日进度优先用后端 growth:daily（真实按天计数）；拿不到才退回
    // 累计互动，并且把口径写清楚 —— 以前这里用「累计互动 ÷ 每日目标」，
    // 标题却叫里程碑，两个口径混在一起，数字看着像永远超额完成。
    final hasDaily = _daily.isNotEmpty;
    final current = hasDaily
        ? (_daily['completed'] as num?)?.toInt() ?? 0
        : g.totalInteractions;
    final ratio = (current / _dailyGoal).clamp(0.0, 1.0);
    final done =
        hasDaily ? (_daily['achieved'] == true) : current >= _dailyGoal;
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.flag_rounded, size: 18, color: p.gold),
              const SizedBox(width: 10),
              Text(hasDaily ? '今日互动目标' : '累计互动（后端未提供今日计数）',
                  style: TextStyle(
                      fontSize: XlFont.h6,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.normal)),
              const Spacer(),
              _tinyChip(p, done ? '已达成' : '进行中', done ? p.green : p.gold),
            ],
          ),
          const SizedBox(height: 18),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              _AnimatedCounter(
                value: current.toDouble(),
                decimals: 0,
                duration: const Duration(milliseconds: 700),
                style: TextStyle(
                        fontSize: 40,
                        fontWeight: FontWeight.w800,
                        color: p.text1,
                        letterSpacing: -1.5,
                        fontFeatures: const [FontFeature.tabularFigures()],
                        height: 1.0)
                    .optical,
              ),
              Text(' / $_dailyGoal 次',
                  style: TextStyle(
                      fontSize: XlFont.caption,
                      fontWeight: FontWeight.w700,
                      color: p.text3,
                      letterSpacing: XlLetterSpacing.wide)),
            ],
          ),
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(99),
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: ratio),
              duration: const Duration(milliseconds: 900),
              curve: XlCurve.easeOut,
              builder: (_, v, __) => Container(
                height: 10,
                decoration: BoxDecoration(
                  color: p.surfaceLo,
                  borderRadius: BorderRadius.circular(99),
                ),
                child: FractionallySizedBox(
                  alignment: Alignment.centerLeft,
                  widthFactor: v,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(colors: [p.gold, p.pink]),
                      borderRadius: BorderRadius.circular(99),
                      boxShadow: [
                        BoxShadow(
                            color: p.pink.withOpacity(0.4),
                            blurRadius: 10,
                            spreadRadius: -2)
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _goalStepBtn(p, Icons.remove_rounded, () => _adjustDailyGoal(-5)),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                    '里程碑每 5 次可调，再聊 ${(_dailyGoal - current).clamp(0, 999)} 次即可达成',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        fontSize: XlFont.label,
                        color: p.text3,
                        fontWeight: FontWeight.w600,
                        letterSpacing: XlLetterSpacing.wider)),
              ),
              const SizedBox(width: 10),
              _goalStepBtn(p, Icons.add_rounded, () => _adjustDailyGoal(5)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _goalStepBtn(XlPalette p, IconData icon, VoidCallback onTap) {
    return _Pressable(
      onTap: onTap,
      child: Container(
        width: 38,
        height: 38,
        decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
        child: Icon(icon, size: 16, color: p.pink),
      ),
    );
  }

  Widget _weekCompareCard(XlPalette p) {
    final g = _data!;
    // 「亲密度」以前拿的是 g.normalizedProgress / 100 —— 那是成长进度
    // （progress_percent，由训练轮次/样本量算出来），跟亲密度是两回事，
    // 名字却叫亲密度。现在读后端 relationship.progress（到下一档的真实进度）。
    // value 为 null 表示后端没给，条形画空 + 标「未获取」，不再拿 0 冒充。
    final rel = (_persona['relationship'] as Map?) ?? const {};
    double? relProgress = (rel['progress'] as num?)?.toDouble();
    if (relProgress != null)
      relProgress = relProgress.clamp(0.0, 1.0).toDouble();
    final rows = <_RealMetric>[
      _RealMetric('亲密度（到下一档）', relProgress, p.pink),
      _RealMetric('成长进度',
          (g.normalizedProgress / 100).clamp(0.0, 1.0).toDouble(), p.gold),
      _RealMetric('情绪能量', _emotionIntensity, p.violet),
    ];
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.insights_rounded, size: 18, color: p.pink),
              const SizedBox(width: 10),
              Text('当前状态',
                  style: TextStyle(
                      fontSize: XlFont.h6,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.normal)),
              const Spacer(),
              Text('实时',
                  style: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.green,
                      fontWeight: FontWeight.w800,
                      letterSpacing: XlLetterSpacing.wider)),
            ],
          ),
          const SizedBox(height: 18),
          for (final r in rows) ...[
            Row(
              children: [
                Container(
                    width: 8,
                    height: 8,
                    decoration: AppTheme.glowDot(r.color, size: 8)),
                const SizedBox(width: 10),
                Text(r.label,
                    style: TextStyle(
                        fontSize: XlFont.captionSm,
                        color: p.text2,
                        fontWeight: FontWeight.w700,
                        letterSpacing: XlLetterSpacing.wider)),
                const Spacer(),
                Text(
                    r.value == null
                        ? '未获取'
                        : '${(r.value! * 100).clamp(0.0, 100.0).toStringAsFixed(0)}%',
                    style: TextStyle(
                        fontSize: XlFont.captionSm,
                        color: r.value == null ? p.text3 : r.color,
                        fontWeight: FontWeight.w800,
                        fontFeatures: const [FontFeature.tabularFigures()])),
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: r.value?.clamp(0.0, 1.0),
                minHeight: 5,
                backgroundColor: p.surfaceLo,
                valueColor: AlwaysStoppedAnimation(r.color),
              ),
            ),
            const SizedBox(height: 16),
          ],
        ],
      ),
    );
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

  /// 情绪真实强度：后端 EmotionEngine.state.intensity（growth:persona）。
  /// 读不到就返回 null，界面显示「未获取」—— 不再用前端写死的
  /// happy=0.85 / sad=0.3 那种假映射冒充实时读数。
  double? get _emotionIntensity {
    final e = _persona['emotion'];
    if (e is Map) {
      final v = e['intensity'];
      if (v is num) return v.toDouble().clamp(0.0, 1.0).toDouble();
    }
    return null;
  }

  String get _emotionIntensityLabel {
    final v = _emotionIntensity;
    return v == null ? '未获取' : '能量 ${(v * 100).toStringAsFixed(0)}%';
  }

  /// 成长时间线：全部节点的时间与内容都来自后端。
  ///
  /// 旧实现四个节点的日期一律是 `DateTime.now()`，标题写「按时间查看她的
  /// 成长轨迹」，但没有任何一条是历史 —— 是假时间线。现在：
  ///   起点（第一条成长记录的真实日期）→ 有活动的那些天（真实按天统计）
  ///   → 此刻的状态（阶段 / 情绪，带来源）。
  /// 后端没数据时明确显示「还没开始记录」，不编日期。
  List<_TimelineNode> _buildTimeline() {
    final g = _data!;
    final nodes = <_TimelineNode>[];

    final firstDate = (_first['first_date'] ?? '').toString();
    final daysTogether = (_first['days_together'] as num?)?.toInt() ?? 0;
    if (firstDate.isNotEmpty) {
      nodes.add(_TimelineNode(
        '起点',
        '第一条成长记录写于 $firstDate',
        daysTogether > 1 ? '一起走过 $daysTogether 天' : '刚开始记录',
        true,
        'blue',
        _parseDate(firstDate),
        Icons.panorama_fish_eye_rounded,
      ));
    }

    // 最近 3 个有活动的日子（真实日期，倒序展示）
    final recent = _activity.reversed.take(3).toList();
    for (final a in recent) {
      final d = (a['date'] ?? '').toString();
      final samples = (a['samples'] as num?)?.toInt() ?? 0;
      final rounds = (a['rounds'] as num?)?.toInt() ?? 0;
      final parts = <String>[
        if (samples > 0) '新增 $samples 条样本',
        if (rounds > 0) '完成 $rounds 轮训练',
      ];
      nodes.add(_TimelineNode(
        d,
        parts.isEmpty ? '有记录，但没有可统计的增量' : parts.join(' · '),
        rounds > 0 ? '训练日' : '积累日',
        true,
        rounds > 0 ? 'gold' : 'pink',
        _parseDate(d),
        rounds > 0 ? Icons.self_improvement_rounded : Icons.edit_note_rounded,
      ));
    }

    final emo = (_persona['emotion'] as Map?) ?? const {};
    final emoReason = (emo['reason'] ?? '').toString();
    nodes.add(_TimelineNode(
      '当前阶段',
      g.displayStage,
      g.progressLabel,
      g.normalizedProgress > 0,
      'green',
      DateTime.now(),
      Icons.auto_awesome_rounded,
    ));
    nodes.add(_TimelineNode(
      '当前情绪',
      g.displayEmotion,
      emoReason.isEmpty
          ? '情绪来源：后端未提供'
          : '情绪来源：${_emotionReasonLabel(emoReason)}',
      true,
      'violet',
      _parseDate((emo['last_shift_at'] ?? '').toString()),
      Icons.mood_rounded,
    ));

    if (nodes.length <= 2 && _activity.isEmpty) {
      nodes.add(_TimelineNode(
        '还没有历史',
        '成长记录来自真实对话与训练，聊过之后这里才会出现日期',
        '待积累',
        false,
        'violet',
        DateTime.now(),
        Icons.hourglass_empty_rounded,
      ));
    }
    return nodes;
  }

  DateTime _parseDate(String raw) {
    // 后端返回 ISO 字符串或 epoch 秒；解析不了就用今天，但不伪造历史
    if (raw.isEmpty) return DateTime.now();
    final n = double.tryParse(raw);
    if (n != null && n > 1e8) {
      return DateTime.fromMillisecondsSinceEpoch((n * 1000).round());
    }
    return DateTime.tryParse(raw)?.toLocal() ?? DateTime.now();
  }

  static String _emotionReasonLabel(String r) {
    if (r.startsWith('keyword:tired')) return '从你的话里读到「累」';
    if (r.startsWith('keyword:shy')) return '从你的话里读到害羞';
    if (r.startsWith('keyword:positive')) return '从你的话里读到正面情绪';
    if (r.startsWith('keyword:negative')) return '从你的话里读到负面情绪';
    if (r.startsWith('signal:quality')) return '回复质量分变化';
    if (r.startsWith('stale_decay')) return '情绪持续太久，已归零';
    if (r.startsWith('no_signal:decay')) return '没有新线索，强度自然衰减';
    if (r.startsWith('no_signal:idle')) return '长时间没聊，回到平静';
    return r;
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    if (_loading) return _loadingView(p);
    if (_data == null) return _errorView(p);
    if (_data!.totalInteractions == 0) return _emptyState(p);
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
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _stagger(0, _heroRow(p)),
          const SizedBox(height: 22),
          _stagger(1, _heroCard(p)),
          const SizedBox(height: 20),
          _stagger(2, LayoutBuilder(
            builder: (context, c) {
              final stacked = c.maxWidth < 1000;
              if (stacked) {
                return Column(
                  children: [
                    _radialCard(p),
                    const SizedBox(height: 18),
                    _rankCard(p),
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 4, child: _radialCard(p)),
                  const SizedBox(width: 18),
                  Expanded(flex: 5, child: _rankCard(p)),
                ],
              );
            },
          )),
          const SizedBox(height: 20),
          _stagger(3, _statsGrid(p)),
          const SizedBox(height: 20),
          _stagger(4, _growthTools(p)),
          const SizedBox(height: 20),
          _stagger(5, _timelineHeaderCard(p)),
          const SizedBox(height: 20),
          _stagger(6, _timelineList(p)),
        ],
      ),
    );
  }

  Widget _stagger(int index, Widget child) {
    final start = (index * 0.09).clamp(0.0, 0.7);
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
                  Text('成长记录',
                      style: TextStyle(
                        fontSize: XlFont.h2,
                        fontWeight: FontWeight.w800,
                        color: p.text1,
                        letterSpacing: XlLetterSpacing.normal,
                      )),
                  const SizedBox(width: 12),
                  _rankBadge(p),
                ],
              ),
              const SizedBox(height: 6),
              Text('她从第一次打招呼开始，一点一点长成现在的样子',
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
        const SizedBox(width: 10),
        _shareBtn(p),
      ],
    );
  }

  Widget _shareBtn(XlPalette p) {
    return _Pressable(
      onTap: () => _showShareCard(p),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: AppTheme.neuXs(context, r: XlRadius.lg),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.share_rounded, size: 15, color: p.gold),
            const SizedBox(width: 8),
            Text('分享',
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

  void _showShareCard(XlPalette p) {
    final g = _data!;
    final now = DateTime.now();
    showDialog(
      context: context,
      barrierColor: p.scrim,
      builder: (ctx) => Dialog(
        backgroundColor: Colors.transparent,
        elevation: 0,
        child: Container(
          width: 340,
          padding: const EdgeInsets.all(24),
          decoration: AppTheme.brand(context, r: XlRadius.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Icon(Icons.auto_awesome_rounded, size: 16, color: p.btnInk),
                  const SizedBox(width: 8),
                  Text('小凌成长报告',
                      style: TextStyle(
                          fontSize: XlFont.caption,
                          fontWeight: FontWeight.w800,
                          color: p.btnInk,
                          letterSpacing: XlLetterSpacing.wider)),
                ],
              ),
              const SizedBox(height: 20),
              Text(g.displayRank,
                  style: TextStyle(
                      fontSize: XlFont.h3,
                      fontWeight: FontWeight.w800,
                      color: p.btnInk,
                      letterSpacing: -0.5)),
              const SizedBox(height: 6),
              Text(
                  _persona.isEmpty
                      ? '关系数据未获取（后端离线）'
                      : "${(_persona['relationship']?['label'] ?? '未知')} · "
                          '亲密度 ${(_persona['relationship']?['score'] ?? 0)}',
                  style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.btnInk.withOpacity(0.8),
                      fontWeight: FontWeight.w600)),
              const SizedBox(height: 18),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _shareStat(p, '交互', '${g.totalInteractions}'),
                  _shareStat(p, '阶段', g.displayStage),
                  _shareStat(p, '代数', '${g.currentGeneration}'),
                ],
              ),
              const SizedBox(height: 18),
              Text('${now.year}-${_two(now.month)}-${_two(now.day)} · 本地生成',
                  style: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.btnInk.withOpacity(0.6),
                      fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _shareStat(XlPalette p, String label, String value) {
    return Column(
      children: [
        Text(value,
            style: TextStyle(
                fontSize: XlFont.caption,
                fontWeight: FontWeight.w800,
                color: p.btnInk)),
        const SizedBox(height: 3),
        Text(label,
            style: TextStyle(
                fontSize: XlFont.micro,
                color: p.btnInk.withOpacity(0.7),
                fontWeight: FontWeight.w600)),
      ],
    );
  }

  String _two(int n) => n.toString().padLeft(2, '0');

  Widget _rankBadge(XlPalette p) {
    final g = _data!;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        gradient: p.gradBrand,
        borderRadius: BorderRadius.circular(XlRadius.pill),
        boxShadow: [
          ...p.raisedXxs,
          BoxShadow(
              color: p.pink.withOpacity(0.35), blurRadius: 12, spreadRadius: -3)
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.emoji_events_rounded, size: 11, color: p.btnInk),
          const SizedBox(width: 5),
          Text(g.displayRank,
              style: TextStyle(
                fontSize: XlFont.micro,
                fontWeight: FontWeight.w800,
                color: p.btnInk,
                letterSpacing: XlLetterSpacing.wider,
              )),
        ],
      ),
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

  Widget _heroCard(XlPalette p) {
    final g = _data!;
    final prog = g.normalizedProgress;
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: AppTheme.brand(context, r: XlRadius.xxxl),
      child: Stack(
        children: [
          Positioned(
            right: -30,
            top: -30,
            child: AnimatedBuilder(
              animation: _pulseCtrl,
              builder: (_, __) {
                final t = XlEffects.enabled ? _pulseCtrl.value : 0.0;
                return Container(
                  width: 180 + t * 24,
                  height: 180 + t * 24,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.white.withOpacity((1 - t) * 0.14),
                  ),
                );
              },
            ),
          ),
          Positioned(
            right: 40,
            bottom: -50,
            child: Container(
              width: 140,
              height: 140,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withOpacity(0.10),
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.black.withOpacity(p.isDark ? 0.28 : 0.20),
                      borderRadius: BorderRadius.circular(XlRadius.pill),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.auto_awesome_rounded,
                            size: 11, color: p.btnInk),
                        const SizedBox(width: 5),
                        Text('CURRENT STAGE',
                            style: TextStyle(
                              fontSize: XlFont.micro,
                              fontWeight: FontWeight.w800,
                              color: p.btnInk,
                              letterSpacing: XlLetterSpacing.ultra,
                            )),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(g.displayStage,
                      style: TextStyle(
                        fontSize: XlFont.caption,
                        color: p.btnInk.withOpacity(0.85),
                        fontWeight: FontWeight.w700,
                        letterSpacing: XlLetterSpacing.wide,
                      )),
                ],
              ),
              const SizedBox(height: 22),
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  _AnimatedCounter(
                    value: prog,
                    decimals: 1,
                    duration: const Duration(milliseconds: 800),
                    style: TextStyle(
                      fontSize: 64,
                      fontWeight: FontWeight.w800,
                      color: p.btnInk,
                      height: 0.95,
                      letterSpacing: -2.0,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ).optical,
                  ),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10, left: 4),
                    child: Text('%',
                        style: TextStyle(
                          fontSize: XlFont.h3,
                          fontWeight: FontWeight.w800,
                          color: p.btnInk.withOpacity(0.7),
                        )),
                  ),
                  const Spacer(),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text('进化代数',
                          style: TextStyle(
                            fontSize: XlFont.label,
                            color: p.btnInk.withOpacity(0.7),
                            fontWeight: FontWeight.w700,
                            letterSpacing: XlLetterSpacing.wider,
                          )),
                      const SizedBox(height: 4),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.baseline,
                        textBaseline: TextBaseline.alphabetic,
                        children: [
                          _AnimatedCounter(
                            value: g.currentGeneration.toDouble(),
                            decimals: 0,
                            duration: const Duration(milliseconds: 800),
                            style: TextStyle(
                              fontSize: XlFont.h3,
                              fontWeight: FontWeight.w800,
                              color: p.btnInk,
                              fontFeatures: const [
                                FontFeature.tabularFigures()
                              ],
                              height: 1.0,
                            ),
                          ),
                          Text('/${g.totalGenerations}',
                              style: TextStyle(
                                fontSize: XlFont.captionSm,
                                fontWeight: FontWeight.w700,
                                color: p.btnInk.withOpacity(0.7),
                              )),
                        ],
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text('成长进度',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    color: p.btnInk.withOpacity(0.75),
                    fontWeight: FontWeight.w600,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
              const SizedBox(height: 14),
              Container(
                height: 10,
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(p.isDark ? 0.22 : 0.16),
                  borderRadius: BorderRadius.circular(99),
                ),
                child: Stack(
                  children: [
                    TweenAnimationBuilder<double>(
                      duration: const Duration(milliseconds: 1100),
                      curve: XlCurve.easeOut,
                      tween: Tween(begin: 0.0, end: g.progressRatio),
                      builder: (_, v, __) => FractionallySizedBox(
                        widthFactor: v,
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(99),
                          child: Stack(
                            fit: StackFit.expand,
                            children: [
                              Container(
                                decoration: BoxDecoration(
                                  color: p.btnInk,
                                  borderRadius: BorderRadius.circular(99),
                                  boxShadow: [
                                    BoxShadow(
                                        color: p.btnInk.withOpacity(0.4),
                                        blurRadius: 10,
                                        spreadRadius: -2)
                                  ],
                                ),
                              ),
                              _ShimmerSweep(anim: _pulseCtrl),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              Row(
                children: [
                  _heroPill(p, Icons.favorite_rounded, g.interactionsLabel),
                  const SizedBox(width: 8),
                  AnimatedSwitcher(
                    duration: XlDuration.normal,
                    transitionBuilder: (child, anim) => FadeTransition(
                      opacity: anim,
                      child: ScaleTransition(
                          scale: Tween(begin: 0.9, end: 1.0).animate(anim),
                          child: child),
                    ),
                    child: _heroPill(p, Icons.mood_rounded, g.displayEmotion,
                        key: ValueKey(g.displayEmotion)),
                  ),
                  const SizedBox(width: 8),
                  _heroPill(
                      p,
                      g.paused ? Icons.pause_rounded : Icons.play_arrow_rounded,
                      g.trainingLabel),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Text('情绪能量',
                      style: TextStyle(
                        fontSize: XlFont.micro,
                        color: p.btnInk.withOpacity(0.6),
                        fontWeight: FontWeight.w600,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                  const Spacer(),
                  _emotionSparkline(p),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _heroPill(XlPalette p, IconData icon, String text, {Key? key}) {
    return Container(
      key: key,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(p.isDark ? 0.22 : 0.16),
        borderRadius: BorderRadius.circular(XlRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: p.btnInk.withOpacity(0.85)),
          const SizedBox(width: 5),
          Text(text,
              style: TextStyle(
                fontSize: XlFont.label,
                fontWeight: FontWeight.w800,
                color: p.btnInk.withOpacity(0.9),
                letterSpacing: XlLetterSpacing.wide,
              )),
        ],
      ),
    );
  }

  Widget _radialCard(XlPalette p) {
    final g = _data!;
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('成长圆环',
                        style: TextStyle(
                          fontSize: XlFont.h6,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.normal,
                        )),
                    const SizedBox(height: 3),
                    Text('当前阶段的整体完成度',
                        style: TextStyle(
                          fontSize: XlFont.label,
                          color: p.text3,
                          fontWeight: FontWeight.w500,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                  ],
                ),
              ),
              _tinyChip(p, 'LIVE', p.green),
            ],
          ),
          const SizedBox(height: 20),
          AspectRatio(
            aspectRatio: 1,
            child: AnimatedBuilder(
              animation: _radialAnim,
              builder: (_, __) => CustomPaint(
                painter: _RadialPainter(
                  palette: p,
                  progress: _radialAnim.value,
                  target: g.progressRatio,
                  gen: g.currentGeneration,
                  totalGen: g.totalGenerations == 0 ? 1 : g.totalGenerations,
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _legendDot(p, p.pink, '已完成'),
              const SizedBox(width: 16),
              _legendDot(p, p.gold, '当前阶段'),
              const SizedBox(width: 16),
              _legendDot(p, p.text3, '未解锁'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _legendDot(XlPalette p, Color c, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: AppTheme.glowDot(c, size: 8),
        ),
        const SizedBox(width: 6),
        Text(label,
            style: TextStyle(
              fontSize: XlFont.micro,
              color: p.text3,
              fontWeight: FontWeight.w700,
              letterSpacing: XlLetterSpacing.wider,
            )),
      ],
    );
  }

  Widget _rankCard(XlPalette p) {
    // 档位、阈值、当前处于第几级全部来自后端 growth:persona（LEVEL_CONFIG 的
    // 真值）。以前这里是 Dart 写死的五档假文案 + 写死「第 3 级」+ 写死
    // current = i == 2，后端把阈值改了前端永远不知道，而且新用户一进来
    // 就显示「已解锁 3 档」——那是假数据。
    final levels = (_persona['levels'] as List?)
            ?.whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList() ??
        const <Map<String, dynamic>>[];
    final rel = (_persona['relationship'] as Map?) ?? const {};
    final curIdx = (_persona['level_index'] as num?)?.toInt() ?? -1;
    final score = (rel['score'] as num?)?.toDouble();
    final nextThreshold = (rel['next_threshold'] as num?)?.toInt();
    final isMax = _persona['is_max'] == true;

    Widget body;
    if (levels.isEmpty) {
      body = Padding(
        padding: const EdgeInsets.symmetric(vertical: 18),
        child: Text(
          _metaError ??
              '后端未提供关系档位数据（growth:persona）\n'
                  '这里不再显示写死的等级 —— 需要后端连上才能拿到真实进度。',
          style: TextStyle(
            fontSize: XlFont.label,
            color: p.text3,
            height: XlLineHeight.relaxed,
            letterSpacing: XlLetterSpacing.wide,
          ),
        ),
      );
    } else {
      body = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 18),
          for (int i = 0; i < levels.length; i++)
            Padding(
              padding: EdgeInsets.only(bottom: i == levels.length - 1 ? 0 : 10),
              child: _rankRow(p, _RankRow.fromBackend(levels[i], score ?? 0.0),
                  i, i == curIdx),
            ),
        ],
      );
    }

    return Container(
      padding: const EdgeInsets.all(22),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('关系等级',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              if (levels.isNotEmpty)
                _tinyChip(
                    p,
                    isMax ? '已满级' : (curIdx >= 0 ? '第 ${curIdx + 1} 级' : '未知'),
                    p.gold),
            ],
          ),
          body,
          if (levels.isNotEmpty) ...[
            const SizedBox(height: 14),
            Text(
              score == null
                  ? '亲密度数据未就绪'
                  : (isMax
                      ? '亲密度 $score（已达最高档）'
                      : '亲密度 $score / ${nextThreshold ?? '-'} 进入下一档'),
              style: TextStyle(
                fontSize: XlFont.micro,
                color: p.text3,
                fontWeight: FontWeight.w700,
                letterSpacing: XlLetterSpacing.wider,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _rankRow(XlPalette p, _RankRow r, int i, bool current) {
    final color = _colorOf(p, r.color);
    return TweenAnimationBuilder<double>(
      duration: Duration(milliseconds: 320 + i * 70),
      curve: XlCurve.easeOut,
      tween: Tween(begin: 0.0, end: 1.0),
      builder: (_, t, child) => Opacity(
        opacity: t,
        child:
            Transform.translate(offset: Offset((1 - t) * 10, 0), child: child),
      ),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: current
            ? AppTheme.sunkenSm(context, r: XlRadius.md)
            : (r.unlocked ? AppTheme.neuXs(context, r: XlRadius.md) : null),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                gradient: r.unlocked
                    ? LinearGradient(colors: [color, color.withOpacity(0.75)])
                    : null,
                color: r.unlocked ? null : p.surfaceLo,
                borderRadius: BorderRadius.circular(XlRadius.sm),
                border: Border.all(
                  color: r.unlocked
                      ? Colors.white.withOpacity(p.isDark ? 0.32 : 0.48)
                      : p.shDark.withOpacity(p.isDark ? 0.28 : 0.12),
                  width: 1,
                ),
                boxShadow: r.unlocked
                    ? [
                        ...p.raisedXxs,
                        BoxShadow(
                            color: color.withOpacity(0.3),
                            blurRadius: 12,
                            spreadRadius: -2)
                      ]
                    : p.sunkenXxs,
              ),
              child: Icon(
                r.icon,
                size: 15,
                color:
                    r.unlocked ? (p.btnInk) : p.decor,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(r.name,
                          style: TextStyle(
                            fontSize: XlFont.captionSm,
                            fontWeight: FontWeight.w800,
                            color: r.unlocked ? p.text1 : p.text2,
                            letterSpacing: XlLetterSpacing.wide,
                          )),
                      if (current) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: color.withOpacity(p.isDark ? 0.18 : 0.14),
                            borderRadius: BorderRadius.circular(XlRadius.pill),
                          ),
                          child: Text('NOW',
                              style: TextStyle(
                                fontSize: XlFont.micro,
                                fontWeight: FontWeight.w800,
                                color: color,
                                letterSpacing: XlLetterSpacing.ultra,
                              )),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(r.desc,
                      style: TextStyle(
                        fontSize: XlFont.label,
                        color: p.text3,
                        fontWeight: FontWeight.w500,
                        height: XlLineHeight.relaxed,
                        letterSpacing: XlLetterSpacing.wide,
                      )),
                ],
              ),
            ),
            if (!r.unlocked)
              Icon(Icons.lock_outline_rounded, size: 14, color: p.decor),
            if (r.unlocked && !current)
              Icon(Icons.check_circle_rounded, size: 15, color: color),
          ],
        ),
      ),
    );
  }

  Widget _growthTools(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LayoutBuilder(
          builder: (context, c) {
            if (c.maxWidth < 900) {
              return Column(
                children: [
                  _dailyGoalCard(p),
                  const SizedBox(height: 18),
                  _weekCompareCard(p),
                ],
              );
            }
            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: _dailyGoalCard(p)),
                const SizedBox(width: 18),
                Expanded(child: _weekCompareCard(p)),
              ],
            );
          },
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            _Pressable(
              onTap: _exportGrowthData,
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                decoration: AppTheme.neuXs(context, r: XlRadius.lg),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.ios_share_rounded, size: 15, color: p.pink),
                    const SizedBox(width: 8),
                    Text('导出成长数据',
                        style: TextStyle(
                            fontSize: XlFont.captionSm,
                            fontWeight: FontWeight.w700,
                            color: p.text1,
                            letterSpacing: XlLetterSpacing.wider)),
                  ],
                ),
              ),
            ),
            // 暂停/运维：后端已把这两件事接成 growth: 指令，前端不能再只显示
            // trainingPaused 却没有任何入口改它。
            _Pressable(
              onTap: _opsBusy ? null : _toggleGrowthPause,
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                decoration: AppTheme.neuXs(context, r: XlRadius.lg),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                        _growthPaused()
                            ? Icons.play_circle_outline_rounded
                            : Icons.pause_circle_outline_rounded,
                        size: 15,
                        color: _growthPaused() ? p.green : p.orange),
                    const SizedBox(width: 8),
                    Text(_growthPaused() ? '恢复成长' : '暂停成长',
                        style: TextStyle(
                            fontSize: XlFont.captionSm,
                            fontWeight: FontWeight.w700,
                            color: p.text1,
                            letterSpacing: XlLetterSpacing.wider)),
                  ],
                ),
              ),
            ),
            _Pressable(
              onTap: _showOpsSheet,
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                decoration: AppTheme.neuXs(context, r: XlRadius.lg),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.tune_rounded, size: 15, color: p.violet),
                    const SizedBox(width: 8),
                    Text('成长运维',
                        style: TextStyle(
                            fontSize: XlFont.captionSm,
                            fontWeight: FontWeight.w700,
                            color: p.text1,
                            letterSpacing: XlLetterSpacing.wider)),
                  ],
                ),
              ),
            ),
          ],
        ),
        if (_opsError != null) ...[
          const SizedBox(height: 10),
          Text(_opsError!,
              style: TextStyle(
                  fontSize: XlFont.labelSm, color: p.red, height: 1.5)),
        ] else if (_ops != null && _growthPaused()) ...[
          const SizedBox(height: 10),
          Text(
              '成长已暂停：${_ops?['pause_reason'] ?? '未记录原因'}'
              '。对话记录照常收集，只是不再自动训练与晋升。',
              style: TextStyle(
                  fontSize: XlFont.labelSm, color: p.text3, height: 1.5)),
        ],
      ],
    );
  }

  /// 暂停状态以后端 growth:status 为准（与 should_train 读的是同一个值）；
  /// 指令不可用时退回 proto 的 trainingPaused —— proto 只有 9 个字段，
  /// 装不下阻塞原因，所以它只能当兜底，不能当权威。
  bool _growthPaused() =>
      _ops != null ? _ops!['paused'] == true : (_data?.paused ?? false);

  Widget _statsGrid(XlPalette p) {
    final g = _data!;
    // 训练状态条以前写死 `paused ? 0.3 : 0.75` —— 一个和任何真实量都无关的
    // 装饰性数字。现在用训练流的真实步数进度；没在训练/暂停时给 null，
    // 让条形画空并且明说「未在训练」。
    final t = _training;
    final trainingProgress = (t != null && t.isTraining && t.totalEpochs > 0)
        ? t.progressRatio
        : null;
    final items = <_GrowthStat>[
      _GrowthStat(
          '交互次数',
          '${g.totalInteractions}',
          '次',
          Icons.chat_bubble_outline_rounded,
          'pink',
          (g.totalInteractions / 200).clamp(0.0, 1.0).toDouble(),
          '累计对话',
          number: g.totalInteractions.toDouble()),
      _GrowthStat('当前情绪', g.displayEmotion, '', Icons.mood_rounded, 'gold',
          _emotionIntensity, _emotionIntensityLabel),
      _GrowthStat(
          '训练状态',
          g.trainingLabel,
          '',
          Icons.auto_awesome_rounded,
          'violet',
          trainingProgress,
          g.paused
              ? '手动暂停'
              : (trainingProgress == null
                  ? '当前未在训练'
                  : '进度 ${(trainingProgress * 100).toStringAsFixed(0)}%')),
      _GrowthStat('当前段位', g.displayRank, '', Icons.emoji_events_rounded,
          'green', g.generationRatio, '第 ${g.currentGeneration} 代'),
    ];
    return LayoutBuilder(
      builder: (context, c) {
        final cols = c.maxWidth > 1180
            ? 4
            : c.maxWidth > 780
                ? 2
                : 1;
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: cols,
            mainAxisSpacing: 14,
            crossAxisSpacing: 14,
            childAspectRatio: cols == 4 ? 1.55 : (cols == 2 ? 2.1 : 2.8),
          ),
          itemCount: items.length,
          itemBuilder: (_, i) => _statCard(p, items[i], i),
        );
      },
    );
  }

  Widget _statCard(XlPalette p, _GrowthStat s, int i) {
    final color = _colorOf(p, s.color);
    return TweenAnimationBuilder<double>(
      duration: Duration(milliseconds: 400 + i * 80),
      curve: XlCurve.easeOut,
      tween: Tween(begin: 0.0, end: 1.0),
      builder: (_, t, child) => Transform.translate(
        offset: Offset(0, (1 - t) * 14),
        child: Opacity(opacity: t, child: child),
      ),
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: AppTheme.neu(context, r: XlRadius.xl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                    borderRadius: BorderRadius.circular(XlRadius.md),
                    border:
                        Border.all(color: color.withOpacity(0.28), width: 1),
                    boxShadow: [
                      BoxShadow(
                          color: color.withOpacity(0.20),
                          blurRadius: 14,
                          spreadRadius: -3)
                    ],
                  ),
                  child: Icon(s.icon, size: 18, color: color),
                ),
                const Spacer(),
                Tooltip(
                  message: _statHint(s.label),
                  decoration: BoxDecoration(
                    color: p.surfaceHi,
                    borderRadius: BorderRadius.circular(XlRadius.sm),
                  ),
                  textStyle: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.text1,
                      fontWeight: FontWeight.w600),
                  child: Icon(Icons.info_outline_rounded,
                      size: 13, color: p.decor),
                ),
                const SizedBox(width: 6),
                Text(s.hint,
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.text3,
                      fontWeight: FontWeight.w700,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Flexible(
                  child: s.number != null
                      ? _AnimatedCounter(
                          value: s.number!,
                          decimals: 0,
                          duration: const Duration(milliseconds: 800),
                          style: TextStyle(
                            fontSize:
                                s.value.length > 4 ? XlFont.h4 : XlFont.h2,
                            fontWeight: FontWeight.w800,
                            color: p.text1,
                            letterSpacing: XlLetterSpacing.tight,
                            fontFeatures: const [FontFeature.tabularFigures()],
                            height: 1.0,
                          ),
                        )
                      : Text(s.value,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize:
                                s.value.length > 4 ? XlFont.h4 : XlFont.h2,
                            fontWeight: FontWeight.w800,
                            color: p.text1,
                            letterSpacing: XlLetterSpacing.tight,
                            fontFeatures: const [FontFeature.tabularFigures()],
                            height: 1.0,
                          )),
                ),
                if (s.unit.isNotEmpty) ...[
                  const SizedBox(width: 3),
                  Text(s.unit,
                      style: TextStyle(
                        fontSize: XlFont.captionSm,
                        fontWeight: FontWeight.w700,
                        color: p.text3,
                      )),
                ],
              ],
            ),
            const SizedBox(height: 4),
            Text(s.label,
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.text2,
                  fontWeight: FontWeight.w600,
                  letterSpacing: XlLetterSpacing.wider,
                )),
            const SizedBox(height: 12),
            _neuProgress(p, s.progress, height: 5, color: color),
          ],
        ),
      ),
    );
  }

  String _statHint(String label) {
    switch (label) {
      case '交互次数':
        return '感知维度：累计对话轮次，衡量互动深度';
      case '当前情绪':
        return '情绪指数：理解维度，综合语气与上下文得出';
      case '训练状态':
        return '进化维度：后台微调进度，决定模型响应质量';
      case '当前段位':
        return '守护维度：关系等级，由亲密度阈值决定';
      default:
        return label;
    }
  }

  Widget _emotionSparkline(XlPalette p) {
    // 读不到真实强度时显示一条空槽 + 「无」，不用不确定进度条冒充「在跑」，
    // 也不用写死的 0.5 冒充读数。
    final energy = _emotionIntensity;
    if (energy == null) {
      return SizedBox(
        width: 60,
        height: 20,
        child: Center(
          child: Text('无数据',
              style: TextStyle(
                  fontSize: XlFont.micro,
                  color: p.text3,
                  fontWeight: FontWeight.w700,
                  letterSpacing: XlLetterSpacing.wider)),
        ),
      );
    }
    return Container(
      width: 60,
      height: 20,
      margin: const EdgeInsets.only(left: 4),
      alignment: Alignment.center,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(99),
        child: LinearProgressIndicator(
          value: energy,
          minHeight: 5,
          backgroundColor: Colors.black.withOpacity(0.2),
          valueColor: AlwaysStoppedAnimation(p.btnInk),
        ),
      ),
    );
  }

  Widget _timelineHeaderCard(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('时间轴视图',
                    style: TextStyle(
                      fontSize: XlFont.h6,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.normal,
                    )),
                const SizedBox(height: 4),
                Text('按时间查看她的成长轨迹',
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text3,
                      fontWeight: FontWeight.w500,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.all(4),
            decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
            child: Row(
              children: List.generate(_ranges.length, (i) {
                final selected = _rangeIndex == i;
                return _Pressable(
                  onTap: () {
                    setState(() => _rangeIndex = i);
                    _timelineCtrl.forward(from: 0);
                    // 时间范围决定向后端要几天的数据，切换必须重新取，
                    // 否则「7 天 / 30 天 / 全部」切了个寂寞（原来只是重放动画）。
                    _loadMeta();
                  },
                  child: AnimatedContainer(
                    duration: XlDuration.fast,
                    curve: XlCurve.standard,
                    padding:
                        const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                    decoration: selected
                        ? BoxDecoration(
                            gradient: p.gradBrand,
                            borderRadius: BorderRadius.circular(XlRadius.pill),
                            boxShadow: p.raisedXxs,
                          )
                        : null,
                    child: Text(_ranges[i],
                        style: TextStyle(
                          fontSize: XlFont.label,
                          fontWeight:
                              selected ? FontWeight.w800 : FontWeight.w600,
                          color: selected ? p.btnInk : p.text2,
                          letterSpacing: XlLetterSpacing.wide,
                        )),
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  Widget _timelineList(XlPalette p) {
    final nodes = _buildTimeline();
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('成长节点',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              Text('${nodes.where((n) => n.done).length}/${nodes.length} 已解锁',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w700,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
          const SizedBox(height: 20),
          AnimatedBuilder(
            animation: _timelineAnim,
            builder: (_, __) {
              return Column(
                children: List.generate(nodes.length, (i) {
                  final delay = i * 0.12;
                  final t = ((_timelineAnim.value - delay) / (1 - delay))
                      .clamp(0.0, 1.0);
                  return _timelineItem(p, nodes[i], i, nodes.length, t);
                }),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _timelineItem(
      XlPalette p, _TimelineNode n, int i, int total, double t) {
    final color = _colorOf(p, n.color);
    final last = i == total - 1;
    return Opacity(
      opacity: t,
      child: Transform.translate(
        offset: Offset((1 - t) * 16, 0),
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SizedBox(
                width: 40,
                child: Column(
                  children: [
                    ScaleTransition(
                      scale: Tween(begin: 0.0, end: 1.0).animate(
                          CurvedAnimation(
                              parent: _timelineCtrl,
                              curve: Interval((i * 0.12).clamp(0.0, 0.9),
                                  ((i * 0.12) + 0.4).clamp(0.0, 1.0),
                                  curve: XlCurve.spring))),
                      child: Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          gradient: n.done
                              ? LinearGradient(
                                  colors: [color, color.withOpacity(0.72)])
                              : null,
                          color: n.done ? null : p.surfaceLo,
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: n.done
                                ? Colors.white
                                    .withOpacity(p.isDark ? 0.32 : 0.48)
                                : p.shDark.withOpacity(p.isDark ? 0.30 : 0.13),
                            width: 1.4,
                          ),
                          boxShadow: n.done
                              ? [
                                  ...p.raisedXxs,
                                  BoxShadow(
                                      color: color.withOpacity(0.35),
                                      blurRadius: 14,
                                      spreadRadius: -3)
                                ]
                              : p.sunkenXxs,
                        ),
                        child: Icon(
                          n.icon,
                          size: 16,
                          color: n.done
                              ? (p.btnInk)
                              : p.decor,
                        ),
                      ),
                    ),
                    if (!last)
                      Expanded(
                        child: Container(
                          width: 2,
                          margin: const EdgeInsets.symmetric(vertical: 4),
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [
                                color.withOpacity(n.done ? 0.5 : 0.15),
                                i + 1 < total && !n.done
                                    ? Colors.transparent
                                    : color.withOpacity(0.3),
                              ],
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Padding(
                  padding: EdgeInsets.only(bottom: last ? 0 : 20, top: 4),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(n.title,
                                style: TextStyle(
                                  fontSize: XlFont.caption,
                                  fontWeight: FontWeight.w800,
                                  color: n.done ? p.text1 : p.text2,
                                  letterSpacing: XlLetterSpacing.wide,
                                )),
                          ),
                          _statusPill(p, n.status, n.done, color),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(n.desc,
                          style: TextStyle(
                            fontSize: XlFont.label,
                            color: p.text3,
                            fontWeight: FontWeight.w500,
                            height: XlLineHeight.relaxed,
                            letterSpacing: XlLetterSpacing.wide,
                          )),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Icon(Icons.schedule_rounded,
                              size: 11, color: p.decor),
                          const SizedBox(width: 5),
                          Text(_formatDate(n.date),
                              style: TextStyle(
                                fontSize: XlFont.micro,
                                color: p.decor,
                                fontWeight: FontWeight.w700,
                                letterSpacing: XlLetterSpacing.wider,
                              )),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _statusPill(XlPalette p, String text, bool active, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: active ? color.withOpacity(p.isDark ? 0.14 : 0.10) : p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(
          color: active ? color.withOpacity(0.30) : p.edgeSoft,
          width: 1,
        ),
      ),
      child: Text(text,
          style: TextStyle(
            fontSize: XlFont.micro,
            fontWeight: FontWeight.w800,
            color: active ? color : p.text3,
            letterSpacing: XlLetterSpacing.wider,
          )),
    );
  }

  String _formatDate(DateTime d) {
    final now = DateTime.now();
    final diff = d.difference(now).inDays;
    if (diff.abs() < 1) return '今天';
    if (diff > 0) return '$diff 天后';
    return '${-diff} 天前';
  }

  Widget _neuProgress(XlPalette p, double? value,
      {double height = 5, Color? color}) {
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
        widthFactor: (value ?? 0.0).clamp(0.0, 1.0),
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [c.withOpacity(0.7), c]),
            borderRadius: BorderRadius.circular(99),
            boxShadow: [
              BoxShadow(
                  color: c.withOpacity(0.35), blurRadius: 8, spreadRadius: -2)
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

  Widget _emptyState(XlPalette p) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedBuilder(
            animation: _pulseCtrl,
            builder: (_, __) {
              final t = XlEffects.enabled ? _pulseCtrl.value : 0.0;
              return Stack(
                alignment: Alignment.center,
                children: [
                  Container(
                    width: 96 + t * 18,
                    height: 96 + t * 18,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: p.pink.withOpacity((1 - t) * 0.14),
                    ),
                  ),
                  Container(
                    width: 96,
                    height: 96,
                    decoration: AppTheme.brandOrb(context, size: 96),
                    child:
                        Icon(Icons.favorite_rounded, size: 38, color: p.btnInk),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 24),
          Text('开始互动，见证成长',
              style: TextStyle(
                fontSize: XlFont.h5,
                fontWeight: FontWeight.w800,
                color: p.text1,
                letterSpacing: XlLetterSpacing.normal,
              )),
          const SizedBox(height: 8),
          Text('每一次对话，都会让她变得更懂你',
              style: TextStyle(
                fontSize: XlFont.caption,
                color: p.text3,
                fontWeight: FontWeight.w500,
                letterSpacing: XlLetterSpacing.wider,
              )),
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
          Row(children: [
            _skeleton(p, width: 140, height: 30, radius: 10),
            const SizedBox(width: 12),
            _skeleton(p, width: 70, height: 22, radius: 99)
          ]),
          const SizedBox(height: 22),
          _skeleton(p, width: double.infinity, height: 180, radius: 26),
          const SizedBox(height: 20),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                  child: _skeleton(p,
                      width: double.infinity, height: 260, radius: 22)),
              const SizedBox(width: 18),
              Expanded(
                  flex: 5,
                  child: _skeleton(p,
                      width: double.infinity, height: 260, radius: 22)),
            ],
          ),
          const SizedBox(height: 20),
          _skeleton(p, width: double.infinity, height: 110, radius: 22),
          const SizedBox(height: 20),
          for (int i = 0; i < 3; i++) ...[
            _skeleton(p, width: double.infinity, height: 72, radius: 18),
            const SizedBox(height: 14),
          ],
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
        child: AnimatedBuilder(
          animation: _pulseCtrl,
          builder: (_, __) {
            return LayoutBuilder(builder: (ctx, c) {
              final w = c.maxWidth;
              final dx = (_pulseCtrl.value * 2.2 - 0.6) * w;
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
        ),
      ),
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

class _RadialPainter extends CustomPainter {
  final XlPalette palette;
  final double progress;
  final double target;
  final int gen;
  final int totalGen;
  _RadialPainter({
    required this.palette,
    required this.progress,
    required this.target,
    required this.gen,
    required this.totalGen,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final baseR = size.width / 2 - 40;
    if (baseR <= 0) return;

    final trackPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    trackPaint
      ..strokeWidth = 14
      ..color = palette.surfaceLo;
    canvas.drawCircle(center, baseR, trackPaint);

    trackPaint
      ..strokeWidth = 1.4
      ..color = palette.text2.withOpacity(0.10);
    canvas.drawCircle(center, baseR - 8, trackPaint);
    canvas.drawCircle(center, baseR + 8, trackPaint);

    final segments = 40;
    final segAngle = 2 * math.pi / segments;
    final activeSegs = (segments * target * progress).round();

    for (var i = 0; i < activeSegs; i++) {
      final a0 = -math.pi / 2 + i * segAngle;
      final a1 = a0 + segAngle * 0.72;
      final rect = Rect.fromCircle(center: center, radius: baseR);
      final segPaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 14
        ..strokeCap = StrokeCap.round
        ..shader = SweepGradient(
          startAngle: a0,
          endAngle: a1,
          colors: [palette.pink, palette.gold],
          transform: GradientRotation(-math.pi / 2),
        ).createShader(rect);
      canvas.drawArc(rect, a0, a1 - a0, false, segPaint);
    }

    final arcRects = Rect.fromCircle(center: center, radius: baseR);
    final sweepPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 14
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        colors: [palette.pink, palette.gold, palette.violet, palette.pink],
        stops: const [0.0, 0.35, 0.7, 1.0],
      ).createShader(arcRects);

    canvas.drawArc(
      arcRects,
      -math.pi / 2,
      2 * math.pi * target * progress,
      false,
      sweepPaint,
    );

    final glowPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 26
      ..strokeCap = StrokeCap.round
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 12)
      ..shader = SweepGradient(
        colors: [
          palette.pink.withOpacity(0.5),
          palette.gold.withOpacity(0.3),
          palette.pink.withOpacity(0.5),
        ],
      ).createShader(arcRects);

    canvas.drawArc(
      arcRects,
      -math.pi / 2,
      2 * math.pi * target * progress,
      false,
      glowPaint,
    );

    final dotAngle = -math.pi / 2 + 2 * math.pi * target * progress;
    final dotCenter = Offset(
      center.dx + baseR * math.cos(dotAngle),
      center.dy + baseR * math.sin(dotAngle),
    );

    canvas.drawCircle(
        dotCenter, 14, Paint()..color = palette.pink.withOpacity(0.24));
    canvas.drawCircle(dotCenter, 9, Paint()..color = palette.gold);
    canvas.drawCircle(dotCenter, 5, Paint()..color = palette.bg);

    final innerR = baseR - 26;
    final innerTrack = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..color = palette.surfaceLo;
    canvas.drawCircle(center, innerR, innerTrack);

    final innerFill = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round
      ..shader = LinearGradient(
        colors: [palette.violet, palette.pink],
      ).createShader(Rect.fromCircle(center: center, radius: innerR));

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: innerR),
      -math.pi / 2,
      2 * math.pi * (gen / (totalGen == 0 ? 1 : totalGen)) * progress,
      false,
      innerFill,
    );

    final p1 = TextPainter(textDirection: TextDirection.ltr)
      ..text = TextSpan(
        text: '${(target * 100).toStringAsFixed(1)}',
        style: TextStyle(
          fontSize: 34,
          fontWeight: FontWeight.w800,
          color: palette.text1,
          letterSpacing: -0.8,
          fontFeatures: const [FontFeature.tabularFigures()],
        ).optical,
      )
      ..layout();
    p1.paint(canvas,
        Offset(center.dx - p1.width / 2, center.dy - p1.height / 2 - 10));

    final p2 = TextPainter(textDirection: TextDirection.ltr)
      ..text = TextSpan(
        text: 'OVERALL',
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w800,
          color: palette.text3,
          letterSpacing: 2.4,
        ),
      )
      ..layout();
    p2.paint(canvas,
        Offset(center.dx - p2.width / 2, center.dy + p2.height / 2 - 2));
  }

  @override
  bool shouldRepaint(covariant _RadialPainter old) =>
      old.progress != progress ||
      old.target != target ||
      old.palette != palette ||
      old.gen != gen ||
      old.totalGen != totalGen;
}

class _TimelineNode {
  final String title;
  final String desc;
  final String status;
  final bool done;
  final String color;
  final DateTime date;
  final IconData icon;
  _TimelineNode(this.title, this.desc, this.status, this.done, this.color,
      this.date, this.icon);
}

/// 关系等级的一档。字段全部来自后端 LEVEL_CONFIG（growth:persona），
/// 只有视觉映射（颜色/图标）留在前端 —— 那是表现，不是数据。
class _RankRow {
  final String name;
  final String desc;
  final String color;
  final bool unlocked;
  final IconData icon;
  final int threshold;
  const _RankRow(this.name, this.desc, this.color, this.unlocked, this.icon,
      {this.threshold = 0});

  factory _RankRow.fromBackend(Map<String, dynamic> level, double score) {
    final threshold = (level['threshold'] as num?)?.toInt() ?? 0;
    final key = (level['level'] ?? '').toString();
    return _RankRow(
      (level['label'] ?? '未命名档位').toString(),
      // 后端的 style 字段就是这一档的相处方式描述（"礼貌客气，保持距离"…）
      (level['style'] ?? '').toString(),
      _rankColorKey(key),
      // 是否解锁由后端阈值 + 当前真实分数决定，不再前端写死前三档亮着
      score >= threshold,
      _rankIcon(key),
      threshold: threshold,
    );
  }

  static String _rankColorKey(String level) {
    switch (level) {
      case 'stranger':
        return 'pink';
      case 'familiar':
        return 'gold';
      case 'friend':
        return 'violet';
      case 'close':
        return 'green';
      case 'bonded':
        return 'blue';
      default:
        return 'violet'; // 后端加了新档位但前端还没配色：给个中性色，
    } // 而不是猜一个可能和相邻档位撞色的
  }

  static IconData _rankIcon(String level) {
    switch (level) {
      case 'stranger':
        return Icons.waving_hand_rounded;
      case 'familiar':
        return Icons.handshake_rounded;
      case 'friend':
        return Icons.psychology_alt_rounded;
      case 'close':
        return Icons.favorite_rounded;
      case 'bonded':
        return Icons.auto_awesome_rounded;
      default:
        return Icons.bolt_rounded;
    }
  }
}

class _GrowthStat {
  final String label;
  final String value;
  final String unit;
  final IconData icon;
  final String color;

  /// null = 后端没给这个量（画空槽），0 = 真的是 0。
  final double? progress;
  final String hint;
  final double? number;
  const _GrowthStat(this.label, this.value, this.unit, this.icon, this.color,
      this.progress, this.hint,
      {this.number});
}

class _Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  const _Pressable({required this.child, this.onTap, this.scale = 0.96});
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
                    Colors.white.withOpacity(0.45),
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

class _AnimatedCounter extends StatelessWidget {
  final double value;
  final int decimals;
  final TextStyle? style;
  final Duration duration;
  const _AnimatedCounter({
    required this.value,
    this.decimals = 0,
    this.style,
    this.duration = const Duration(milliseconds: 800),
  });
  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: value),
      duration: duration,
      curve: XlCurve.easeOut,
      builder: (_, v, __) => Text(v.toStringAsFixed(decimals), style: style),
    );
  }
}

class _RealMetric {
  final String label;

  /// null = 后端没有这个数值。0 是「真的是 0」，两者必须在界面上区分开，
  /// 否则「没数据」会被显示成「数据是零」。
  final double? value;
  final Color color;
  const _RealMetric(this.label, this.value, this.color);
}

/// 成长运维浮层：回滚 / GC / 清库。
///
/// 三条破坏性动作（回滚基底、删旧代、清样本）在这个界面里**必须两步**：
/// 先看演练（`growth:rollback <代>` / `growth:gc` / `growth:purge <范围>`，
/// 后端返回 readonly/dry_run 的预览），再点确认（`confirm`，后端起后台任务）。
/// 演练没通过就点不动确认 —— 前端不替用户猜结果，也不把「没测」显示成「过了」。
class _GrowthOpsDialog extends StatefulWidget {
  final Map<String, dynamic>? ops;
  final Future<Map<String, dynamic>> Function(String cmd) command;
  final Future<Map<String, dynamic>> Function(Map<String, dynamic> started)
      awaitTask;
  final void Function(bool busy) onBusyChanged;

  const _GrowthOpsDialog({
    required this.ops,
    required this.command,
    required this.awaitTask,
    required this.onBusyChanged,
  });

  @override
  State<_GrowthOpsDialog> createState() => _GrowthOpsDialogState();
}

class _GrowthOpsDialogState extends State<_GrowthOpsDialog> {
  static const _scopes = <String>['all', 'trained', 'disliked', 'dpo'];

  Map<String, dynamic> _rb = const {};
  Map<String, dynamic> _gc = const {};
  Map<String, dynamic> _purge = const {};
  int? _rbGen;
  Map<String, dynamic>? _rbPreview;
  String _scope = 'all';
  bool _ackWipe = false;
  bool _gcForce = false;
  bool _loading = true;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final rs = await Future.wait([
        widget.command('growth:rollback'),
        widget.command('growth:gc'),
        widget.command('growth:purge $_scope'),
      ]);
      if (!mounted) return;
      final first = rs[0];
      final trash = (first['trash'] as List? ?? const []).whereType<Map>().toList();
      setState(() {
        _rb = Map<String, dynamic>.from(first);
        _gc = Map<String, dynamic>.from(rs[1]);
        _purge = Map<String, dynamic>.from(rs[2]);
        _rbGen = trash.isEmpty ? null : (trash.first['gen'] as num?)?.toInt();
        _rbPreview = null;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '预览读取失败：$e';
      });
    }
  }

  Future<void> _run(String cmd, String doing,
      {void Function(Map<String, dynamic>)? onDone}) async {
    if (_busy) return;
    setState(() => _busy = true);
    widget.onBusyChanged(true);
    try {
      final d = await widget.command(cmd);
      if (d['ok'] == false && d['task_id'] == null) {
        _toast(false, '$doing：${d['error'] ?? '后端未回应'}');
        return;
      }
      if (onDone != null) {
        onDone(d);
        if (doing == '演练') _toast(d['ok'] == true, _message(d));
        return;
      }
      final fin = await widget.awaitTask(d);
      // 后台任务外层永远 ok:true（任务本身跑完了），作业返回值在 result 里。
      // 只看外层就会把「GC 被稳定期拦住」报成成功，所以两层都要判。
      final inner = fin['result'];
      final ok = fin['ok'] != false &&
          (inner is! Map || inner['ok'] != false) &&
          fin['status'] != 'failed' && fin['status'] != 'cancelled';
      _toast(ok, '$doing：${_message(fin)}');
      if (mounted) setState(() => _rbPreview = null);
      await _load();
    } catch (e) {
      _toast(false, '$doing失败：$e');
    } finally {
      if (mounted) setState(() => _busy = false);
      widget.onBusyChanged(false);
    }
  }

  /// 后台任务把作业返回值塞在 result 里，外层还有 status/error，两层都要看。
  String _message(Map<String, dynamic> d) {
    final inner = d['result'];
    if (inner is Map) {
      final m = inner['message'] ?? inner['error'] ?? inner['reason'];
      if (m != null && '$m'.isNotEmpty) return '$m';
    }
    final top = d['message'] ?? d['error'];
    return (top ?? '后端未给出说明').toString();
  }

  void _toast(bool ok, String msg) {
    if (!mounted) return;
    final p = XlPalette.of(context);
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: ok
            ? p.surface
            : p.red.withOpacity(p.isDark ? 0.24 : 0.14),
        content: Text(msg,
            style: TextStyle(fontWeight: FontWeight.w600, color: p.text1)),
      ));
  }

  int _asInt(dynamic v) => v is num ? v.toInt() : 0;

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final trash = (_rb['trash'] as List? ?? const [])
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
    final rbReady = _rbPreview != null && _rbPreview!['dry_run'] == true;
    final gcDeleted = _gc['deletable'];
    final gcCount = gcDeleted is List ? gcDeleted.length : 0;
    final purgeN = _asInt(_purge['would_remove']);
    final blockers = _opsBlockers();
    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
      child: Container(
        constraints: const BoxConstraints(maxWidth: 560, maxHeight: 640),
        padding: const EdgeInsets.fromLTRB(24, 20, 24, 18),
        decoration: AppTheme.neuLg(context, r: XlRadius.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.tune_rounded, size: 18, color: p.violet),
                const SizedBox(width: 10),
                Text('成长运维',
                    style: TextStyle(
                        fontSize: XlFont.h6,
                        fontWeight: FontWeight.w800,
                        color: p.text1)),
                const Spacer(),
                if (widget.ops != null)
                  _statusPill(
                      widget.ops!['paused'] == true ? '已暂停' : '成长中',
                      true,
                      widget.ops!['paused'] == true ? p.orange : p.green),
              ],
            ),
            const SizedBox(height: 8),
            Text('下面每一项默认只读或演练，只有点了「确认」才会真的动模型与数据。',
                style: TextStyle(
                    fontSize: XlFont.label, color: p.text3, height: 1.5)),
            const SizedBox(height: 14),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(_error!,
                    style: TextStyle(
                        fontSize: XlFont.label, color: p.red, height: 1.5)),
              ),
            Flexible(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (blockers.isNotEmpty) _blockers(blockers),
                    _section(p, '回滚到旧代',
                        detail: _rb['note']?.toString() ?? '读取中…',
                        children: [
                          if (_loading)
                            _hint(p, '正在读回收区…')
                          else if (trash.isEmpty)
                            _hint(p, '回收区为空：还没发生过换代，没有可回滚的基底。')
                          else ...[
                            Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: trash.map((t) {
                                final g = _asInt(t['gen']);
                                final gone = t['exists'] != true;
                                return _choice(
                                    p, gone ? '$g 代（文件已不在）' : '$g 代',
                                    _rbGen == g, () {
                                  setState(() {
                                    _rbGen = g;
                                    _rbPreview = null;
                                  });
                                });
                              }).toList(),
                            ),
                            const SizedBox(height: 10),
                            Row(
                              children: [
                                _btn(p, '演练（不搬文件）', _busy || _rbGen == null,
                                    () => _run('growth:rollback $_rbGen', '演练',
                                        onDone: (d) => setState(() {
                                              _rbPreview = d;
                                            }))),
                                const SizedBox(width: 8),
                                _btn(p, '确认回滚',
                                    _busy || !rbReady || (_rbPreview?['ok'] != true),
                                    () => _run(
                                        'growth:rollback $_rbGen confirm', '回滚'),
                                    danger: true),
                              ],
                            ),
                            if (_rbPreview != null) ...[
                              const SizedBox(height: 10),
                              _preview(p, _message(_rbPreview!)),
                            ],
                          ],
                        ]),
                    _section(p, '清理旧代（GC）',
                        detail: '当前 keep_generations=${_asInt(_gc['keep_generations'])}'
                            '，回收代 ${_asInt(_gc['trash_generations'])} 个',
                        children: [
                          if (_loading)
                            _hint(p, '正在演练…')
                          else ...[
                            _hint(p, _gc['message']?.toString() ??
                                '演练未返回说明（后端可能读不到生命周期登记）'),
                            if (gcCount > 0)
                              _hint(p, '将被删除：$gcCount 个旧代，'
                                  '预计释放 ${_gc['freed_human'] ?? '?'}'),
                            _switchRow(p, '跳过稳定期约束（force）', _gcForce,
                                (v) => setState(() => _gcForce = v)),
                            const SizedBox(height: 6),
                            Row(
                              children: [
                                _btn(p, '重新演练', _busy, _load),
                                const SizedBox(width: 8),
                                _btn(p, '确认删除', _busy,
                                    () => _run('growth:gc run${_gcForce ? ' force' : ''}',
                                        'GC'),
                                    danger: true),
                              ],
                            ),
                          ],
                        ]),
                    _section(p, '清理训练样本',
                        detail: '只删登记过的对话样本，不碰模型文件',
                        children: [
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: _scopes.map((s) {
                              return _choice(p, _scopeLabel(s), _scope == s, () {
                                // 换口径等于换一次不可撤销操作，勾选要作废
                                setState(() {
                                  _scope = s;
                                  _ackWipe = false;
                                });
                                unawaited(_load());
                              });
                            }).toList(),
                          ),
                          const SizedBox(height: 10),
                          if (_loading)
                            _hint(p, '正在统计…')
                          else
                            _hint(p, '预览：按「${_scopeLabel(_scope)}」口径将删除 '
                                '$purgeN 条（只数条数，没有执行任何删除）'),
                          _switchRow(p, '我确认这一步不可撤销', _ackWipe,
                              (v) => setState(() => _ackWipe = v)),
                          const SizedBox(height: 6),
                          _btn(p, '确认清理样本', _busy || !_ackWipe || purgeN == 0,
                              () => _run('growth:purge $_scope confirm', '清库'),
                              danger: true),
                        ]),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                _btn(p, '关闭', false, () => Navigator.pop(context)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  List<String> _opsBlockers() {
    final b = widget.ops?['train_blockers'];
    if (b is List) return b.map((e) => '$e').toList();
    return const [];
  }

  Widget _blockers(List<String> blockers) {
    final p = XlPalette.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('下一轮练不动的原因',
                style: TextStyle(
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w800,
                    color: p.text2)),
            const SizedBox(height: 6),
            ...blockers.map((b) => Text('· $b',
                style: TextStyle(fontSize: XlFont.label, color: p.text3))),
          ],
        ),
      ),
    );
  }

  String _scopeLabel(String s) => const {
        'all': '全部样本',
        'trained': '已训练过的',
        'disliked': '被点踩的',
        'dpo': 'DPO 偏好对',
      }[s] ??
      s;

  Widget _section(XlPalette p, String title,
      {required String detail, required List<Widget> children}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: TextStyle(
                  fontSize: XlFont.bodySm,
                  fontWeight: FontWeight.w800,
                  color: p.text1)),
          const SizedBox(height: 3),
          Text(detail,
              style: TextStyle(fontSize: XlFont.labelSm, color: p.text3)),
          const SizedBox(height: 10),
          ...children,
        ],
      ),
    );
  }

  Widget _hint(XlPalette p, String text) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(text,
            style: TextStyle(
                fontSize: XlFont.label, color: p.text2, height: 1.5)),
      );

  Widget _preview(XlPalette p, String text) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
        child: Text('演练结果：$text',
            style: TextStyle(
                fontSize: XlFont.label, color: p.text2, height: 1.5)),
      );

  Widget _choice(XlPalette p, String label, bool on, VoidCallback onTap) =>
      _Pressable(
        onTap: onTap,
        child: Container(
          padding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          decoration: BoxDecoration(
            color: on ? p.violet.withOpacity(p.isDark ? 0.18 : 0.12) : null,
            borderRadius: BorderRadius.circular(XlRadius.pill),
            border: Border.all(
                color: on ? p.violet.withOpacity(0.4) : p.edge, width: 1),
          ),
          child: Text(label,
              style: TextStyle(
                  fontSize: XlFont.label,
                  fontWeight: FontWeight.w700,
                  color: on ? p.violet : p.text2)),
        ),
      );

  Widget _switchRow(
          XlPalette p, String label, bool value, void Function(bool) onChanged) =>
      GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: _busy ? null : () => onChanged(!value),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            children: [
              Container(
                width: 34,
                height: 19,
                decoration: BoxDecoration(
                  color: value ? p.violet.withOpacity(0.35) : p.surfaceLo,
                  borderRadius: BorderRadius.circular(XlRadius.pill),
                  border: Border.all(
                      color: value ? p.violet.withOpacity(0.5) : p.edge,
                      width: 1),
                ),
                child: AnimatedAlign(
                  duration: XlDuration.normal,
                  curve: XlCurve.standard,
                  alignment:
                      value ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.all(2.5),
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: value ? p.violet : p.text4,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Flexible(
                child: Text(label,
                    style: TextStyle(fontSize: XlFont.label, color: p.text2)),
              ),
            ],
          ),
        ),
      );

  Widget _btn(XlPalette p, String label, bool disabled, VoidCallback onTap,
          {bool danger = false}) =>
      _Pressable(
        onTap: disabled ? null : onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
          decoration: BoxDecoration(
            color: disabled
                ? p.surfaceLo
                : (danger
                    ? p.red.withOpacity(p.isDark ? 0.16 : 0.10)
                    : p.violet.withOpacity(p.isDark ? 0.14 : 0.10)),
            borderRadius: BorderRadius.circular(XlRadius.pill),
          ),
          child: Text(label,
              style: TextStyle(
                  fontSize: XlFont.label,
                  fontWeight: FontWeight.w800,
                  color: disabled
                      ? p.text4
                      : (danger ? p.red : p.violet))),
        ),
      );

  Widget _statusPill(String text, bool active, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
        decoration: BoxDecoration(
          color: active ? color.withOpacity(0.12) : Colors.transparent,
          borderRadius: BorderRadius.circular(XlRadius.pill),
          border: Border.all(color: color.withOpacity(0.3), width: 1),
        ),
        child: Text(text,
            style: TextStyle(
                fontSize: XlFont.micro,
                fontWeight: FontWeight.w800,
                color: color)),
      );
}
