import 'package:flutter/material.dart';
import '../theme/theme.dart';

class McpPanel extends StatefulWidget {
  const McpPanel({super.key});
  @override
  State<McpPanel> createState() => _McpPanelState();
}

class _McpServerItem {
  String name;
  String type;
  String command;
  String url;
  List<String> args;
  bool connected;
  bool connecting;
  String error;
  int toolCount;
  List<_McpToolItem> tools;

  _McpServerItem({
    required this.name,
    required this.type,
    this.command = '',
    this.url = '',
    this.args = const [],
    this.connected = false,
    this.connecting = false,
    this.error = '',
    this.toolCount = 0,
    List<_McpToolItem>? tools,
  }) : tools = tools ?? [];
}

class _McpToolItem {
  final String name;
  final String description;
  _McpToolItem({required this.name, required this.description});
}

class _McpPanelState extends State<McpPanel> with TickerProviderStateMixin {
  final List<_McpServerItem> _servers = [];
  final Set<int> _expanded = {};
  late AnimationController _enterCtrl;

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 400), vsync: this);
    _enterCtrl.forward();
  }

  @override
  void dispose() {
    _enterCtrl.dispose();
    super.dispose();
  }

  void _showAddDialog() {
    final nameCtrl = TextEditingController();
    final commandCtrl = TextEditingController();
    final urlCtrl = TextEditingController();
    final argsCtrl = TextEditingController();
    String type = 'stdio';

    showDialog(
      context: context,
      builder: (ctx) {
        final p = XlPalette.of(context);
        return StatefulBuilder(builder: (ctx, setDialog) {
          return AlertDialog(
            backgroundColor: p.surface,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.xl)),
            title: Text('添加 MCP 服务器',
                style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
            content: SizedBox(
              width: 420,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _field(p, '名称', nameCtrl, '例如：filesystem'),
                    const SizedBox(height: 12),
                    Text('传输类型',
                        style: TextStyle(fontSize: XlFont.label, color: p.text2, fontWeight: FontWeight.w700, letterSpacing: XlLetterSpacing.wide)),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        _typeChip(p, 'stdio', type, () => setDialog(() => type = 'stdio')),
                        const SizedBox(width: 8),
                        _typeChip(p, 'http', type, () => setDialog(() => type = 'http')),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (type == 'stdio') ...[
                      _field(p, '命令', commandCtrl, '例如：npx'),
                      const SizedBox(height: 12),
                      _field(p, '参数（空格分隔）', argsCtrl, '例如：-y @modelcontextprotocol/server-filesystem /tmp'),
                    ] else ...[
                      _field(p, 'URL', urlCtrl, '例如：http://localhost:3000/mcp'),
                    ],
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: Text('取消', style: TextStyle(color: p.text3, fontWeight: FontWeight.w700)),
              ),
              _Pressable(
                onTap: () {
                  final name = nameCtrl.text.trim();
                  if (name.isEmpty) return;
                  setState(() {
                    _servers.add(_McpServerItem(
                      name: name,
                      type: type,
                      command: commandCtrl.text.trim(),
                      url: urlCtrl.text.trim(),
                      args: argsCtrl.text.trim().isEmpty
                          ? []
                          : argsCtrl.text.trim().split(RegExp(r'\s+')),
                    ));
                  });
                  Navigator.pop(ctx);
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
                  decoration: AppTheme.btn(context, r: XlRadius.pill),
                  child: Text('添加',
                      style: TextStyle(fontSize: XlFont.label, fontWeight: FontWeight.w800, color: p.btnInk, letterSpacing: XlLetterSpacing.wider)),
                ),
              ),
            ],
          );
        });
      },
    );
  }

  Widget _typeChip(XlPalette p, String label, String current, VoidCallback onTap) {
    final selected = label == current;
    return _Pressable(
      onTap: onTap,
      scale: 0.94,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: selected
            ? AppTheme.btn(context, r: XlRadius.pill)
            : AppTheme.sunkenXs(context, r: XlRadius.pill),
        child: Text(label,
            style: TextStyle(
              fontSize: XlFont.captionSm,
              fontWeight: FontWeight.w800,
              color: selected ? p.btnInk : p.text3,
              letterSpacing: XlLetterSpacing.wide,
            )),
      ),
    );
  }

  Widget _field(XlPalette p, String label, TextEditingController ctrl, String hint) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: TextStyle(fontSize: XlFont.label, color: p.text2, fontWeight: FontWeight.w700, letterSpacing: XlLetterSpacing.wide)),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          decoration: AppTheme.sunken(context, r: XlRadius.md),
          child: TextField(
            controller: ctrl,
            style: TextStyle(fontSize: XlFont.bodySm, color: p.text1),
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: TextStyle(fontSize: XlFont.bodySm, color: p.decor),
              border: InputBorder.none,
              isDense: true,
              contentPadding: const EdgeInsets.symmetric(vertical: 10),
            ),
          ),
        ),
      ],
    );
  }

  void _toggleConnect(int index) {
    final s = _servers[index];
    if (s.connecting) return;
    if (s.connected) {
      setState(() {
        s.connected = false;
        s.tools.clear();
        s.toolCount = 0;
      });
      return;
    }
    setState(() {
      s.connecting = true;
      s.error = '';
    });
    Future.delayed(const Duration(milliseconds: 1200), () {
      if (!mounted) return;
      setState(() {
        s.connecting = false;
        s.connected = true;
        s.toolCount = 3;
        s.tools = [
          _McpToolItem(name: 'read_file', description: '读取文件内容'),
          _McpToolItem(name: 'write_file', description: '写入文件内容'),
          _McpToolItem(name: 'list_dir', description: '列出目录内容'),
        ];
      });
    });
  }

  void _deleteServer(int index) {
    setState(() {
      _servers.removeAt(index);
    });
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Column(
      children: [
        _header(p),
        const SizedBox(height: 14),
        Expanded(child: _list(p)),
      ],
    );
  }

  Widget _header(XlPalette p) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(children: [
          Icon(Icons.hub_rounded, size: 20, color: p.pink),
          const SizedBox(width: 10),
          Text('MCP 服务器',
              style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.wider)),
        ]),
        _Pressable(
          onTap: _showAddDialog,
          scale: 0.94,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: AppTheme.btn(context, r: XlRadius.pill),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.add_rounded, size: 16, color: p.btnInk),
              const SizedBox(width: 4),
              Text('添加服务器',
                  style: TextStyle(fontSize: XlFont.label, fontWeight: FontWeight.w800, color: p.btnInk, letterSpacing: XlLetterSpacing.wider)),
            ]),
          ),
        ),
      ],
    );
  }

  Widget _list(XlPalette p) {
    if (_servers.isEmpty) return _emptyState(p);
    return ListView.builder(
      padding: const EdgeInsets.only(bottom: 16),
      itemCount: _servers.length,
      itemBuilder: (_, i) => _serverCard(p, _servers[i], i),
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
            child: Icon(Icons.hub_rounded, size: 32, color: p.btnInk),
          ),
          const SizedBox(height: 16),
          Text('暂无 MCP 服务器',
              style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
          const SizedBox(height: 6),
          Text('添加一个连接外部工具',
              style: TextStyle(fontSize: XlFont.caption, color: p.text3, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _serverCard(XlPalette p, _McpServerItem s, int index) {
    final expanded = _expanded.contains(index);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: AppTheme.neu(context, r: XlRadius.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: p.pink.withOpacity(p.isDark ? 0.16 : 0.10),
                  borderRadius: BorderRadius.circular(XlRadius.md),
                  border: Border.all(color: p.pink.withOpacity(0.25), width: 1),
                ),
                child: Icon(Icons.dns_rounded, size: 16, color: p.pink),
              ),
              const SizedBox(width: 12),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(s.name,
                    style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.wide)),
                const SizedBox(height: 2),
                Text('${s.type} · ${s.connected ? s.toolCount : 0} 个工具',
                    style: TextStyle(fontSize: XlFont.micro, color: p.text3, fontWeight: FontWeight.w600, letterSpacing: XlLetterSpacing.wider)),
              ])),
              _statusDot(p, s),
            ]),
            const SizedBox(height: 12),
            Row(children: [
              _connectBtn(p, s, index),
              const SizedBox(width: 8),
              _toolsBtn(p, s, index, expanded),
              const Spacer(),
              _deleteBtn(p, index),
            ]),
            AnimatedCrossFade(
              duration: XlDuration.normal,
              crossFadeState: expanded && s.connected ? CrossFadeState.showSecond : CrossFadeState.showFirst,
              firstChild: const SizedBox(width: double.infinity),
              secondChild: _toolList(p, s),
            ),
          ],
        ),
      ),
    );
  }

  Widget _statusDot(XlPalette p, _McpServerItem s) {
    Color color;
    String label;
    if (s.connecting) {
      color = p.gold;
      label = '连接中';
    } else if (s.connected) {
      color = p.green;
      label = '已连接';
    } else {
      color = p.red;
      label = '未连接';
    }
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(shape: BoxShape.circle, color: color),
      ),
      const SizedBox(width: 6),
      Text(label,
          style: TextStyle(fontSize: XlFont.micro, color: color, fontWeight: FontWeight.w800, letterSpacing: XlLetterSpacing.wider)),
    ]);
  }

  Widget _connectBtn(XlPalette p, _McpServerItem s, int index) {
    final connected = s.connected;
    return _Pressable(
      onTap: () => _toggleConnect(index),
      scale: 0.94,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: connected ? AppTheme.ghost(context, r: XlRadius.pill) : AppTheme.btn(context, r: XlRadius.pill),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(s.connecting ? Icons.hourglass_empty_rounded : (connected ? Icons.link_off_rounded : Icons.link_rounded),
              size: 13, color: connected ? p.text2 : p.btnInk),
          const SizedBox(width: 4),
          Text(s.connecting ? '连接中' : (connected ? '断开' : '连接'),
              style: TextStyle(fontSize: XlFont.micro, fontWeight: FontWeight.w800, color: connected ? p.text2 : p.btnInk, letterSpacing: XlLetterSpacing.wider)),
        ]),
      ),
    );
  }

  Widget _toolsBtn(XlPalette p, _McpServerItem s, int index, bool expanded) {
    if (!s.connected) return const SizedBox.shrink();
    return _Pressable(
      onTap: () => setState(() {
        if (expanded) {
          _expanded.remove(index);
        } else {
          _expanded.add(index);
        }
      }),
      scale: 0.94,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded, size: 13, color: p.pink),
          const SizedBox(width: 4),
          Text('工具列表',
              style: TextStyle(fontSize: XlFont.micro, fontWeight: FontWeight.w800, color: p.pink, letterSpacing: XlLetterSpacing.wider)),
        ]),
      ),
    );
  }

  Widget _deleteBtn(XlPalette p, int index) {
    return _Pressable(
      onTap: () => _deleteServer(index),
      scale: 0.94,
      child: Container(
        padding: const EdgeInsets.all(8),
        decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
        child: Icon(Icons.delete_outline_rounded, size: 14, color: p.red),
      ),
    );
  }

  Widget _toolList(XlPalette p, _McpServerItem s) {
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: AppTheme.sunken(context, r: XlRadius.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: s.tools.map((t) => Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(t.name,
                  style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w800, color: p.text1, fontFamily: 'monospace')),
              if (t.description.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(t.description,
                      style: TextStyle(fontSize: XlFont.micro, color: p.text3, fontWeight: FontWeight.w500)),
                ),
            ]),
          )).toList(),
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
      onTapCancel: () { if (mounted) setState(() => _down = false); },
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
