import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;

class CustomAgent {
  String name;
  String description;
  String systemPrompt;
  String model;
  List<String> tools;
  int maxSteps;
  double temperature;
  bool isDefault;
  CustomAgent({
    required this.name,
    required this.description,
    required this.systemPrompt,
    required this.model,
    required this.tools,
    required this.maxSteps,
    required this.temperature,
    this.isDefault = false,
  });

  Map<String, dynamic> toJson() => {
        'name': name,
        'description': description,
        'systemPrompt': systemPrompt,
        'model': model,
        'tools': tools,
        'maxSteps': maxSteps,
        'temperature': temperature,
        'isDefault': isDefault,
      };

  factory CustomAgent.fromJson(Map<String, dynamic> j) => CustomAgent(
        name: j['name'] as String? ?? '',
        description: j['description'] as String? ?? '',
        systemPrompt: j['systemPrompt'] as String? ?? '',
        model: j['model'] as String? ?? '',
        tools: (j['tools'] as List? ?? []).map((e) => e.toString()).toList(),
        maxSteps: (j['maxSteps'] as num? ?? 12).toInt(),
        temperature: (j['temperature'] as num? ?? 0.7).toDouble(),
        isDefault: j['isDefault'] as bool? ?? false,
      );
}

class AgentCreator extends StatefulWidget {
  final String dataPath;
  const AgentCreator({super.key, this.dataPath = 'data/custom_agents.json'});

  @override
  State<AgentCreator> createState() => _AgentCreatorState();
}

class _AgentCreatorState extends State<AgentCreator> {
  static const List<String> _toolOptions = [
    '文件读取',
    '文件写入',
    '终端',
    '搜索',
    '浏览器',
    'MCP工具',
    'Git',
  ];

  final TextEditingController _nameCtrl = TextEditingController();
  final TextEditingController _descCtrl = TextEditingController();
  final TextEditingController _promptCtrl = TextEditingController();
  final TextEditingController _stepsCtrl = TextEditingController(text: '12');

