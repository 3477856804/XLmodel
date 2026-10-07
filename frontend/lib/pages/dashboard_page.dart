import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;
import '../widgets/model_showcase.dart';
import 'terminal_page.dart';

class DashboardPage extends StatefulWidget {
  final void Function(int) onNavigate;
  final VoidCallback onOpenModelStore;
  final VoidCallback onOpenPlugins;
  const DashboardPage({
    super.key,
    required this.onNavigate,
    required this.onOpenModelStore,
    required this.onOpenPlugins,
  });
  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> with TickerProviderStateMixin {
  pb.GrowthStatusReply? _growth;
  pb.TrainingStatusReply? _training;
  pb.StatusReply? _status;
  pb.HardwareInfo? _hardware;
  String? _modelPath;
  String _modelName = '小凌';
  bool _loading = true;
  String _greeting = '';
  late AnimationController _enterCtrl;
  late AnimationController _pulseCtrl;
  late AnimationController _ringCtrl;
  late AnimationController _actCtrl;
  late AnimationController _shimmerCtrl;
  late AnimationController _breatheCtrl;
  late AnimationController _spinCtrl;
  late Animation<double> _actAnim;
  final List<_Activity> _activities = [];

  @override
  void initState() {
    super.initState();
    _greeting = _calcGreeting();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 1200), vsync: this);
    _pulseCtrl = AnimationController(duration: const Duration(seconds: 4), vsync: this)..repeat();
    _ringCtrl = AnimationController(duration: const Duration(milliseconds: 1400), vsync: this);
    _actCtrl = AnimationController(duration: const Duration(milliseconds: 1100), vsync: this);
    _shimmerCtrl = AnimationController(duration: const Duration(milliseconds: 1600), vsync: this)..repeat();
    _breatheCtrl = AnimationController(duration: const Duration(milliseconds: 1400), vsync: this)..repeat(reverse: true);
    _spinCtrl = AnimationController(duration: const Duration(milliseconds: 900), vsync: this);
    _actAnim = CurvedAnimation(parent: _actCtrl, curve: XlCurve.easeOut);
    _enterCtrl.forward();
    _bootstrap();
  }

  @override
  void dispose() {
    _enterCtrl.dispose();
    _pulseCtrl.dispose();
    _ringCtrl.dispose();
    _actCtrl.dispose();
    _shimmerCtrl.dispose();
    _breatheCtrl.dispose();
    _spinCtrl.dispose();
    super.dispose();
  }

  String _calcGreeting() {
    final h = DateTime.now().hour;
    if (h < 5) return '夜深了';
    if (h < 11) return '早上好';
    if (h < 14) return '中午好';
    if (h < 18) return '下午好';
    if (h < 22) return '晚上好';
    return '夜深了';
  }

  void _openTerminal() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const TerminalPage()),
    );
  }

  Future<void> _bootstrap() async {
    final boot = await XlClient.stub.bootstrap();
    if (!mounted) return;
    setState(() {
      _status = boot.status;
      _growth = boot.growth;
      _training = boot.training;
      _hardware = boot.hardware;
      if (boot.models.models.isNotEmpty) {
        _modelPath = boot.models.models.first.path;
        _modelName = boot.models.models.first.name;
      }
      _loading = false;
    });
    _seedActivities();
    _ringCtrl.forward(from: 0);
    _actCtrl.forward(from: 0);
  }

  void _seedActivities() {
    _activities.clear();
    final g = _growth;
    if (g == null) return;
    _activities
      ..add(_Activity('成长进度更新', g.shortSummary, Icons.trending_up_rounded, 'pink', DateTime.now().subtract(const Duration(minutes: 2))))
      ..add(_Activity('记忆已写入', g.interactionsLabel, Icons.psychology_outlined, 'violet', DateTime.now().subtract(const Duration(minutes: 18))))
      ..add(_Activity('情绪状态', g.displayEmotion, Icons.mood_rounded, 'gold', DateTime.now().subtract(const Duration(hours: 1))))
      ..add(_Activity('进化代数', g.generationLabel, Icons.auto_awesome_rounded, 'green', DateTime.now().subtract(const Duration(hours: 3))));
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

  Animation<double> _stagger(int index) {
    final start = (index * 0.12).clamp(0.0, 0.8);
    final end = (start + 0.35).clamp(0.0, 1.0);
    return CurvedAnimation(
      parent: _enterCtrl,
      curve: Interval(start, end, curve: XlCurve.easeOut),
    );
  }

  Widget _wrapStagger(int index, Widget child) {
    final anim = _stagger(index);
    return AnimatedBuilder(
      animation: anim,
      builder: (_, __) => Opacity(
        opacity: anim.value,
        child: Transform.translate(
          offset: Offset(0, (1 - anim.value) * 18),
          child: child,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    if (_loading) return _loadingView(p);
    return Stack(
      children: [
        Positioned.fill(child: AppTheme.aurora(context, child: const SizedBox.shrink())),
        _body(p),
      ],
    );
  }

  Widget _body(XlPalette p) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_status == null) ...[
            _offlineBanner(p),
            const SizedBox(height: 16),
          ],
          _wrapStagger(0, _heroRow(p)),
          const SizedBox(height: 22),
          _wrapStagger(1, _statsGrid(p)),
          const SizedBox(height: 22),
          _wrapStagger(2, _middleRow(p)),
          const SizedBox(height: 22),
          _wrapStagger(3, _bottomRow(p)),
        ],
      ),
    );
  }

  Widget _heroRow(XlPalette p) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text('$_greeting，欢迎回来',
                      style: TextStyle(
                        fontSize: XlFont.h2,
                        fontWeight: FontWeight.w800,
                        color: p.text1,
                        letterSpacing: XlLetterSpacing.normal,
                      )),
                  const SizedBox(width: 12),
                  _stageChip(p),
                ],
              ),
              const SizedBox(height: 6),
              Text(_buildSubline(),
                  style: TextStyle(
                    fontSize: XlFont.caption,
                    color: p.text2,
                    fontWeight: FontWeight.w500,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
            ],
          ),
        ),
        const SizedBox(width: 20),
        _refreshBtn(p),
      ],
    );
  }

  String _buildSubline() {
    final g = _growth;
    if (g == null) return '后端连接中，正在拉取小凌的状态…';
    return '她今天状态不错 · 已陪伴你 ${g.totalInteractions} 次对话 · 进化到第 ${g.currentGeneration} 代';
  }

  Widget _offlineBanner(XlPalette p) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: p.gold.withOpacity(p.isDark ? 0.10 : 0.06),
        borderRadius: BorderRadius.circular(XlRadius.lg),
        border: Border.all(color: p.gold.withOpacity(0.35), width: 1),
      ),
      child: Row(
        children: [
          Icon(Icons.cloud_off_rounded, size: 16, color: p.gold),
          const SizedBox(width: 10),
          Expanded(
            child: Text('后端未连接，部分功能不可用',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text1,
                  fontWeight: FontWeight.w700,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ),
          _Pressable(
            scale: 0.94,
            onTap: () async {
              _spinCtrl.repeat();
              setState(() => _loading = true);
              await _bootstrap();
              if (mounted) {
                _spinCtrl.stop();
                _spinCtrl.value = 0;
              }
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: AppTheme.ghost(context, r: XlRadius.pill),
              child: Text('重试',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: p.gold,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ),
          ),
        ],
      ),
    );
  }

  Widget _stageChip(XlPalette p) {
    final g = _growth;
    if (g == null) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: AppTheme.brand(context, r: XlRadius.pill),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.auto_awesome_rounded, size: 11, color: p.btnInk),
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
      scale: 0.94,
      onTap: () async {
        _spinCtrl.repeat();
        setState(() => _loading = true);
        await _bootstrap();
        if (mounted) {
          _spinCtrl.stop();
          _spinCtrl.value = 0;
        }
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: AppTheme.btn(context, r: XlRadius.lg),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            RotationTransition(
              turns: _spinCtrl,
              child: Icon(Icons.refresh_rounded, size: 15, color: p.btnInk),
            ),
            const SizedBox(width: 8),
            Text('刷新',
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

  Widget _statsGrid(XlPalette p) {
    final g = _growth;
    final prog = g?.normalizedProgress ?? 0.0;
    final inter = g?.totalInteractions ?? 0;
    final gen = g?.currentGeneration ?? 0;
    final totalGen = g?.totalGenerations ?? 0;
    final items = <_Stat>[
      _Stat('成长值', prog, '%', Icons.trending_up_rounded, 'pink', (prog / 100).clamp(0.0, 1.0), '本周 +${(prog * 0.08).toStringAsFixed(1)}%', 0),
      _Stat('亲密度', (prog * 0.72), '%', Icons.favorite_rounded, 'gold', (prog * 0.72 / 100).clamp(0.0, 1.0), '今日聊了 ${(inter * 0.04).toInt()} 次', 1),
      _Stat('记忆条数', inter.toDouble(), '条', Icons.psychology_outlined, 'violet', (inter / 200).clamp(0.0, 1.0), '新增 ${(inter * 0.03).toInt()} 条', 2),
      _Stat('进化代数', gen.toDouble(), '/$totalGen', Icons.auto_awesome_rounded, 'green', totalGen == 0 ? 0.0 : (gen / totalGen).clamp(0.0, 1.0), '下一步：深度融合', 3),
    ];
    return LayoutBuilder(
      builder: (context, c) {
        final cols = c.maxWidth > 1180 ? 4 : c.maxWidth > 780 ? 2 : 1;
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: cols,
            mainAxisSpacing: 14,
            crossAxisSpacing: 14,
            childAspectRatio: cols == 4 ? 1.5 : (cols == 2 ? 2.1 : 2.8),
          ),
          itemCount: items.length,
          itemBuilder: (_, i) => _statCard(p, items[i], i),
        );
      },
    );
  }

  Widget _statCard(XlPalette p, _Stat s, int i) {
    final color = _colorOf(p, s.color);
    return _HoverGlowCard(
      accent: color,
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: AppTheme.neuLg(context, r: XlRadius.xl),
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
                    border: Border.all(color: color.withOpacity(0.28), width: 1),
                    boxShadow: [BoxShadow(color: color.withOpacity(0.20), blurRadius: 14, spreadRadius: -3)],
                  ),
                  child: Icon(s.icon, size: 18, color: color),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: AppTheme.sunkenHair(context, r: XlRadius.pill),
                  child: Text('LIVE',
                      style: TextStyle(
                        fontSize: XlFont.micro,
                        fontWeight: FontWeight.w800,
                        color: p.green,
                        letterSpacing: XlLetterSpacing.ultra,
                      )),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                _AnimatedCounter(
                  value: s.rawValue,
                  delay: Duration(milliseconds: 200 + i * 100),
                  style: TextStyle(
                    fontSize: XlFont.h1,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.tight,
                    fontFeatures: const [FontFeature.tabularFigures()],
                    height: 1.0,
                  ),
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
            ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: s.progress,
                minHeight: 5,
                backgroundColor: p.surfaceLo,
                valueColor: AlwaysStoppedAnimation(color),
              ),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Icon(Icons.arrow_upward_rounded, size: 11, color: color),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(s.hint,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: XlFont.micro,
                        color: p.text3,
                        fontWeight: FontWeight.w600,
                        letterSpacing: XlLetterSpacing.wide,
                      )),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _middleRow(XlPalette p) {
    return LayoutBuilder(
      builder: (context, c) {
        final stacked = c.maxWidth < 1000;
        if (stacked) {
          return Column(
            children: [
              _showcaseCard(p),
              const SizedBox(height: 18),
              _actionsCard(p),
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(flex: 5, child: _showcaseCard(p)),
            const SizedBox(width: 18),
            Expanded(flex: 3, child: _actionsCard(p)),
          ],
        );
      },
    );
  }

  Widget _showcaseCard(XlPalette p) {
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
                    Text('3D 角色展示',
                        style: TextStyle(
                          fontSize: XlFont.h6,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.normal,
                        )),
                    const SizedBox(height: 3),
                    Text('拖拽旋转 · 滚轮缩放',
                        style: TextStyle(
                          fontSize: XlFont.label,
                          color: p.text3,
                          fontWeight: FontWeight.w500,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                  ],
                ),
              ),
              _smallBadge(p, _growth?.displayStage ?? '就绪', p.pink),
            ],
          ),
          const SizedBox(height: 18),
          Center(
            child: AnimatedBuilder(
              animation: _pulseCtrl,
              builder: (_, __) {
                final t = _pulseCtrl.value;
                return Stack(
                  alignment: Alignment.center,
                  children: [
                    Container(
                      width: 300 + t * 24,
                      height: 300 + t * 24,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: RadialGradient(
                          colors: [
                            p.pink.withOpacity((1 - t) * 0.14),
                            p.pink.withOpacity(0),
                          ],
                        ),
                      ),
                    ),
                    ModelShowcase(
                      modelPath: _modelPath,
                      characterName: _modelName,
                      width: 300,
                      height: 300,
                      showControls: false,
                    ),
                  ],
                );
              },
            ),
          ),
          const SizedBox(height: 18),
          _traitsRow(p),
        ],
      ),
    );
  }

  Widget _traitsRow(XlPalette p) {
    final traits = <_Trait>[
      const _Trait('温柔', 'pink', 0.82),
      const _Trait('活泼', 'gold', 0.64),
      const _Trait('聪慧', 'violet', 0.74),
      const _Trait('专注', 'green', 0.56),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('性格特质',
            style: TextStyle(
              fontSize: XlFont.label,
              fontWeight: FontWeight.w800,
              color: p.text3,
              letterSpacing: XlLetterSpacing.ultra,
            )),
        const SizedBox(height: 12),
        Row(
          children: [
            for (int i = 0; i < traits.length; i++) ...[
              Expanded(child: _traitBar(p, traits[i])),
              if (i != traits.length - 1) const SizedBox(width: 12),
            ],
          ],
        ),
      ],
    );
  }

  Widget _traitBar(XlPalette p, _Trait t) {
    final color = _colorOf(p, t.color);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(t.name,
                style: TextStyle(
                  fontSize: XlFont.label,
                  fontWeight: FontWeight.w700,
                  color: p.text2,
                  letterSpacing: XlLetterSpacing.wider,
                )),
            const Spacer(),
            Text('${(t.value * 100).toInt()}',
                style: TextStyle(
                  fontSize: XlFont.micro,
                  fontWeight: FontWeight.w800,
                  color: color,
                  fontFeatures: const [FontFeature.tabularFigures()],
                )),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: t.value,
            minHeight: 4,
            backgroundColor: p.surfaceLo,
            valueColor: AlwaysStoppedAnimation(color),
          ),
        ),
      ],
    );
  }

  Widget _actionsCard(XlPalette p) {
    final actions = <_Action>[
      _Action('继续聊天', '和小凌说话', Icons.chat_bubble_outline_rounded, 'pink', () => widget.onNavigate(0)),
      _Action('语音对话', '按住说话', Icons.mic_none_rounded, 'gold', () => widget.onNavigate(0)),
      _Action('模型商店', '按硬件推荐', Icons.shopping_bag_outlined, 'violet', widget.onOpenModelStore),
      _Action('插件管理', '扩展功能', Icons.extension_outlined, 'green', widget.onOpenPlugins),
      _Action('开发者工具', '终端 / 文件浏览', Icons.terminal_rounded, 'blue', () => _openTerminal()),
      _Action('开始训练', 'LoRA 微调', Icons.auto_awesome_outlined, 'blue', () => widget.onNavigate(2)),
      _Action('查看成长', '完整轨迹', Icons.trending_up_rounded, 'pink', () => widget.onNavigate(3)),
    ];
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('快捷操作',
              style: TextStyle(
                fontSize: XlFont.h6,
                fontWeight: FontWeight.w800,
                color: p.text1,
                letterSpacing: XlLetterSpacing.normal,
              )),
          const SizedBox(height: 4),
          Text('一键抵达常用功能',
              style: TextStyle(
                fontSize: XlFont.label,
                color: p.text3,
                fontWeight: FontWeight.w500,
                letterSpacing: XlLetterSpacing.wider,
              )),
          const SizedBox(height: 16),
          for (int i = 0; i < actions.length; i++) ...[
            _actionTile(p, actions[i], i, badge: actions[i].title == '开始训练' && (_training?.isTraining ?? false)),
            if (i != actions.length - 1) const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }

  Widget _actionTile(XlPalette p, _Action a, int i, {bool badge = false}) {
    final color = _colorOf(p, a.color);
    return TweenAnimationBuilder<double>(
      duration: Duration(milliseconds: 300 + i * 60),
      curve: XlCurve.easeOut,
      tween: Tween(begin: 0.0, end: 1.0),
      builder: (_, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset((1 - t) * 12, 0), child: child),
      ),
      child: _Pressable(
        onTap: a.onTap,
        scale: 0.97,
        child: Stack(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: AppTheme.neuXs(context, r: XlRadius.md),
              child: Row(
                children: [
                  Container(
                    width: 34,
                    height: 34,
                    decoration: BoxDecoration(
                      color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                      borderRadius: BorderRadius.circular(XlRadius.sm),
                      border: Border.all(color: color.withOpacity(0.28), width: 1),
                    ),
                    child: Icon(a.icon, size: 15, color: color),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(a.title,
                            style: TextStyle(
                              fontSize: XlFont.caption,
                              fontWeight: FontWeight.w700,
                              color: p.text1,
                              letterSpacing: XlLetterSpacing.wide,
                            )),
                        const SizedBox(height: 1),
                        Text(a.sub,
                            style: TextStyle(
                              fontSize: XlFont.micro,
                              color: p.text3,
                              fontWeight: FontWeight.w500,
                              letterSpacing: XlLetterSpacing.wider,
                            )),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right_rounded, size: 16, color: p.decor),
                ],
              ),
            ),
            if (badge)
              Positioned(
                top: 8,
                right: 8,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: p.pink,
                    shape: BoxShape.circle,
                    boxShadow: [BoxShadow(color: p.pink.withOpacity(0.7), blurRadius: 5, spreadRadius: -1)],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _bottomRow(XlPalette p) {
    return LayoutBuilder(
      builder: (context, c) {
        final stacked = c.maxWidth < 1000;
        if (stacked) {
          return Column(
            children: [
              _activityCard(p),
              const SizedBox(height: 18),
              _systemCard(p),
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(flex: 3, child: _activityCard(p)),
            const SizedBox(width: 18),
            Expanded(flex: 2, child: _systemCard(p)),
          ],
        );
      },
    );
  }

  Widget _activityCard(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('最近活动',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              Text('${_activities.length} 条',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w700,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
          const SizedBox(height: 16),
          if (_activities.isEmpty)
            _emptyState(p, '暂无活动', '数据加载后将显示最新动态')
          else
            AnimatedBuilder(
              animation: _actAnim,
              builder: (_, __) {
                return Column(
                  children: List.generate(_activities.length, (i) {
                    final delay = i * 0.12;
                    final t = ((_actAnim.value - delay) / (1 - delay)).clamp(0.0, 1.0);
                    return _activityItem(p, _activities[i], i, t);
                  }),
                );
              },
            ),
        ],
      ),
    );
  }

  Widget _emptyState(XlPalette p, String title, String sub) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 28),
      child: Column(
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: AppTheme.brandOrb(context, size: 64),
            child: Icon(Icons.auto_awesome_rounded, size: 26, color: p.btnInk),
          ),
          const SizedBox(height: 16),
          Text(title,
              style: TextStyle(
                fontSize: XlFont.caption,
                color: p.text2,
                fontWeight: FontWeight.w700,
              )),
          const SizedBox(height: 4),
          Text(sub,
              style: TextStyle(
                fontSize: XlFont.micro,
                color: p.text3,
                fontWeight: FontWeight.w500,
              )),
        ],
      ),
    );
  }

  Widget _activityItem(XlPalette p, _Activity a, int i, double t) {
    final color = _colorOf(p, a.color);
    return Opacity(
      opacity: t,
      child: Transform.translate(
        offset: Offset((1 - t) * 10, 0),
        child: Padding(
          padding: EdgeInsets.only(bottom: i == _activities.length - 1 ? 0 : 14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Column(
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                      borderRadius: BorderRadius.circular(XlRadius.sm),
                      border: Border.all(color: color.withOpacity(0.28), width: 1),
                    ),
                    child: Icon(a.icon, size: 15, color: color),
                  ),
                  if (i != _activities.length - 1)
                    Container(
                      width: 2,
                      height: 22,
                      margin: const EdgeInsets.symmetric(vertical: 2),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [color.withOpacity(0.35), Colors.transparent],
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(a.title,
                          style: TextStyle(
                            fontSize: XlFont.captionSm,
                            fontWeight: FontWeight.w700,
                            color: p.text1,
                            letterSpacing: XlLetterSpacing.wide,
                          )),
                      const SizedBox(height: 3),
                      Text(a.sub,
                          style: TextStyle(
                            fontSize: XlFont.label,
                            color: p.text3,
                            fontWeight: FontWeight.w500,
                            height: XlLineHeight.relaxed,
                          )),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(formatRelative(a.time),
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.decor,
                      fontWeight: FontWeight.w700,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _systemCard(XlPalette p) {
    final training = _training?.isTraining ?? false;
    final connected = _status != null;
    final hw = _hardware;
    final items = <_Sys>[
      _Sys('后端服务', connected ? '运行中' : '未连接', Icons.dns_outlined, connected ? p.green : p.red, connected),
      _Sys('模型加载', _modelPath == null ? '待加载' : '已就绪', Icons.memory_outlined, _modelPath == null ? p.gold : p.green, _modelPath != null),
      _Sys('训练引擎', training ? '训练中' : '待机', Icons.auto_awesome_outlined, training ? p.pink : p.text3, training),
      _Sys('语音合成', '就绪', Icons.volume_up_outlined, p.green, true),
      _Sys('知识图谱', '${_growth?.totalInteractions ?? 0} 节点', Icons.hub_outlined, p.violet, true),
      _Sys('硬件加速', hw == null ? '未知' : hw.accelLabel, Icons.speed_rounded, hw?.hasGpu == true ? p.green : p.blue, hw?.hasGpu == true),
    ];
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('系统状态',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              AnimatedBuilder(
                animation: _breatheCtrl,
                builder: (_, __) {
                  final c = connected ? p.green : p.red;
                  return Transform.scale(
                    scale: 1.0 + _breatheCtrl.value * 0.3,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: AppTheme.glowDot(c, size: 8),
                    ),
                  );
                },
              ),
            ],
          ),
          const SizedBox(height: 16),
          for (int i = 0; i < items.length; i++) ...[
            _sysRow(p, items[i]),
            if (i != items.length - 1) const SizedBox(height: 10),
          ],
        ],
      ),
    );
  }

  Widget _sysRow(XlPalette p, _Sys s) {
    return Row(
      children: [
        Container(
          width: 28,
          height: 28,
          decoration: AppTheme.neuXxs(context, r: XlRadius.xs),
          child: Icon(s.icon, size: 13, color: s.color),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(s.name,
              style: TextStyle(
                fontSize: XlFont.captionSm,
                color: p.text2,
                fontWeight: FontWeight.w600,
                letterSpacing: XlLetterSpacing.wide,
              )),
        ),
        Text(s.value,
            style: TextStyle(
              fontSize: XlFont.label,
              fontWeight: FontWeight.w800,
              color: s.active ? s.color : p.text3,
              letterSpacing: XlLetterSpacing.wider,
            )),
      ],
    );
  }

  Widget _smallBadge(XlPalette p, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(p.isDark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: color.withOpacity(0.30), width: 1),
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

  Widget _loadingView(XlPalette p) {
    return Stack(
      children: [
        Positioned.fill(child: AppTheme.aurora(context, child: const SizedBox.shrink())),
        SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(26, 6, 26, 30),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  _SkeletonBox(width: 180, height: 28, p: p),
                  const SizedBox(width: 12),
                  _SkeletonBox(width: 60, height: 22, p: p, radius: XlRadius.pill),
                ],
              ),
              const SizedBox(height: 8),
              _SkeletonBox(width: 260, height: 14, p: p),
              const SizedBox(height: 22),
              LayoutBuilder(
                builder: (context, c) {
                  final cols = c.maxWidth > 1180 ? 4 : c.maxWidth > 780 ? 2 : 1;
                  return GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: cols,
                      mainAxisSpacing: 14,
                      crossAxisSpacing: 14,
                      childAspectRatio: cols == 4 ? 1.5 : (cols == 2 ? 2.1 : 2.8),
                    ),
                    itemCount: 4,
                    itemBuilder: (_, __) => _SkeletonCard(p: p, shimmerCtrl: _shimmerCtrl),
                  );
                },
              ),
              const SizedBox(height: 22),
              _SkeletonCard(p: p, shimmerCtrl: _shimmerCtrl, height: 200),
              const SizedBox(height: 18),
              _SkeletonCard(p: p, shimmerCtrl: _shimmerCtrl, height: 140),
            ],
          ),
        ),
      ],
    );
  }
}

