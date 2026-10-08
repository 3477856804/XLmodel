import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../theme/theme.dart';

class BrowserPanel extends StatefulWidget {
  const BrowserPanel({super.key});
  @override
  State<BrowserPanel> createState() => _BrowserPanelState();
}

class _BrowserPanelState extends State<BrowserPanel> {
  final TextEditingController _urlCtrl = TextEditingController();
  final TextEditingController _selClickCtrl = TextEditingController();
  final TextEditingController _selFillCtrl = TextEditingController();
  final TextEditingController _valFillCtrl = TextEditingController();
  final TextEditingController _jsCtrl = TextEditingController();
  final ScrollController _textScroll = ScrollController();

  bool _loading = false;
  bool _reachable = false;
  bool _rendered = false;
  bool _showImage = true;
  String _currentUrl = '';
  Uint8List? _image;
  String _pageText = '';
  String _message = '';

  @override
  void initState() {
    super.initState();
    _probe();
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    _selClickCtrl.dispose();
    _selFillCtrl.dispose();
    _valFillCtrl.dispose();
    _jsCtrl.dispose();
    _textScroll.dispose();
    super.dispose();
  }

  Future<Map<String, dynamic>> _send(String op, [Map<String, dynamic> args = const {}]) async {
    final payload = args.isEmpty ? '' : jsonEncode(args);
    final sep = payload.isEmpty ? '' : ' ';
    final cmd = 'browser:$op$sep$payload';
    final resp = await XlClient.stub.command(
      cmd,
      opt: const XlCallOptions(timeout: Duration(seconds: 60)),
    );
    final out = resp.output.trim();
    try {
      final v = jsonDecode(out);
      if (v is Map<String, dynamic>) return v;
    } catch (_) {}
    return {'ok': false, 'error': out.isEmpty ? '空响应' : out};
  }

  void _applyResult(Map<String, dynamic> m) {
    _reachable = true;
    if (m['rendered'] is bool) _rendered = m['rendered'] == true;
    final url = m['url'] ?? m['current_url'];
    if (url is String && url.isNotEmpty) _currentUrl = url;
    final img = m['image_b64'];
    if (img is String && img.isNotEmpty) {
      try {
        _image = base64Decode(img);
      } catch (_) {}
    }
    if (m['text'] is String) _pageText = m['text'] as String;
    if (m['error'] is String && (m['error'] as String).isNotEmpty) {
      _message = m['error'] as String;
    } else if (m['ok'] == true) {
      final t = m['title'];
      _message = t is String && t.isNotEmpty ? t : (url is String ? url : '完成');
    }
  }

