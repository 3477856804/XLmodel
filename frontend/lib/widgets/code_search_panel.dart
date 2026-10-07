import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling.pb.dart';

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
  late AnimationController _enterCtrl;

  static const _kinds = <String, String>{
    '全部': 'all',
    '定义': 'definition',
    '引用': 'reference',
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
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(child: _queryField(p)),
            const SizedBox(width: 10),
            _searchBtn(p),
          ],
        ),
        const SizedBox(height: 10),
        _kindChips(p),
      ],
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
                hintText: '搜索代码…',
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
    final isDef = m.kind == 'definition';
    return _Pressable(
      onTap: () => _copyMatch(m),
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
                ],
              ),
            ),
          ],
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
          Text('输入关键词搜索代码',
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
