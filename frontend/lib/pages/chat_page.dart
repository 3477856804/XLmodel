import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import 'agent_page.dart';

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});
  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> with TickerProviderStateMixin {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _inputFocus = FocusNode();
  final _player = AudioPlayer();
  final List<_Msg> _msgs = [];
  final Set<String> _speaking = {};
  bool _busy = false;
  bool _ttsOn = true;
  bool _autoScroll = true;
  bool _showScrollDown = false;
  bool _connected = false;
  bool _playing = false;
  bool _inputFocused = false;
  int _charCount = 0;
  String _stage = '';
  String _version = '';
  String? _playingId;
  Duration _playPos = Duration.zero;
  Duration _playDur = Duration.zero;
  int _msgSeq = 0;
  int _chatCount = 0;
  int _totalChars = 0;
  late AnimationController _pulseCtrl;
  late AnimationController _enterCtrl;
  late AnimationController _typingCtrl;
  late AnimationController _waveCtrl;
  late Animation<double> _enterAnim;
  StreamSubscription? _posSub;
  StreamSubscription? _durSub;
  StreamSubscription? _completeSub;
  final TextEditingController _searchCtrl = TextEditingController();
  bool _searchOpen = false;
  String _query = '';
  final List<String> _inputHistory = [];
  int _historyIdx = -1;
  bool _interruptRequested = false;
  bool _showTimestamp = false;
  String? _quotedText;
  int _matchCount = 0;

  static const _quickReplies = <String>[
    '你好呀',
    '你叫什么名字',
    '你会一直成长吗',
    '你是什么模型',
    '讲个笑话',
    '你的声音是什么样的',
    '你记得我们聊过什么吗',
    '今天心情怎么样',
  ];

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(duration: const Duration(seconds: 3), vsync: this)..repeat();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 800), vsync: this);
    _enterAnim = CurvedAnimation(parent: _enterCtrl, curve: XlCurve.easeOut);
    _typingCtrl = AnimationController(duration: const Duration(milliseconds: 1200), vsync: this)..repeat();
    _waveCtrl = AnimationController(duration: const Duration(milliseconds: 1400), vsync: this)..repeat();
    _enterCtrl.forward();
    _inputFocus.addListener(_onFocusChange);
    _input.addListener(() {
      if (mounted) setState(() => _charCount = _input.text.length);
    });
    _scroll.addListener(_onScroll);
    _posSub = _player.onPositionChanged.listen((d) {
      if (mounted) setState(() => _playPos = d);
    });
    _durSub = _player.onDurationChanged.listen((d) {
      if (mounted) setState(() => _playDur = d);
    });
    _completeSub = _player.onPlayerComplete.listen((_) {
      if (mounted) {
        setState(() {
          _playing = false;
          _playingId = null;
          _playPos = Duration.zero;
        });
      }
    });
    _searchCtrl.addListener(() {
      if (!mounted) return;
      final q = _searchCtrl.text.trim();
      setState(() {
        _query = q;
        _matchCount = q.isEmpty
            ? 0
            : _msgs.where((m) => m.text.toLowerCase().contains(q.toLowerCase())).length;
      });
    });
    _hello();
  }

  void _onFocusChange() {
    if (mounted) setState(() => _inputFocused = _inputFocus.hasFocus);
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    _inputFocus.removeListener(_onFocusChange);
    _inputFocus.dispose();
    _pulseCtrl.dispose();
    _enterCtrl.dispose();
    _typingCtrl.dispose();
    _waveCtrl.dispose();
    _posSub?.cancel();
    _durSub?.cancel();
    _completeSub?.cancel();
    _searchCtrl.dispose();
    _player.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scroll.hasClients) return;
    final max = _scroll.position.maxScrollExtent;
    final cur = _scroll.position.pixels;
    final atBottom = (max - cur) < 40;
    if (atBottom != _autoScroll) setState(() => _autoScroll = atBottom);
    final show = !atBottom && max > 200;
    if (show != _showScrollDown) setState(() => _showScrollDown = show);
  }

  Future<void> _hello() async {
    try {
      final s = await XlClient.stub.status();
      if (!mounted) return;
      setState(() {
        _connected = true;
        _stage = s.displayStage;
        _version = s.displayVersion;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _connected = false;
        _stage = '未连接后端';
      });
    }
    if (!mounted) return;
    setState(() {
      _msgs.add(_Msg(
        id: 'm${_msgSeq++}',
        who: 'xl',
        text: '你好呀，我是小凌。今天想聊点什么？',
        time: DateTime.now(),
        status: _MsgStatus.done,
      ));
    });
    _scrollBottom();
  }

  Future<void> _send([String? preset]) async {
    final text = (preset ?? _input.text).trim();
    if (text.isEmpty || _busy) return;
    if (preset == null) _input.clear();
    final myId = 'm${_msgSeq++}';
    final replyId = 'm${_msgSeq++}';
    setState(() {
      _msgs.add(_Msg(
        id: myId,
        who: 'me',
        text: text,
        time: DateTime.now(),
        status: _MsgStatus.done,
      ));
      _msgs.add(_Msg(
        id: replyId,
        who: 'xl',
        text: '',
        time: DateTime.now(),
        status: _MsgStatus.streaming,
      ));
      _busy = true;
      _chatCount++;
      _totalChars += text.length;
    });
    _scrollBottom(force: true);
    try {
      final session = await XlClient.stub.chatSession(
        text,
        onDelta: (delta) {
          if (!mounted) return;
          final idx = _msgs.indexWhere((m) => m.id == replyId);
          if (idx < 0) return;
          setState(() {
            _msgs[idx] = _msgs[idx].copyWith(text: _msgs[idx].text + delta);
          });
          _scrollBottom();
        },
      );
      if (!mounted) return;
      final idx = _msgs.indexWhere((m) => m.id == replyId);
      if (idx < 0) return;
      if (session.hasError) {
        setState(() {
          _msgs[idx] = _msgs[idx].copyWith(
            text: session.error ?? '出错了',
            status: _MsgStatus.error,
          );
        });
      } else {
        setState(() {
          _msgs[idx] = _msgs[idx].copyWith(status: _MsgStatus.done);
        });
        if (_ttsOn) {
          final reply = _msgs[idx].text;
          if (reply.isNotEmpty) _speak(reply, replyId);
        }
      }
    } catch (e) {
      if (!mounted) return;
      final idx = _msgs.indexWhere((m) => m.id == replyId);
      if (idx >= 0) {
        setState(() {
          _msgs[idx] = _msgs[idx].copyWith(
            text: '出错了：$e',
            status: _MsgStatus.error,
          );
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
      _scrollBottom();
    }
  }

  Future<void> _retryError(int errorIdx) async {
    if (_busy || errorIdx < 0 || errorIdx >= _msgs.length) return;
    String? prompt;
    for (int i = errorIdx - 1; i >= 0; i--) {
      if (_msgs[i].who == 'me') {
        prompt = _msgs[i].text;
        break;
      }
    }
    if (prompt == null || prompt.isEmpty) return;
    final targetId = _msgs[errorIdx].id;
    setState(() {
      _msgs[errorIdx] = _msgs[errorIdx].copyWith(text: '', status: _MsgStatus.streaming);
      _busy = true;
    });
    _scrollBottom(force: true);
    try {
      final session = await XlClient.stub.chatSession(prompt, onDelta: (delta) {
        if (!mounted) return;
        final idx = _msgs.indexWhere((m) => m.id == targetId);
        if (idx < 0) return;
        setState(() => _msgs[idx] = _msgs[idx].copyWith(text: _msgs[idx].text + delta));
        _scrollBottom();
      });
      if (!mounted) return;
      final idx = _msgs.indexWhere((m) => m.id == targetId);
      if (idx < 0) return;
      if (session.hasError) {
        setState(() => _msgs[idx] = _msgs[idx].copyWith(text: session.error ?? '出错了', status: _MsgStatus.error));
      } else {
        setState(() => _msgs[idx] = _msgs[idx].copyWith(status: _MsgStatus.done));
        final reply = _msgs[idx].text;
        if (_ttsOn && reply.isNotEmpty) _speak(reply, targetId);
      }
    } catch (e) {
      if (!mounted) return;
      final idx = _msgs.indexWhere((m) => m.id == targetId);
      if (idx >= 0) {
        setState(() => _msgs[idx] = _msgs[idx].copyWith(text: '出错了：$e', status: _MsgStatus.error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
      _scrollBottom();
    }
  }

  Future<void> _speak(String text, String msgId) async {
    if (_speaking.contains(msgId)) return;
    setState(() => _speaking.add(msgId));
    try {
      final result = await XlClient.stub.readAloudBytes(text);
      if (!mounted || !result.success || result.bytes.isEmpty) return;
      final dir = await getTemporaryDirectory();
      final f = File('${dir.path}/xl_tts_$msgId.mp3');
      await f.writeAsBytes(result.bytes);
      await _player.play(DeviceFileSource(f.path));
      if (mounted) {
        setState(() {
          _playing = true;
          _playingId = msgId;
        });
      }
    } catch (_) {
    } finally {
      if (mounted) setState(() => _speaking.remove(msgId));
    }
  }

  Future<void> _togglePlay(String text, String msgId) async {
    if (_playing && _playingId == msgId) {
      await _player.pause();
      if (mounted) setState(() => _playing = false);
      return;
    }
    if (_playingId == msgId && _playPos > Duration.zero) {
      await _player.resume();
      if (mounted) setState(() => _playing = true);
      return;
    }
    await _speak(text, msgId);
  }

  void _scrollBottom({bool force = false}) {
    if (!force && !_autoScroll) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 260),
        curve: XlCurve.easeOut,
      );
    });
  }

  void _toggleSearch() {
    setState(() {
      _searchOpen = !_searchOpen;
      if (!_searchOpen) {
        _searchCtrl.clear();
        _query = '';
        _matchCount = 0;
      }
    });
    if (_searchOpen) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _inputFocus.requestFocus());
    }
  }

  Future<void> _exportChat() async {
    final p = XlPalette.of(context);
    if (_msgs.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: p.surface,
        content: Text('暂无对话可导出', style: TextStyle(color: p.text1, fontSize: XlFont.captionSm)),
      ));
      return;
    }
    try {
      final dir = await getApplicationDocumentsDirectory();
      final stamp = DateTime.now().millisecondsSinceEpoch;
      final txtPath = '${dir.path}/xiaoling_chat_$stamp.txt';
      final jsonPath = '${dir.path}/xiaoling_chat_$stamp.json';
      final buf = StringBuffer();
      for (final m in _msgs) {
        final who = m.who == 'me' ? '我' : '小凌';
        buf.writeln('[$who] ${m.time.toIso8601String()}');
        buf.writeln(m.text);
        buf.writeln('');
      }
      await File(txtPath).writeAsString(buf.toString());
      final payload = _msgs
          .map((m) => {
                'who': m.who,
                'text': m.text,
                'time': m.time.toIso8601String(),
                'status': m.status.name,
              })
          .toList();
      await File(jsonPath).writeAsString(const JsonEncoder.withIndent('  ').convert(payload));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: p.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.md)),
        content: Row(children: [
          Icon(Icons.check_circle_rounded, color: p.green, size: 16),
          const SizedBox(width: 8),
          Expanded(child: Text('已导出 ${_msgs.length} 条对话',
              style: TextStyle(color: p.text1, fontSize: XlFont.captionSm, fontWeight: FontWeight.w700))),
        ]),
      ));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: p.surface,
        content: Text('导出失败: $e', style: TextStyle(color: p.red, fontSize: XlFont.captionSm)),
      ));
    }
  }

  void _interruptGeneration() {
    if (!_busy || _interruptRequested) return;
    setState(() {
      _interruptRequested = true;
      final idx = _msgs.indexWhere((m) => m.status == _MsgStatus.streaming);
      if (idx >= 0) {
        _msgs[idx] = _msgs[idx].copyWith(
          text: _msgs[idx].text.isEmpty ? '（已手动中断）' : '${_msgs[idx].text}\n（已手动中断）',
          status: _MsgStatus.done,
        );
      }
      _busy = false;
    });
  }

  void _navigateHistory(bool up) {
    if (_inputHistory.isEmpty) return;
    setState(() {
      if (up) {
        if (_historyIdx == -1) {
          _historyIdx = _inputHistory.length - 1;
        } else if (_historyIdx > 0) {
          _historyIdx--;
        }
      } else {
        if (_historyIdx < 0) return;
        _historyIdx++;
        if (_historyIdx >= _inputHistory.length) {
          _historyIdx = -1;
          _input.clear();
          return;
        }
      }
      _input.value = TextEditingValue(
        text: _inputHistory[_historyIdx],
        selection: TextSelection.collapsed(offset: _inputHistory[_historyIdx].length),
      );
    });
  }

  void _pushHistory(String text) {
    final t = text.trim();
    if (t.isEmpty) return;
    if (_inputHistory.isNotEmpty && _inputHistory.last == t) return;
    _inputHistory.add(t);
    if (_inputHistory.length > 30) _inputHistory.removeAt(0);
    _historyIdx = -1;
  }

  void _requestQuote(String text) {
    setState(() => _quotedText = text);
    _inputFocus.requestFocus();
  }

  List<InlineSpan> _highlightSpans(String source, TextStyle base, Color hit) {
    if (_query.isEmpty) return [TextSpan(text: source, style: base)];
    final spans = <InlineSpan>[];
    final q = _query.toLowerCase();
    final lower = source.toLowerCase();
    int i = 0;
    while (i < source.length) {
      final pos = lower.indexOf(q, i);
      if (pos < 0) {
        spans.add(TextSpan(text: source.substring(i), style: base));
        break;
      }
      if (pos > i) spans.add(TextSpan(text: source.substring(i, pos), style: base));
      spans.add(TextSpan(
        text: source.substring(pos, pos + q.length),
        style: base.copyWith(
          backgroundColor: hit.withOpacity(0.32),
          color: hit,
          fontWeight: FontWeight.w800,
        ),
      ));
      i = pos + q.length;
    }
    return spans;
  }

  Widget _searchBar(XlPalette p) {
    return Container(
      margin: const EdgeInsets.fromLTRB(26, 0, 26, 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: AppTheme.screen(context, r: XlRadius.xl),
      child: Row(children: [
        Icon(Icons.search_rounded, size: 16, color: p.pink),
        const SizedBox(width: 10),
        Expanded(
          child: TextField(
            controller: _searchCtrl,
            style: TextStyle(fontSize: XlFont.bodySm, color: p.text1, fontWeight: FontWeight.w600),
            decoration: InputDecoration(
              isDense: true,
              border: InputBorder.none,
              hintText: '在对话历史中搜索…',
              hintStyle: TextStyle(fontSize: XlFont.bodySm, color: p.decor),
            ),
          ),
        ),
        Text('$_matchCount 命中',
            style: TextStyle(
              fontSize: XlFont.micro,
              color: _matchCount > 0 ? p.gold : p.decor,
              fontWeight: FontWeight.w800,
              letterSpacing: XlLetterSpacing.wider,
            )),
        const SizedBox(width: 8),
        _Pressable(
          scale: 0.9,
          onTap: _toggleSearch,
          child: Container(
            width: 26,
            height: 26,
            decoration: AppTheme.neuXxs(context, r: XlRadius.sm),
            child: Icon(Icons.close_rounded, size: 13, color: p.text2),
          ),
        ),
      ]),
    );
  }

  Widget _msgText(XlPalette p, _Msg m) {
    final base = TextStyle(
      fontSize: XlFont.bodySm,
      height: XlLineHeight.relaxed,
      color: m.who == 'me' ? p.btnInk : p.text1,
      fontWeight: m.who == 'me' ? FontWeight.w600 : FontWeight.w400,
    );
    return RichText(
      text: TextSpan(
        children: _highlightSpans(m.text, base, p.gold),
      ),
    );
  }

  Widget _interruptButton(XlPalette p) {
    return _Pressable(
      scale: 0.92,
      onTap: _interruptGeneration,
      child: Container(
        margin: const EdgeInsets.only(right: 10),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          gradient: LinearGradient(colors: [p.red, p.red.withOpacity(0.82)]),
          borderRadius: BorderRadius.circular(XlRadius.pill),
          border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.3 : 0.2), width: 1),
          boxShadow: [...p.raisedXs, BoxShadow(color: p.red.withOpacity(0.32), blurRadius: 12, spreadRadius: -2)],
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.stop_rounded, size: 14, color: p.btnInk),
          const SizedBox(width: 6),
          Text('中断',
              style: TextStyle(
                fontSize: XlFont.captionSm,
                fontWeight: FontWeight.w800,
                color: p.btnInk,
                letterSpacing: XlLetterSpacing.wider,
              )),
        ]),
      ),
    );
  }

  Widget _quoteBanner(XlPalette p) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: AppTheme.accentSoft(context, r: XlRadius.md),
      child: Row(children: [
        Icon(Icons.format_quote_rounded, size: 14, color: p.pink),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            _quotedText!,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: XlFont.captionSm,
              color: p.text2,
              fontWeight: FontWeight.w600,
              height: XlLineHeight.snug,
            ),
          ),
        ),
        const SizedBox(width: 8),
        _Pressable(
          scale: 0.9,
          onTap: () => setState(() => _quotedText = null),
          child: Icon(Icons.close_rounded, size: 14, color: p.text3),
        ),
      ]),
    );
  }

  void _clearChat() {
    showDialog(
      context: context,
      barrierColor: XlPalette.of(context).scrim,
      builder: (ctx) {
        final p = XlPalette.of(ctx);
        return Dialog(
          backgroundColor: Colors.transparent,
          elevation: 0,
          child: Container(
            width: 400,
            padding: const EdgeInsets.all(24),
            decoration: AppTheme.neuLg(ctx, r: XlRadius.xxxl),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('清空对话',
                    style: TextStyle(
                      fontSize: XlFont.h5,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                    )),
                const SizedBox(height: 6),
                Text('所有消息将被移除，此操作不可撤销',
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.text2,
                      fontWeight: FontWeight.w500,
                    )),
                const SizedBox(height: 22),
                Row(
                  children: [
                    Expanded(
                      child: _Pressable(
                        onTap: () => Navigator.pop(ctx),
                        scale: 0.95,
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          decoration: AppTheme.ghost(ctx, r: XlRadius.pill),
                          child: Center(
                            child: Text('取消',
                                style: TextStyle(
                                  fontSize: XlFont.captionSm,
                                  fontWeight: FontWeight.w800,
                                  color: p.text1,
                                )),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _Pressable(
                        scale: 0.95,
                        onTap: () {
                          Navigator.pop(ctx);
                          setState(() {
                            _msgs.clear();
                            _msgSeq = 0;
                            _chatCount = 0;
                            _totalChars = 0;
                          });
                          _hello();
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          decoration: AppTheme.btn(ctx, r: XlRadius.pill),
                          child: Center(
                            child: Text('清空',
                                style: TextStyle(
                                  fontSize: XlFont.captionSm,
                                  fontWeight: FontWeight.w800,
                                  color: p.btnInk,
                                )),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Stack(
      children: [
        Positioned.fill(child: AppTheme.aurora(context, child: const SizedBox.shrink())),
        Column(
          children: [
            _header(p),
            if (_searchOpen) _searchBar(p),
            _statsRow(p),
            Expanded(child: _list(p)),
            _inputBar(p),
          ],
        ),
        Positioned(
          right: 28,
          bottom: 128,
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 260),
            switchInCurve: XlCurve.spring,
            switchOutCurve: XlCurve.easeOut,
            transitionBuilder: (child, anim) => ScaleTransition(
              scale: anim,
              child: FadeTransition(opacity: anim, child: child),
            ),
            child: _showScrollDown ? _scrollDownBtn(p) : const SizedBox.shrink(),
          ),
        ),
      ],
    );
  }

  Widget _header(XlPalette p) {
    return AnimatedBuilder(
      animation: _enterAnim,
      builder: (_, child) => Opacity(
        opacity: _enterAnim.value,
        child: Transform.translate(
          offset: Offset(0, (1 - _enterAnim.value) * -12),
          child: child,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(26, 20, 26, 10),
        child: Row(
          children: [
            _avatar(p),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    children: [
                      Text('小凌',
                          style: TextStyle(
                            fontSize: XlFont.h5,
                            fontWeight: FontWeight.w800,
                            color: p.text1,
                            letterSpacing: XlLetterSpacing.normal,
                          )),
                      const SizedBox(width: 10),
                      _statusChip(p),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(_stage.isEmpty ? '在线等你' : _stage,
                      style: TextStyle(
                        fontSize: XlFont.label,
                        color: p.text3,
                        fontWeight: FontWeight.w500,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                ],
              ),
            ),
            _agentEntryBtn(p),
            const SizedBox(width: 8),
            _headerBtn(
              p,
              _ttsOn ? Icons.volume_up_rounded : Icons.volume_off_rounded,
              _ttsOn ? p.pink : p.text3,
              () => setState(() => _ttsOn = !_ttsOn),
            ),
            const SizedBox(width: 8),
            _headerBtn(
              p,
              _searchOpen ? Icons.filter_alt_rounded : Icons.search_rounded,
              _searchOpen ? p.pink : p.text2,
              _toggleSearch,
            ),
            const SizedBox(width: 8),
            _headerBtn(p, Icons.ios_share_rounded, p.text2, _exportChat),
            const SizedBox(width: 8),
            _headerBtn(
              p,
              Icons.schedule_rounded,
              _showTimestamp ? p.gold : p.text2,
              () => setState(() => _showTimestamp = !_showTimestamp),
            ),
            const SizedBox(width: 8),
            _headerBtn(p, Icons.cleaning_services_outlined, p.text2, _clearChat),
          ],
        ),
      ),
    );
  }

  Widget _avatar(XlPalette p) {
    return AnimatedBuilder(
      animation: _pulseCtrl,
      builder: (_, __) {
        final t = _pulseCtrl.value;
        final breatheScale = _busy ? 1.0 + (t * 0.5).clamp(0.0, 1.0) * 0.05 : 1.0;
        return Stack(
          alignment: Alignment.center,
          children: [
            Container(
              width: 52 + t * 8,
              height: 52 + t * 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: p.pink.withOpacity((1 - t) * 0.18),
              ),
            ),
            Transform.scale(
              scale: breatheScale,
              child: Container(
                width: 52,
                height: 52,
                decoration: AppTheme.brandOrb(context, size: 52),
                child: Icon(Icons.favorite_rounded, color: p.btnInk, size: 20),
              ),
            ),
            if (_busy)
              Positioned(
                bottom: 0,
                right: 0,
                child: Container(
                  width: 16,
                  height: 16,
                  decoration: AppTheme.glowDot(p.green, size: 16),
                ),
              ),
          ],
        );
      },
    );
  }

  Widget _statusChip(XlPalette p) {
    final c = _connected ? p.green : p.gold;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: c.withOpacity(p.isDark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: c.withOpacity(0.30), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 5,
            height: 5,
            decoration: AppTheme.glowDot(c, size: 5),
          ),
          const SizedBox(width: 5),
          Text(_connected ? 'ONLINE' : 'OFFLINE',
              style: TextStyle(
                fontSize: XlFont.micro,
                fontWeight: FontWeight.w800,
                color: c,
                letterSpacing: XlLetterSpacing.ultra,
              )),
        ],
      ),
    );
  }

  Widget _agentEntryBtn(XlPalette p) {
    return _Pressable(
      onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AgentPage())),
      scale: 0.92,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: AppTheme.brand(context, r: XlRadius.pill),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.auto_awesome_rounded, size: 15, color: p.btnInk),
            const SizedBox(width: 6),
            Text('Agent',
                style: TextStyle(
                  fontSize: XlFont.label,
                  fontWeight: FontWeight.w800,
                  color: p.btnInk,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _headerBtn(XlPalette p, IconData icon, Color color, VoidCallback onTap) {
    return _Pressable(
      onTap: onTap,
      scale: 0.92,
      child: Container(
        width: 42,
        height: 42,
        decoration: AppTheme.neuXs(context, r: XlRadius.md),
        child: Icon(icon, size: 17, color: color),
      ),
    );
  }

  Widget _statsRow(XlPalette p) {
    final stats = <_MiniStat>[
      _MiniStat('对话', '$_chatCount', '轮', Icons.chat_bubble_outline_rounded, p.pink),
      _MiniStat('字符', '$_totalChars', '字', Icons.text_fields_rounded, p.gold),
      _MiniStat('版本', _version.isEmpty ? '—' : _version.replaceFirst('v', ''), '', Icons.tag_rounded, p.violet),
      _MiniStat('语音', _ttsOn ? '开' : '关', '', Icons.volume_up_rounded, p.green),
    ];
    return Padding(
      padding: const EdgeInsets.fromLTRB(26, 0, 26, 10),
      child: Row(
        children: [
          for (int i = 0; i < stats.length; i++) ...[
            Expanded(child: _miniStatCard(p, stats[i])),
            if (i != stats.length - 1) const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }

  Widget _miniStatCard(XlPalette p, _MiniStat s) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: AppTheme.neuXxs(context, r: XlRadius.md),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: s.color.withOpacity(p.isDark ? 0.14 : 0.10),
              borderRadius: BorderRadius.circular(XlRadius.xs),
              border: Border.all(color: s.color.withOpacity(0.28), width: 1),
            ),
            child: Icon(s.icon, size: 13, color: s.color),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(s.label,
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.text3,
                      fontWeight: FontWeight.w700,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
                const SizedBox(height: 1),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Flexible(
                      child: Text(s.value,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: XlFont.caption,
                            color: p.text1,
                            fontWeight: FontWeight.w800,
                            fontFeatures: const [FontFeature.tabularFigures()],
                            height: 1.1,
                          )),
                    ),
                    if (s.unit.isNotEmpty)
                      Text(s.unit,
                          style: TextStyle(
                            fontSize: XlFont.micro,
                            color: p.text3,
                            fontWeight: FontWeight.w700,
                          )),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _list(XlPalette p) {
    if (_msgs.isEmpty) return _emptyState(p);
    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.fromLTRB(26, 8, 26, 8),
      itemCount: _msgs.length,
      itemBuilder: (_, i) {
        final m = _msgs[i];
        final prev = i > 0 ? _msgs[i - 1] : null;
        final showTime = prev == null || m.time.difference(prev.time).inMinutes >= 3;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (showTime) _timeDivider(p, m.time),
            _AnimatedBubble(child: _bubble(p, m, i)),
          ],
        );
      },
    );
  }

  Widget _emptyState(XlPalette p) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 30),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 96,
              height: 96,
              decoration: AppTheme.brandOrbLg(context, size: 96),
              child: Icon(Icons.favorite_rounded, size: 40, color: p.btnInk),
            ),
            const SizedBox(height: 22),
            Text('开始对话吧',
                style: TextStyle(
                  fontSize: XlFont.h5,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                )),
            const SizedBox(height: 8),
            Text('小凌已经准备好，随时可以聊',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: XlFont.caption,
                  color: p.text2,
                  fontWeight: FontWeight.w500,
                  height: XlLineHeight.relaxed,
                )),
            const SizedBox(height: 26),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: _quickReplies.take(4).map((q) => _Pressable(
                onTap: _busy ? null : () => _send(q),
                scale: 0.93,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: AppTheme.accentSoft(context, r: XlRadius.pill),
                  child: Text(q,
                      style: TextStyle(
                        fontSize: XlFont.label,
                        fontWeight: FontWeight.w700,
                        color: _busy ? p.decor : p.pink,
                        letterSpacing: XlLetterSpacing.wide,
                      )),
                ),
              )).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _timeDivider(XlPalette p, DateTime t) {
    return TweenAnimationBuilder<double>(
      duration: const Duration(milliseconds: 400),
      curve: XlCurve.easeOut,
      tween: Tween(begin: 0.0, end: 1.0),
      builder: (_, v, child) => Opacity(
        opacity: v,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 14),
          child: Center(child: child),
        ),
      ),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        decoration: AppTheme.sunkenHair(context, r: XlRadius.pill),
        child: Text(formatRelative(t),
            style: TextStyle(
              fontSize: XlFont.micro,
              fontWeight: FontWeight.w700,
              color: p.text3,
              letterSpacing: XlLetterSpacing.wider,
            )),
      ),
    );
  }

  Widget _bubble(XlPalette p, _Msg m, int index) {
    final isMe = m.who == 'me';
    final isEmptyStream = m.status == _MsgStatus.streaming && m.text.isEmpty;
    final isError = m.status == _MsgStatus.error && !isMe;
    return Align(
      alignment: isMe ? Alignment.centerRight : Alignment.centerLeft,
      child: Column(
        crossAxisAlignment: isMe ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                if (!isMe) ...[
                  _miniAvatar(p),
                  const SizedBox(width: 10),
                ],
                Flexible(
                  child: Container(
                    constraints: BoxConstraints(
                      maxWidth: MediaQuery.of(context).size.width * 0.62,
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: isMe ? _meBubble(p) : _aiBubble(p, m.status),
                    child: isEmptyStream
                        ? _typingIndicator(p)
                        : isError
                            ? _errorBody(p, m, index)
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  _msgText(p, m),
                                  if (_showTimestamp && m.text.isNotEmpty)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 4),
                                      child: Text(
                                        '${m.time.year}-${m.time.month.toString().padLeft(2, '0')}-${m.time.day.toString().padLeft(2, '0')} ${m.time.hour.toString().padLeft(2, '0')}:${m.time.minute.toString().padLeft(2, '0')}:${m.time.second.toString().padLeft(2, '0')}',
                                        style: TextStyle(
                                          fontSize: XlFont.micro,
                                          color: (isMe ? p.btnInk : p.text3).withOpacity(0.7),
                                          fontWeight: FontWeight.w600,
                                          fontFeatures: const [FontFeature.tabularFigures()],
                                        ),
                                      ),
                                    ),
                                  if (!isMe && m.status == _MsgStatus.done && m.text.isNotEmpty)
                                    _bubbleActions(p, m),
                                ],
                              ),
                  ),
                ),
                if (isMe) ...[
                  const SizedBox(width: 10),
                  _meAvatar(p),
                ],
              ],
            ),
          ),
          if (!isMe && m.status == _MsgStatus.done && m.text.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(left: 46, bottom: 4),
              child: Text(formatClock(m.time),
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    color: p.decor,
                    fontWeight: FontWeight.w500,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ),
          if (isMe)
            Padding(
              padding: const EdgeInsets.only(right: 46, bottom: 4),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(formatClock(m.time),
                      style: TextStyle(
                        fontSize: XlFont.micro,
                        color: p.decor,
                        fontWeight: FontWeight.w500,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                  const SizedBox(width: 6),
                  Icon(Icons.done_all_rounded, size: 12, color: p.pink.withOpacity(0.75)),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _errorBody(XlPalette p, _Msg m, int index) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.error_outline_rounded, size: 14, color: p.red),
            const SizedBox(width: 6),
            Text('回复失败',
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.red,
                  fontWeight: FontWeight.w800,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
        const SizedBox(height: 6),
        Text(m.text,
            style: TextStyle(
              fontSize: XlFont.bodySm,
              height: XlLineHeight.relaxed,
              color: p.text2,
            )),
        const SizedBox(height: 10),
        _Pressable(
          onTap: _busy ? null : () => _retryError(index),
          scale: 0.94,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: p.red.withOpacity(p.isDark ? 0.14 : 0.10),
              borderRadius: BorderRadius.circular(XlRadius.pill),
              border: Border.all(color: p.red.withOpacity(0.35), width: 1),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.refresh_rounded, size: 11, color: p.red),
                const SizedBox(width: 5),
                Text('重新生成',
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      fontWeight: FontWeight.w800,
                      color: p.red,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ],
            ),
          ),
        ),
      ],
    );
  }

  BoxDecoration _meBubble(XlPalette p) {
    return BoxDecoration(
      gradient: p.gradBrand,
      borderRadius: const BorderRadius.only(
        topLeft: Radius.circular(XlRadius.lg),
        topRight: Radius.circular(XlRadius.lg),
        bottomLeft: Radius.circular(XlRadius.lg),
        bottomRight: Radius.circular(XlRadius.micro),
      ),
      border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.28 : 0.4), width: 1),
      boxShadow: [...p.raisedXs, BoxShadow(color: p.pink.withOpacity(0.28), blurRadius: 18, spreadRadius: -4)],
    );
  }

  BoxDecoration _aiBubble(XlPalette p, _MsgStatus s) {
    final border = s == _MsgStatus.error ? p.red.withOpacity(0.42) : p.shDark.withOpacity(p.isDark ? 0.22 : 0.10);
    return BoxDecoration(
      color: p.screenSoft,
      borderRadius: const BorderRadius.only(
        topLeft: Radius.circular(XlRadius.lg),
        topRight: Radius.circular(XlRadius.lg),
        bottomLeft: Radius.circular(XlRadius.micro),
        bottomRight: Radius.circular(XlRadius.lg),
      ),
      border: Border.all(color: border, width: 1),
      boxShadow: p.sunkenSm,
    );
  }

  Widget _miniAvatar(XlPalette p) {
    return Container(
      width: 32,
      height: 32,
      decoration: AppTheme.brandOrb(context, size: 32),
      child: Icon(Icons.favorite_rounded, size: 13, color: p.btnInk),
    );
  }

  Widget _meAvatar(XlPalette p) {
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        gradient: p.face,
        shape: BoxShape.circle,
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedXxs,
      ),
      child: Center(
        child: Text('我',
            style: TextStyle(
              fontSize: XlFont.captionSm,
              fontWeight: FontWeight.w800,
              color: p.text2,
            )),
      ),
    );
  }

  Widget _typingIndicator(XlPalette p) {
    return AnimatedBuilder(
      animation: _typingCtrl,
      builder: (_, __) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            final delay = i * 0.2;
            final phase = (_typingCtrl.value - delay) % 1.0;
            final bounce = phase < 0.5 ? phase * 2 : (1 - phase) * 2;
            final scale = 0.6 + bounce * 0.6;
            final opacity = 0.3 + bounce * 0.7;
            return Padding(
              padding: EdgeInsets.only(right: i < 2 ? 5 : 0),
              child: Transform.scale(
                scale: scale,
                child: Opacity(
                  opacity: opacity,
                  child: Container(
                    width: 7,
                    height: 7,
                    decoration: BoxDecoration(
                      color: p.pink,
                      shape: BoxShape.circle,
                      boxShadow: [BoxShadow(color: p.pink.withOpacity(0.4), blurRadius: 6, spreadRadius: -1)],
                    ),
                  ),
                ),
              ),
            );
          }),
        );
      },
    );
  }

  Widget _bubbleActions(XlPalette p, _Msg m) {
    final isSpeaking = _speaking.contains(m.id);
    final isPlaying = _playing && _playingId == m.id;
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _bubbleAction(
            p,
            isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded,
            isSpeaking ? '合成中' : (isPlaying ? '暂停' : '朗读'),
            isSpeaking ? p.gold : p.pink,
            isSpeaking ? null : () => _togglePlay(m.text, m.id),
          ),
          const SizedBox(width: 6),
          _bubbleAction(p, Icons.copy_rounded, '复制', p.text2, () {
            Clipboard.setData(ClipboardData(text: m.text));
            ScaffoldMessenger.of(context).clearSnackBars();
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(
              behavior: SnackBarBehavior.floating,
              backgroundColor: p.surface,
              elevation: 0,
              duration: const Duration(milliseconds: 1200),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.md)),
              content: Text('已复制',
                  style: TextStyle(
                    color: p.text1,
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w700,
                  )),
            ));
          }),
          const SizedBox(width: 6),
          _bubbleAction(p, Icons.format_quote_rounded, '引用', p.gold, () => _requestQuote(m.text)),
          const SizedBox(width: 6),
          _bubbleAction(p, Icons.refresh_rounded, '重发', p.text2, () {
            final lastUser = _msgs.lastWhere(
              (it) => it.who == 'me',
              orElse: () => _Msg(id: '', who: 'me', text: '', time: DateTime.now(), status: _MsgStatus.done),
            );
            if (lastUser.text.isNotEmpty) _send(lastUser.text);
          }),
        ],
      ),
    );
  }

  Widget _bubbleAction(XlPalette p, IconData icon, String label, Color color, VoidCallback? onTap) {
    return _Pressable(
      onTap: onTap,
      scale: 0.92,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
        decoration: AppTheme.ghost(context, r: XlRadius.pill),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 11, color: color),
            const SizedBox(width: 4),
            Text(label,
                style: TextStyle(
                  fontSize: XlFont.micro,
                  fontWeight: FontWeight.w700,
                  color: color,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _scrollDownBtn(XlPalette p) {
    return _Pressable(
      onTap: () => _scrollBottom(force: true),
      scale: 0.93,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: AppTheme.neu(context, r: XlRadius.pill),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.arrow_downward_rounded, size: 14, color: p.pink),
            const SizedBox(width: 6),
            Text('最新消息',
                style: TextStyle(
                  fontSize: XlFont.label,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _inputBar(XlPalette p) {
    return Container(
      padding: const EdgeInsets.fromLTRB(26, 8, 26, 20),
      child: Column(
        children: [
          _quickRepliesRow(p),
          if (_playing && _playingId != null) _nowPlayingBar(p),
          if (_quotedText != null) _quoteBanner(p),
          const SizedBox(height: 8),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(child: _inputField(p)),
              const SizedBox(width: 12),
              if (_busy) _interruptButton(p),
              _sendButton(p),
            ],
          ),
          Padding(
            padding: const EdgeInsets.only(top: 4, right: 2),
            child: Align(
              alignment: Alignment.centerRight,
              child: Text(
                '$_charCount/2000',
                style: TextStyle(
                  fontSize: XlFont.micro,
                  color: _charCount > 2000 ? p.red : p.decor,
                  fontWeight: FontWeight.w700,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _quickRepliesRow(XlPalette p) {
    return SizedBox(
      height: 34,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _quickReplies.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, i) {
          final q = _quickReplies[i];
          return _Pressable(
            onTap: _busy ? null : () => _send(q),
            scale: 0.93,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              decoration: AppTheme.neuXs(context, r: XlRadius.pill),
              child: Text(q,
                  style: TextStyle(
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w700,
                    color: _busy ? p.decor : p.text2,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
            ),
          );
        },
      ),
    );
  }

  Widget _nowPlayingBar(XlPalette p) {
    final pct = _playDur.inMilliseconds == 0
        ? 0.0
        : (_playPos.inMilliseconds / _playDur.inMilliseconds).clamp(0.0, 1.0);
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: AppTheme.neu(context, r: XlRadius.md),
      child: Row(
        children: [
          AnimatedBuilder(
            animation: _waveCtrl,
            builder: (_, __) {
              return Row(
                children: List.generate(4, (i) {
                  final t = ((_waveCtrl.value + i * 0.25) % 1.0);
                  final h = 4 + (t < 0.5 ? t * 2 : (1 - t) * 2) * 12;
                  return Padding(
                    padding: EdgeInsets.only(right: i < 3 ? 2 : 0),
                    child: Container(
                      width: 3,
                      height: h,
                      decoration: BoxDecoration(
                        gradient: p.gradBrand,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  );
                }),
              );
            },
          ),
          const SizedBox(width: 12),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(99),
              child: LinearProgressIndicator(
                value: pct,
                minHeight: 4,
                backgroundColor: p.surfaceLo,
                valueColor: AlwaysStoppedAnimation(p.pink),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Text('${_fmtDur(_playPos)} / ${_fmtDur(_playDur)}',
              style: TextStyle(
                fontSize: XlFont.micro,
                color: p.text3,
                fontWeight: FontWeight.w800,
                fontFeatures: const [FontFeature.tabularFigures()],
              )),
          const SizedBox(width: 10),
          _Pressable(
            scale: 0.9,
            onTap: () async {
              await _player.stop();
              if (mounted) {
                setState(() {
                  _playing = false;
                  _playingId = null;
                  _playPos = Duration.zero;
                });
              }
            },
            child: Icon(Icons.close_rounded, size: 16, color: p.text3),
          ),
        ],
      ),
    );
  }

  String _fmtDur(Duration d) {
    final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  Widget _inputField(XlPalette p) {
    return AnimatedContainer(
      duration: XlDuration.fast,
      curve: XlCurve.standard,
      decoration: _inputFocused
          ? BoxDecoration(
              color: p.screen,
              borderRadius: BorderRadius.circular(XlRadius.xl),
              border: Border.all(color: p.pink.withOpacity(0.5), width: 1.5),
              boxShadow: [
                ...p.sunkenDeep,
                BoxShadow(color: p.pink.withOpacity(0.18), blurRadius: 16, spreadRadius: -4),
              ],
            )
          : AppTheme.screen(context, r: XlRadius.xl),
      padding: const EdgeInsets.fromLTRB(18, 6, 8, 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: CallbackShortcuts(
              bindings: {
                const SingleActivator(LogicalKeyboardKey.enter, control: true): () => _send(),
                const SingleActivator(LogicalKeyboardKey.escape): () => _input.clear(),
                const SingleActivator(LogicalKeyboardKey.arrowUp, alt: true): () => _navigateHistory(true),
                const SingleActivator(LogicalKeyboardKey.arrowDown, alt: true): () => _navigateHistory(false),
              },
              child: TextField(
                controller: _input,
                focusNode: _inputFocus,
                enabled: !_busy,
                maxLines: 4,
                minLines: 1,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) {
                  _pushHistory(_input.text);
                  if (_quotedText != null) {
                    final q = _quotedText!;
                    final mine = _input.text;
                    _quotedText = null;
                    _input.clear();
                    _send('引用自：$q\n$mine');
                    return;
                  }
                  _send();
                },
                style: TextStyle(
                  fontSize: XlFont.bodySm,
                  color: p.text1,
                  height: XlLineHeight.relaxed,
                ),
                decoration: InputDecoration(
                  hintText: _busy ? '小凌正在打字…' : '和小凌说句话…',
                  hintStyle: TextStyle(
                    fontSize: XlFont.bodySm,
                    color: p.decor,
                    fontWeight: FontWeight.w500,
                  ),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(vertical: 10),
                ),
              ),
            ),
          ),
          _focusBtn(p),
        ],
      ),
    );
  }

  Widget _focusBtn(XlPalette p) {
    return _Pressable(
      onTap: () => _inputFocus.requestFocus(),
      scale: 0.9,
      child: Container(
        width: 32,
        height: 32,
        decoration: AppTheme.neuXs(context, r: XlRadius.sm),
        child: Icon(Icons.sentiment_satisfied_alt_rounded, size: 15, color: p.text2),
      ),
    );
  }

  Widget _sendButton(XlPalette p) {
    return _SendButton(
      busy: _busy,
      onTap: _busy ? null : () => _send(),
    );
  }
}

class _AnimatedBubble extends StatefulWidget {
  final Widget child;
  const _AnimatedBubble({required this.child});
  @override
  State<_AnimatedBubble> createState() => _AnimatedBubbleState();
}

class _AnimatedBubbleState extends State<_AnimatedBubble> with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<Offset> _slide;
  late Animation<double> _fade;
  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(duration: const Duration(milliseconds: 260), vsync: this);
    _slide = Tween<Offset>(begin: const Offset(0, 0.2), end: Offset.zero).animate(
      CurvedAnimation(parent: _ctrl, curve: XlCurve.springSoft),
    );
    _fade = CurvedAnimation(parent: _ctrl, curve: XlCurve.easeOut);
    _ctrl.forward();
  }
  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }
  @override
  Widget build(BuildContext context) {
    return SlideTransition(
      position: _slide,
      child: FadeTransition(opacity: _fade, child: widget.child),
    );
  }
}

class _SendButton extends StatefulWidget {
  final bool busy;
  final VoidCallback? onTap;
  const _SendButton({required this.busy, this.onTap});
  @override
  State<_SendButton> createState() => _SendButtonState();
}

class _SendButtonState extends State<_SendButton> {
  bool _down = false;
  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return GestureDetector(
      onTapDown: widget.onTap == null ? null : (_) => setState(() => _down = true),
      onTapUp: widget.onTap == null ? null : (_) => setState(() => _down = false),
      onTapCancel: () => setState(() => _down = false),
      onTap: widget.onTap,
      child: AnimatedScale(
        scale: _down ? 0.9 : 1.0,
        duration: XlDuration.micro,
        child: AnimatedContainer(
          duration: XlDuration.fast,
          width: 52,
          height: 52,
          decoration: widget.busy
              ? AppTheme.sunkenXs(context, r: 999)
              : (_down ? AppTheme.btnPressed(context, r: 999) : AppTheme.btn(context, r: 999)),
          child: widget.busy
              ? Padding(
                  padding: const EdgeInsets.all(16),
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: p.pink.withOpacity(0.75),
                  ),
                )
              : Icon(Icons.send_rounded, color: p.btnInk, size: 20),
        ),
      ),
    );
  }
}

enum _MsgStatus { streaming, done, error }

class _Msg {
  final String id;
  final String who;
  final String text;
  final DateTime time;
  final _MsgStatus status;
  const _Msg({
    required this.id,
    required this.who,
    required this.text,
    required this.time,
    required this.status,
  });
  _Msg copyWith({String? text, _MsgStatus? status}) => _Msg(
        id: id,
        who: who,
        text: text ?? this.text,
        time: time,
        status: status ?? this.status,
      );
}

class _MiniStat {
  final String label;
  final String value;
  final String unit;
  final IconData icon;
  final Color color;
  const _MiniStat(this.label, this.value, this.unit, this.icon, this.color);
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
