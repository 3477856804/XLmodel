import 'dart:ui';
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

/// 应用主壳：极光背景 + 五页 + 毛玻璃底部导航
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

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
      body: AppTheme.auroraBackground(
        child: SafeArea(
          bottom: false,
          child: IndexedStack(index: _index, children: _pages),
        ),
      ),
      bottomNavigationBar: _glassNavBar(),
    );
  }

  Widget _glassNavBar() {
    return ClipRRect(
      borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 30, sigmaY: 30),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.6),
            border: Border(
              top: BorderSide(color: Colors.white.withOpacity(0.5), width: 1),
            ),
          ),
          child: SafeArea(
            top: false,
            child: SizedBox(
              height: 68,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _navItem(0, Icons.chat_bubble_outline, Icons.chat_bubble, '聊天'),
                  _navItem(1, Icons.dashboard_outlined, Icons.dashboard_rounded, '工作台'),
                  _navItem(2, Icons.bubble_chart_outlined, Icons.bubble_chart_rounded, '训练'),
                  _navItem(3, Icons.favorite_border, Icons.favorite_rounded, '成长'),
                  _navItem(4, Icons.settings_outlined, Icons.settings_rounded, '设置'),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _navItem(int i, IconData outline, IconData filled, String label) {
    final selected = _index == i;
    return GestureDetector(
      onTap: () => setState(() => _index = i),
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
        padding: EdgeInsets.symmetric(
          horizontal: selected ? 14 : 10,
          vertical: 8,
        ),
        decoration: BoxDecoration(
          color: selected ? AppTheme.primaryPink.withOpacity(0.12) : Colors.transparent,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              selected ? filled : outline,
              color: selected ? AppTheme.primaryPink : AppTheme.textLight,
              size: 22,
            ),
            const SizedBox(height: 3),
            Text(
              label,
              style: TextStyle(
                fontSize: 10.5,
                fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                color: selected ? AppTheme.primaryPink : AppTheme.textLight,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
