import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;

class GrowthPage extends StatefulWidget {
  const GrowthPage({super.key});
  @override
  State<GrowthPage> createState() => _GrowthPageState();
}

class _GrowthPageState extends State<GrowthPage> with TickerProviderStateMixin {
  pb.GrowthStatusReply? _data;
  pb.TrainingStatusReply? _training;
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

  static const _ranges = <String>['7 天', '30 天', '全部'];

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 900), vsync: this);
    _radialCtrl = AnimationController(duration: const Duration(milliseconds: 1400), vsync: this);
    _pulseCtrl = AnimationController(duration: const Duration(seconds: 4), vsync: this)..repeat();
    _timelineCtrl = AnimationController(duration: const Duration(milliseconds: 1200), vsync: this);
    _enterAnim = CurvedAnimation(parent: _enterCtrl, curve: XlCurve.easeOut);
    _radialAnim = CurvedAnimation(parent: _radialCtrl, curve: XlCurve.easeOut);
    _timelineAnim = CurvedAnimation(parent: _timelineCtrl, curve: XlCurve.easeOut);
    _enterCtrl.forward();
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
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
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

  List<_TimelineNode> _buildTimeline() {
    final g = _data!;
    return [
      _TimelineNode('初识', '第一次和你说话', '已完成', true, 'pink', DateTime.now().subtract(const Duration(days: 30)), Icons.waving_hand_rounded),
      _TimelineNode('第一次成长', '累计对话达到 10 次', '已达成', true, 'gold', DateTime.now().subtract(const Duration(days: 22)), Icons.trending_up_rounded),
      _TimelineNode('记忆突破', '知识图谱节点超过 50', '已达成', true, 'violet', DateTime.now().subtract(const Duration(days: 14)), Icons.hub_rounded),
      _TimelineNode('当前阶段', g.displayStage, '进行中', true, 'green', DateTime.now().subtract(const Duration(days: 3)), Icons.auto_awesome_rounded),
      _TimelineNode('深度共鸣', '亲密度达到 80%', '未解锁', false, 'blue', DateTime.now().add(const Duration(days: 10)), Icons.favorite_rounded),
      _TimelineNode('灵魂契合', '完成 1000 次对话', '未解锁', false, 'pink', DateTime.now().add(const Duration(days: 30)), Icons.psychology_rounded),
    ];
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
          _heroRow(p),
          const SizedBox(height: 22),
          _heroCard(p),
          const SizedBox(height: 20),
          LayoutBuilder(
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
          ),
          const SizedBox(height: 20),
          _statsGrid(p),
          const SizedBox(height: 20),
          _timelineHeaderCard(p),
          const SizedBox(height: 20),
          _timelineList(p),
        ],
      ),
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
      ],
    );
  }

  Widget _rankBadge(XlPalette p) {
    final g = _data!;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        gradient: p.gradBrand,
        borderRadius: BorderRadius.circular(XlRadius.pill),
        boxShadow: [...p.raisedXxs, BoxShadow(color: p.pink.withOpacity(0.35), blurRadius: 12, spreadRadius: -3)],
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
                final t = _pulseCtrl.value;
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
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.black.withOpacity(p.isDark ? 0.28 : 0.20),
                      borderRadius: BorderRadius.circular(XlRadius.pill),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.auto_awesome_rounded, size: 11, color: p.btnInk),
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
                  Text(prog.toStringAsFixed(1),
                      style: TextStyle(
                        fontSize: 64,
                        fontWeight: FontWeight.w800,
                        color: p.btnInk,
                        height: 0.95,
                        letterSpacing: -2.0,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      )),
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
                          Text('${g.currentGeneration}',
                              style: TextStyle(
                                fontSize: XlFont.h3,
                                fontWeight: FontWeight.w800,
                                color: p.btnInk,
                                fontFeatures: const [FontFeature.tabularFigures()],
                                height: 1.0,
                              )),
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
                        child: Container(
                          decoration: BoxDecoration(
                            color: p.btnInk,
                            borderRadius: BorderRadius.circular(99),
                            boxShadow: [BoxShadow(color: p.btnInk.withOpacity(0.4), blurRadius: 10, spreadRadius: -2)],
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
                  _heroPill(p, Icons.mood_rounded, g.displayEmotion),
                  const SizedBox(width: 8),
                  _heroPill(p, g.paused ? Icons.pause_rounded : Icons.play_arrow_rounded, g.trainingLabel),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _heroPill(XlPalette p, IconData icon, String text) {
    return Container(
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
    final ranks = <_RankRow>[
      _RankRow('初识阶段', '聊过一两次，互相陌生', 'pink', true, Icons.waving_hand_rounded),
      _RankRow('熟悉阶段', '开始记得你的偏好', 'gold', true, Icons.handshake_rounded),
      _RankRow('默契阶段', '能猜到你的情绪', 'violet', true, Icons.psychology_alt_rounded),
      _RankRow('知心阶段', '不需要解释就懂', 'green', false, Icons.favorite_rounded),
      _RankRow('灵魂契合', '像老朋友一样', 'blue', false, Icons.auto_awesome_rounded),
    ];
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
              _tinyChip(p, '第 3 级', p.gold),
            ],
          ),
          const SizedBox(height: 18),
          for (int i = 0; i < ranks.length; i++)
            Padding(
              padding: EdgeInsets.only(bottom: i == ranks.length - 1 ? 0 : 10),
              child: _rankRow(p, ranks[i], i),
            ),
        ],
      ),
    );
  }

  Widget _rankRow(XlPalette p, _RankRow r, int i) {
    final color = _colorOf(p, r.color);
    final current = i == 2;
    return TweenAnimationBuilder<double>(
      duration: Duration(milliseconds: 320 + i * 70),
      curve: XlCurve.easeOut,
      tween: Tween(begin: 0.0, end: 1.0),
      builder: (_, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset((1 - t) * 10, 0), child: child),
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
                gradient: r.unlocked ? LinearGradient(colors: [color, color.withOpacity(0.75)]) : null,
                color: r.unlocked ? null : p.surfaceLo,
                borderRadius: BorderRadius.circular(XlRadius.sm),
                border: Border.all(
                  color: r.unlocked
                      ? Colors.white.withOpacity(p.isDark ? 0.32 : 0.48)
                      : p.shDark.withOpacity(p.isDark ? 0.28 : 0.12),
                  width: 1,
                ),
                boxShadow: r.unlocked
                    ? [...p.raisedXxs, BoxShadow(color: color.withOpacity(0.3), blurRadius: 12, spreadRadius: -2)]
                    : p.sunkenXxs,
              ),
              child: Icon(
                r.icon,
                size: 15,
                color: r.unlocked ? (p.isDark ? p.btnInk : Colors.white) : p.decor,
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
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
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
            if (!r.unlocked) Icon(Icons.lock_outline_rounded, size: 14, color: p.decor),
            if (r.unlocked && !current) Icon(Icons.check_circle_rounded, size: 15, color: color),
          ],
        ),
      ),
    );
  }

  Widget _statsGrid(XlPalette p) {
    final g = _data!;
    final items = <_GrowthStat>[
      _GrowthStat('交互次数', '${g.totalInteractions}', '次', Icons.chat_bubble_outline_rounded, 'pink', (g.totalInteractions / 200).clamp(0.0, 1.0), '今日 +${(g.totalInteractions * 0.04).toInt()}'),
      _GrowthStat('当前情绪', g.displayEmotion, '', Icons.mood_rounded, 'gold', g.emotionEnergy, '相比昨日 +12%'),
      _GrowthStat('训练状态', g.trainingLabel, '', Icons.auto_awesome_rounded, 'violet', g.paused ? 0.3 : 0.75, g.paused ? '手动暂停' : '后台运行'),
      _GrowthStat('当前段位', g.displayRank, '', Icons.emoji_events_rounded, 'green', 0.62, '距下段位 38%'),
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
                    border: Border.all(color: color.withOpacity(0.28), width: 1),
                    boxShadow: [BoxShadow(color: color.withOpacity(0.20), blurRadius: 14, spreadRadius: -3)],
                  ),
                  child: Icon(s.icon, size: 18, color: color),
                ),
                const Spacer(),
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
                  child: Text(s.value,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: s.value.length > 4 ? XlFont.h4 : XlFont.h2,
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
                  onTap: () => setState(() => _rangeIndex = i),
                  child: AnimatedContainer(
                      duration: XlDuration.fast,
                      curve: XlCurve.standard,
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
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
                            fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
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
                  final t = ((_timelineAnim.value - delay) / (1 - delay)).clamp(0.0, 1.0);
                  return _timelineItem(p, nodes[i], i, nodes.length, t);
                }),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _timelineItem(XlPalette p, _TimelineNode n, int i, int total, double t) {
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
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        gradient: n.done ? LinearGradient(colors: [color, color.withOpacity(0.72)]) : null,
                        color: n.done ? null : p.surfaceLo,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: n.done
                              ? Colors.white.withOpacity(p.isDark ? 0.32 : 0.48)
                              : p.shDark.withOpacity(p.isDark ? 0.30 : 0.13),
                          width: 1.4,
                        ),
                        boxShadow: n.done
                            ? [...p.raisedXxs, BoxShadow(color: color.withOpacity(0.35), blurRadius: 14, spreadRadius: -3)]
                            : p.sunkenXxs,
                      ),
                      child: Icon(
                        n.icon,
                        size: 16,
                        color: n.done ? (p.isDark ? p.btnInk : Colors.white) : p.decor,
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
                          Icon(Icons.schedule_rounded, size: 11, color: p.decor),
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

  Widget _neuProgress(XlPalette p, double value, {double height = 5, Color? color}) {
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
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [c.withOpacity(0.7), c]),
            borderRadius: BorderRadius.circular(99),
            boxShadow: [BoxShadow(color: c.withOpacity(0.35), blurRadius: 8, spreadRadius: -2)],
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

  Widget _loadingView(XlPalette p) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedBuilder(
            animation: _pulseCtrl,
            builder: (_, __) {
              final t = _pulseCtrl.value;
              return Stack(
                alignment: Alignment.center,
                children: [
                  Container(
                    width: 72 + t * 16,
                    height: 72 + t * 16,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: p.pink.withOpacity((1 - t) * 0.18),
                    ),
                  ),
                  Container(
                    width: 72,
                    height: 72,
                    decoration: BoxDecoration(
                      gradient: p.gradBrand,
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.32 : 0.5), width: 2),
                      boxShadow: [...p.raised, BoxShadow(color: p.pink.withOpacity(0.4), blurRadius: 26, spreadRadius: -5)],
                    ),
                    child: Icon(Icons.favorite_rounded, size: 28, color: p.btnInk),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 22),
          Text('正在读取成长记录…',
              style: TextStyle(
                fontSize: XlFont.caption,
                color: p.text2,
                fontWeight: FontWeight.w600,
                letterSpacing: XlLetterSpacing.wider,
              )),
        ],
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

    canvas.drawCircle(dotCenter, 14, Paint()..color = palette.pink.withOpacity(0.24));
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
        ),
      )
      ..layout();
    p1.paint(canvas, Offset(center.dx - p1.width / 2, center.dy - p1.height / 2 - 10));

    final p2 = TextPainter(textDirection: TextDirection.ltr)
      ..text = TextSpan(
        text: 'OVERALL',
        style: TextStyle(
          fontSize: 9,
          fontWeight: FontWeight.w800,
          color: palette.text3,
          letterSpacing: 2.4,
        ),
      )
      ..layout();
    p2.paint(canvas, Offset(center.dx - p2.width / 2, center.dy + p2.height / 2 - 2));
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
  _TimelineNode(this.title, this.desc, this.status, this.done, this.color, this.date, this.icon);
}

class _RankRow {
  final String name;
  final String desc;
  final String color;
  final bool unlocked;
  final IconData icon;
  const _RankRow(this.name, this.desc, this.color, this.unlocked, this.icon);
}

class _GrowthStat {
  final String label;
  final String value;
  final String unit;
  final IconData icon;
  final String color;
  final double progress;
  final String hint;
  const _GrowthStat(this.label, this.value, this.unit, this.icon, this.color, this.progress, this.hint);
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