  List<CustomAgent> _agents = [];
  final List<String> _modelOptions = [];
  String _selectedModel = '';
  bool _modelsLoading = true;
  bool _testRunning = false;
  Set<String> _selectedTools = {'文件读取', '终端'};
  double _temperature = 0.7;
  int? _editingIndex;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
    _loadModels();
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    _promptCtrl.dispose();
    _stepsCtrl.dispose();
    super.dispose();
  }

  File get _file => File(widget.dataPath);

  Future<void> _loadModels() async {
    try {
      final res = await XlClient.stub.installedModels();
      if (!mounted) return;
      setState(() {
        _modelOptions
          ..clear()
          ..addAll(res.models.map((m) => m.name).where((n) => n.isNotEmpty));
        if (_selectedModel.isEmpty && _modelOptions.isNotEmpty) {
          _selectedModel = _modelOptions.first;
        }
        _modelsLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _modelsLoading = false);
    }
  }

  Future<void> _load() async {
    try {
      if (await _file.exists()) {
        final raw = await _file.readAsString();
        if (raw.trim().isNotEmpty) {
          final list = jsonDecode(raw) as List;
          _agents = list.map((e) => CustomAgent.fromJson(e as Map<String, dynamic>)).toList();
        }
      }
    } catch (_) {
      _agents = [];
    }
    if (!mounted) return;
    setState(() => _loading = false);
  }

  Future<void> _persist() async {
    try {
      await _file.parent.create(recursive: true);
      final encoded = jsonEncode(_agents.map((e) => e.toJson()).toList());
      await _file.writeAsString(encoded);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('保存失败: $e')));
    }
  }

  void _resetForm() {
    _nameCtrl.clear();
    _descCtrl.clear();
    _promptCtrl.clear();
    _stepsCtrl.text = '12';
    _selectedModel = _modelOptions.isNotEmpty ? _modelOptions.first : '';
    _selectedTools = {'文件读取', '终端'};
    _temperature = 0.7;
    _editingIndex = null;
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请输入 Agent 名称')));
      return;
    }
    final agent = CustomAgent(
      name: name,
      description: _descCtrl.text.trim(),
      systemPrompt: _promptCtrl.text,
      model: _selectedModel,
      tools: _selectedTools.toList(),
      maxSteps: int.tryParse(_stepsCtrl.text.trim()) ?? 12,
      temperature: _temperature,
    );
    setState(() {
      if (_editingIndex != null && _editingIndex! >= 0 && _editingIndex! < _agents.length) {
        agent.isDefault = _agents[_editingIndex!].isDefault;
        _agents[_editingIndex!] = agent;
      } else {
        if (_agents.isEmpty) agent.isDefault = true;
        _agents.add(agent);
      }
    });
    await _persist();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('已保存 Agent: $name')));
    _resetForm();
  }

  void _edit(int i) {
    final a = _agents[i];
    setState(() {
      _editingIndex = i;
      _nameCtrl.text = a.name;
      _descCtrl.text = a.description;
      _promptCtrl.text = a.systemPrompt;
      _stepsCtrl.text = '${a.maxSteps}';
      if (a.model.isNotEmpty && !_modelOptions.contains(a.model)) {
        _modelOptions.add(a.model);
      }
      _selectedModel = a.model.isEmpty
          ? (_modelOptions.isNotEmpty ? _modelOptions.first : '')
          : a.model;
      _selectedTools = Set.from(a.tools);
      _temperature = a.temperature;
    });
  }

  Future<void> _delete(int i) async {
    setState(() {
      _agents.removeAt(i);
    });
    await _persist();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已删除')));
  }

  Future<void> _setDefault(int i) async {
    setState(() {
      for (var j = 0; j < _agents.length; j++) {
        _agents[j].isDefault = j == i;
      }
    });
    await _persist();
  }

  Future<void> _testRun() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请先填写 Agent 名称')));
      return;
    }
    if (_testRunning) return;
    setState(() => _testRunning = true);
    final lines = <String>[];
    void Function(void Function())? setDialog;
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogCtx) {
        final p = XlPalette.of(dialogCtx);
        return StatefulBuilder(
          builder: (dialogCtx, setDialogFn) {
            setDialog = setDialogFn;
            return AlertDialog(
              backgroundColor: p.surface,
              title: Text('测试运行 · $name',
                  style: TextStyle(color: p.text1, fontWeight: FontWeight.w800)),
              content: SizedBox(
                width: 420,
                height: 320,
                child: lines.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(strokeWidth: 2, color: p.pink)),
                            const SizedBox(height: 12),
                            Text('正在调用 AgentStart…',
                                style: TextStyle(color: p.text3, fontSize: XlFont.captionSm)),
                          ],
                        ),
                      )
                    : SingleChildScrollView(
                        child: Text(lines.join('\n'),
                            style: TextStyle(
                                color: p.text2,
                                fontFamily: 'monospace',
                                fontSize: XlFont.captionSm,
                                height: XlLineHeight.relaxed)),
                      ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogCtx).pop(),
                  child: Text('关闭', style: TextStyle(color: p.pink)),
                ),
              ],
            );
          },
        );
      },
    );
    try {
      final stream = XlClient.stub.agentStart(pb.AgentRequest(
        task: '你好，请用一句话向我介绍你自己。',
        context: _promptCtrl.text,
        maxSteps: 5,
      ));
      await for (final ev in stream) {
        if (ev.error.isNotEmpty) {
          lines.add('[错误] ${ev.error}');
        } else if (ev.content.isNotEmpty) {
          lines.add(ev.content);
        } else if (ev.toolName.isNotEmpty) {
          lines.add('[工具] ${ev.toolName}');
        }
        setDialog?.call(() {});
      }
      if (lines.isEmpty) lines.add('未收到任何事件，后端可能未启动 Agent 运行时');
    } catch (e) {
      lines.add('[失败] $e');
    }
    setDialog?.call(() {});
    if (mounted) setState(() => _testRunning = false);
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    if (_loading) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _formCard(p),
          const SizedBox(height: 18),
          _savedCard(p),
        ],
      ),
    );
  }

  Widget _formCard(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: AppTheme.brandOrb(context, size: 36),
                child: Icon(Icons.smart_toy_outlined, size: 18, color: p.btnInk),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_editingIndex != null ? '编辑 Agent' : '创建自定义 Agent',
                        style: TextStyle(
                          fontSize: XlFont.h6,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.normal,
                        )),
                    const SizedBox(height: 2),
                    Text('定义专属助手的人格、能力与边界',
                        style: TextStyle(
                          fontSize: XlFont.label,
                          color: p.text3,
                          fontWeight: FontWeight.w500,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          _label(p, 'Agent 名称'),
          const SizedBox(height: 8),
          _sunkenField(p, controller: _nameCtrl, hint: '例如：代码审查助手'),
          const SizedBox(height: 16),
          _label(p, '描述'),
          const SizedBox(height: 8),
          _sunkenField(p, controller: _descCtrl, hint: '一句话说明这个 Agent 负责什么', maxLines: 2),
          const SizedBox(height: 16),
          _label(p, '系统提示词'),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: AppTheme.screen(context, r: XlRadius.md),
            child: TextField(
              controller: _promptCtrl,
              maxLines: 6,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: XlFont.captionSm,
                color: p.text1,
                height: XlLineHeight.normal,
              ),
              decoration: InputDecoration(
                border: InputBorder.none,
                hintText: '你是一个严谨的代码审查助手，重点关注安全性与性能…',
                hintStyle: TextStyle(
                  fontFamily: 'monospace',
                  color: p.text3,
                  fontSize: XlFont.captionSm,
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: _modelPicker(p)),
              const SizedBox(width: 16),
              Expanded(child: _stepsInput(p)),
            ],
          ),
          const SizedBox(height: 16),
          _label(p, '工具集'),
          const SizedBox(height: 8),
          _toolsPicker(p),
          const SizedBox(height: 16),
          _tempRow(p),
          const SizedBox(height: 22),
          Row(
            children: [
              Expanded(child: _primaryBtn(p)),
              const SizedBox(width: 12),
              _ghostBtn(p),
            ],
          ),
        ],
      ),
    );
  }

  Widget _label(XlPalette p, String text) {
    return Text(text,
        style: TextStyle(
          fontSize: XlFont.label,
          fontWeight: FontWeight.w800,
          color: p.text3,
          letterSpacing: XlLetterSpacing.ultra,
        ));
  }

  Widget _sunkenField(XlPalette p,
      {required TextEditingController controller, required String hint, int maxLines = 1}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      decoration: AppTheme.sunken(context, r: XlRadius.md),
      child: TextField(
        controller: controller,
        maxLines: maxLines,
        style: TextStyle(
          fontSize: XlFont.bodySm,
          color: p.text1,
          fontWeight: FontWeight.w600,
        ),
        decoration: InputDecoration(
          border: InputBorder.none,
          hintText: hint,
          hintStyle: TextStyle(color: p.text3, fontSize: XlFont.bodySm),
        ),
      ),
    );
  }

  Widget _modelPicker(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _label(p, '模型选择'),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14),
          decoration: AppTheme.sunken(context, r: XlRadius.md),
          child: _modelsLoading
              ? Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Row(children: [
                    SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: p.decor)),
                    const SizedBox(width: 10),
                    Text('加载模型中…',
                        style: TextStyle(fontSize: XlFont.bodySm, color: p.decor)),
                  ]),
                )
              : _modelOptions.isEmpty
                  ? Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Text('未连接模型，请先在模型页下载',
                          style: TextStyle(fontSize: XlFont.bodySm, color: p.decor)),
                    )
                  : DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        value: _modelOptions.contains(_selectedModel)
                            ? _selectedModel
                            : _modelOptions.first,
                        isExpanded: true,
                        dropdownColor: p.surface,
                        icon: Icon(Icons.expand_more_rounded, color: p.decor),
                        style: TextStyle(
                          fontSize: XlFont.bodySm,
                          color: p.text1,
                          fontWeight: FontWeight.w600,
                        ),
                        items: _modelOptions
                            .map((m) => DropdownMenuItem(value: m, child: Text(m)))
                            .toList(),
                        onChanged: (v) =>
                            setState(() => _selectedModel = v ?? _modelOptions.first),
                      ),
                    ),
        ),
      ],
    );
  }

  Widget _stepsInput(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _label(p, '最大步数'),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          decoration: AppTheme.sunken(context, r: XlRadius.md),
          child: TextField(
            controller: _stepsCtrl,
            keyboardType: TextInputType.number,
            style: TextStyle(
              fontSize: XlFont.bodySm,
              color: p.text1,
              fontWeight: FontWeight.w700,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
            decoration: InputDecoration(
              border: InputBorder.none,
              hintText: '12',
              hintStyle: TextStyle(color: p.text3, fontSize: XlFont.bodySm),
            ),
          ),
        ),
      ],
    );
  }

  Widget _toolsPicker(XlPalette p) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: _toolOptions.map((t) {
        final selected = _selectedTools.contains(t);
        return GestureDetector(
          onTap: () => setState(() {
            if (selected) {
              _selectedTools.remove(t);
            } else {
              _selectedTools.add(t);
            }
          }),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: selected
                ? AppTheme.accentSoft(context, r: XlRadius.pill)
                : AppTheme.ghost(context, r: XlRadius.pill),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  selected ? Icons.check_circle_rounded : Icons.circle_outlined,
                  size: 13,
                  color: selected ? p.pink : p.decor,
                ),
                const SizedBox(width: 6),
                Text(t,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                      color: selected ? p.pink : p.text2,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _tempRow(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            _label(p, '温度 (Temperature)'),
            const Spacer(),
            Text(_temperature.toStringAsFixed(2),
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  color: p.gold,
                  fontFeatures: const [FontFeature.tabularFigures()],
                )),
          ],
        ),
        SliderTheme(
          data: SliderThemeData(
            activeTrackColor: p.pink,
            inactiveTrackColor: p.surfaceLo,
            thumbColor: p.pink,
            overlayColor: p.pink.withOpacity(0.15),
            trackHeight: 3,
          ),
          child: Slider(
            value: _temperature,
            min: 0,
            max: 2,
            divisions: 20,
            onChanged: (v) => setState(() => _temperature = v),
          ),
        ),
      ],
    );
  }

  Widget _primaryBtn(XlPalette p) {
    return GestureDetector(
      onTap: _save,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: AppTheme.btnLg(context, r: XlRadius.pill),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.save_rounded, size: 16, color: p.btnInk),
            const SizedBox(width: 8),
            Text(_editingIndex != null ? '更新 Agent' : '保存 Agent',
                style: TextStyle(
                  fontSize: XlFont.caption,
                  fontWeight: FontWeight.w800,
                  color: p.btnInk,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _ghostBtn(XlPalette p) {
    return GestureDetector(
      onTap: _testRunning ? null : _testRun,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        decoration: AppTheme.ghost(context, r: XlRadius.pill),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _testRunning
                ? SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2, color: p.text1),
                  )
                : Icon(Icons.play_arrow_rounded, size: 16, color: p.text1),
            const SizedBox(width: 8),
            Text(_testRunning ? '运行中' : '测试运行',
                style: TextStyle(
                  fontSize: XlFont.caption,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _savedCard(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('已保存的 Agent',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: AppTheme.sunkenHair(context, r: XlRadius.pill),
                child: Text('${_agents.length}',
                    style: TextStyle(
                      fontSize: XlFont.label,
                      fontWeight: FontWeight.w800,
                      color: p.text2,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    )),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (_agents.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 20),
              child: Center(
                child: Column(
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: AppTheme.brandOrb(context, size: 56),
                      child: Icon(Icons.smart_toy_outlined, size: 24, color: p.btnInk),
                    ),
                    const SizedBox(height: 12),
                    Text('暂无自定义 Agent',
                        style: TextStyle(
                          fontSize: XlFont.caption,
                          color: p.text2,
                          fontWeight: FontWeight.w700,
                        )),
                  ],
                ),
              ),
            )
          else
            for (int i = 0; i < _agents.length; i++) ...[
              _agentTile(p, _agents[i], i),
              if (i != _agents.length - 1) const SizedBox(height: 10),
            ],
        ],
      ),
    );
  }

  Widget _agentTile(XlPalette p, CustomAgent a, int i) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: a.isDefault ? AppTheme.accentSoft(context, r: XlRadius.lg) : AppTheme.neuXs(context, r: XlRadius.lg),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: p.pink.withOpacity(p.isDark ? 0.14 : 0.10),
              borderRadius: BorderRadius.circular(XlRadius.md),
              border: Border.all(color: p.pink.withOpacity(0.3), width: 1),
            ),
            child: Icon(Icons.smart_toy_outlined, size: 18, color: p.pink),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(a.name,
                        style: TextStyle(
                          fontSize: XlFont.caption,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.wide,
                        )),
                    const SizedBox(width: 8),
                    if (a.isDefault)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: p.gold.withOpacity(p.isDark ? 0.18 : 0.14),
                          borderRadius: BorderRadius.circular(XlRadius.pill),
                          border: Border.all(color: p.gold.withOpacity(0.4), width: 1),
                        ),
                        child: Text('默认',
                            style: TextStyle(
                              fontSize: XlFont.micro,
                              fontWeight: FontWeight.w800,
                              color: p.gold,
                              letterSpacing: XlLetterSpacing.wider,
                            )),
                      ),
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  a.description.isEmpty ? a.model : '${a.description} · ${a.model}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w500,
                    letterSpacing: XlLetterSpacing.wider,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          _iconBtn(p, Icons.edit_outlined, () => _edit(i)),
          const SizedBox(width: 6),
          _iconBtn(p, Icons.star_outline_rounded, () => _setDefault(i), active: a.isDefault),
          const SizedBox(width: 6),
          _iconBtn(p, Icons.delete_outline_rounded, () => _delete(i), danger: true),
        ],
      ),
    );
  }

  Widget _iconBtn(XlPalette p, IconData icon, VoidCallback onTap,
      {bool danger = false, bool active = false}) {
    final color = danger ? p.red : (active ? p.gold : p.text2);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(8),
        decoration: AppTheme.neuXxs(context, r: XlRadius.sm),
        child: Icon(icon, size: 14, color: color),
      ),
    );
  }
}
