import 'package:flutter/material.dart';
import 'theme/theme.dart';
import 'pages/splash_page.dart';
import 'pages/chat_page.dart';
import 'pages/dashboard_page.dart';
import 'pages/training_page.dart';
import 'pages/growth_page.dart';
import 'pages/settings_page.dart';

void main() => runApp(const XiaoLingApp());

class XiaoLingApp extends StatelessWidget {
  const XiaoLingApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '小凌',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: const SplashPage(),
      routes: {'/home': (_) => const HomeShell()},
    );
  }
}

/// 应用主壳：左侧边栏 + 内容区
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _titles = ['聊天', '工作台', '训练', '成长', '设置'];
  static const _icons = [
    Icons.chat_bubble_outline,
    Icons.dashboard_outlined,
    Icons.bubble_chart_outlined,
    Icons.favorite_outline,
    Icons.settings_outlined,
  ];
  static const _iconsActive = [
    Icons.chat_bubble,
    Icons.dashboard_rounded,
    Icons.bubble_chart_rounded,
    Icons.favorite_rounded,
    Icons.settings_rounded,
  ];

  final _pages = const [
    ChatPage(),
    DashboardPage(),
    TrainingPage(),
    GrowthPage(),
    SettingsPage(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF5F8),
      body: Row(
        children: [
          _buildSidebar(),
          Expanded(child: _pages[_index]),
        ],
      ),
    );
  }

  Widget _buildSidebar() {
    return Container(
      width: 200,
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.5),
        border: Border(
          right: BorderSide(color: AppTheme.primaryPink.withOpacity(0.08), width: 1),
        ),
      ),
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
              child: Row(
                children: [
                  Container(
                    width: 34, height: 34,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(colors: [AppTheme.primaryPink, AppTheme.gold]),
                      borderRadius: BorderRadius.circular(10),
                      boxShadow: [BoxShadow(color: AppTheme.primaryPink.withOpacity(0.25), blurRadius: 12, offset: const Offset(0,3))],
                    ),
                    child: const Icon(Icons.auto_awesome, color: Colors.white, size: 18),
                  ),
                  const SizedBox(width: 10),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('小凌', style: TextStyle(color: Color(0xFF1a1a1a), fontWeight: FontWeight.w700, fontSize: 15)),
                      Text('XIAOLING', style: TextStyle(color: AppTheme.gold, fontSize: 9, letterSpacing: 2, fontWeight: FontWeight.w500)),
                    ],
                  ),
                ],
              ),
            ),
            for (int i = 0; i < 5; i++)
              _navItem(i, _icons[i], _iconsActive[i], _titles[i]),
            const Spacer(),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text('v0.0.1 · Flutter+gRPC', style: TextStyle(color: Colors.black.withOpacity(0.25), fontSize: 10, letterSpacing: 1)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _navItem(int i, IconData icon, IconData activeIcon, String label) {
    final selected = _index == i;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
      child: InkWell(
        onTap: () => setState(() => _index = i),
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            gradient: selected
                ? LinearGradient(colors: [AppTheme.primaryPink.withOpacity(0.12), AppTheme.gold.withOpacity(0.06)])
                : null,
            borderRadius: BorderRadius.circular(10),
            border: selected ? Border.all(color: AppTheme.primaryPink.withOpacity(0.15)) : null,
          ),
          child: Row(
            children: [
              Icon(selected ? activeIcon : icon, size: 18, color: selected ? AppTheme.primaryPink : Colors.black.withOpacity(0.45)),
              const SizedBox(width: 12),
              Text(label, style: TextStyle(fontSize: 13.5, color: selected ? AppTheme.primaryPink : Colors.black.withOpacity(0.45), fontWeight: selected ? FontWeight.w600 : FontWeight.normal)),
            ],
          ),
        ),
      ),
    );
  }
}