class _SkeletonBox extends StatelessWidget {
  final double width;
  final double height;
  final XlPalette p;
  final double radius;
  const _SkeletonBox({required this.width, required this.height, required this.p, this.radius = XlRadius.md});
  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: p.shDark.withOpacity(p.isDark ? 0.15 : 0.06), width: 1),
      ),
    );
  }
}

class _SkeletonCard extends StatelessWidget {
  final XlPalette p;
  final AnimationController shimmerCtrl;
  final double? height;
  const _SkeletonCard({required this.p, required this.shimmerCtrl, this.height});
  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      padding: const EdgeInsets.all(18),
      decoration: AppTheme.neuLg(context, r: XlRadius.xl),
      child: AnimatedBuilder(
        animation: shimmerCtrl,
        builder: (_, __) {
          final t = shimmerCtrl.value;
          return Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(XlRadius.xl),
              gradient: LinearGradient(
                begin: Alignment(-1.0 + t * 2.5, 0),
                end: Alignment(-0.4 + t * 2.5, 0),
                colors: [
                  p.surfaceLo,
                  p.surfaceHi.withOpacity(0.6),
                  p.surfaceLo,
                ],
                stops: const [0.0, 0.5, 1.0],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _AnimatedCounter extends StatefulWidget {
  final double value;
  final Duration delay;
  final TextStyle style;
  const _AnimatedCounter({required this.value, this.delay = Duration.zero, required this.style});
  @override
  State<_AnimatedCounter> createState() => _AnimatedCounterState();
}

class _AnimatedCounterState extends State<_AnimatedCounter> with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;
  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(duration: const Duration(milliseconds: 800), vsync: this);
    _anim = Tween<double>(begin: 0, end: widget.value).animate(
      CurvedAnimation(parent: _ctrl, curve: XlCurve.easeOut),
    );
    if (widget.delay == Duration.zero) {
      _ctrl.forward();
    } else {
      Future.delayed(widget.delay, () {
        if (mounted) _ctrl.forward();
      });
    }
  }
  @override
  void didUpdateWidget(_AnimatedCounter old) {
    super.didUpdateWidget(old);
    if (old.value != widget.value) {
      _anim = Tween<double>(begin: old.value, end: widget.value).animate(
        CurvedAnimation(parent: _ctrl, curve: XlCurve.easeOut),
      );
      _ctrl.forward(from: 0);
    }
  }
  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }
  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _anim,
      builder: (_, __) => Text(
        _anim.value.toStringAsFixed(0),
        style: widget.style,
      ),
    );
  }
}