  Future<void> _probe() async {
    try {
      final m = await _send('status');
      if (!mounted) return;
      setState(() {
        _reachable = m['ok'] == true;
        if (m['rendered'] == true) _rendered = true;
        final u = m['current_url'];
        if (u is String) _currentUrl = u;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _reachable = false);
    }
  }

  Future<void> _run(Future<Map<String, dynamic>> Function() job) async {
    setState(() => _loading = true);
    try {
      final m = await job();
      if (!mounted) return;
      setState(() => _applyResult(m));
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _message = '连接失败: $e';
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _go() {
    final url = _urlCtrl.text.trim();
    if (url.isEmpty) return;
    if (!url.startsWith('http')) _urlCtrl.text = url;
    _run(() => _send('navigate', {'url': url}));
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Container(
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _urlBar(p),
          const SizedBox(height: 10),
          _statusRow(p),
          const SizedBox(height: 12),
          Expanded(child: _body(p)),
          const SizedBox(height: 12),
          _tools(p),
        ],
      ),
    );
  }

  Widget _urlBar(XlPalette p) {
    return Row(
      children: [
        _roundBtn(p, Icons.arrow_back_rounded, '后退', () => _run(() => _send('back'))),
        const SizedBox(width: 6),
        _roundBtn(p, Icons.arrow_forward_rounded, '前进', () => _run(() => _send('forward'))),
        const SizedBox(width: 6),
        _roundBtn(p, Icons.refresh_rounded, '刷新', () => _run(() => _send('reload'))),
        const SizedBox(width: 10),
        Expanded(
          child: Container(
            decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
            child: Row(
              children: [
                Icon(Icons.lock_outline_rounded, size: 14, color: p.gold),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _urlCtrl,
                    style: TextStyle(fontSize: XlFont.bodySm, color: p.text1),
                    cursorColor: p.pink,
                    onSubmitted: (_) => _go(),
                    textInputAction: TextInputAction.go,
                    decoration: InputDecoration(
                      isCollapsed: true,
                      border: InputBorder.none,
                      hintText: '输入网址，回车访问',
                      hintStyle: TextStyle(fontSize: XlFont.bodySm, color: p.text4),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 10),
        _goBtn(p),
      ],
    );
  }

  Widget _goBtn(XlPalette p) {
    return GestureDetector(
      onTap: _loading ? null : _go,
      child: Container(
        width: 44,
        height: 44,
        decoration: AppTheme.btn(context, r: XlRadius.pill),
        child: _loading
            ? SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2, color: p.btnInk),
              )
            : Icon(Icons.arrow_upward_rounded, size: 20, color: p.btnInk),
      ),
    );
  }

  Widget _roundBtn(XlPalette p, IconData icon, String tip, VoidCallback onTap) {
    return Tooltip(
      message: tip,
      child: GestureDetector(
        onTap: _loading ? null : onTap,
        child: Container(
          width: 38,
          height: 38,
          decoration: AppTheme.ghost(context, r: XlRadius.pill),
          child: Icon(icon, size: 18, color: p.text2),
        ),
      ),
    );
  }

  Widget _statusRow(XlPalette p) {
    final Color chipColor;
    final String chipLabel;
    if (!_reachable) {
      chipColor = p.red;
      chipLabel = '引擎未配置';
    } else if (_rendered) {
      chipColor = p.green;
      chipLabel = 'JS 渲染';
    } else {
      chipColor = p.gold;
      chipLabel = '静态模式';
    }
    return Row(
      children: [
        Container(width: 8, height: 8, decoration: AppTheme.glowDot(chipColor, size: 8)),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            _currentUrl.isEmpty ? '尚未访问页面' : _currentUrl,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: XlFont.captionSm, color: p.text3, fontWeight: FontWeight.w600),
          ),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
          decoration: AppTheme.pill(context, color: chipColor),
          child: Text(
            chipLabel,
            style: TextStyle(fontSize: XlFont.micro, fontWeight: FontWeight.w800, color: chipColor, letterSpacing: XlLetterSpacing.wider),
          ),
        ),
      ],
    );
  }

  Widget _body(XlPalette p) {
    if (!_reachable) return _unavailable(p);
    return Container(
      decoration: AppTheme.screen(context, r: XlRadius.lg),
      child: Column(
        children: [
          _viewToggle(p),
          Expanded(child: _showImage ? _imageView(p) : _textView(p)),
        ],
      ),
    );
  }

