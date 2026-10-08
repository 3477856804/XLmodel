import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../rpc/xiaoling.pb.dart' as pb;
import '../theme/theme.dart';

class CodeViewer extends StatefulWidget {
  final pb.FileContent? file;
  const CodeViewer({super.key, this.file});
  @override
  State<CodeViewer> createState() => _CodeViewerState();
}

class _CodeViewerState extends State<CodeViewer> {
  static const int _maxLines = 1000;
  bool _copied = false;

  @override
  void didUpdateWidget(covariant CodeViewer old) {
    super.didUpdateWidget(old);
    if (old.file?.path != widget.file?.path) {
      _copied = false;
    }
  }

  Future<void> _copyAll(String content) async {
    await Clipboard.setData(ClipboardData(text: content));
    if (!mounted) return;
    setState(() => _copied = true);
    Future.delayed(const Duration(seconds: 1), () {
      if (mounted) setState(() => _copied = false);
    });
  }

  Set<String> get _keywords {
    final lang = (widget.file?.language ?? '').toLowerCase();
    if (lang == 'python' || lang == 'py') {
      return const {'def', 'class', 'import', 'from', 'return', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'finally', 'with', 'as', 'in', 'is', 'not', 'and', 'or', 'None', 'True', 'False', 'pass', 'break', 'continue', 'lambda', 'yield', 'global', 'nonlocal'};
    }
    return const {'class', 'void', 'return', 'if', 'else', 'elif', 'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'import', 'export', 'final', 'const', 'var', 'static', 'new', 'this', 'super', 'extends', 'implements', 'abstract', 'async', 'await', 'try', 'catch', 'throw', 'true', 'false', 'null'};
  }

  String get _commentStart {
    final lang = (widget.file?.language ?? '').toLowerCase();
    if (lang == 'python' || lang == 'py') return '#';
    return '//';
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Container(
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _topBar(p),
          const SizedBox(height: 12),
          Expanded(child: _body(p)),
        ],
      ),
    );
  }

  Widget _topBar(XlPalette p) {
    final f = widget.file;
    final name = f == null ? '未选择文件' : _baseName(f.path);
    final lang = f?.language ?? '';
    final lines = f?.lines ?? 0;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
      child: Row(
        children: [
          Icon(Icons.description_rounded, size: 14, color: p.text3),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              f == null ? '在左侧选择文件查看内容' : name,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: XlFont.captionSm,
                fontWeight: FontWeight.w700,
                color: p.text1,
                letterSpacing: XlLetterSpacing.wide,
              ),
            ),
          ),
          if (lang.isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: AppTheme.pill(context, color: p.gold),
              child: Text(lang.toUpperCase(),
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w800,
                    color: p.gold,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ),
          const SizedBox(width: 8),
          Text('${lines <= _maxLines ? lines : _maxLines} 行',
              style: TextStyle(
                fontSize: XlFont.micro,
                color: p.text3,
                fontWeight: FontWeight.w600,
                fontFeatures: const [FontFeature.tabularFigures()],
              )),
          const SizedBox(width: 8),
          _Pressable(
            onTap: f == null ? null : () => _copyAll(f.content),
            scale: 0.94,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: AppTheme.ghost(context, r: XlRadius.pill),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(_copied ? Icons.check_rounded : Icons.copy_rounded,
                      size: 12, color: _copied ? p.green : p.pink),
                  const SizedBox(width: 6),
                  Text(_copied ? '已复制' : '复制',
                      style: TextStyle(
                        fontSize: XlFont.captionSm,
                        fontWeight: FontWeight.w700,
                        color: _copied ? p.green : p.pink,
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

  String _baseName(String path) {
    if (path.isEmpty) return '';
    final parts = path.split(RegExp(r'[/\\]'));
    return parts.isEmpty ? path : parts.last;
  }

  Widget _body(XlPalette p) {
    final f = widget.file;
    if (f == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.code_rounded, size: 36, color: p.decor),
            const SizedBox(height: 10),
            Text('等待选择文件',
                style: TextStyle(
                  fontSize: XlFont.caption,
                  fontWeight: FontWeight.w700,
                  color: p.text2,
                )),
          ],
        ),
      );
    }
    final allLines = f.content.split('\n');
    final truncated = allLines.length > _maxLines;
    final viewLines = truncated ? allLines.sublist(0, _maxLines) : allLines;
    return Container(
      decoration: AppTheme.screen(context, r: XlRadius.lg),
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.vertical,
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _lineNumbers(p, viewLines.length),
                    Container(width: 1, color: p.divider),
                    const SizedBox(width: 12),
                    _codeColumn(p, viewLines),
                    const SizedBox(width: 12),
                  ],
                ),
              ),
            ),
          ),
          if (truncated)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 6),
              color: p.gold.withOpacity(p.isDark ? 0.10 : 0.06),
              child: Text(
                '文件过大，仅显示前 $_maxLines 行',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: XlFont.micro,
                  fontWeight: FontWeight.w700,
                  color: p.gold,
                  letterSpacing: XlLetterSpacing.wider,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _lineNumbers(XlPalette p, int count) {
    return Container(
      padding: const EdgeInsets.only(left: 12, right: 8),
      color: p.surfaceHi,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: List.generate(count, (i) {
          return SizedBox(
            height: 19,
            child: Text(
              '${i + 1}',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: p.text3.withOpacity(0.4),
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _codeColumn(XlPalette p, List<String> lines) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (int i = 0; i < lines.length; i++)
          SizedBox(
            height: 19,
            child: RichText(
              text: TextSpan(
                children: _highlightLine(p, lines[i]),
              ),
            ),
          ),
      ],
    );
  }

  List<InlineSpan> _highlightLine(XlPalette p, String line) {
    final comment = _commentStart;
    final out = <InlineSpan>[];
    final kw = _keywords;
    final commentIdx = line.indexOf(comment);
    String codePart = line;
    String? commentPart;
    if (commentIdx >= 0) {
      codePart = line.substring(0, commentIdx);
      commentPart = line.substring(commentIdx);
    }
    final codeRe = RegExp("(\"[^\"]*\"|'[^']*'|[A-Za-z_][A-Za-z0-9_]*|\\s+|\\S)");
    for (final m in codeRe.allMatches(codePart)) {
      final tok = m.group(0)!;
      if (RegExp(r'^\s+$').hasMatch(tok)) {
        out.add(TextSpan(text: tok));
      } else if (tok.startsWith('"') || tok.startsWith("'")) {
        out.add(TextSpan(text: tok, style: TextStyle(color: p.gold)));
      } else if (kw.contains(tok)) {
        out.add(TextSpan(
          text: tok,
          style: TextStyle(color: p.pink, fontWeight: FontWeight.w700),
        ));
      } else {
        out.add(TextSpan(text: tok, style: TextStyle(color: p.text2)));
      }
    }
    if (commentPart != null) {
      out.add(TextSpan(
        text: commentPart,
        style: TextStyle(color: p.text3.withOpacity(0.5)),
      ));
    }
    return out;
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
