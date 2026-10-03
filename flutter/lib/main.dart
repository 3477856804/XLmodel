// 小凌 · Flutter UI 客户端（v0.0.3 新架构）
// 架构：Flutter(UI) ──gRPC──> Python 后端（rpc/server.py）
//
// 运行前：
//   1. 先启动 Python 后端：python3 -m rpc.server
//   2. 生成 Dart gRPC 代码：cd flutter && ./gen_dart_grpc.sh
//   3. flutter run

import 'package:flutter/material.dart';
import 'package:grpc/grpc.dart';

import 'grpc/xiaoling.pbgrpc.dart';

void main() => runApp(const XiaoLingApp());

// ---------------- 粉色少女风主题 ----------------
class XL {
  static const bgTop    = Color(0xFFFFF5F8);
  static const bgMid    = Color(0xFFFDE8EF);
  static const bgBottom = Color(0xFFFBDCE6);
  static const accent   = Color(0xFFE85A8A);
  static const accentHov= Color(0xFFFF7AA2);
  static const soft     = Color(0xFFFFE0EA);
  static const textMain = Color(0xFF4A3A40);
  static const textMuted= Color(0xFFB09AA2);
  static const card     = Colors.white;
}

class XiaoLingApp extends StatelessWidget {
  const XiaoLingApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '小凌',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: XL.accent,
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: XL.bgTop,
        fontFamily: 'PingFang SC',
      ),
      home: const ChatPage(),
    );
  }
}

// ---------------- 一条消息 ----------------
class Msg {
  final String who;     // 'me' / 'xl'
  final String text;
  Msg(this.who, this.text);
}

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});
  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<Msg> _msgs = [];
  bool _busy = false;
  String _status = '连接中…';
  late XiaoLingClient _stub;
  late ClientChannel _chan;

  @override
  void initState() {
    super.initState();
    _chan = ClientChannel('localhost',
        port: 50051,
        options: const ChannelOptions(
          connectTimeout: Duration(seconds: 2),
        ));
    _stub = XiaoLingClient(_chan);
    _hello();
  }

  Future<void> _hello() async {
    try {
      final s = await _stub.getStatus(StatusRequest());
      setState(() => _status = 'v${s.version} · ${s.stage}');
    } catch (_) {
      setState(() => _status = '未连接后端');
    }
    setState(() => _msgs.add(Msg('xl', '我在呢～想聊什么都可以。')));
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _busy) return;
    _input.clear();
    setState(() {
      _msgs.add(Msg('me', text));
      _busy = true;
      _msgs.add(Msg('xl', '')); // 占位，流式填充
    });
    _scrollToBottom();
    try {
      final stream = _stub.chat(ChatRequest(text: text));
      final xl = _msgs.last;
      await for (final chunk in stream) {
        if (chunk.delta.isNotEmpty) {
          setState(() => xl.text.isNotEmpty
              ? _msgs[_msgs.length - 1] = Msg('xl', xl.text + chunk.delta)
              : null);
          // 直接改最后一条
          _msgs[_msgs.length - 1] = Msg('xl',
              (_msgs[_msgs.length - 1].text) + chunk.delta);
          setState(() {});
          _scrollToBottom();
        }
        if (chunk.done) break;
      }
    } catch (e) {
      setState(() {
        _msgs[_msgs.length - 1] = Msg('xl', '出错了：$e');
      });
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
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter, end: Alignment.bottomCenter,
            colors: [XL.bgTop, XL.bgMid, XL.bgBottom],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              _header(),
              Expanded(child: _chatList()),
              _inputBar(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _header() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        children: [
          const Text('🌸', style: TextStyle(fontSize: 26)),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('小凌',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700,
                      color: XL.textMain, letterSpacing: 1)),
              Text(_status, style: const TextStyle(fontSize: 11, color: XL.textMuted)),
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

  Widget _bubble(Msg m) {
    final isMe = m.who == 'me';
    return Align(
      alignment: isMe ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.75),
        decoration: BoxDecoration(
          color: isMe ? XL.accent : Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: isMe ? null : Border.all(color: const Color(0xFFFFB6CD)),
        ),
        child: Text(
          m.text.isEmpty && _busy && !isMe ? '…' : m.text,
          style: TextStyle(
            fontSize: 14, height: 1.5,
            color: isMe ? Colors.white : XL.textMain,
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
                color: Colors.white,
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: const Color(0xFFF0D4DE)),
              ),
              child: TextField(
                controller: _input,
                enabled: !_busy,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                decoration: const InputDecoration(
                  hintText: '说点什么呀～',
                  hintStyle: TextStyle(color: XL.textMuted),
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: _busy ? null : _send,
            child: Container(
              width: 46, height: 46,
              decoration: BoxDecoration(
                color: _busy ? const Color(0xFFE8C8D2) : XL.accent,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.send_rounded, color: Colors.white, size: 20),
            ),
          ),
        ],
      ),
    );
  }
}
