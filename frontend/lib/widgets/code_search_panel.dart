import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling.pb.dart';
import '../rpc/xiaoling_client_ext.dart';
import 'code_viewer.dart';

class CodeSearchPanel extends StatefulWidget {
  const CodeSearchPanel({super.key});
  @override
  State<CodeSearchPanel> createState() => _CodeSearchPanelState();
}

class _CodeSearchPanelState extends State<CodeSearchPanel> with TickerProviderStateMixin {
  final _queryCtrl = TextEditingController();
  final _scroll = ScrollController();
  List<CodeMatch> _matches = [];
  ProjectContextReply? _project;
  bool _loading = false;
  bool _searched = false;
  String? _error;
  int _total = 0;
  double _elapsedMs = 0;
  String _kind = 'all';
  String _searchMode = 'keyword';
  bool _callBusy = false;
  late AnimationController _enterCtrl;

  static const _kinds = <String, String>{
    '全部': 'all',
    '定义': 'definition',
    '引用': 'reference',
  };

  static const _symbolTypes = <String, IconData>{
    'function': Icons.functions_rounded,
    'method': Icons.memory_rounded,
    'class': Icons.category_rounded,
    'variable': Icons.circle_outlined,
    'import': Icons.input_rounded,
  };

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 500), vsync: this);
    _enterCtrl.forward();
    _loadProject();
  }

  @override
  void dispose() {
    _queryCtrl.dispose();
    _scroll.dispose();
    _enterCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadProject() async {
    try {
      final r = await XlClient.stub.projectContext(Empty());
      if (mounted) setState(() => _project = r);
    } catch (e) { debugPrint('操作失败: $e'); }
  }

  String get _kindParam {
    if (_searchMode == 'symbol') return 'symbol';
    switch (_kind) {
      case 'definition':
        return 'definition';
      case 'reference':
        return 'reference';
      default:
        return '';
    }
  }

  Future<void> _search() async {
    final q = _queryCtrl.text.trim();
    if (q.isEmpty || _loading) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _loading = true;
      _searched = true;
      _error = null;
    });
    try {
      final r = await XlClient.stub.codeSearch(CodeSearchRequest(
        query: q,
        type: _kindParam,
        maxResults: 50,
      ));
      if (!mounted) return;
      setState(() {
        _matches = List<CodeMatch>.from(r.matches);
        _total = r.total;
        _elapsedMs = r.elapsedMs;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _matches = [];
        _loading = false;
      });
    }
  }

  void _copyMatch(CodeMatch m) {
    Clipboard.setData(ClipboardData(text: m.text));
    ScaffoldMessenger.of(context).clearSnackBars();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      behavior: SnackBarBehavior.floating,
      backgroundColor: XlPalette.of(context).surface,
      elevation: 0,
      duration: const Duration(milliseconds: 1100),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.md)),
      content: Text('已复制',
          style: TextStyle(
            color: XlPalette.of(context).text1,
            fontSize: XlFont.captionSm,
            fontWeight: FontWeight.w700,
          )),
    ));
  }

  Future<void> _openFile(CodeMatch m) async {
    try {
      final content = await XlClient.stub.fileRead(FileReadRequest(path: m.file));
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (ctx) => Dialog(
          backgroundColor: Colors.transparent,
          insetPadding: const EdgeInsets.all(24),
          child: Container(
            constraints: const BoxConstraints(maxWidth: 900, maxHeight: 700),
            decoration: BoxDecoration(
              color: XlPalette.of(ctx).bg,
              borderRadius: BorderRadius.circular(XlRadius.xl),
            ),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    border: Border(bottom: BorderSide(color: XlPalette.of(ctx).divider, width: 1)),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.description_rounded, size: 16, color: XlPalette.of(ctx).pink),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text('${m.file}:${m.line}',
                            style: TextStyle(
                              fontSize: XlFont.caption,
                              fontWeight: FontWeight.w800,
                              color: XlPalette.of(ctx).text1,
                            )),
                      ),
                      IconButton(
                        icon: Icon(Icons.close_rounded, size: 18, color: XlPalette.of(ctx).text3),
                        onPressed: () => Navigator.of(ctx).pop(),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: CodeViewer(file: content),
                ),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('打开文件失败: $e')));
    }
  }

  Future<Map<String, dynamic>> _call(String cmd) async {
    final reply = await XlClient.stub.command(cmd);
    final decoded = jsonDecode(reply.output) as Map<String, dynamic>;
    if (decoded['ok'] != true) {
      throw Exception(decoded['error']?.toString() ?? '请求失败');
    }
    return decoded;
  }

  String _symbolNameOf(CodeMatch m) {
    final text = m.text.trim();
    final re = RegExp(r'([A-Za-z_][A-Za-z0-9_]*)');
    final first = re.firstMatch(text)?.group(1);
    if (first != null && first != 'def' && first != 'class' && first != 'function') {
      return first;
    }
    return _queryCtrl.text.trim();
  }

  Future<void> _openPath(String path, {int line = 1}) async {
    try {
      final content = await XlClient.stub.fileRead(FileReadRequest(path: path));
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (ctx) => Dialog(
          backgroundColor: Colors.transparent,
          insetPadding: const EdgeInsets.all(24),
          child: Container(
            constraints: const BoxConstraints(maxWidth: 900, maxHeight: 700),
            decoration: BoxDecoration(
              color: XlPalette.of(ctx).bg,
              borderRadius: BorderRadius.circular(XlRadius.xl),
            ),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    border: Border(bottom: BorderSide(color: XlPalette.of(ctx).divider, width: 1)),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.location_on_rounded, size: 16, color: XlPalette.of(ctx).pink),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text('$path:$line',
                            style: TextStyle(
                              fontSize: XlFont.caption,
                              fontWeight: FontWeight.w800,
                              color: XlPalette.of(ctx).text1,
                            )),
                      ),
                      IconButton(
                        icon: Icon(Icons.close_rounded, size: 18, color: XlPalette.of(ctx).text3),
                        onPressed: () => Navigator.of(ctx).pop(),
                      ),
                    ],
                  ),
                ),
                Expanded(child: CodeViewer(file: content, focusLine: line)),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('打开文件失败: $e')));
    }
  }

  Future<void> _openCallInfo(CodeMatch m) async {
    final name = _symbolNameOf(m);
    if (name.isEmpty || _callBusy) return;
    FocusScope.of(context).unfocus();
    setState(() => _callBusy = true);
    Map<String, dynamic>? callers;
    Map<String, dynamic>? callees;
    Map<String, dynamic>? chain;
    String? fail;
    try {
      final results = await Future.wait([
        _call('code:callers $name'),
        _call('code:callees $name'),
        _call('code:chain $name --depth 2'),
      ]);
      callers = results[0];
      callees = results[1];
      chain = results[2];
    } catch (e) {
      fail = e.toString();
    }
    if (!mounted) return;
    setState(() => _callBusy = false);
    if (fail != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        content: const Text('代码索引未构建'),
      ));
      return;
    }
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        maxChildSize: 0.9,
        minChildSize: 0.35,
        expand: false,
        builder: (ctx, scroll) => Container(
          decoration: BoxDecoration(
            color: XlPalette.of(ctx).bg,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          ),
          padding: const EdgeInsets.all(16),
          child: ListView(
            controller: scroll,
            children: [
              Row(
                children: [
                  Icon(Icons.account_tree_rounded, size: 18, color: XlPalette.of(ctx).pink),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text('调用关系 · $name',
                        style: TextStyle(
                          fontSize: XlFont.bodySm,
                          fontWeight: FontWeight.w800,
                          color: XlPalette.of(ctx).text1,
                        )),
                  ),
                  IconButton(
                    icon: Icon(Icons.close_rounded, size: 18, color: XlPalette.of(ctx).text3),
                    onPressed: () => Navigator.of(ctx).pop(),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              _callersSection(ctx, callers?['callers'] as List?),
              const SizedBox(height: 12),
              _calleesSection(ctx, callees?['callees'] as List?),
              const SizedBox(height: 12),
              _chainSection(ctx, chain?['chain'] as Map?),
            ],
          ),
        ),
      ),
    );
  }

  Widget _callersSection(BuildContext context, List? data) {
    final p = XlPalette.of(context);
    final list = (data ?? []);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('调用者 · ${list.length}',
            style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.gold)),
        const SizedBox(height: 6),
        if (list.isEmpty)
          Text('无', style: TextStyle(fontSize: XlFont.captionSm, color: p.text3))
        else
          ...list.map((e) {
            final m = (e as Map).cast<String, dynamic>();
            return _callerRow(context, m['caller']?.toString() ?? '',
                m['file']?.toString() ?? '', (m['line'] as num?)?.toInt() ?? 1);
          }),
      ],
    );
  }

  Widget _callerRow(BuildContext context, String caller, String file, int line) {
    final p = XlPalette.of(context);
    return _Pressable(
      onTap: () => _openPath(file, line: line),
      scale: 0.98,
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        padding: const EdgeInsets.all(10),
        decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
        child: Row(
          children: [
            Icon(Icons.arrow_upward_rounded, size: 13, color: p.pink),
            const SizedBox(width: 8),
            Expanded(
              child: Text(caller,
                  style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w700, color: p.text1)),
            ),
            Text('$file:$line',
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: XlFont.micro, color: p.text3)),
          ],
        ),
      ),
    );
  }

  Widget _calleesSection(BuildContext context, List? data) {
    final p = XlPalette.of(context);
    final list = (data ?? []);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('被调用 · ${list.length}',
            style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.gold)),
        const SizedBox(height: 6),
        if (list.isEmpty)
          Text('无', style: TextStyle(fontSize: XlFont.captionSm, color: p.text3))
        else
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: list.map((e) {
              final m = (e as Map).cast<String, dynamic>();
              final c = m['callee']?.toString() ?? '';
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: AppTheme.pill(context, color: p.pink, r: XlRadius.pill),
                child: Text(c,
                    style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w700, color: p.btnInk)),
              );
            }).toList(),
          ),
      ],
    );
  }

  Widget _chainSection(BuildContext context, Map? root) {
    final p = XlPalette.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('调用链',
            style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.gold)),
        const SizedBox(height: 6),
        if (root == null)
          Text('无', style: TextStyle(fontSize: XlFont.captionSm, color: p.text3))
        else
          _chainNode(context, root, 0),
      ],
    );
  }

  Widget _chainNode(BuildContext context, Map node, int depth) {
    final p = XlPalette.of(context);
    final name = node['name']?.toString() ?? '';
    final file = node['file']?.toString();
    final line = (node['line'] as num?)?.toInt() ?? 1;
    final children = (node['children'] as List?) ?? [];
    return Padding(
      padding: EdgeInsets.only(left: 14.0 * depth, bottom: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Pressable(
            onTap: (file != null && file.isNotEmpty)
                ? () => _openPath(file, line: line)
                : null,
            scale: 0.98,
            child: Row(
              children: [
                Icon(Icons.chevron_right_rounded, size: 12, color: p.gold),
                const SizedBox(width: 6),
                Text(name,
                    style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w700, color: p.text1)),
                if (file != null && file.isNotEmpty) ...[
                  const SizedBox(width: 6),
                  Text('$file:$line',
                      style: TextStyle(fontSize: XlFont.micro, color: p.text3)),
                ],
              ],
            ),
          ),
          ...children.map((c) => _chainNode(context, (c as Map).cast<String, dynamic>(), depth + 1)),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Column(
      children: [
        _projectBar(p),
        const SizedBox(height: 10),
        _searchBar(p),
        const SizedBox(height: 10),
        Expanded(child: _resultsArea(p)),
      ],
    );
  }

  Widget _projectBar(XlPalette p) {
    final proj = _project;
    final name = proj?.projectName.isEmpty ?? true ? '未知项目' : proj!.projectName;
    final files = proj == null ? '—' : '${proj.totalFiles} 文件';
    final lines = proj == null ? '—' : '${proj.totalLines} 行';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: AppTheme.neuXxs(context, r: XlRadius.md),
      child: Row(
        children: [
          Icon(Icons.folder_rounded, size: 15, color: p.gold),
          const SizedBox(width: 8),
          Expanded(
            child: Text(name,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text1,
                  fontWeight: FontWeight.w800,
                )),
          ),
          const SizedBox(width: 10),
          Text('$files · $lines',
              style: TextStyle(
                fontSize: XlFont.micro,
                color: p.gold,
                fontWeight: FontWeight.w700,
                letterSpacing: XlLetterSpacing.wider,
                fontFeatures: const [FontFeature.tabularFigures()],
              )),
        ],
      ),
    );
  }

  Widget _searchBar(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _modeTabs(p),
        const SizedBox(height: 10),
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(child: _queryField(p)),
            const SizedBox(width: 10),
            _searchBtn(p),
          ],
        ),
        const SizedBox(height: 10),
        if (_searchMode == 'keyword') _kindChips(p),
      ],
    );
  }

  Widget _modeTabs(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(3),
      decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
      child: Row(
        children: [
          Expanded(child: _modeTab(p, '关键词', 'keyword', Icons.text_fields_rounded)),
          Expanded(child: _modeTab(p, '符号', 'symbol', Icons.bubble_chart_rounded)),
        ],
      ),
    );
  }

  Widget _modeTab(XlPalette p, String label, String mode, IconData icon) {
    final selected = _searchMode == mode;
    return _Pressable(
      onTap: () {
        if (_searchMode != mode) {
          setState(() {
            _searchMode = mode;
            _searched = false;
            _matches = [];
          });
        }
      },
      scale: 0.95,
      child: AnimatedContainer(
        duration: XlDuration.fast,
        curve: XlCurve.standard,
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: selected
            ? AppTheme.brand(context, r: XlRadius.pill)
            : const BoxDecoration(),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 14, color: selected ? p.btnInk : p.text3),
            const SizedBox(width: 6),
            Text(label,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  color: selected ? p.btnInk : p.text3,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          ],
        ),
      ),
    );
  }

  Widget _queryField(XlPalette p) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
      decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
      child: Row(
        children: [
          Icon(Icons.search_rounded, size: 16, color: p.decor),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              controller: _queryCtrl,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _search(),
              style: TextStyle(fontSize: XlFont.bodySm, color: p.text1),
              decoration: InputDecoration(
                hintText: _searchMode == 'symbol' ? '输入符号名（函数/类/变量）…' : '搜索代码…',
                hintStyle: TextStyle(fontSize: XlFont.bodySm, color: p.decor),
                border: InputBorder.none,
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(vertical: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _searchBtn(XlPalette p) {
    return _Pressable(
      onTap: _loading ? null : _search,
      scale: 0.92,
      child: Container(
        width: 46,
        height: 46,
        decoration: _loading
            ? AppTheme.sunkenXs(context, r: XlRadius.pill)
            : AppTheme.btn(context, r: XlRadius.pill),
        child: _loading
            ? Padding(
                padding: const EdgeInsets.all(13),
                child: CircularProgressIndicator(strokeWidth: 2, color: p.pink.withOpacity(0.75)),
              )
            : Icon(Icons.search_rounded, size: 20, color: p.btnInk),
      ),
    );
  }

  Widget _kindChips(XlPalette p) {
    return Row(
      children: _kinds.entries.map((e) {
        final selected = _kind == e.value;
        return Padding(
          padding: const EdgeInsets.only(right: 8),
          child: _Pressable(
            onTap: () => setState(() => _kind = e.value),
            scale: 0.93,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              decoration: selected
                  ? AppTheme.brand(context, r: XlRadius.pill)
                  : AppTheme.neuXs(context, r: XlRadius.pill),
              child: Text(e.key,
                  style: TextStyle(
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w800,
                    color: selected ? p.btnInk : p.text2,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _resultsArea(XlPalette p) {
    if (_loading) {
      return Center(child: CircularProgressIndicator(color: p.pink));
    }
    if (_error != null) {
      return _errorBox(p);
    }
    if (!_searched) {
      return _hintBox(p);
    }
    if (_matches.isEmpty) {
      return _emptyBox(p);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
          child: Text('找到 $_total 个匹配，耗时 ${_elapsedMs.toStringAsFixed(0)}ms',
              style: TextStyle(
                fontSize: XlFont.micro,
                color: p.gold,
                fontWeight: FontWeight.w700,
                letterSpacing: XlLetterSpacing.wider,
                fontFeatures: const [FontFeature.tabularFigures()],
              )),
        ),
        Expanded(
          child: Container(
            decoration: AppTheme.screenSoft(context, r: XlRadius.xl),
            child: ListView.separated(
              controller: _scroll,
              padding: const EdgeInsets.all(10),
              itemCount: _matches.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (_, i) => _matchTile(p, _matches[i]),
            ),
          ),
        ),
      ],
    );
  }

  Widget _matchTile(XlPalette p, CodeMatch m) {
    final isSymbolMode = _searchMode == 'symbol';
    final symbolIcon = _symbolTypes[m.kind] ?? Icons.code_rounded;
    final isDef = m.kind == 'definition' || (isSymbolMode && m.kind.isNotEmpty);
    return _Pressable(
      onTap: () => isSymbolMode ? _openFile(m) : _copyMatch(m),
      scale: 0.98,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (isDef)
              Container(
                width: 3,
                margin: const EdgeInsets.only(right: 10, top: 2, bottom: 2),
                decoration: BoxDecoration(
                  gradient: p.gradGold,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      if (isSymbolMode) ...[
                        Icon(symbolIcon, size: 13, color: p.gold),
                        const SizedBox(width: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: AppTheme.pill(context, color: p.gold, r: XlRadius.pill),
                          child: Text(m.kind,
                              style: TextStyle(
                                fontSize: XlFont.micro,
                                color: p.gold,
                                fontWeight: FontWeight.w800,
                                letterSpacing: XlLetterSpacing.wider,
                              )),
                        ),
                        const SizedBox(width: 8),
                      ],
                      Expanded(
                        child: Text(m.file,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: XlFont.micro,
                              color: p.pink,
                              fontWeight: FontWeight.w700,
                              letterSpacing: XlLetterSpacing.wide,
                            )),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: AppTheme.pill(context, color: p.gold, r: XlRadius.pill),
                        child: Text('L${m.line}',
                            style: TextStyle(
                              fontSize: XlFont.micro,
                              color: p.gold,
                              fontWeight: FontWeight.w800,
                              fontFeatures: const [FontFeature.tabularFigures()],
                            )),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  _highlightedText(p, m.text, _queryCtrl.text.trim()),
                  if (isSymbolMode && isDef) ...[
                    const SizedBox(height: 8),
                    _callersBtn(p, m),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _callersBtn(XlPalette p, CodeMatch m) {
    return Align(
      alignment: Alignment.centerLeft,
      child: _Pressable(
        onTap: _callBusy ? null : () => _openCallInfo(m),
        scale: 0.94,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
          decoration: AppTheme.ghost(context, r: XlRadius.pill),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.account_tree_rounded, size: 12, color: p.pink),
              const SizedBox(width: 6),
              Text('查看调用者',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: p.pink,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
        ),
      ),
    );
  }

  Widget _highlightedText(XlPalette p, String text, String query) {
    final base = TextStyle(
      fontSize: XlFont.captionSm,
      height: XlLineHeight.normal,
      color: p.text2,
      fontFamily: 'monospace',
    );
    if (query.isEmpty) {
      return Text(text, style: base);
    }
    final spans = <InlineSpan>[];
    final lower = text.toLowerCase();
    final q = query.toLowerCase();
    var idx = 0;
    while (idx < text.length) {
      final hit = lower.indexOf(q, idx);
      if (hit < 0) {
        spans.add(TextSpan(text: text.substring(idx), style: base));
        break;
      }
      if (hit > idx) {
        spans.add(TextSpan(text: text.substring(idx, hit), style: base));
      }
      spans.add(WidgetSpan(
        alignment: PlaceholderAlignment.middle,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 1),
          decoration: BoxDecoration(
            color: p.pink.withOpacity(0.30),
            borderRadius: BorderRadius.circular(3),
          ),
          child: Text(text.substring(hit, hit + q.length),
              style: base.copyWith(color: p.pink, fontWeight: FontWeight.w800)),
        ),
      ));
      idx = hit + q.length;
    }
    return Text.rich(TextSpan(children: spans));
  }

  Widget _hintBox(XlPalette p) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.manage_search_rounded, size: 44, color: p.decor),
          const SizedBox(height: 12),
          Text(_searchMode == 'symbol' ? '输入符号名查找定义与引用' : '输入关键词搜索代码',
              style: TextStyle(
                fontSize: XlFont.bodySm,
                color: p.text3,
                fontWeight: FontWeight.w600,
              )),
        ],
      ),
    );
  }

  Widget _emptyBox(XlPalette p) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.search_off_rounded, size: 44, color: p.decor),
          const SizedBox(height: 12),
          Text('未找到匹配结果',
              style: TextStyle(
                fontSize: XlFont.bodySm,
                color: p.text3,
                fontWeight: FontWeight.w600,
              )),
        ],
      ),
    );
  }

  Widget _errorBox(XlPalette p) {
    return Center(
      child: Container(
        margin: const EdgeInsets.all(24),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: p.red.withOpacity(p.isDark ? 0.10 : 0.06),
          borderRadius: BorderRadius.circular(XlRadius.lg),
          border: Border.all(color: p.red.withOpacity(0.5), width: 1.2),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded, size: 28, color: p.red),
            const SizedBox(height: 10),
            Text('搜索失败',
                style: TextStyle(
                  fontSize: XlFont.bodySm,
                  color: p.red,
                  fontWeight: FontWeight.w800,
                )),
            const SizedBox(height: 12),
            _Pressable(
              onTap: _search,
              scale: 0.94,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
                decoration: AppTheme.btn(context, r: XlRadius.pill),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.refresh_rounded, size: 14, color: p.btnInk),
                    const SizedBox(width: 6),
                    Text('重试',
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
