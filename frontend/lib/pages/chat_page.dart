import 'package:flutter/material.dart';
import 'package:grpc/grpc.dart';
import '../theme/theme.dart';
import '../rpc/xiaoling.pbgrpc.dart';

/// 聊天页 — 液态玻璃风
class ChatPage extends StatefulWidget {
  const ChatPage({super.key});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<_Msg> _msgs = [];
  bool _busy = false;
  String _status = '连接中…';
  late ClientChannel _chan;
  late XiaoLingClient _stub;

  @override
  void initState() {
    super.initState();
    _chan = ClientChannel('localhost',
        port: 50051,
        options: const ChannelOptions(connectTimeout: Duration(seconds: 2)));
    _stub = XiaoLingClient(_chan);
    _hello();
  }

  @override
  void dispose() {
    _chan.shutdown();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _hello() async {
    try {
      final s = await _stub.getStatus(StatusRequest());
      setState(() => _status = 'v${s.version} · ${s.stage}');
    } catch (_) {
      setState(() => _status = '未连接后端');
    }
    setState(() => _msgs.add(_Msg('xl', '我在呢～想聊什么都可以。')));
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _busy) return;
    _input.clear();
    setState(() {
      _msgs.add(_Msg('me', text));
      _busy = true;
      _msgs.add(_Msg('xl', ''));
    });
    _scrollToBottom();
    try {
      final stream = _stub.chat(ChatRequest(text: text));
      await for (final chunk in stream) {
        if (chunk.delta.isNotEmpty) {
          _msgs[_msgs.length - 1] =
              _Msg('xl', _msgs[_msgs.length - 1].text + chunk.delta);
          setState(() {});
          _scrollToBottom();
        }
        if (chunk.done) break;
      }
    } catch (e) {
      _msgs[_msgs.length - 1] = _Msg('xl', '出错了：$e');
      setState(() {});
    } finally {
      setState(() => _busy = false);
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _header(),
        Expanded(child: _chatList()),
        _inputBar(),
      ],
    );
  }

  Widget _header() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
      child: Row(
        children: [
          Container(
            width: 44, height: 44,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppTheme.lightPink, AppTheme.primaryPink],
              ),
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white.withOpacity(0.6), width: 2),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.primaryPink.withOpacity(0.3),
                  blurRadius: 12, offset: const Offset(0, 4),
                ),
              ],
            ),
            child: const Icon(Icons.favorite, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('小凌',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700,
                      color: AppTheme.textPrimary, letterSpacing: 0.5)),
              Row(
                children: [
                  Container(
                    width: 6, height: 6,
                    decoration: const BoxDecoration(
                      color: Colors.green, shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 5),
                  Text(_status,
                      style: const TextStyle(fontSize: 11, color: AppTheme.textLight)),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _chatList() {
    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: _msgs.length,
      itemBuilder: (_, i) => _bubble(_msgs[i]),
    );
  }

  Widget _bubble(_Msg m) {
    final isMe = m.who == 'me';
    return Align(
      alignment: isMe ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.72),
        decoration: isMe
            ? BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppTheme.lightPink, AppTheme.primaryPink],
                ),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(18),
                  topRight: Radius.circular(18),
                  bottomLeft: Radius.circular(18),
                  bottomRight: Radius.circular(4),
                ),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryPink.withOpacity(0.25),
                    blurRadius: 12, offset: const Offset(0, 4),
                  ),
                ],
              )
            : BoxDecoration(
                color: Colors.white.withOpacity(0.65),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(4),
                  topRight: Radius.circular(18),
                  bottomLeft: Radius.circular(18),
                  bottomRight: Radius.circular(18),
                ),
                border: Border.all(color: Colors.white.withOpacity(0.6)),
              ),
        child: Text(
          m.text.isEmpty && _busy && !isMe ? '正在输入…' : m.text,
          style: TextStyle(
            fontSize: 14.5, height: 1.5,
            color: isMe ? Colors.white : AppTheme.textPrimary,
          ),
        ),
      ),
    );
  }

  Widget _inputBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      child: Row(
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.6),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: Colors.white.withOpacity(0.6)),
              ),
              child: TextField(
                controller: _input,
                enabled: !_busy,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                decoration: const InputDecoration(
                  hintText: '说点什么呀～',
                  hintStyle: TextStyle(color: AppTheme.textLight, fontSize: 14),
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: _busy ? null : _send,
            child: Container(
              width: 48, height: 48,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppTheme.lightPink, AppTheme.primaryPink],
                ),
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white.withOpacity(0.5), width: 1.5),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryPink.withOpacity(0.35),
                    blurRadius: 12, offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: const Icon(Icons.send_rounded, color: Colors.white, size: 20),
            ),
          ),
        ],
      ),
    );
  }
}

class _Msg {
  final String who;
  final String text;
  _Msg(this.who, this.text);
}
