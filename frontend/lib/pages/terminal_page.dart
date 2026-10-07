import 'package:flutter/material.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling.pb.dart' as pb;
import '../theme/theme.dart';
import '../widgets/terminal_panel.dart';
import '../widgets/file_explorer.dart';
import '../widgets/code_viewer.dart';

class TerminalPage extends StatefulWidget {
  const TerminalPage({super.key});
  @override
  State<TerminalPage> createState() => _TerminalPageState();
}

class _TerminalPageState extends State<TerminalPage> with SingleTickerProviderStateMixin {
  late final TabController _tabCtrl;
  pb.FileContent? _file;
  bool _loadingFile = false;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  Future<void> _onFileTap(pb.FileItem item) async {
    setState(() => _loadingFile = true);
    try {
      final content = await XlClient.fastCall(
        (s) => s.fileRead(pb.FileReadRequest(path: item.path)),
        label: 'fileRead',
      );
      if (!mounted) return;
      setState(() {
        _file = content;
        _loadingFile = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _loadingFile = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('读取失败: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Scaffold(
      backgroundColor: p.bg,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: p.text1),
          onPressed: () => Navigator.of(context).maybePop(),
        ),
        title: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: AppTheme.brandOrb(context, size: 32),
              child: Icon(Icons.terminal_rounded, size: 16, color: p.btnInk),
            ),
            const SizedBox(width: 12),
            Text('开发者工具',
                style: TextStyle(
                  fontSize: XlFont.h5,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                  letterSpacing: XlLetterSpacing.normal,
                )),
          ],
        ),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: Container(
              decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
              padding: const EdgeInsets.all(4),
              child: TabBar(
                controller: _tabCtrl,
                indicator: BoxDecoration(
                  gradient: p.btnFace,
                  borderRadius: BorderRadius.circular(XlRadius.pill),
                ),
                indicatorSize: TabBarIndicatorSize.tab,
                dividerColor: Colors.transparent,
                labelColor: p.isDark ? p.btnInk : Colors.white,
                unselectedLabelColor: p.text2,
                labelStyle: const TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  letterSpacing: XlLetterSpacing.wider,
                ),
                unselectedLabelStyle: const TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w600,
                  letterSpacing: XlLetterSpacing.wider,
                ),
                tabs: const [
                  Tab(text: '终端', height: 36),
                  Tab(text: '文件浏览器', height: 36),
                ],
              ),
            ),
          ),
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: TabBarView(
          controller: _tabCtrl,
          children: [
            const TerminalPanel(),
            _fileBrowserTab(p),
          ],
        ),
      ),
    );
  }

  Widget _fileBrowserTab(XlPalette p) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Expanded(flex: 4, child: FileExplorer(onFileTap: _onFileTap)),
        const SizedBox(width: 14),
        Expanded(
          flex: 6,
          child: Stack(
            children: [
              CodeViewer(file: _file),
              if (_loadingFile)
                Positioned.fill(
                  child: Container(
                    color: p.scrimSoft.withOpacity(0.3),
                    alignment: Alignment.center,
                    child: const CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
