import 'dart:async';
import 'package:flutter/material.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling.pb.dart' as pb;
import '../theme/theme.dart';

class TerminalPanel extends StatefulWidget {
  const TerminalPanel({super.key});
  @override
  State<TerminalPanel> createState() => _TerminalPanelState();
}

class _TerminalPanelState extends State<TerminalPanel> {
  final ScrollController _scrollCtrl = ScrollController();
  final TextEditingController _inputCtrl = TextEditingController();
  final List<String> _lines = [];
  String? _sessionId;
  bool _connected = false;
  bool _creating = false;
  String? _error;
  StreamSubscription<pb.TerminalOutput>? _sub;
  static final RegExp _ansi = RegExp(r'\x1B\[[0-9;?]*[ -/]*[@-~]');

  @override
  void initState() {
    super.initState();
    _startSession();
  }

  @override
  void dispose() {
    _shutdown();
    _scrollCtrl.dispose();
    _inputCtrl.dispose();
    super.dispose();
  }

  Future<void> _shutdown() async {
    final id = _sessionId;
    _sessionId = null;
    await _sub?.cancel();
    _sub = null;
    if (id != null && id.isNotEmpty) {
      try {
        await XlClient.fastCall(
          (s) => s.terminalClose(pb.TerminalSessionId(id: id)),
          label: 'terminalClose',
        );
      } catch (e) { debugPrint('操作失败: $e'); }
    }
  }

  Future<void> _startSession() async {
    if (_creating) return;
    setState(() {
      _creating = true;
      _error = null;
    });
    try {
      final resp = await XlClient.fastCall(
        (s) => s.terminalCreate(pb.Empty()),
        label: 'terminalCreate',
      );
      if (!mounted) return;
      _sessionId = resp.id;
      _connected = true;
      _creating = false;
      _lines.clear();
      _lines.add('小凌终端已连接 · 会话 ${_shortId(resp.id)}');
      setState(() {});
      _subscribe();
    } catch (e) {
      if (!mounted) return;
      _creating = false;
      _connected = false;
      _error = e.toString();
      setState(() {});
    }
  }

  void _subscribe() {
    final id = _sessionId;
    if (id == null || id.isEmpty) return;
    final stream = XlClient.stub.terminalRead(pb.TerminalSessionId(id: id));
    _sub = stream.listen(
      (out) {
        if (!mounted) return;
        if (out.closed) {
          setState(() {
            _connected = false;
            _lines.add('[会话已关闭]');
          });
          _scrollToBottom();
          return;
        }
        final data = out.data.replaceAll(_ansi, '');
        if (data.isEmpty) return;
        final split = data.split('\n');
        setState(() {
          for (final l in split) {
            if (l.isNotEmpty) _lines.add(l);
          }
        });
        _scrollToBottom();
      },
      onError: (e) {
        if (!mounted) return;
        setState(() {
          _connected = false;
          _error = e.toString();
        });
      },
      onDone: () {
        if (!mounted) return;
        setState(() => _connected = false);
      },
    );
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollCtrl.hasClients) return;
      _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _send(String cmd) async {
    final id = _sessionId;
    if (id == null || id.isEmpty) return;
    if (cmd.trim().isNotEmpty) {
      setState(() => _lines.add('\$ $cmd'));
    }
    _inputCtrl.clear();
    try {
      await XlClient.fastCall(
        (s) => s.terminalWrite(pb.TerminalInput(sessionId: id, data: '$cmd\n')),
        label: 'terminalWrite',
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _lines.add('[发送失败] $e'));
    }
    _scrollToBottom();
  }

  Future<void> _restart() async {
    await _shutdown();
    if (!mounted) return;
    setState(() {
      _lines.clear();
      _sessionId = null;
      _connected = false;
    });
    await _startSession();
  }

