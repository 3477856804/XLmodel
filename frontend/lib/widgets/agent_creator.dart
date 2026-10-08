import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling.pb.dart';
import '../services/local_store.dart';

class CustomAgent {
  String name;
  String description;
  String systemPrompt;
  List<String> skills;
  String permissionLevel;
  List<String> toolNames;
  final DateTime createdAt;
  CustomAgent({
    required this.name,
    required this.description,
    required this.systemPrompt,
    required this.skills,
    required this.permissionLevel,
    required this.toolNames,
    DateTime? createdAt,
  }) : createdAt = createdAt ?? DateTime.now();

  Map<String, dynamic> toJson() => {
        'name': name,
        'description': description,
        'systemPrompt': systemPrompt,
        'skills': skills,
        'permissionLevel': permissionLevel,
        'toolNames': toolNames,
        'createdAt': createdAt.toIso8601String(),
      };

  factory CustomAgent.fromJson(Map<String, dynamic> json) {
    DateTime? created;
    final rawTime = json['createdAt'];
    if (rawTime is String) created = DateTime.tryParse(rawTime);
    final rawSkills = json['skills'];
    final rawTools = json['toolNames'];
    return CustomAgent(
      name: json['name'].toString(),
      description: json['description'].toString(),
      systemPrompt: json['systemPrompt'].toString(),
      skills: rawSkills is List ? rawSkills.map((e) => e.toString()).toList() : [],
      permissionLevel: json['permissionLevel']?.toString() ?? 'default',
      toolNames: rawTools is List ? rawTools.map((e) => e.toString()).toList() : [],
      createdAt: created,
    );
  }
}

class AgentCreator extends StatefulWidget {
  const AgentCreator({super.key});
  @override
  State<AgentCreator> createState() => _AgentCreatorState();
}

class _AgentCreatorState extends State<AgentCreator> with TickerProviderStateMixin {
  final List<CustomAgent> _agents = [];
  final Set<String> _expanded = {};
  bool _loading = true;
  String? _loadError;

  static const List<Map<String, String>> _availableTools = [
    {'name': 'list_dir', 'label': '列目录', 'group': '文件'},
    {'name': 'read_file', 'label': '读文件', 'group': '文件'},
    {'name': 'write_file', 'label': '写文件', 'group': '文件'},
    {'name': 'search_code', 'label': '代码搜索', 'group': '搜索'},
    {'name': 'run_command', 'label': '执行命令', 'group': '沙箱'},
    {'name': 'run_sandboxed', 'label': '沙箱执行', 'group': '沙箱'},
    {'name': 'browser_action', 'label': '浏览器动作', 'group': '浏览器'},
    {'name': 'browser_route', 'label': '浏览器导航', 'group': '浏览器'},
    {'name': 'browser_screenshot', 'label': '截图', 'group': '浏览器'},
    {'name': 'browser_click', 'label': '点击', 'group': '浏览器'},
    {'name': 'browser_fill', 'label': '填表', 'group': '浏览器'},
    {'name': 'browser_evaluate', 'label': 'JS执行', 'group': '浏览器'},
    {'name': 'browser_console', 'label': '控制台', 'group': '浏览器'},
    {'name': 'memory_store', 'label': '记忆存储', 'group': '记忆'},
    {'name': 'semantic_search', 'label': '语义搜索', 'group': '记忆'},
  ];

  static const List<Map<String, String>> _permissionLevels = [
    {'value': 'readonly', 'label': '只读', 'desc': '仅读取文件和搜索，无写入/执行权限'},
    {'value': 'default', 'label': '默认', 'desc': '可写文件、可在沙箱内执行命令'},
    {'value': 'full', 'label': '完全', 'desc': '完全权限，可执行任意命令'},
  ];

