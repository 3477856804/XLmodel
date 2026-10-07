import 'dart:convert';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../services/local_store.dart';

class WorkflowBuilder extends StatefulWidget {
  const WorkflowBuilder({super.key});

  @override
  State<WorkflowBuilder> createState() => _WorkflowBuilderState();
}

class _WorkflowNodeModel {
  final String id;
  String type;
  Map<String, String> config;
  String? nextId;
  _WorkflowNodeModel({
    required this.id,
    required this.type,
    Map<String, String>? config,
    this.nextId,
  }) : config = config ?? {};

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'config': Map<String, dynamic>.from(config),
        'nextId': nextId,
      };

  factory _WorkflowNodeModel.fromJson(Map<String, dynamic> json) {
    final cfg = <String, String>{};
    final rawCfg = json['config'];
    if (rawCfg is Map) {
      rawCfg.forEach((k, v) => cfg[k.toString()] = v.toString());
    }
    return _WorkflowNodeModel(
      id: json['id'].toString(),
      type: json['type'].toString(),
      config: cfg,
      nextId: json['nextId']?.toString(),
    );
  }
}

class _SavedWorkflow {
  final String name;
  final String description;
  final List<_WorkflowNodeModel> nodes;
  _SavedWorkflow({
    required this.name,
    required this.description,
    required this.nodes,
  });

  Map<String, dynamic> toJson() => {
        'name': name,
        'description': description,
        'nodes': nodes.map((n) => n.toJson()).toList(),
      };

  factory _SavedWorkflow.fromJson(Map<String, dynamic> json) {
    final nodes = <_WorkflowNodeModel>[];
    final rawNodes = json['nodes'];
    if (rawNodes is List) {
      for (final n in rawNodes) {
        if (n is Map) nodes.add(_WorkflowNodeModel.fromJson(Map<String, dynamic>.from(n)));
      }
    }
    return _SavedWorkflow(
      name: json['name'].toString(),
      description: json['description'].toString(),
      nodes: nodes,
    );
  }
}

class _WorkflowBuilderState extends State<WorkflowBuilder> {
  final TextEditingController _nameCtrl = TextEditingController(text: '我的工作流');
  final TextEditingController _descCtrl = TextEditingController(text: '描述这个工作流的用途');
  final List<_WorkflowNodeModel> _nodes = [];
  final List<_SavedWorkflow> _saved = [];
  int _nodeCounter = 0;
  List<String> _runResults = [];
  bool _running = false;

  static const Map<String, IconData> _typeIcons = {
    'trigger': Icons.play_arrow_rounded,
    'action': Icons.build_rounded,
    'llm': Icons.auto_awesome_rounded,
    'condition': Icons.filter_list_rounded,
  };

  static const Map<String, String> _typeLabels = {
    'trigger': '触发',
    'action': '动作',
    'llm': 'LLM',
    'condition': '条件',
  };