class _Stat {
  final String label;
  final double rawValue;
  final String unit;
  final IconData icon;
  final String color;
  final double progress;
  final String hint;
  final int index;
  const _Stat(this.label, this.rawValue, this.unit, this.icon, this.color, this.progress, this.hint, this.index);
}

class _Action {
  final String title;
  final String sub;
  final IconData icon;
  final String color;
  final VoidCallback onTap;
  const _Action(this.title, this.sub, this.icon, this.color, this.onTap);
}

class _Activity {
  final String title;
  final String sub;
  final IconData icon;
  final String color;
  final DateTime time;
  _Activity(this.title, this.sub, this.icon, this.color, this.time);
}

class _Trait {
  final String name;
  final String color;
  final double value;
  const _Trait(this.name, this.color, this.value);
}

class _Sys {
  final String name;
  final String value;
  final IconData icon;
  final Color color;
  final bool active;
  const _Sys(this.name, this.value, this.icon, this.color, this.active);
}

class _HoverGlowCard extends StatefulWidget {
  final Widget child;
  final Color accent;
  final double scale;
  const _HoverGlowCard({required this.child, required this.accent, this.scale = 1.02});
  @override
  State<_HoverGlowCard> createState() => _HoverGlowCardState();
}

class _HoverGlowCardState extends State<_HoverGlowCard> {
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: AnimatedScale(
        scale: _hover ? widget.scale : 1.0,
        duration: XlDuration.fast,
        curve: XlCurve.standard,
        child: AnimatedContainer(
          duration: XlDuration.fast,
          curve: XlCurve.standard,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(XlRadius.xl),
            boxShadow: _hover
                ? [
                    ...Theme.of(context).extension<XlPalette>()!.raised,
                    BoxShadow(
                      color: widget.accent.withOpacity(0.35),
                      blurRadius: 24,
                      spreadRadius: -4,
                    ),
                  ]
                : null,
          ),
          child: widget.child,
        ),
      ),
    );
  }
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
    return GestureDetector(
      onTapDown: widget.onTap == null ? null : (_) => setState(() => _down = true),
      onTapUp: widget.onTap == null ? null : (_) => setState(() => _down = false),
      onTapCancel: () {
        if (mounted) setState(() => _down = false);
      },
      onTap: widget.onTap,
      child: AnimatedScale(
        scale: _down ? widget.scale : 1.0,
        duration: XlDuration.micro,
        curve: XlCurve.standard,
        child: widget.child,
      ),
    );
  }
}