  late AnimationController _enterCtrl;

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 400), vsync: this);
    _enterCtrl.forward();
    _load();
  }

  @override
  void dispose() {
    _enterCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final data = await LocalStore.readJson('custom_agents.json');
      if (!mounted) return;
      final raw = data['agents'];
      if (raw is List) {
        final loaded = <CustomAgent>[];
        for (final a in raw) {
          if (a is Map) loaded.add(CustomAgent.fromJson(Map<String, dynamic>.from(a)));
        }
        setState(() => _agents
          ..clear()
          ..addAll(loaded));
      }
      setState(() => _loading = false);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loadError = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _persist() async {
    await LocalStore.writeJson('custom_agents.json', {
      'agents': _agents.map((a) => a.toJson()).toList(),
    });
  }

  Future<void> _openEditor({CustomAgent? existing}) async {
    final result = await showModalBottomSheet<CustomAgent>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _AgentEditorSheet(
        existing: existing,
        availableTools: _availableTools,
        permissionLevels: _permissionLevels,
      ),
    );
    if (result != null) {
      setState(() {
        final idx = _agents.indexWhere((a) => a.name == result.name);
        if (idx >= 0) {
          _agents[idx] = result;
        } else {
          _agents.add(result);
        }
      });
      await _persist();
    }
  }

  Future<void> _testAgent(CustomAgent agent) async {
    final p = XlPalette.of(context);
    final taskCtrl = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: p.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.lg)),
        title: Text('测试 ${agent.name}',
            style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
        content: SizedBox(
          width: 420,
          child: TextField(
            controller: taskCtrl,
            autofocus: true,
            maxLines: 3,
            style: TextStyle(fontSize: XlFont.bodySm, color: p.text1),
            decoration: InputDecoration(
              hintText: '输入测试任务…',
              hintStyle: TextStyle(color: p.decor),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(XlRadius.md)),
            ),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: Text('取消', style: TextStyle(color: p.text3))),
          TextButton(onPressed: () => Navigator.pop(ctx, taskCtrl.text.trim()), child: Text('运行', style: TextStyle(color: p.pink))),
        ],
      ),
    );
    if (result == null || result.isEmpty) return;

    final ctxData = jsonEncode({
      'agent_name': agent.name,
      'permission_level': agent.permissionLevel,
      'tool_names': agent.toolNames,
      'system_prompt': agent.systemPrompt,
    });

    try {
      final stream = XlClient.stub.agentStart(AgentRequest(
        task: result,
        context: ctxData,
        autonomous: true,
        maxSteps: 20,
      ));
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (ctx) => _TestRunDialog(stream: stream, agentName: agent.name),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('启动失败: $e')));
    }
  }

  Future<void> _deleteAgent(CustomAgent agent) async {
    final p = XlPalette.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: p.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.lg)),
        title: Text('删除 Agent', style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
        content: Text('确定删除「${agent.name}」？此操作不可撤销。', style: TextStyle(fontSize: XlFont.bodySm, color: p.text2)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text('取消', style: TextStyle(color: p.text3))),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: Text('删除', style: TextStyle(color: p.red))),
        ],
      ),
    );
    if (ok == true) {
      setState(() => _agents.removeWhere((a) => a.name == agent.name));
      await _persist();
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Column(
      children: [
        _header(p),
        const SizedBox(height: 12),
        Expanded(child: _body(p)),
      ],
    );
  }

  Widget _header(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Row(
        children: [
          Icon(Icons.smart_toy_rounded, size: 18, color: p.pink),
          const SizedBox(width: 8),
          Text('自定义 Agent',
              style: TextStyle(
                fontSize: XlFont.h6,
                fontWeight: FontWeight.w800,
                color: p.text1,
                letterSpacing: XlLetterSpacing.normal,
              )),
          const Spacer(),
          _Pressable(
            onTap: () => _openEditor(),
            scale: 0.95,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: AppTheme.btn(context, r: XlRadius.pill),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.add_rounded, size: 16, color: p.btnInk),
                  const SizedBox(width: 4),
                  Text('新建 Agent',
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

  Widget _body(XlPalette p) {
    if (_loading) return Center(child: CircularProgressIndicator(color: p.pink));
    if (_loadError != null) return Center(child: Text('加载失败: $_loadError', style: TextStyle(color: p.red)));
    if (_agents.isEmpty) return _emptyState(p);
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 20),
      itemCount: _agents.length,
      itemBuilder: (_, i) => _agentCard(p, _agents[i]),
    );
  }

  Widget _emptyState(XlPalette p) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: AppTheme.brandOrbLg(context, size: 80),
            child: Icon(Icons.smart_toy_rounded, size: 32, color: p.btnInk),
          ),
          const SizedBox(height: 16),
          Text('暂无自定义 Agent',
              style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
          const SizedBox(height: 6),
          Text('创建一个专属 Agent 来自动化你的工作流',
              style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
        ],
      ),
    );
  }

  Widget _agentCard(XlPalette p, CustomAgent agent) {
    final expanded = _expanded.contains(agent.name);
    final permInfo = _permissionLevels.firstWhere(
      (e) => e['value'] == agent.permissionLevel,
      orElse: () => {'label': agent.permissionLevel, 'desc': ''},
    );
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neu(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: AppTheme.orb(context, size: 36, color: p.pinkSoft),
                child: Icon(Icons.psychology_rounded, size: 18, color: p.pink),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(agent.name,
                        style: TextStyle(fontSize: XlFont.body, fontWeight: FontWeight.w800, color: p.text1)),
                    Text(agent.description,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
                  ],
                ),
              ),
              IconButton(
                icon: Icon(Icons.play_arrow_rounded, size: 20, color: p.gold),
                onPressed: () => _testAgent(agent),
                tooltip: '测试运行',
              ),
              IconButton(
                icon: Icon(Icons.edit_rounded, size: 18, color: p.text2),
                onPressed: () => _openEditor(existing: agent),
                tooltip: '编辑',
              ),
              IconButton(
                icon: Icon(Icons.delete_outline_rounded, size: 18, color: p.red),
                onPressed: () => _deleteAgent(agent),
                tooltip: '删除',
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: AppTheme.pill(context, color: p.gold, r: XlRadius.pill),
                child: Text('权限: ${permInfo['label']}',
                    style: TextStyle(fontSize: XlFont.micro, color: p.gold, fontWeight: FontWeight.w800)),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: AppTheme.pill(context, color: p.pink, r: XlRadius.pill),
                child: Text('工具: ${agent.toolNames.length}',
                    style: TextStyle(fontSize: XlFont.micro, color: p.pink, fontWeight: FontWeight.w800)),
              ),
              const Spacer(),
              _Pressable(
                onTap: () => setState(() {
                  if (expanded) {
                    _expanded.remove(agent.name);
                  } else {
                    _expanded.add(agent.name);
                  }
                }),
                child: Icon(expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded, size: 18, color: p.text3),
              ),
            ],
          ),
          if (expanded) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: AppTheme.sunkenXs(context, r: XlRadius.sm),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('系统提示词', style: TextStyle(fontSize: XlFont.micro, color: p.text3, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 4),
                  Text(agent.systemPrompt, style: TextStyle(fontSize: XlFont.captionSm, color: p.text2, height: XlLineHeight.normal)),
                  const SizedBox(height: 10),
                  Text('技能 (${agent.skills.length})', style: TextStyle(fontSize: XlFont.micro, color: p.text3, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: agent.skills.map((s) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: AppTheme.pill(context, color: p.pink, r: XlRadius.pill),
                      child: Text(s, style: TextStyle(fontSize: XlFont.micro, color: p.pink, fontWeight: FontWeight.w700)),
                    )).toList(),
                  ),
                  const SizedBox(height: 10),
                  Text('允许工具 (${agent.toolNames.length})', style: TextStyle(fontSize: XlFont.micro, color: p.text3, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: agent.toolNames.map((t) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: AppTheme.pill(context, color: p.gold, r: XlRadius.pill),
                      child: Text(t, style: TextStyle(fontSize: XlFont.micro, color: p.gold, fontWeight: FontWeight.w700)),
                    )).toList(),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _AgentEditorSheet extends StatefulWidget {
  final CustomAgent? existing;
  final List<Map<String, String>> availableTools;
  final List<Map<String, String>> permissionLevels;
  const _AgentEditorSheet({this.existing, required this.availableTools, required this.permissionLevels});
  @override
  State<_AgentEditorSheet> createState() => _AgentEditorSheetState();
}

class _AgentEditorSheetState extends State<_AgentEditorSheet> {
  late TextEditingController _nameCtrl;
  late TextEditingController _descCtrl;
  late TextEditingController _promptCtrl;
  late TextEditingController _skillCtrl;
  late List<String> _skills;
  late String _permissionLevel;
  late Set<String> _selectedTools;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    _nameCtrl = TextEditingController(text: e?.name ?? '');
    _descCtrl = TextEditingController(text: e?.description ?? '');
    _promptCtrl = TextEditingController(text: e?.systemPrompt ?? '');
    _skillCtrl = TextEditingController();
    _skills = List<String>.from(e?.skills ?? []);
    _permissionLevel = e?.permissionLevel ?? 'default';
    _selectedTools = Set<String>.from(e?.toolNames ?? []);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    _promptCtrl.dispose();
    _skillCtrl.dispose();
    super.dispose();
  }

  void _addSkill() {
    final s = _skillCtrl.text.trim();
    if (s.isNotEmpty && !_skills.contains(s)) {
      setState(() {
        _skills.add(s);
        _skillCtrl.clear();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final isDark = p.isDark;
    final bg = isDark ? p.surface : const Color(0xFFF5F0F2);
    final media = MediaQuery.of(context);
    return Container(
      margin: EdgeInsets.only(bottom: media.viewInsets.bottom),
      constraints: BoxConstraints(maxHeight: media.size.height * 0.85),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(color: p.divider, borderRadius: BorderRadius.circular(2)),
              ),
            ),
            const SizedBox(height: 16),
            Text(widget.existing == null ? '新建 Agent' : '编辑 Agent',
                style: TextStyle(fontSize: XlFont.h5, fontWeight: FontWeight.w800, color: p.text1)),
            const SizedBox(height: 16),
            _field(p, '名称', _nameCtrl, hint: '如：代码审查专家'),
            const SizedBox(height: 12),
            _field(p, '描述', _descCtrl, hint: '一句话描述这个 Agent 的职责'),
            const SizedBox(height: 12),
            _field(p, '系统提示词', _promptCtrl, hint: '定义 Agent 的行为、知识边界和工作方式…', maxLines: 5),
            const SizedBox(height: 16),
            Text('权限级别', style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.text1)),
            const SizedBox(height: 8),
            ...widget.permissionLevels.map((perm) => _permOption(p, perm)),
            const SizedBox(height: 16),
            Text('工具白名单', style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.text1)),
            const SizedBox(height: 4),
            Text('勾选此 Agent 可使用的工具（不选则允许全部）',
                style: TextStyle(fontSize: XlFont.micro, color: p.text3)),
            const SizedBox(height: 8),
            _toolsGrid(p),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    decoration: AppTheme.sunkenXs(context, r: XlRadius.sm),
                    child: TextField(
                      controller: _skillCtrl,
                      style: TextStyle(fontSize: XlFont.captionSm, color: p.text1),
                      decoration: InputDecoration(
                        hintText: '添加技能标签…',
                        hintStyle: TextStyle(fontSize: XlFont.captionSm, color: p.decor),
                        border: InputBorder.none,
                        isDense: true,
                        contentPadding: const EdgeInsets.symmetric(vertical: 10),
                      ),
                      onSubmitted: (_) => _addSkill(),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(onPressed: _addSkill, icon: Icon(Icons.add_rounded, color: p.pink)),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: _skills.map((s) => Chip(
                label: Text(s, style: TextStyle(fontSize: XlFont.micro, color: p.pink)),
                backgroundColor: p.pinkSoft,
                deleteIcon: Icon(Icons.close_rounded, size: 14, color: p.pink),
                onDeleted: () => setState(() => _skills.remove(s)),
              )).toList(),
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(onPressed: () => Navigator.pop(context), child: Text('取消', style: TextStyle(color: p.text3))),
                const SizedBox(width: 12),
                ElevatedButton(
                  onPressed: () {
                    if (_nameCtrl.text.trim().isEmpty) return;
                    Navigator.pop(context, CustomAgent(
                      name: _nameCtrl.text.trim(),
                      description: _descCtrl.text.trim(),
                      systemPrompt: _promptCtrl.text.trim(),
                      skills: _skills,
                      permissionLevel: _permissionLevel,
                      toolNames: _selectedTools.toList(),
                      createdAt: widget.existing?.createdAt,
                    ));
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: p.pink,
                    foregroundColor: p.btnInk,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.pill)),
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                  ),
                  child: const Text('保存', style: TextStyle(fontWeight: FontWeight.w800)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _field(XlPalette p, String label, TextEditingController ctrl, {String? hint, int maxLines = 1}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.text1)),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: AppTheme.sunkenXs(context, r: XlRadius.sm),
          child: TextField(
            controller: ctrl,
            maxLines: maxLines,
            style: TextStyle(fontSize: XlFont.captionSm, color: p.text1),
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: TextStyle(fontSize: XlFont.captionSm, color: p.decor),
              border: InputBorder.none,
              isDense: true,
              contentPadding: const EdgeInsets.symmetric(vertical: 10),
            ),
          ),
        ),
      ],
    );
  }

  Widget _permOption(XlPalette p, Map<String, String> perm) {
    final selected = _permissionLevel == perm['value'];
    return _Pressable(
      onTap: () => setState(() => _permissionLevel = perm['value']!),
      scale: 0.98,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: selected
            ? AppTheme.brand(context, r: XlRadius.md)
            : AppTheme.sunkenXs(context, r: XlRadius.md),
        child: Row(
          children: [
            Icon(
              selected ? Icons.radio_button_checked_rounded : Icons.radio_button_unchecked_rounded,
              size: 18,
              color: selected ? p.btnInk : p.text3,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(perm['label']!,
                      style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w800, color: selected ? p.btnInk : p.text1)),
                  Text(perm['desc']!,
                      style: TextStyle(fontSize: XlFont.micro, color: selected ? p.btnInk.withOpacity(0.8) : p.text3)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _toolsGrid(XlPalette p) {
    final groups = <String, List<Map<String, String>>>{};
    for (final t in widget.availableTools) {
      final g = t['group']!;
      groups.putIfAbsent(g, () => []).add(t);
    }
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: AppTheme.sunkenXs(context, r: XlRadius.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: groups.entries.map((entry) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Text(entry.key, style: TextStyle(fontSize: XlFont.micro, color: p.text3, fontWeight: FontWeight.w800)),
              ),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: entry.value.map((tool) {
                  final selected = _selectedTools.contains(tool['name']);
                  return FilterChip(
                    label: Text(tool['label']!, style: TextStyle(fontSize: XlFont.micro, color: selected ? p.btnInk : p.text2)),
                    selected: selected,
                    onSelected: (v) => setState(() {
                      if (v) {
                        _selectedTools.add(tool['name']!);
                      } else {
                        _selectedTools.remove(tool['name']);
                      }
                    }),
                    backgroundColor: p.surface,
                    selectedColor: p.pink,
                    checkmarkColor: p.btnInk,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.pill)),
                    side: BorderSide.none,
                  );
                }).toList(),
              ),
              const SizedBox(height: 6),
            ],
          );
        }).toList(),
      ),
    );
  }
}

