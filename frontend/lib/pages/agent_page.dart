import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../widgets/agent_panel.dart';
import '../widgets/code_search_panel.dart';

class AgentPage extends StatefulWidget {
  const AgentPage({super.key});
  @override
  State<AgentPage> createState() => _AgentPageState();
}

class _AgentPageState extends State<AgentPage> with TickerProviderStateMixin {
  late final TabController _tabCtrl;

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
              _header(p),
              Expanded(
                child: TabBarView(
                  controller: _tabCtrl,
                  children: const [
                    AgentPanel(),
                    CodeSearchPanel(),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _header(XlPalette p) {
    return Container(
      padding: EdgeInsets.only(top: MediaQuery.of(context).padding.top),
      decoration: BoxDecoration(
        gradient: p.navFace,
        border: Border(bottom: BorderSide(color: p.divider, width: 1)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              const SizedBox(width: 8),
              _backBtn(p),
              Expanded(
                child: ShaderMask(
                  shaderCallback: (b) => p.gradText.createShader(b),
                  child: Text('Agent 工作台',
                      style: TextStyle(
                        fontSize: XlFont.h5,
                        fontWeight: FontWeight.w800,
                        color: p.text1,
                        letterSpacing: XlLetterSpacing.normal,
                      )),
                ),
              ),
              Icon(Icons.auto_awesome_rounded, size: 18, color: p.pink),
              const SizedBox(width: 16),
            ],
          ),
          TabBar(
            controller: _tabCtrl,
            labelColor: p.text1,
            unselectedLabelColor: p.text3,
            labelStyle: const TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w800, letterSpacing: XlLetterSpacing.wide),
            unselectedLabelStyle: const TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w600, letterSpacing: XlLetterSpacing.wide),
            indicatorSize: TabBarIndicatorSize.label,
            indicator: UnderlineTabIndicator(
              borderSide: BorderSide(color: p.pink, width: 2.5),
              insets: const EdgeInsets.symmetric(horizontal: 28),
            ),
            tabs: const [
              Tab(text: 'Agent 任务'),
              Tab(text: '代码搜索'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _backBtn(XlPalette p) {
    return IconButton(
      onPressed: () => Navigator.of(context).maybePop(),
      icon: Icon(Icons.arrow_back_rounded, size: 20, color: p.text1),
      tooltip: '返回',
    );
  }
}
