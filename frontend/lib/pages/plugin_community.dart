import 'dart:convert';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../widgets/plugin_store.dart';

class PluginCommunityPage extends StatefulWidget {
  const PluginCommunityPage({super.key});
  @override
  State<PluginCommunityPage> createState() => _PluginCommunityPageState();
}

class _PluginCommunityPageState extends State<PluginCommunityPage> {
  bool _loading = true;
  bool _online = false;
  final List<Map<String, dynamic>> _plugins = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final reply = await XlClient.stub.command('plugin:market');
      final decoded = jsonDecode(reply.output);
      final list = (decoded['plugins'] as List?) ?? [];
      if (!mounted) return;
      setState(() {
        _online = true;
        _plugins
          ..clear()
          ..addAll(list.map((e) => Map<String, dynamic>.from(e as Map)));
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _online = false;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Scaffold(
      backgroundColor: p.bg,
      body: Stack(
        children: [
          Positioned.fill(child: AppTheme.aurora(context, child: const SizedBox.shrink())),
          Column(
            children: [
              _appBar(p),
              Expanded(child: _body(p)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _appBar(XlPalette p) {
    return SafeArea(
      bottom: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(10, 8, 16, 8),
        child: Row(
          children: [
            _Pressable(
              onTap: () => Navigator.pop(context),
              child: Container(
                width: 38,
                height: 38,
                decoration: AppTheme.neuXs(context, r: XlRadius.md),
                child: Icon(Icons.arrow_back_rounded, size: 18, color: p.text1),
              ),
            ),
            const SizedBox(width: 12),
            ShaderMask(
              shaderCallback: (b) => p.gradText.createShader(b),
              child: const Text('小凌社区',
                  style: TextStyle(
                    fontSize: XlFont.h4,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
            ),
            const Spacer(),
            Container(
              width: 38,
              height: 38,
              decoration: AppTheme.brandOrb(context, size: 38),
              child: Icon(Icons.forum_rounded, size: 17, color: p.btnInk),
            ),
          ],
        ),
      ),
    );
  }

  Widget _body(XlPalette p) {
    if (_loading) return _loadingView(p);
    if (!_online) return _offlineView(p);
    if (_plugins.isEmpty) return _emptyCommunity(p);
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _header(p),
          const SizedBox(height: 16),
          const PluginStore(),
        ],
      ),
    );
  }

  Widget _header(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('插件市场',
            style: TextStyle(
              fontSize: XlFont.h6,
              fontWeight: FontWeight.w800,
              color: p.text1,
              letterSpacing: XlLetterSpacing.normal,
            )),
        const SizedBox(height: 4),
        Text('共 ${_plugins.length} 个本地插件，全部来自磁盘真实清单',
            style: TextStyle(
              fontSize: XlFont.captionSm,
              color: p.text2,
              fontWeight: FontWeight.w500,
            )),
      ],
    );
  }

  Widget _emptyCommunity(XlPalette p) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 76,
              height: 76,
              decoration: AppTheme.brandOrbLg(context, size: 76),
              child: Icon(Icons.forum_rounded, size: 34, color: p.btnInk),
            ),
            const SizedBox(height: 18),
            ShaderMask(
              shaderCallback: (b) => p.gradText.createShader(b),
              child: const Text('社区建设中',
                  style: TextStyle(
                    fontSize: XlFont.h4,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
            ),
            const SizedBox(height: 10),
            Text('欢迎贡献插件',
                style: TextStyle(
                  fontSize: XlFont.h6,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                )),
            const SizedBox(height: 6),
            Text('把你写的 Python 插件放进插件目录，写入 manifest.json 即可被发现',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text2,
                  height: XlLineHeight.relaxed,
                  fontWeight: FontWeight.w500,
                )),
          ],
        ),
      ),
    );
  }

  Widget _offlineView(XlPalette p) {
    return Center(
      child: Container(
        margin: const EdgeInsets.all(32),
        padding: const EdgeInsets.all(36),
        decoration: AppTheme.neu(context, r: XlRadius.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 60,
              height: 60,
              decoration: AppTheme.brandOrb(context, size: 60),
              child: Icon(Icons.link_off_rounded, size: 26, color: p.btnInk),
            ),
            const SizedBox(height: 16),
            Text('插件服务未连接',
                style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
            const SizedBox(height: 6),
            Text('请确认后端已启动后重试',
                style: TextStyle(fontSize: XlFont.captionSm, color: p.text2, fontWeight: FontWeight.w500)),
            const SizedBox(height: 16),
            _Pressable(
              onTap: () {
                setState(() => _loading = true);
                _load();
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 9),
                decoration: AppTheme.btn(context, r: XlRadius.pill),
                child: Text('重试',
                    style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w800, color: p.btnInk, letterSpacing: XlLetterSpacing.wider)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _loadingView(XlPalette p) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      padding: const EdgeInsets.all(26),
      mainAxisSpacing: 14,
      crossAxisSpacing: 14,
      childAspectRatio: 1.5,
      children: [
        for (int i = 0; i < 4; i++)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: AppTheme.neu(context, r: XlRadius.xl),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(width: 40, height: 40, decoration: BoxDecoration(color: p.surfaceLo, shape: BoxShape.circle)),
                const SizedBox(height: 14),
                Container(width: 90, height: 12, decoration: BoxDecoration(color: p.surfaceLo, borderRadius: BorderRadius.circular(6))),
                const SizedBox(height: 8),
                Container(width: double.infinity, height: 8, decoration: BoxDecoration(color: p.surfaceLo, borderRadius: BorderRadius.circular(4))),
              ],
            ),
          ),
      ],
    );
  }
}

class _Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  const _Pressable({required this.child, this.onTap});
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
      onTapCancel: widget.onTap == null ? null : () => setState(() => _down = false),
      onTap: widget.onTap,
      child: AnimatedScale(
        scale: _down ? 0.96 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: widget.child,
      ),
    );
  }
}