  String _shortId(String id) {
    if (id.length <= 8) return id;
    return id.substring(0, 8);
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
          _statusBar(p),
          const SizedBox(height: 12),
          Expanded(child: _outputArea(p)),
          const SizedBox(height: 12),
          _inputArea(p),
        ],
      ),
    );
  }

  Widget _statusBar(XlPalette p) {
    final dot = _connected ? p.green : p.red;
    return Row(
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: AppTheme.glowDot(dot, size: 10),
        ),
        const SizedBox(width: 10),
        Text(
          _sessionId == null ? '未连接' : '会话 ${_shortId(_sessionId!)}',
          style: TextStyle(
            fontSize: XlFont.captionSm,
            fontWeight: FontWeight.w700,
            color: p.text2,
            letterSpacing: XlLetterSpacing.wider,
          ),
        ),
        const SizedBox(width: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: AppTheme.pill(context, color: _connected ? p.green : p.red),
          child: Text(
            _connected ? 'connected' : 'disconnected',
            style: TextStyle(
              fontSize: XlFont.micro,
              fontWeight: FontWeight.w800,
              color: _connected ? p.green : p.red,
              letterSpacing: XlLetterSpacing.wider,
            ),
          ),
        ),
        const Spacer(),
        _statusBtn(p, Icons.add_rounded, '新建', p.gold, () => _restart()),
        const SizedBox(width: 8),
        _statusBtn(p, Icons.close_rounded, '关闭', p.pink, () => _shutdownAndClear()),
      ],
    );
  }

  void _shutdownAndClear() async {
    await _shutdown();
    if (!mounted) return;
    setState(() {
      _connected = false;
      _sessionId = null;
      _lines.clear();
      _lines.add('[终端已关闭]');
    });
  }

  Widget _statusBtn(XlPalette p, IconData icon, String label, Color color, VoidCallback onTap) {
    return _Pressable(
      onTap: onTap,
      scale: 0.94,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: AppTheme.ghost(context, r: XlRadius.pill),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 12, color: color),
            const SizedBox(width: 6),
            Text(label,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w700,
                  color: color,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _outputArea(XlPalette p) {
    return Container(
      decoration: AppTheme.screen(context, r: XlRadius.lg),
      padding: const EdgeInsets.all(12),
      child: _error != null && !_connected
          ? _errorView(p)
          : ListView.builder(
              controller: _scrollCtrl,
              itemCount: _lines.length,
              itemBuilder: (_, i) => Text(
                _lines[i],
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 13,
                  height: 1.35,
                  color: _lines[i].startsWith('[') ? p.gold : p.text2,
                ),
              ),
            ),
    );
  }

  Widget _errorView(XlPalette p) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.error_outline_rounded, size: 32, color: p.red),
          const SizedBox(height: 12),
          Text('连接失败',
              style: TextStyle(
                fontSize: XlFont.caption,
                fontWeight: FontWeight.w700,
                color: p.text1,
              )),
          const SizedBox(height: 6),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Text(
              _error ?? '未知错误',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: XlFont.label,
                color: p.text3,
                height: XlLineHeight.relaxed,
              ),
            ),
          ),
          const SizedBox(height: 14),
          _Pressable(
            onTap: _restart,
            scale: 0.94,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: AppTheme.btn(context, r: XlRadius.pill),
              child: Text('重连',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: p.isDark ? p.btnInk : Colors.white,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ),
          ),
        ],
      ),
    );
  }

  Widget _inputArea(XlPalette p) {
    return Container(
      decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Row(
        children: [
          Text('\$ ',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 13,
                fontWeight: FontWeight.w800,
                color: p.gold,
              )),
          Expanded(
            child: TextField(
              controller: _inputCtrl,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 13,
                color: p.text1,
              ),
              cursorColor: p.pink,
              decoration: InputDecoration(
                isCollapsed: true,
                border: InputBorder.none,
                hintText: _connected ? '输入命令后回车' : '等待连接…',
                hintStyle: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 13,
                  color: p.text4,
                ),
              ),
              onSubmitted: _send,
              textInputAction: TextInputAction.send,
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
