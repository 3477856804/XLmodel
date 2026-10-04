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

/// 应用主壳
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
      backgroundColor: const Color(0xFFFDD8E5),
      body: SafeArea(
        bottom: false,
        child: IndexedStack(index: _index, children: _pages),
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(
              color: AppTheme.primaryPink.withOpacity(0.15),
              blurRadius: 16, offset: const Offset(0, -4),
            ),
          ],
        ),
        child: BottomNavigationBar(
          currentIndex: _index,
          onTap: (i) => setState(() => _index = i),
          type: BottomNavigationBarType.fixed,
          backgroundColor: Colors.white,
          selectedItemColor: AppTheme.primaryPink,
          unselectedItemColor: AppTheme.textLight,
          selectedFontSize: 11,
          unselectedFontSize: 11,
          showUnselectedLabels: true,
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.chat_bubble_outline),
              activeIcon: Icon(Icons.chat_bubble),
              label: '聊天',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.dashboard_outlined),
              activeIcon: Icon(Icons.dashboard_rounded),
              label: '工作台',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.bubble_chart_outlined),
              activeIcon: Icon(Icons.bubble_chart_rounded),
              label: '训练',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.favorite_border),
              activeIcon: Icon(Icons.favorite_rounded),
              label: '成长',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.settings_outlined),
              activeIcon: Icon(Icons.settings_rounded),
              label: '设置',
            ),
          ],
        ),
      ),
    );
  }
}
