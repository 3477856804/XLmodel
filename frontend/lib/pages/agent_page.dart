import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../widgets/agent_panel.dart';
import '../widgets/code_search_panel.dart';

class AgentPage extends StatefulWidget {
  const AgentPage({super.key});
  @override
  State<AgentPage> createState() => _AgentPageState();
}

class _AgentPageState extends State<AgentPage> with TickerProviderStateMixin {
  late final TabController _tabCtrl;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Scaffold(
      backgroundColor: p.bg,
      body: Stack(
        children: [
          Positioned.fill(child: AppTheme.aurora(context, child: const SizedBox.shrink())),
          Column(
            children: [
              _header(p),
              Expanded(
                child: TabBarView(
                  controller: _tabCtrl,
                  children: const [
                    AgentPanel(),
                    CodeSearchPanel(),
                    SubAgentPanel(),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _header(XlPalette p) {
    return Container(
      padding: EdgeInsets.only(top: MediaQuery.of(context).padding.top),
      decoration: BoxDecoration(
        gradient: p.navFace,
        border: Border(bottom: BorderSide(color: p.divider, width: 1)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              const SizedBox(width: 8),
              _backBtn(p),
              Expanded(
                child: ShaderMask(
                  shaderCallback: (b) => p.gradText.createShader(b),
                  child: Text('Agent 工作台',
                      style: TextStyle(
                        fontSize: XlFont.h5,
                        fontWeight: FontWeight.w800,
                        color: p.text1,
                        letterSpacing: XlLetterSpacing.normal,
                      )),
                ),
              ),
              Icon(Icons.auto_awesome_rounded, size: 18, color: p.pink),
              const SizedBox(width: 16),
            ],
          ),
          TabBar(
            controller: _tabCtrl,
            labelColor: p.text1,
            unselectedLabelColor: p.text3,
            labelStyle: const TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w800, letterSpacing: XlLetterSpacing.wide),
            unselectedLabelStyle: const TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w600, letterSpacing: XlLetterSpacing.wide),
            indicatorSize: TabBarIndicatorSize.label,
            indicator: UnderlineTabIndicator(
              borderSide: BorderSide(color: p.pink, width: 2.5),
              insets: const EdgeInsets.symmetric(horizontal: 28),
            ),
            tabs: const [
              Tab(text: 'Agent 任务'),
              Tab(text: '代码搜索'),
              Tab(text: '子 Agent'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _backBtn(XlPalette p) {
    return IconButton(
      onPressed: () => Navigator.of(context).maybePop(),
      icon: Icon(Icons.arrow_back_rounded, size: 20, color: p.text1),
      tooltip: '返回',
    );
  }
}

class _SubTask {
  final String id;
  final String description;
  String status = 'pending';
  double progress = 0;
  String result = '';
  _SubTask({required this.id, required this.description});
}

class _SubAgent {
  final String name;
  final List<_SubTask> tasks;
  _SubAgent({required this.name, List<_SubTask>? tasks}) : tasks = tasks ?? [];
  bool get busy => tasks.any((t) => t.status == 'pending' || t.status == 'running');
}

class SubAgentPanel extends StatefulWidget {
  const SubAgentPanel({super.key});
  @override
  State<SubAgentPanel> createState() => _SubAgentPanelState();
}

class _SubAgentPanelState extends State<SubAgentPanel> {
  final List<_SubAgent> _agents = [];
  Timer? _timer;
  final Set<String> _expanded = {};
  int _seq = 0;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 450), (_) => _tick());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _tick() {
    if (!mounted) return;
    var changed = false;
    for (final agent in _agents) {
      for (final task in agent.tasks) {
        if (task.status == 'pending') {
          task.status = 'running';
          task.progress = 12;
          changed = true;
        } else if (task.status == 'running') {
          task.progress += 18;
          changed = true;
          if (task.progress >= 100) {
            task.progress = 100;
            task.status = 'completed';
            task.result = '子 Agent 完成任务: ${task.description}';
          }
        }
      }
    }
    if (changed) setState(() {});
  }

  Future<void> _createAgent() async {
    final ctrl = TextEditingController();
    final p = XlPalette.of(context);
    final name = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: p.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.lg)),
        title: Text('创建子 Agent', style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
        content: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: AppTheme.sunkenXs(ctx, r: XlRadius.sm),
          child: TextField(
            controller: ctrl,
            autofocus: true,
            style: TextStyle(fontSize: XlFont.bodySm, color: p.text1),
            decoration: InputDecoration(
              hintText: '输入子 Agent 名称',
              hintStyle: TextStyle(fontSize: XlFont.bodySm, color: p.decor),
              border: InputBorder.none,
              isDense: true,
            ),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: Text('取消', style: TextStyle(color: p.text3))),
          Container(
            decoration: AppTheme.btn(ctx, r: XlRadius.pill),
            child: TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim().isEmpty ? 'agent_${DateTime.now().millisecondsSinceEpoch.remainder(100000)}' : ctrl.text.trim()),
              child: Text('创建', style: TextStyle(color: p.btnInk, fontWeight: FontWeight.w800)),
            ),
          ),
        ],
      ),
    );
    if (name != null && name.isNotEmpty) {
      setState(() => _agents.add(_SubAgent(name: name)));
    }
  }

  Future<void> _delegateTask(_SubAgent agent) async {
    final ctrl = TextEditingController();
    final p = XlPalette.of(context);
    final desc = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: p.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.lg)),
        title: Text('委派任务给 ${agent.name}', style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
        content: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: AppTheme.sunkenXs(ctx, r: XlRadius.sm),
          child: TextField(
            controller: ctrl,
            autofocus: true,
            maxLines: 3,
            minLines: 1,
            style: TextStyle(fontSize: XlFont.bodySm, color: p.text1, height: XlLineHeight.relaxed),
            decoration: InputDecoration(
              hintText: '描述要委派的任务…',
              hintStyle: TextStyle(fontSize: XlFont.bodySm, color: p.decor),
              border: InputBorder.none,
              isDense: true,
            ),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: Text('取消', style: TextStyle(color: p.text3))),
          Container(
            decoration: AppTheme.btn(ctx, r: XlRadius.pill),
            child: TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: Text('委派', style: TextStyle(color: p.btnInk, fontWeight: FontWeight.w800)),
            ),
          ),
        ],
      ),
    );
    if (desc != null && desc.isNotEmpty) {
      setState(() {
        _seq++;
        agent.tasks.add(_SubTask(id: 't$_seq', description: desc));
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Column(
      children: [
        _topBar(p),
        const SizedBox(height: 12),
        Expanded(child: _agents.isEmpty ? _emptyState(p) : _agentList(p)),
      ],
    );
  }

  Widget _topBar(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Row(
        children: [
          Icon(Icons.people_alt_rounded, size: 18, color: p.pink),
          const SizedBox(width: 8),
          Text('子 Agent 编排',
              style: TextStyle(
                fontSize: XlFont.h6,
                fontWeight: FontWeight.w800,
                color: p.text1,
                letterSpacing: XlLetterSpacing.normal,
              )),
          const Spacer(),
          _PressableMini(
            onTap: _createAgent,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: AppTheme.btn(context, r: XlRadius.pill),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.add_rounded, size: 16, color: p.btnInk),
                  const SizedBox(width: 4),
                  Text('创建子 Agent',
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
    );
  }

  Widget _emptyState(XlPalette p) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 84,
              height: 84,
              decoration: AppTheme.brandOrbLg(context, size: 84),
              child: Icon(Icons.people_alt_rounded, size: 34, color: p.btnInk),
            ),
            const SizedBox(height: 18),
            Text('暂无子 Agent，创建一个来并行处理任务',
                style: TextStyle(
                  fontSize: XlFont.h6,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                )),
          ],
        ),
      ),
    );
  }

  Widget _agentList(XlPalette p) {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 20),
      itemCount: _agents.length,
      itemBuilder: (_, i) => _agentCard(p, _agents[i]),
    );
  }

  Widget _agentCard(XlPalette p, _SubAgent agent) {
    final busy = agent.busy;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neu(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: AppTheme.orb(context, size: 36, color: p.pinkSoft),
                child: Icon(Icons.memory_rounded, size: 18, color: p.pink),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(agent.name,
                        style: TextStyle(
                          fontSize: XlFont.body,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                        )),
                    const SizedBox(height: 2),
                    Text('${agent.tasks.length} 个任务 · ${busy ? '忙碌' : '空闲'}',
                        style: TextStyle(
                          fontSize: XlFont.captionSm,
                          color: busy ? p.gold : p.text3,
                          fontWeight: FontWeight.w700,
                          letterSpacing: XlLetterSpacing.wide,
                        )),
                  ],
                ),
              ),
              Container(
                width: 8,
                height: 8,
                decoration: AppTheme.glowDot(busy ? p.gold : p.green, size: 8),
              ),
              const SizedBox(width: 8),
              _PressableMini(
                onTap: () => _delegateTask(agent),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: AppTheme.btn(context, r: XlRadius.pill),
                  child: Text('委派任务',
                      style: TextStyle(
                        fontSize: XlFont.captionSm,
                        fontWeight: FontWeight.w800,
                        color: p.btnInk,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                ),
              ),
            ],
          ),
          if (agent.tasks.isNotEmpty) ...[
            const SizedBox(height: 12),
            ...agent.tasks.asMap().entries.map((e) => _taskTile(p, agent, e.value)),
          ],
        ],
      ),
    );
  }

  Widget _taskTile(XlPalette p, _SubAgent agent, _SubTask task) {
    final expanded = _expanded.contains(task.id);
    Color statusColor;
    IconData statusIcon;
    switch (task.status) {
      case 'running':
        statusColor = p.gold;
        statusIcon = Icons.sync_rounded;
        break;
      case 'completed':
        statusColor = p.green;
        statusIcon = Icons.check_circle_rounded;
        break;
      case 'failed':
        statusColor = p.red;
        statusIcon = Icons.error_rounded;
        break;
      default:
        statusColor = p.text3;
        statusIcon = Icons.hourglass_empty_rounded;
    }
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: AppTheme.sunkenXs(context, r: XlRadius.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(statusIcon, size: 14, color: statusColor),
              const SizedBox(width: 6),
              Expanded(
                child: Text(task.description,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.text1,
                      fontWeight: FontWeight.w600,
                      height: XlLineHeight.normal,
                    )),
              ),
              Text(task.status,
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    color: statusColor,
                    fontWeight: FontWeight.w800,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
          const SizedBox(height: 8),
          _neuProgress(p, task.progress),
          if (task.status == 'completed' && task.result.isNotEmpty) ...[
            const SizedBox(height: 8),
            _PressableMini(
              onTap: () => setState(() {
                if (expanded) {
                  _expanded.remove(task.id);
                } else {
                  _expanded.add(task.id);
                }
              }),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: AppTheme.ghost(context, r: XlRadius.pill),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded, size: 12, color: p.pink),
                    const SizedBox(width: 4),
                    Text(expanded ? '收起结果' : '查看结果',
                        style: TextStyle(
                          fontSize: XlFont.micro,
                          fontWeight: FontWeight.w800,
                          color: p.pink,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                  ],
                ),
              ),
            ),
            if (expanded) ...[
              const SizedBox(height: 6),
              Text(task.result,
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    height: XlLineHeight.relaxed,
                    color: p.text2,
                  )),
            ],
          ],
        ],
      ),
    );
  }

  Widget _neuProgress(XlPalette p, double ratio) {
    final clamped = (ratio / 100).clamp(0.0, 1.0);
    return Container(
      height: 6,
      decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
      child: Align(
        alignment: Alignment.centerLeft,
        child: FractionallySizedBox(
          widthFactor: clamped <= 0 ? 0.0001 : clamped,
          child: Container(
            decoration: BoxDecoration(
              gradient: p.gradBrand,
              borderRadius: BorderRadius.circular(XlRadius.pill),
            ),
          ),
        ),
      ),
    );
  }
}

class _PressableMini extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  const _PressableMini({required this.child, this.onTap});
  @override
  State<_PressableMini> createState() => _PressableMiniState();
}

class _PressableMiniState extends State<_PressableMini> {
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
        scale: _down ? 0.94 : 1.0,
        duration: XlDuration.micro,
        curve: XlCurve.standard,
        child: widget.child,
      ),
    );
  }
}