  @override
  void initState() {
    super.initState();
    _addNode('trigger');
    _loadSaved();
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadSaved() async {
    final data = await LocalStore.readJson('workflows.json');
    if (!mounted) return;
    final raw = data['workflows'];
    if (raw is List) {
      final loaded = <_SavedWorkflow>[];
      for (final w in raw) {
        if (w is Map) loaded.add(_SavedWorkflow.fromJson(Map<String, dynamic>.from(w)));
      }
      setState(() => _saved
        ..clear()
        ..addAll(loaded));
    }
  }

  Future<void> _persistSaved() async {
    await LocalStore.writeJson('workflows.json', {
      'workflows': _saved.map((w) => w.toJson()).toList(),
    });
  }

  void _addNode(String type) {
    final id = 'node_${_nodeCounter++}';
    Map<String, String> config = {};
    if (type == 'trigger') {
      config = {'triggerType': 'manual'};
    } else if (type == 'action') {
      config = {'action': 'log', 'message': '', 'seconds': '1', 'key': '', 'value': ''};
    } else if (type == 'llm') {
      config = {'prompt': ''};
    } else if (type == 'condition') {
      config = {'expression': ''};
    }
    setState(() {
      _nodes.add(_WorkflowNodeModel(id: id, type: type, config: config));
    });
  }

  void _deleteNode(String id) {
    setState(() {
      _nodes.removeWhere((n) => n.id == id);
      for (final n in _nodes) {
        if (n.nextId == id) n.nextId = null;
      }
    });
  }

  void _saveWorkflow() {
    if (_nameCtrl.text.trim().isEmpty) return;
    setState(() {
      final idx = _saved.indexWhere((w) => w.name == _nameCtrl.text.trim());
      final copy = _nodes.map((n) => _WorkflowNodeModel(
        id: n.id,
        type: n.type,
        config: Map<String, String>.from(n.config),
        nextId: n.nextId,
      )).toList();
      final wf = _SavedWorkflow(
        name: _nameCtrl.text.trim(),
        description: _descCtrl.text.trim(),
        nodes: copy,
      );
      if (idx >= 0) {
        _saved[idx] = wf;
      } else {
        _saved.add(wf);
      }
    });
    _persistSaved();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('已保存: ${_nameCtrl.text.trim()}')),
    );
  }

  void _loadWorkflow(_SavedWorkflow wf) {
    setState(() {
      _nameCtrl.text = wf.name;
      _descCtrl.text = wf.description;
      _nodes
        ..clear()
        ..addAll(wf.nodes.map((n) => _WorkflowNodeModel(
              id: n.id,
              type: n.type,
              config: Map<String, String>.from(n.config),
              nextId: n.nextId,
            )));
    });
  }

  void _deleteSaved(_SavedWorkflow wf) {
    setState(() {
      _saved.removeWhere((w) => w.name == wf.name);
    });
    _persistSaved();
  }

  Future<void> _runWorkflow() async {
    setState(() {
      _running = true;
      _runResults = [];
    });
    final trigger = _nodes.where((n) => n.type == 'trigger').toList();
    if (trigger.isEmpty) {
      setState(() {
        _runResults = ['错误: 没有触发节点'];
        _running = false;
      });
      return;
    }
    final spec = {
      'name': 'ui_workflow',
      'description': '前端搭建的工作流',
      'nodes': _nodes
          .map((n) => {
                'id': n.id,
                'type': n.type,
                'config': Map<String, dynamic>.from(n.config),
                'next': n.nextId ?? '',
              })
          .toList(),
      'context': <String, dynamic>{},
    };
    try {
      final reply = await XlClient.stub.command('workflow:run ${jsonEncode(spec)}');
      final decoded = jsonDecode(reply.output);
      if (decoded is Map && decoded['ok'] == false) {
        if (!mounted) return;
        setState(() {
          _runResults = ['执行失败: ${decoded['error'] ?? ''}'];
          _running = false;
        });
        return;
      }
      final results = decoded['results'];
      final lines = <String>[];
      if (results is List) {
        for (final r in results) {
          if (r is Map) {
            final node = (r['node'] ?? '').toString();
            final res = (r['result'] ?? '').toString();
            lines.add('$node -> $res');
          }
        }
      }
      if (lines.isEmpty) {
        lines.add('工作流已执行，共 ${_nodes.length} 个节点');
      }
      if (!mounted) return;
      setState(() {
        _runResults = lines;
        _running = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _runResults = ['执行失败: $e'];
        _running = false;
      });
    }
  }

  void _showAddDialog() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        final p = XlPalette.of(ctx);
        return Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: p.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('添加节点',
                  style: TextStyle(
                      fontSize: XlFont.h5, fontWeight: FontWeight.w800, color: p.text1)),
              const SizedBox(height: 16),
              ..._typeLabels.entries.map((e) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _PressTile(
                      icon: _typeIcons[e.key]!,
                      label: '${e.value}节点',
                      color: _colorFor(e.key, p),
                      onTap: () {
                        Navigator.pop(ctx);
                        _addNode(e.key);
                      },
                    ),
                  )),
            ],
          ),
        );
      },
    );
  }

  Color _colorFor(String type, XlPalette p) {
    switch (type) {
      case 'trigger':
        return p.green;
      case 'action':
        return p.pink;
      case 'llm':
        return p.violet;
      case 'condition':
        return p.gold;
      default:
        return p.pink;
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _header(p),
          const SizedBox(height: 20),
          _nodeList(p),
          const SizedBox(height: 16),
          _addButton(p),
          const SizedBox(height: 20),
          _runSection(p),
          const SizedBox(height: 24),
          _savedSection(p),
        ],
      ),
    );
  }

  Widget _header(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.account_tree_rounded, size: 20, color: p.pink),
              const SizedBox(width: 10),
              Text('工作流配置',
                  style: TextStyle(
                      fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
            ],
          ),
          const SizedBox(height: 16),
          _labeledField(p, '名称', _nameCtrl),
          const SizedBox(height: 12),
          _labeledField(p, '描述', _descCtrl),
          const SizedBox(height: 16),
          Align(
            alignment: Alignment.centerRight,
            child: _Pressable(
              onTap: _saveWorkflow,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                decoration: AppTheme.btn(context, r: XlRadius.pill),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.save_rounded, size: 15, color: p.btnInk),
                    const SizedBox(width: 8),
                    Text('保存',
                        style: TextStyle(
                            fontSize: XlFont.captionSm,
                            fontWeight: FontWeight.w800,
                            color: p.btnInk,
                            letterSpacing: XlLetterSpacing.wider)),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _labeledField(XlPalette p, String label, TextEditingController ctrl) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: TextStyle(
                fontSize: XlFont.label,
                color: p.text3,
                fontWeight: FontWeight.w700,
                letterSpacing: XlLetterSpacing.wider)),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          decoration: AppTheme.sunken(context, r: XlRadius.md),
          child: TextField(
            controller: ctrl,
            style: TextStyle(
                fontSize: XlFont.caption, color: p.text1, fontWeight: FontWeight.w600),
            decoration: const InputDecoration(
              border: InputBorder.none,
              isDense: true,
            ),
          ),
        ),
      ],
    );
  }

  Widget _nodeList(XlPalette p) {
    if (_nodes.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(30),
        alignment: Alignment.center,
        decoration: AppTheme.neuSm(context, r: XlRadius.lg),
        child: Text('暂无节点，点击下方按钮添加',
            style: TextStyle(
                fontSize: XlFont.caption, color: p.text3, fontWeight: FontWeight.w600)),
      );
    }
    return Column(
      children: [
        for (int i = 0; i < _nodes.length; i++) ...[
          _nodeCard(p, _nodes[i], i),
          if (i != _nodes.length - 1)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Icon(Icons.arrow_downward_rounded, size: 16, color: p.decor),
            ),
        ],
      ],
    );
  }

  Widget _nodeCard(XlPalette p, _WorkflowNodeModel node, int index) {
    final color = _colorFor(node.type, p);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neuLg(context, r: XlRadius.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                  borderRadius: BorderRadius.circular(XlRadius.sm),
                  border: Border.all(color: color.withOpacity(0.30), width: 1),
                ),
                child: Icon(_typeIcons[node.type], size: 18, color: color),
              ),
              const SizedBox(width: 12),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: p.gold.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(XlRadius.pill),
                  border: Border.all(color: p.gold.withOpacity(0.35), width: 1),
                ),
                child: Text(_typeLabels[node.type] ?? node.type,
                    style: TextStyle(
                        fontSize: XlFont.micro,
                        fontWeight: FontWeight.w800,
                        color: p.gold,
                        letterSpacing: XlLetterSpacing.wider)),
              ),
              const SizedBox(width: 8),
              Text('#$index',
                  style: TextStyle(
                      fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w600)),
              const Spacer(),
              _Pressable(
                onTap: () => _deleteNode(node.id),
                child: Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: p.red.withOpacity(0.10),
                    borderRadius: BorderRadius.circular(XlRadius.xs),
                  ),
                  child: Icon(Icons.close_rounded, size: 14, color: p.red),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _configFields(p, node),
          const SizedBox(height: 12),
          _nextSelector(p, node),
        ],
      ),
    );
  }

  Widget _configFields(XlPalette p, _WorkflowNodeModel node) {
    switch (node.type) {
      case 'trigger':
        return _dropdownField(
          p,
          '触发类型',
          node.config['triggerType'] ?? 'manual',
          const ['manual', 'timer', 'event'],
          (v) => setState(() => node.config['triggerType'] = v),
        );
      case 'action':
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _dropdownField(
              p,
              '动作类型',
              node.config['action'] ?? 'log',
              const ['log', 'delay', 'set_var', 'tool'],
              (v) => setState(() => node.config['action'] = v),
            ),
            const SizedBox(height: 10),
            if ((node.config['action'] ?? 'log') == 'log')
              _textField(p, '消息', node.config['message'] ?? '',
                  (v) => node.config['message'] = v)
            else if ((node.config['action'] ?? 'log') == 'delay')
              _textField(p, '秒数', node.config['seconds'] ?? '1',
                  (v) => node.config['seconds'] = v, numeric: true)
            else if ((node.config['action'] ?? 'log') == 'set_var') ...[
              _textField(p, '变量名', node.config['key'] ?? '',
                  (v) => node.config['key'] = v),
              const SizedBox(height: 8),
              _textField(p, '变量值', node.config['value'] ?? '',
                  (v) => node.config['value'] = v),
            ] else
              _textField(p, '工具参数', node.config['tool'] ?? '',
                  (v) => node.config['tool'] = v),
          ],
        );
      case 'llm':
        return _textField(p, '提示词模板', node.config['prompt'] ?? '',
            (v) => node.config['prompt'] = v, maxLines: 3);
      case 'condition':
        return _textField(p, '条件表达式', node.config['expression'] ?? '',
            (v) => node.config['expression'] = v);
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _dropdownField(
      XlPalette p, String label, String value, List<String> items, ValueChanged<String> onChanged) {
    return Row(
      children: [
        SizedBox(
          width: 64,
          child: Text(label,
              style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.text3,
                  fontWeight: FontWeight.w700,
                  letterSpacing: XlLetterSpacing.wider)),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: AppTheme.sunkenSm(context, r: XlRadius.sm),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: value,
                isExpanded: true,
                dropdownColor: p.surface,
                icon: Icon(Icons.arrow_drop_down_rounded, color: p.text3),
                style: TextStyle(
                    fontSize: XlFont.captionSm, color: p.text1, fontWeight: FontWeight.w600),
                items: items
                    .map((e) => DropdownMenuItem(value: e, child: Text(e)))
                    .toList(),
                onChanged: (v) {
                  if (v != null) onChanged(v);
                },
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _textField(XlPalette p, String label, String value, ValueChanged<String> onChanged,
      {bool numeric = false, int maxLines = 1}) {
    return Row(
      crossAxisAlignment: maxLines > 1 ? CrossAxisAlignment.start : CrossAxisAlignment.center,
      children: [
        SizedBox(
          width: 64,
          child: Padding(
            padding: EdgeInsets.only(top: maxLines > 1 ? 12 : 0),
            child: Text(label,
                style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w700,
                    letterSpacing: XlLetterSpacing.wider)),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
            decoration: AppTheme.sunkenSm(context, r: XlRadius.sm),
            child: TextField(
              controller: TextEditingController(text: value),
              onChanged: onChanged,
              maxLines: maxLines,
              keyboardType: numeric ? TextInputType.number : TextInputType.text,
              style: TextStyle(
                  fontSize: XlFont.captionSm, color: p.text1, fontWeight: FontWeight.w600),
              decoration: const InputDecoration(
                border: InputBorder.none,
                isDense: true,
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _nextSelector(XlPalette p, _WorkflowNodeModel node) {
    final options = <String>[''];
    options.addAll(_nodes.where((n) => n.id != node.id).map((n) => n.id));
    return Row(
      children: [
        Icon(Icons.subdirectory_arrow_right_rounded, size: 14, color: p.decor),
        const SizedBox(width: 8),
        Text('下一节点',
            style: TextStyle(
                fontSize: XlFont.label,
                color: p.text3,
                fontWeight: FontWeight.w700,
                letterSpacing: XlLetterSpacing.wider)),
        const SizedBox(width: 8),
        Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: AppTheme.sunkenSm(context, r: XlRadius.sm),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: node.nextId ?? '',
                isExpanded: true,
                dropdownColor: p.surface,
                icon: Icon(Icons.arrow_drop_down_rounded, color: p.text3),
                style: TextStyle(
                    fontSize: XlFont.captionSm, color: p.text1, fontWeight: FontWeight.w600),
                items: options.map((e) {
                  if (e.isEmpty) {
                    return const DropdownMenuItem(value: '', child: Text('（无）'));
                  }
                  final target = _nodes.firstWhere((n) => n.id == e);
                  return DropdownMenuItem(
                      value: e, child: Text('${_typeLabels[target.type]} · #${_nodes.indexOf(target)}'));
                }).toList(),
                onChanged: (v) => setState(() => node.nextId = (v == null || v.isEmpty) ? null : v),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _addButton(XlPalette p) {
    return _Pressable(
      onTap: _showAddDialog,
      scale: 0.97,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: AppTheme.neuSm(context, r: XlRadius.md),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.add_rounded, size: 18, color: p.pink),
            const SizedBox(width: 8),
            Text('添加节点',
                style: TextStyle(
                    fontSize: XlFont.caption,
                    fontWeight: FontWeight.w800,
                    color: p.pink,
                    letterSpacing: XlLetterSpacing.wider)),
          ],
        ),
      ),
    );
  }

  Widget _runSection(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.play_circle_outline_rounded, size: 20, color: p.gold),
              const SizedBox(width: 10),
              Text('测试运行',
                  style: TextStyle(
                      fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
              const Spacer(),
              _Pressable(
                onTap: _running ? null : _runWorkflow,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 18, vertical: 9),
                  decoration: AppTheme.btn(context, r: XlRadius.pill),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (_running)
                        SizedBox(
                          width: 13,
                          height: 13,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: p.btnInk),
                        )
                      else
                        Icon(Icons.play_arrow_rounded, size: 15, color: p.btnInk),
                      const SizedBox(width: 6),
                      Text('运行',
                          style: TextStyle(
                              fontSize: XlFont.captionSm,
                              fontWeight: FontWeight.w800,
                              color: p.btnInk,
                              letterSpacing: XlLetterSpacing.wider)),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (_runResults.isNotEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: AppTheme.sunkenDeep(context, r: XlRadius.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (int i = 0; i < _runResults.length; i++)
                    Padding(
                      padding: EdgeInsets.only(
                          bottom: i == _runResults.length - 1 ? 0 : 6),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${i + 1}. ',
                              style: TextStyle(
                                  fontSize: XlFont.captionSm,
                                  color: p.gold,
                                  fontWeight: FontWeight.w800)),
                          Expanded(
                            child: Text(_runResults[i],
                                style: TextStyle(
                                    fontSize: XlFont.captionSm,
                                    color: p.text2,
                                    fontWeight: FontWeight.w500)),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            )
          else
            Text('点击"运行"执行当前工作流，结果将显示在这里',
                style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _savedSection(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.folder_open_rounded, size: 18, color: p.violet),
              const SizedBox(width: 10),
              Text('已保存的工作流',
                  style: TextStyle(
                      fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
              const SizedBox(width: 8),
              Text('${_saved.length}',
                  style: TextStyle(
                      fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w700)),
            ],
          ),
          const SizedBox(height: 14),
          if (_saved.isEmpty)
            Text('暂无已保存的工作流',
                style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w600))
          else
            ..._saved.map((wf) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: AppTheme.neuXs(context, r: XlRadius.md),
                    child: Row(
                      children: [
                        Icon(Icons.account_tree_rounded, size: 15, color: p.pink),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(wf.name,
                                  style: TextStyle(
                                      fontSize: XlFont.caption,
                                      fontWeight: FontWeight.w700,
                                      color: p.text1)),
                              Text('${wf.nodes.length} 个节点',
                                  style: TextStyle(
                                      fontSize: XlFont.micro,
                                      color: p.text3,
                                      fontWeight: FontWeight.w500)),
                            ],
                          ),
                        ),
                        _Pressable(
                          onTap: () => _loadWorkflow(wf),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 6),
                            child: Text('加载',
                                style: TextStyle(
                                    fontSize: XlFont.captionSm,
                                    fontWeight: FontWeight.w700,
                                    color: p.pink)),
                          ),
                        ),
                        _Pressable(
                          onTap: () => _deleteSaved(wf),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 6),
                            child: Icon(Icons.delete_outline_rounded,
                                size: 15, color: p.red),
                          ),
                        ),
                      ],
                    ),
                  ),
                )),
        ],
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

class _PressTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;
  const _PressTile(
      {required this.icon,
      required this.label,
      required this.color,
      required this.onTap});
  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return _Pressable(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: AppTheme.neuXs(context, r: XlRadius.md),
        child: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                borderRadius: BorderRadius.circular(XlRadius.sm),
                border: Border.all(color: color.withOpacity(0.28), width: 1),
              ),
              child: Icon(icon, size: 15, color: color),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(label,
                  style: TextStyle(
                      fontSize: XlFont.caption,
                      fontWeight: FontWeight.w700,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide)),
            ),
            Icon(Icons.chevron_right_rounded, size: 16, color: p.decor),
          ],
        ),
      ),
    );
  }
}
