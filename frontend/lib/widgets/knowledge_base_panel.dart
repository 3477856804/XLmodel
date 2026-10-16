import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';

class KnowledgeBasePanel extends StatefulWidget {
  const KnowledgeBasePanel({super.key});
  @override
  State<KnowledgeBasePanel> createState() => _KnowledgeBasePanelState();
}

class _KbSource {
  final String file;
  final String path;
  final int chunk;
  final int offset;
  _KbSource({required this.file, required this.path, required this.chunk, required this.offset});
  factory _KbSource.fromMap(Map<String, dynamic> m) => _KbSource(
        file: m['file']?.toString() ?? '',
        path: m['path']?.toString() ?? '',
        chunk: (m['chunk'] as num?)?.toInt() ?? 0,
        offset: (m['offset'] as num?)?.toInt() ?? 0,
      );
}

class _KbResult {
  final String chunkId;
  final double score;
  final String text;
  final String matchedBy;
  final _KbSource source;
  _KbResult({
    required this.chunkId,
    required this.score,
    required this.text,
    required this.matchedBy,
    required this.source,
  });
  factory _KbResult.fromMap(Map<String, dynamic> m) => _KbResult(
        chunkId: m['chunk_id']?.toString() ?? '',
        score: (m['score'] as num?)?.toDouble() ?? 0,
        text: m['text']?.toString() ?? '',
        matchedBy: m['matched_by']?.toString() ?? 'keyword',
        source: _KbSource.fromMap((m['source'] as Map?)?.cast<String, dynamic>() ?? {}),
      );
}

class _KbDoc {
  final String name;
  final String path;
  final int chunks;
  final int chars;
  _KbDoc({required this.name, required this.path, required this.chunks, required this.chars});
  factory _KbDoc.fromMap(Map<String, dynamic> m) => _KbDoc(
        name: m['name']?.toString() ?? '',
        path: m['path']?.toString() ?? '',
        chunks: (m['chunks'] as num?)?.toInt() ?? 0,
        chars: (m['chars'] as num?)?.toInt() ?? 0,
      );
}