class _TestRunDialog extends StatefulWidget {
  final Stream<AgentEvent> stream;
  final String agentName;
  const _TestRunDialog({required this.stream, required this.agentName});
  @override
  State<_TestRunDialog> createState() => _TestRunDialogState();
}

class _TestRunDialogState extends State<_TestRunDialog> {
  final List<AgentEvent> _events = [];
  bool _done = false;

  @override
  void initState() {
    super.initState();
    widget.stream.listen((ev) {
      if (!mounted) return;
      setState(() {
        _events.add(ev);
        if (ev.done) _done = true;
      });
    }, onError: (e) {
      if (!mounted) return;
      setState(() => _done = true);
    }, onDone: () {
      if (!mounted) return;
      setState(() => _done = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return AlertDialog(
      backgroundColor: p.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.lg)),
      title: Text('测试运行: ${widget.agentName}', style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
      content: SizedBox(
        width: 480,
        height: 400,
        child: _events.isEmpty
            ? Center(child: CircularProgressIndicator(color: p.pink))
            : ListView.builder(
                itemCount: _events.length,
                itemBuilder: (_, i) => _eventTile(p, _events[i]),
              ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(_done ? '关闭' : '等待中…', style: TextStyle(color: p.pink)),
        ),
      ],
    );
  }

  Widget _eventTile(XlPalette p, AgentEvent ev) {
    IconData icon;
    Color color;
    switch (ev.type) {
      case 'tool_call':
        icon = Icons.build_rounded;
        color = p.blue;
        break;
      case 'tool_result':
        icon = Icons.check_circle_rounded;
        color = p.green;
        break;
      case 'done':
        icon = Icons.flag_rounded;
        color = p.green;
        break;
      case 'error':
        icon = Icons.error_rounded;
        color = p.red;
        break;
      default:
        icon = Icons.bubble_chart_rounded;
        color = p.text3;
    }
    final body = ev.type == 'tool_call' ? ev.toolArgs : (ev.type == 'tool_result' ? ev.toolResult : ev.content);
    final label = ev.type == 'tool_call' ? '调用 ${ev.toolName}' : ev.type;
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: TextStyle(fontSize: XlFont.micro, color: color, fontWeight: FontWeight.w800)),
                if (body.isNotEmpty)
                  Text(body.length > 200 ? '${body.substring(0, 200)}…' : body,
                      style: TextStyle(fontSize: XlFont.micro, color: p.text2, height: XlLineHeight.normal)),
              ],
            ),
          ),
        ],
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
