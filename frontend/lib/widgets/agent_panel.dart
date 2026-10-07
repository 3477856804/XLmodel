import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling.pb.dart';

class AgentPanel extends StatefulWidget {
  const AgentPanel({super.key});
  @override
  State<AgentPanel> createState() => _AgentPanelState();
}

class _AgentPanelState extends State<AgentPanel> with TickerProviderStateMixin {
  final _taskCtrl = TextEditingController();
  final _maxStepsCtrl = TextEditingController(text: '20');
  final _scroll = ScrollController();
  final List<AgentEvent> _events = [];
  StreamSubscription<AgentEvent>? _sub;
  bool _running = false;
  bool _autonomous = true;
  int _step = 0;
  int _totalSteps = 0;
  final Set<int> _expanded = {};
  late AnimationController _enterCtrl;

  static const _examples = <String>[
    '搜索项目中的 TODO',
    '列出所有 Dart 文件',
    '统计代码行数',
  ];

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 500), vsync: this);
    _enterCtrl.forward();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _taskCtrl.dispose();
    _maxStepsCtrl.dispose();
    _scroll.dispose();
    _enterCtrl.dispose();
    super.dispose();
  }

  void _scrollBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 240),
        curve: XlCurve.easeOut,
      );
    });
  }

  Future<void> _run() async {
    final task = _taskCtrl.text.trim();
    if (task.isEmpty || _running) return;
    final maxSteps = int.tryParse(_maxStepsCtrl.text.trim()) ?? 20;
    setState(() {
      _running = true;
      _events.clear();
      _expanded.clear();
      _step = 0;
      _totalSteps = 0;
    });
    try {
      final stream = XlClient.stub.agentStart(AgentRequest(
        task: task,
        autonomous: _autonomous,
        maxSteps: maxSteps,
      ));
      _sub = stream.listen(
        (ev) {
          if (!mounted) return;
          setState(() {
            _events.add(ev);
            if (ev.step > 0) _step = ev.step;
            if (ev.totalSteps > 0) _totalSteps = ev.totalSteps;
          });
          _scrollBottom();
          if (ev.done || ev.type == 'error') {
            setState(() => _running = false);
          }
        },
        onError: (e) {
          if (!mounted) return;
          setState(() {
            _events.add(AgentEvent(type: 'error', error: e.toString()));
            _running = false;
          });
        },
        onDone: () {
          if (!mounted) return;
          if (_running) setState(() => _running = false);
        },
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _events.add(AgentEvent(type: 'error', error: e.toString()));
        _running = false;
      });
    }
  }

  void _stop() {
    _sub?.cancel();
    _sub = null;
    if (mounted) setState(() => _running = false);
  }

  String _prettyJson(String raw) {
    if (raw.trim().isEmpty) return '';
    try {
      final decoded = jsonDecode(raw);
      const encoder = JsonEncoder.withIndent('  ');
      return encoder.convert(decoded);
    } catch (_) {
      return raw;
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Column(
      children: [
        _inputArea(p),
        const SizedBox(height: 10),
        _eventsArea(p),
      ],
    );
  }

  Widget _inputArea(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(child: _taskField(p)),
              const SizedBox(width: 12),
              _running ? _stopBtn(p) : _runBtn(p),
            ],
          ),
          const SizedBox(height: 12),
          _paramRow(p),
          const SizedBox(height: 12),
          _progress(p),
        ],
      ),
    );
  }

  Widget _taskField(XlPalette p) {
    return Container(
      constraints: const BoxConstraints(minHeight: 48, maxHeight: 110),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      decoration: AppTheme.screen(context, r: XlRadius.lg),
      child: TextField(
        controller: _taskCtrl,
        maxLines: 3,
        minLines: 1,
        enabled: !_running,
        textInputAction: TextInputAction.newline,
        style: TextStyle(fontSize: XlFont.bodySm, color: p.text1, height: XlLineHeight.relaxed),
        decoration: InputDecoration(
          hintText: '描述任务，Agent 将自动规划并执行…',
          hintStyle: TextStyle(fontSize: XlFont.bodySm, color: p.decor, fontWeight: FontWeight.w500),
          border: InputBorder.none,
          isDense: true,
        ),
      ),
    );
  }

  Widget _runBtn(XlPalette p) {
    return _Pressable(
      onTap: _run,
      scale: 0.94,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        decoration: AppTheme.btn(context, r: XlRadius.pill),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.play_arrow_rounded, size: 18, color: p.btnInk),
            const SizedBox(width: 4),
            Text('执行',
                style: TextStyle(
                  fontSize: XlFont.label,
                  fontWeight: FontWeight.w800,
                  color: p.btnInk,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _stopBtn(XlPalette p) {
    return _Pressable(
      onTap: _stop,
      scale: 0.94,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        decoration: AppTheme.red(context, r: XlRadius.pill),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.stop_rounded, size: 18, color: p.red),
            const SizedBox(width: 4),
            Text('停止',
                style: TextStyle(
                  fontSize: XlFont.label,
                  fontWeight: FontWeight.w800,
                  color: p.red,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _paramRow(XlPalette p) {
    return Row(
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('自主执行',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text2,
                  fontWeight: FontWeight.w700,
                  letterSpacing: XlLetterSpacing.wide,
                )),
            const SizedBox(width: 8),
            _ToggleSwitch(
              value: _autonomous,
              onChanged: _running
                  ? null
                  : (v) => setState(() => _autonomous = v),
            ),
          ],
        ),
        const SizedBox(width: 18),
        Text('最大步数',
            style: TextStyle(
              fontSize: XlFont.captionSm,
              color: p.text2,
              fontWeight: FontWeight.w700,
              letterSpacing: XlLetterSpacing.wide,
            )),
        const SizedBox(width: 8),
        Container(
          width: 64,
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: AppTheme.sunkenXs(context, r: XlRadius.sm),
          child: TextField(
            controller: _maxStepsCtrl,
            enabled: !_running,
            keyboardType: TextInputType.number,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: XlFont.captionSm,
              color: p.text1,
              fontWeight: FontWeight.w800,
            ),
            decoration: const InputDecoration(
              border: InputBorder.none,
              isDense: true,
              contentPadding: EdgeInsets.symmetric(vertical: 6),
            ),
          ),
        ),
      ],
    );
  }

  Widget _progress(XlPalette p) {
    final ratio = _totalSteps > 0 ? (_step / _totalSteps).clamp(0.0, 1.0) : 0.0;
    return Row(
      children: [
        Expanded(
          child: LayoutBuilder(
            builder: (context, c) {
              return Container(
                height: 8,
                decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: FractionallySizedBox(
                    widthFactor: ratio <= 0 ? 0.0001 : ratio,
                    child: Container(
                      decoration: BoxDecoration(
                        gradient: p.gradBrand,
                        borderRadius: BorderRadius.circular(XlRadius.pill),
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        const SizedBox(width: 10),
        Text(
          _totalSteps > 0 ? 'Step $_step/$_totalSteps' : '待机',
          style: TextStyle(
            fontSize: XlFont.micro,
            color: p.gold,
            fontWeight: FontWeight.w800,
            letterSpacing: XlLetterSpacing.wider,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
        ),
      ],
    );
  }

  Widget _eventsArea(XlPalette p) {
    if (_events.isEmpty) return _emptyState(p);
    return Expanded(
      child: Container(
        decoration: AppTheme.screenSoft(context, r: XlRadius.xl),
        child: ListView.builder(
          controller: _scroll,
          padding: const EdgeInsets.all(14),
          itemCount: _events.length,
          itemBuilder: (_, i) => _eventCard(p, _events[i], i),
        ),
      ),
    );
  }

  Widget _emptyState(XlPalette p) {
    return Expanded(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 84,
                height: 84,
                decoration: AppTheme.brandOrbLg(context, size: 84),
                child: Icon(Icons.auto_awesome_rounded, size: 34, color: p.btnInk),
              ),
              const SizedBox(height: 18),
              Text('输入任务开始自主执行',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                  )),
              const SizedBox(height: 20),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                alignment: WrapAlignment.center,
                children: _examples.map((q) => _Pressable(
                  onTap: () => _taskCtrl.text = q,
                  scale: 0.93,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    decoration: AppTheme.accentSoft(context, r: XlRadius.pill),
                    child: Text(q,
                        style: TextStyle(
                          fontSize: XlFont.label,
                          fontWeight: FontWeight.w700,
                          color: p.pink,
                          letterSpacing: XlLetterSpacing.wide,
                        )),
                  ),
                )).toList(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _eventCard(XlPalette p, AgentEvent e, int index) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (e.step > 0)
            Padding(
              padding: const EdgeInsets.only(left: 4, bottom: 4),
              child: Text('Step ${e.step}${e.totalSteps > 0 ? '/${e.totalSteps}' : ''}',
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    color: p.text3,
                    fontWeight: FontWeight.w700,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ),
          _buildCard(p, e),
        ],
      ),
    );
  }

  Widget _buildCard(XlPalette p, AgentEvent e) {
    switch (e.type) {
      case 'plan':
        return _gradientCard(
          p,
          icon: Icons.auto_awesome_rounded,
          title: '执行计划',
          body: e.content,
          gradient: p.gradBrand,
          ink: p.btnInk,
        );
      case 'thought':
        return _sunkenCard(
          p,
          icon: Icons.lightbulb_rounded,
          body: e.content,
          iconColor: p.gold,
        );
      case 'delegate':
        return _delegateCard(p, e, completed: e.content.contains('完成') || e.content.contains('completed'));
      case 'tool_call':
        if (e.toolName.contains('sub_agent') || e.toolName.contains('delegate')) {
          return _delegateCard(p, e);
        }
        return _raisedCard(
          p,
          icon: Icons.build_rounded,
          title: '调用工具: ${e.toolName.isEmpty ? 'tool' : e.toolName}',
          body: _prettyJson(e.toolArgs),
          iconColor: p.pink,
        );
      case 'tool_result':
        return _toolResultCard(p, e);
      case 'error':
        return _errorCard(p, e.error.isEmpty ? e.content : e.error);
      case 'done':
        return _gradientCard(
          p,
          icon: Icons.flag_rounded,
          title: '任务完成',
          body: e.content,
          gradient: p.gradGold,
          ink: p.btnInk,
        );
      case 'message':
      default:
        return _messageBubble(p, e.content);
    }
  }

  Widget _headerRow(XlPalette p, IconData icon, Color iconColor, String? title, Color titleColor) {
    return Row(
      children: [
        Icon(icon, size: 15, color: iconColor),
        const SizedBox(width: 8),
        if (title != null)
          Expanded(
            child: Text(title,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  color: titleColor,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ),
      ],
    );
  }

  Widget _gradientCard(XlPalette p,
      {required IconData icon,
      required String title,
      required String body,
      required Gradient gradient,
      required Color ink}) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(XlRadius.lg),
        border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.30 : 0.45), width: 1),
        boxShadow: p.raisedSm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _headerRow(p, icon, ink, title, ink),
          if (body.trim().isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(body,
                style: TextStyle(
                  fontSize: XlFont.bodySm,
                  height: XlLineHeight.relaxed,
                  color: ink,
                  fontWeight: FontWeight.w500,
                )),
          ],
        ],
      ),
    );
  }

  Widget _sunkenCard(XlPalette p,
      {required IconData icon, required String body, required Color iconColor}) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(XlRadius.lg),
        border: Border.all(color: p.shDark.withOpacity(p.isDark ? 0.26 : 0.11), width: 1),
        boxShadow: p.sunkenSm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _headerRow(p, icon, iconColor, null, p.text2),
          const SizedBox(height: 6),
          Text(body,
              style: TextStyle(
                fontSize: XlFont.bodySm,
                height: XlLineHeight.relaxed,
                color: p.text2,
                fontStyle: FontStyle.italic,
              )),
        ],
      ),
    );
  }

  Widget _raisedCard(XlPalette p,
      {required IconData icon,
      required String title,
      required String body,
      required Color iconColor}) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neu(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _headerRow(p, icon, iconColor, title, p.text1),
          if (body.trim().isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: AppTheme.sunkenXs(context, r: XlRadius.sm),
              child: Text(body,
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    height: XlLineHeight.normal,
                    color: p.text2,
                    fontFamily: 'monospace',
                  )),
            ),
          ],
        ],
      ),
    );
  }

  Widget _delegateCard(XlPalette p, AgentEvent e, {bool completed = false}) {
    final isDelegateType = e.type == 'delegate';
    final title = isDelegateType
        ? '委派子 Agent'
        : '调用工具: ${e.toolName.isEmpty ? 'sub_agent' : e.toolName}';
    final body = isDelegateType ? e.content : _prettyJson(e.toolArgs);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neu(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.people_alt_rounded, size: 15, color: p.pink),
              const SizedBox(width: 8),
              Expanded(
                child: Text(title,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ),
              completed
                  ? Icon(Icons.check_circle_rounded, size: 15, color: p.green)
                  : const _RotatingDot(),
            ],
          ),
          if (body.trim().isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: AppTheme.sunkenXs(context, r: XlRadius.sm),
              child: Text(body,
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    height: XlLineHeight.normal,
                    color: p.text2,
                    fontFamily: isDelegateType ? null : 'monospace',
                  )),
            ),
          ],
        ],
      ),
    );
  }

  Widget _toolResultCard(XlPalette p, AgentEvent e) {
    final idx = _events.indexOf(e);
    final prev = idx > 0 ? _events[idx - 1] : null;
    final isSubAgentResult = prev != null &&
        prev.type == 'tool_call' &&
        (prev.toolName.contains('sub_agent') || prev.toolName.contains('delegate'));
    final full = e.toolResult;
    final expanded = _expanded.contains(idx);
    final truncated = full.length > 500;
    final shown = (!truncated || expanded) ? full : '${full.substring(0, 500)}…';
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.screen(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _headerRow(
              p,
              isSubAgentResult ? Icons.people_alt_rounded : Icons.check_circle_rounded,
              isSubAgentResult ? p.pink : p.green,
              isSubAgentResult ? '子 Agent 结果' : '工具结果',
              p.text1),
          const SizedBox(height: 8),
          Text(shown,
              style: TextStyle(
                fontSize: XlFont.captionSm,
                height: XlLineHeight.normal,
                color: p.text2,
                fontFamily: 'monospace',
              )),
          if (truncated) ...[
            const SizedBox(height: 8),
            _Pressable(
              onTap: () => setState(() {
                if (expanded) {
                  _expanded.remove(idx);
                } else {
                  _expanded.add(idx);
                }
              }),
              scale: 0.95,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                decoration: AppTheme.ghost(context, r: XlRadius.pill),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                        size: 13, color: p.pink),
                    const SizedBox(width: 4),
                    Text(expanded ? '收起' : '展开',
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
          ],
        ],
      ),
    );
  }

  Widget _errorCard(XlPalette p, String body) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: p.red.withOpacity(p.isDark ? 0.10 : 0.06),
        borderRadius: BorderRadius.circular(XlRadius.lg),
        border: Border.all(color: p.red.withOpacity(0.55), width: 1.4),
        boxShadow: p.raisedSm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _headerRow(p, Icons.error_rounded, p.red, '错误', p.red),
          const SizedBox(height: 6),
          Text(body,
              style: TextStyle(
                fontSize: XlFont.bodySm,
                height: XlLineHeight.relaxed,
                color: p.red,
                fontWeight: FontWeight.w500,
              )),
        ],
      ),
    );
  }

  Widget _messageBubble(XlPalette p, String body) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: p.screenSoft,
          borderRadius: BorderRadius.circular(XlRadius.lg),
          border: Border.all(color: p.shDark.withOpacity(p.isDark ? 0.22 : 0.10), width: 1),
          boxShadow: p.sunkenSm,
        ),
        child: Text(body,
            style: TextStyle(
              fontSize: XlFont.bodySm,
              height: XlLineHeight.relaxed,
              color: p.text1,
            )),
      ),
    );
  }
}