class _KnowledgeBasePanelState extends State<KnowledgeBasePanel> with TickerProviderStateMixin {
  final _queryCtrl = TextEditingController();
  final _scroll = ScrollController();
  final List<_KbResult> _results = [];
  final List<_KbDoc> _docs = [];
  bool _loading = false;
  bool _searched = false;
  bool _docsLoading = false;
  String? _error;
  String _semantic = '';
  int _docCount = 0;
  int _chunkCount = 0;
  String? _expandedId;
  String? _expandedText;
  String? _expandedError;
  late AnimationController _enterCtrl;

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 500), vsync: this);
    _enterCtrl.forward();
    _loadDocs();
  }

  @override
  void dispose() {
    _queryCtrl.dispose();
    _scroll.dispose();
    _enterCtrl.dispose();
    super.dispose();
  }

  Future<Map<String, dynamic>> _call(String cmd) async {
    final reply = await XlClient.stub.command(cmd);
    final decoded = jsonDecode(reply.output) as Map<String, dynamic>;
    if (decoded['ok'] != true) {
      throw Exception(decoded['error']?.toString() ?? '请求失败');
    }
    return decoded;
  }

  Future<void> _loadDocs() async {
    setState(() => _docsLoading = true);
    try {
      final d = await _call('kb: list');
      if (!mounted) return;
      final stats = (d['stats'] as Map?)?.cast<String, dynamic>() ?? {};
      setState(() {
        _docs
          ..clear()
          ..addAll(((d['documents'] as List?) ?? [])
              .map((e) => _KbDoc.fromMap((e as Map).cast<String, dynamic>())));
        _docCount = (stats['total_docs'] as num?)?.toInt() ?? _docs.length;
        _chunkCount = (stats['total_chunks'] as num?)?.toInt() ?? 0;
        _semantic = stats['semantic'] == true ? '语义' : '关键词';
        _docsLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _docsLoading = false);
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
      _expandedId = null;
      _expandedText = null;
    });
    try {
      final d = await _call('kb: search $q');
      if (!mounted) return;
      setState(() {
        _results
          ..clear()
          ..addAll(((d['results'] as List?) ?? [])
              .map((e) => _KbResult.fromMap((e as Map).cast<String, dynamic>())));
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _results.clear();
        _loading = false;
      });
    }
  }

  Future<void> _toggleExpand(_KbResult r) async {
    if (_expandedId == r.chunkId) {
      setState(() {
        _expandedId = null;
        _expandedText = null;
      });
      return;
    }
    setState(() {
      _expandedId = r.chunkId;
      _expandedText = null;
      _expandedError = null;
    });
    try {
      final d = await _call('kb: source ${r.chunkId}');
      if (!mounted) return;
      final src = (d['source'] as Map?)?.cast<String, dynamic>() ?? {};
      setState(() {
        _expandedText = src['text']?.toString() ?? r.text;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _expandedError = e.toString());
    }
  }

  Future<void> _deleteDoc(_KbDoc doc) async {
    try {
      await _call('kb: delete ${doc.name}');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(milliseconds: 1100),
        content: Text('已删除 ${doc.name}'),
      ));
      await _loadDocs();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('删除失败: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Column(
      children: [
        _header(p),
        const SizedBox(height: 10),
        _searchBar(p),
        const SizedBox(height: 10),
        Expanded(child: _body(p)),
      ],
    );
  }

  Widget _header(XlPalette p) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: AppTheme.neuXxs(context, r: XlRadius.md),
      child: Row(
        children: [
          Icon(Icons.library_books_rounded, size: 15, color: p.gold),
          const SizedBox(width: 8),
          Text('知识库检索',
              style: TextStyle(
                fontSize: XlFont.captionSm,
                color: p.text1,
                fontWeight: FontWeight.w800,
              )),
          const Spacer(),
          Text('$_docCount 文档 · $_chunkCount 块 · $_semantic',
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
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(child: _queryField(p)),
        const SizedBox(width: 10),
        _searchBtn(p),
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
                hintText: '输入问题，检索已索引文档…',
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
                child: CircularProgressIndicator(strokeWidth: 2, color: p.pink.withValues(alpha: 0.75)),
              )
            : Icon(Icons.search_rounded, size: 20, color: p.btnInk),
      ),
    );
  }

  Widget _body(XlPalette p) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Expanded(flex: 3, child: _resultsArea(p)),
        const SizedBox(width: 10),
        SizedBox(width: 220, child: _docsPanel(p)),
      ],
    );
  }

  Widget _resultsArea(XlPalette p) {
    if (_loading) {
      return Center(child: CircularProgressIndicator(color: p.pink));
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded, size: 30, color: p.red),
            const SizedBox(height: 10),
            Text('检索失败',
                style: TextStyle(fontSize: XlFont.bodySm, color: p.red, fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text(_error!,
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
          ],
        ),
      );
    }
    if (!_searched) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.manage_search_rounded, size: 44, color: p.decor),
            const SizedBox(height: 12),
            Text('输入关键词，从索引文档中检索答案',
                style: TextStyle(fontSize: XlFont.bodySm, color: p.text3, fontWeight: FontWeight.w600)),
          ],
        ),
      );
    }
    if (_results.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.search_off_rounded, size: 44, color: p.decor),
            const SizedBox(height: 12),
            Text('未找到相关片段',
                style: TextStyle(fontSize: XlFont.bodySm, color: p.text3, fontWeight: FontWeight.w600)),
          ],
        ),
      );
    }
    return Container(
      decoration: AppTheme.screenSoft(context, r: XlRadius.xl),
      child: ListView.separated(
        controller: _scroll,
        padding: const EdgeInsets.all(10),
        itemCount: _results.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (_, i) => _resultTile(p, _results[i]),
      ),
    );
  }

  Widget _resultTile(XlPalette p, _KbResult r) {
    final expanded = _expandedId == r.chunkId;
    return _Pressable(
      onTap: () => _toggleExpand(r),
      scale: 0.98,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.description_rounded, size: 13, color: p.pink),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(r.source.file,
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
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: AppTheme.pill(context, color: p.gold, r: XlRadius.pill),
                  child: Text('块${r.source.chunk + 1}',
                      style: TextStyle(
                        fontSize: XlFont.micro,
                        color: p.gold,
                        fontWeight: FontWeight.w800,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                ),
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: AppTheme.pill(context, color: p.pink, r: XlRadius.pill),
                  child: Text(r.score.toStringAsFixed(3),
                      style: TextStyle(
                        fontSize: XlFont.micro,
                        color: p.pink,
                        fontWeight: FontWeight.w800,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      )),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(r.text,
                maxLines: expanded ? null : 4,
                overflow: expanded ? TextOverflow.visible : TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  height: XlLineHeight.normal,
                  color: p.text2,
                )),
            if (expanded) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: p.goldSoft,
                  borderRadius: BorderRadius.circular(XlRadius.sm),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.my_location_rounded, size: 12, color: p.gold),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text('${r.source.path} · 偏移 ${r.source.offset}',
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: XlFont.micro,
                                color: p.gold,
                                fontWeight: FontWeight.w700,
                                fontFeatures: const [FontFeature.tabularFigures()],
                              )),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    SelectableText(
                      _expandedError ?? _expandedText ?? '加载原文中…',
                      style: TextStyle(
                        fontSize: XlFont.captionSm,
                        height: XlLineHeight.normal,
                        color: p.text1,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _docsPanel(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: AppTheme.screenSoft(context, r: XlRadius.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.folder_special_rounded, size: 14, color: p.gold),
              const SizedBox(width: 6),
              Text('已索引文档',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    color: p.text1,
                    fontWeight: FontWeight.w800,
                  )),
              const Spacer(),
              if (_docsLoading)
                SizedBox(
                  width: 12,
                  height: 12,
                  child: CircularProgressIndicator(strokeWidth: 2, color: p.pink),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(
            child: _docs.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text('暂无索引文档，添加文档后开始检索',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: XlFont.captionSm,
                            height: XlLineHeight.normal,
                            color: p.decor,
                            fontWeight: FontWeight.w600,
                          )),
                    ),
                  )
                : ListView.separated(
                    itemCount: _docs.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 6),
                    itemBuilder: (_, i) => _docTile(p, _docs[i]),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _docTile(XlPalette p, _KbDoc doc) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(doc.name,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.text1,
                      fontWeight: FontWeight.w700,
                    )),
                const SizedBox(height: 2),
                Text('${doc.chunks} 块 · ${doc.chars} 字',
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.gold,
                      fontWeight: FontWeight.w700,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    )),
              ],
            ),
          ),
          _Pressable(
            onTap: () => _deleteDoc(doc),
            scale: 0.9,
            child: Icon(Icons.delete_outline_rounded, size: 16, color: p.red),
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
