import 'package:flutter/material.dart';
import '../theme/theme.dart';

class CodeEditor extends StatefulWidget {
  final String filePath;
  final String initialContent;
  final String language;
  final bool readOnly;
  final Function(String content)? onSave;

  const CodeEditor({
    super.key,
    required this.filePath,
    required this.initialContent,
    this.language = '',
    this.readOnly = false,
    this.onSave,
  });

  @override
  State<CodeEditor> createState() => _CodeEditorState();
}

class _CodeEditorState extends State<CodeEditor> {
  late final TextEditingController _controller;
  late bool _dirty;
  late bool _preview;
  static const double _lineHeight = 19.0;
  static const int _bigFileLines = 5000;

  static const Set<String> _keywords = {
    'def', 'class', 'import', 'from', 'return', 'if', 'else', 'for',
    'while', 'try', 'except', 'with', 'as', 'final', 'const', 'void',
    'new', 'this', 'extends',
  };

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialContent);
    _dirty = false;
    _preview = widget.readOnly;
  }

  @override
  void didUpdateWidget(covariant CodeEditor old) {
    super.didUpdateWidget(old);
    if (old.filePath != widget.filePath ||
        old.initialContent != widget.initialContent) {
      _controller.text = widget.initialContent;
      _dirty = false;
      _preview = widget.readOnly;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  int get _lineCount =>
      _controller.text.isEmpty ? 1 : _controller.text.split('\n').length;

  bool get _isBig => _lineCount > _bigFileLines;

  void _onContentChanged(String value) {
    if (!_dirty) setState(() => _dirty = true);
  }

  void _save() {
    widget.onSave?.call(_controller.text);
    if (mounted) setState(() => _dirty = false);
  }

  String get _baseName {
    if (widget.filePath.isEmpty) return '';
    final parts = widget.filePath.split(RegExp(r'[/\\]'));
    return parts.isEmpty ? widget.filePath : parts.last;
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
          _toolbar(p),
          const SizedBox(height: 12),
          Expanded(child: _body(p)),
        ],
      ),
    );
  }

  Widget _toolbar(XlPalette p) {
    final title = _dirty ? '$_baseName*' : _baseName;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
      child: Row(
        children: [
          Icon(Icons.edit_note_rounded, size: 14, color: p.gold),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              widget.filePath.isEmpty ? '未选择文件' : title,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: XlFont.captionSm,
                fontWeight: FontWeight.w700,
                color: p.gold,
                letterSpacing: XlLetterSpacing.wide,
              ),
            ),
          ),
          if (widget.language.isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: AppTheme.pill(context, color: p.pink),
              child: Text(widget.language.toUpperCase(),
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w800,
                    color: p.pink,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ),
          const SizedBox(width: 8),
          _Pressable(
            onTap: () => setState(() => _preview = !_preview),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: AppTheme.ghost(context, r: XlRadius.pill),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    _preview
                        ? Icons.edit_rounded
                        : Icons.palette_rounded,
                    size: 12,
                    color: p.text2,
                  ),
                  const SizedBox(width: 6),
                  Text(_preview ? '编辑' : '预览(高亮)',
                      style: TextStyle(
                        fontSize: XlFont.captionSm,
                        fontWeight: FontWeight.w700,
                        color: p.text2,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          if (!_preview)
            _Pressable(
              onTap: widget.onSave == null ? null : _save,
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                decoration: BoxDecoration(
                  gradient: p.btnFace,
                  borderRadius: BorderRadius.circular(XlRadius.pill),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.save_rounded, size: 12, color: p.btnInk),
                    const SizedBox(width: 6),
                    Text('保存',
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
    );
  }

  Widget _body(XlPalette p) {
    final count = _lineCount;
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
                    _lineNumbers(p, count),
                    Container(width: 1, color: p.divider),
                    const SizedBox(width: 12),
                    _preview ? _highlighted(p) : _editArea(p),
                    const SizedBox(width: 12),
                  ],
                ),
              ),
            ),
          ),
          if (_isBig)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 6),
              color: p.gold.withOpacity(p.isDark ? 0.10 : 0.06),
              child: Text(
                '文件较大，编辑可能卡顿',
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
      width: 48,
      padding: const EdgeInsets.only(left: 12, right: 8),
      decoration: AppTheme.sunkenXs(context, r: 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: List.generate(count, (i) {
          return SizedBox(
            height: _lineHeight,
            child: Text(
              '${i + 1}',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 13,
                color: p.text3.withOpacity(0.4),
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _editArea(XlPalette p) {
    return TextField(
        controller: _controller,
        maxLines: null,
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 13,
          color: p.text2,
          height: _lineHeight / 13,
        ),
        decoration: const InputDecoration(
          border: InputBorder.none,
          isCollapsed: true,
          contentPadding: EdgeInsets.zero,
        ),
        onChanged: _onContentChanged,
      );
  }

  Widget _highlighted(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final span in _highlight(_controller.text, widget.language))
          SizedBox(
            height: _lineHeight,
            child: Text.rich(span),
          ),
      ],
    );
  }

  List<TextSpan> _highlight(String code, String language) {
    final isPython =
        language.toLowerCase() == 'python' || language.toLowerCase() == 'py';
    final commentStart = isPython ? '#' : '//';
    final lines = code.split('\n');
    final out = <TextSpan>[];
    for (final line in lines) {
      out.add(_highlightLine(line, commentStart));
    }
    return out;
  }

  TextSpan _highlightLine(String line, String commentStart) {
    final children = <InlineSpan>[];
    final commentIdx = line.indexOf(commentStart);
    String codePart = line;
    String? commentPart;
    if (commentIdx >= 0) {
      codePart = line.substring(0, commentIdx);
      commentPart = line.substring(commentIdx);
    }
    final codeRe =
        RegExp("(\"[^\"]*\"|'[^']*'|[A-Za-z_][A-Za-z0-9_]*|\\s+|\\S)");
    for (final m in codeRe.allMatches(codePart)) {
      final tok = m.group(0)!;
      if (RegExp(r'^\s+$').hasMatch(tok)) {
        children.add(TextSpan(text: tok));
      } else if (tok.startsWith('"') || tok.startsWith("'")) {
        children.add(TextSpan(
            text: tok, style: const TextStyle(color: Color(0xFFE8C46A))));
      } else if (_keywords.contains(tok)) {
        children.add(TextSpan(
          text: tok,
          style: const TextStyle(
              color: Color(0xFFFF6FA5), fontWeight: FontWeight.bold),
        ));
      } else {
        children.add(TextSpan(text: tok));
      }
    }
    if (commentPart != null) {
      children.add(TextSpan(
        text: commentPart,
        style: TextStyle(color: Colors.grey.withOpacity(0.5)),
      ));
    }
    return TextSpan(children: children);
  }
}

class _Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  const _Pressable({required this.child, this.onTap, this.scale = 0.94});
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