  Widget _viewToggle(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
      child: Row(
        children: [
          _toggleChip(p, Icons.image_outlined, '截图', _showImage, () => setState(() => _showImage = true)),
          const SizedBox(width: 8),
          _toggleChip(p, Icons.notes_rounded, '文本', !_showImage, () => setState(() => _showImage = false)),
          const Spacer(),
          _miniBtn(p, Icons.camera_alt_outlined, '截图', () => _run(() => _send('screenshot'))),
        ],
      ),
    );
  }

  Widget _toggleChip(XlPalette p, IconData icon, String label, bool active, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: active ? p.pink.withOpacity(0.14) : Colors.transparent,
          borderRadius: BorderRadius.circular(XlRadius.pill),
          border: Border.all(color: active ? p.pink.withOpacity(0.5) : p.edge, width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 13, color: active ? p.pink : p.text3),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w700, color: active ? p.pink : p.text3)),
          ],
        ),
      ),
    );
  }

  Widget _miniBtn(XlPalette p, IconData icon, String label, VoidCallback onTap) {
    return GestureDetector(
      onTap: _loading ? null : onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: AppTheme.ghost(context, r: XlRadius.pill),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 13, color: p.gold),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w700, color: p.gold)),
          ],
        ),
      ),
    );
  }

  Widget _imageView(XlPalette p) {
    if (_image == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.image_not_supported_outlined, size: 36, color: p.text4),
            const SizedBox(height: 10),
            Text(
              _rendered ? '暂无截图' : '静态模式不支持截图',
              style: TextStyle(fontSize: XlFont.caption, color: p.text3),
            ),
          ],
        ),
      );
    }
    return InteractiveViewer(
      panEnabled: true,
      scaleEnabled: true,
      child: Center(
        child: Image.memory(_image!, fit: BoxFit.contain, gaplessPlayback: true),
      ),
    );
  }

  Widget _textView(XlPalette p) {
    if (_pageText.isEmpty) {
      return Center(
        child: Text('暂无文本内容', style: TextStyle(fontSize: XlFont.caption, color: p.text4)),
      );
    }
    return SingleChildScrollView(
      controller: _textScroll,
      padding: const EdgeInsets.all(14),
      child: SelectableText(
        _pageText,
        style: TextStyle(fontSize: XlFont.bodySm, height: XlLineHeight.relaxed, color: p.text2),
      ),
    );
  }

  Widget _unavailable(XlPalette p) {
    return Container(
      decoration: AppTheme.screen(context, r: XlRadius.lg),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.public_off_rounded, size: 44, color: p.text4),
            const SizedBox(height: 14),
            Text('浏览器引擎未配置', style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: Text(
                '后端不可达或 Playwright 未安装。安装并启动后端后即可使用网页访问与 JS 渲染。',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: XlFont.captionSm, color: p.text3, height: XlLineHeight.relaxed),
              ),
            ),
            const SizedBox(height: 16),
            GestureDetector(
              onTap: _probe,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
                decoration: AppTheme.btn(context, r: XlRadius.pill),
                child: Text('重试', style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w800, color: p.btnInk, letterSpacing: XlLetterSpacing.wider)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _tools(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: AppTheme.sunkenXs(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.touch_app_rounded, size: 14, color: p.pink),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _selClickCtrl,
                  style: TextStyle(fontSize: XlFont.captionSm, color: p.text1),
                  cursorColor: p.pink,
                  decoration: InputDecoration(
                    isCollapsed: true,
                    border: InputBorder.none,
                    hintText: '点击元素 CSS 选择器，如 a.nav',
                    hintStyle: TextStyle(fontSize: XlFont.captionSm, color: p.text4),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              _toolAction(p, '点击', () => _run(() => _send('click', {'selector': _selClickCtrl.text.trim()}))),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Icon(Icons.edit_note_rounded, size: 14, color: p.gold),
              const SizedBox(width: 8),
              Expanded(
                flex: 2,
                child: TextField(
                  controller: _selFillCtrl,
                  style: TextStyle(fontSize: XlFont.captionSm, color: p.text1),
                  cursorColor: p.gold,
                  decoration: InputDecoration(
                    isCollapsed: true,
                    border: InputBorder.none,
                    hintText: '输入框选择器，如 input#q',
                    hintStyle: TextStyle(fontSize: XlFont.captionSm, color: p.text4),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _valFillCtrl,
                  style: TextStyle(fontSize: XlFont.captionSm, color: p.text1),
                  cursorColor: p.gold,
                  decoration: InputDecoration(
                    isCollapsed: true,
                    border: InputBorder.none,
                    hintText: '填入内容',
                    hintStyle: TextStyle(fontSize: XlFont.captionSm, color: p.text4),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              _toolAction(p, '填写', () => _run(() => _send('fill', {'selector': _selFillCtrl.text.trim(), 'value': _valFillCtrl.text}))),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Icon(Icons.bolt_rounded, size: 14, color: p.violet),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _jsCtrl,
                  style: TextStyle(fontSize: XlFont.captionSm, color: p.text1),
                  cursorColor: p.violet,
                  decoration: InputDecoration(
                    isCollapsed: true,
                    border: InputBorder.none,
                    hintText: '执行 JS，如 document.title',
                    hintStyle: TextStyle(fontSize: XlFont.captionSm, color: p.text4),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              _toolAction(p, '运行', () => _run(() => _send('evaluate', {'js': _jsCtrl.text}))),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Icon(Icons.info_outline_rounded, size: 12, color: p.decor),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  _message.isEmpty ? '就绪' : _message,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: XlFont.micro, color: p.text3, fontWeight: FontWeight.w500),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _toolAction(XlPalette p, String label, VoidCallback onTap) {
    return GestureDetector(
      onTap: _loading ? null : onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: AppTheme.ghost(context, r: XlRadius.pill),
        child: Text(
          label,
          style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w800, color: p.pink, letterSpacing: XlLetterSpacing.wider),
        ),
      ),
    );
  }
}