class _ToggleSwitch extends StatelessWidget {
  final bool value;
  final ValueChanged<bool>? onChanged;
  const _ToggleSwitch({required this.value, this.onChanged});
  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return _Pressable(
      onTap: onChanged == null ? null : () => onChanged!(!value),
      scale: 0.95,
      child: AnimatedContainer(
        duration: XlDuration.fast,
        curve: XlCurve.standard,
        width: 44,
        height: 24,
        padding: const EdgeInsets.all(3),
        decoration: value
            ? BoxDecoration(
                gradient: p.gradBrand,
                borderRadius: BorderRadius.circular(XlRadius.pill),
                boxShadow: p.raisedXs,
              )
            : AppTheme.sunkenXs(context, r: XlRadius.pill),
        child: AnimatedAlign(
          duration: XlDuration.fast,
          curve: XlCurve.standard,
          alignment: value ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            width: 18,
            height: 18,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: value ? p.btnInk : p.text3,
              boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.2), blurRadius: 3)],
            ),
          ),
        ),
      ),
    );
  }
}

class _Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  const _Pressable({required this.child, this.onTap, this.scale = 0.95});
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

class _RotatingDot extends StatefulWidget {
  const _RotatingDot();
  @override
  State<_RotatingDot> createState() => _RotatingDotState();
}

class _RotatingDotState extends State<_RotatingDot> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(duration: const Duration(milliseconds: 900), vsync: this)..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return RotationTransition(
      turns: _ctrl,
      child: Icon(Icons.sync_rounded, size: 15, color: p.gold),
    );
  }
}
