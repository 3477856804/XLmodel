import 'dart:ui';
import 'dart:io';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'theme/theme.dart';
import 'pages/splash_page.dart';
import 'pages/chat_page.dart';
import 'pages/dashboard_page.dart';
import 'pages/training_page.dart';
import 'pages/growth_page.dart';
import 'pages/settings_page.dart';
import 'pages/model_store_page.dart';
import 'pages/plugins_page.dart';
import 'widgets/notif_panel.dart';
import 'widgets/persona_panel.dart';
import 'rpc/client.dart';
import 'rpc/xiaoling_client_ext.dart';
import 'rpc/xiaoling_ext.dart';

Process? _backendProc;

Future<void> _startBackend() async {
  if (Platform.environment['FLUTTER_TEST'] == '1') return;
  try {
    final exeDir = File(Platform.resolvedExecutable).parent;
    final backendPath = Platform.isWindows
        ? '${exeDir.path}${Platform.pathSeparator}backend.exe'
        : '${exeDir.path}${Platform.pathSeparator}backend';
    final f = File(backendPath);
    if (!await f.exists()) return;
    _backendProc = await Process.start(
      backendPath,
      ['--port', '50051'],
      workingDirectory: exeDir.path,
      mode: ProcessStartMode.detached,
    );
  } catch (_) {}
}

Future<void> _killBackend() async {
  try {
    _backendProc?.kill(ProcessSignal.sigterm);
    await Future.delayed(const Duration(milliseconds: 200));
    _backendProc?.kill(ProcessSignal.sigkill);
  } catch (_) {}
}

Future<void> _probeBackend() async {
  if (Platform.environment['FLUTTER_TEST'] == '1') return;
  try {
    await XlClient.ping();
    XlClient.setAutoReconnect(true);
  } catch (_) {
    XlClient.setAutoReconnect(true);
  }
}

void main() {
  runZonedGuarded<Future<void>>(() async {
    WidgetsFlutterBinding.ensureInitialized();
    FlutterError.onError = (FlutterErrorDetails details) {
      FlutterError.presentError(details);
    };
    PlatformDispatcher.instance.onError = (Object error, StackTrace stack) {
      return true;
    };
    SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      systemNavigationBarColor: Colors.transparent,
    ));
    try {
      await _startBackend();
      await Future.delayed(const Duration(milliseconds: 800));
      await _probeBackend();
    } catch (_) {}
    runApp(const XiaoLingApp());
  }, (Object error, StackTrace stack) {
    runApp(_ErrorApp(error: error));
  });
}

class _FadeScaleRoute<T> extends PageRouteBuilder<T> {
  _FadeScaleRoute({required WidgetBuilder builder, RouteSettings? settings})
      : super(
          settings: settings,
          transitionDuration: XlDuration.slow,
          reverseTransitionDuration: XlDuration.normal,
          pageBuilder: (context, animation, secondaryAnimation) => builder(context),
          transitionsBuilder: (context, animation, secondaryAnimation, child) {
            final curved = CurvedAnimation(parent: animation, curve: XlCurve.easeOut);
            return FadeTransition(
              opacity: curved,
              child: ScaleTransition(
                scale: Tween<double>(begin: 0.98, end: 1.0).animate(curved),
                child: child,
              ),
            );
          },
        );
}

class _ErrorApp extends StatelessWidget {
  final Object error;
  const _ErrorApp({required this.error});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '小凌',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.dark,
      home: Scaffold(
        backgroundColor: const Color(0xFF1A1A2E),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0.0, end: 1.0),
                  duration: XlDuration.slower,
                  curve: XlCurve.easeOut,
                  builder: (_, t, __) {
                    return Stack(
                      alignment: Alignment.center,
                      children: [
                        Container(
                          width: 120 + t * 40,
                          height: 120 + t * 40,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: RadialGradient(
                              colors: [
                                const Color(0xFFFF6FA5).withOpacity(0.20 * t),
                                const Color(0xFFE8C46A).withOpacity(0.08 * t),
                                Colors.transparent,
                              ],
                            ),
                          ),
                        ),
                        Container(
                          width: 64,
                          height: 64,
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [Color(0xFFFF6FA5), Color(0xFFE8C46A)],
                            ),
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color: const Color(0xFFFF6FA5).withOpacity(0.4 * t),
                                blurRadius: 24,
                                spreadRadius: -4,
                              ),
                            ],
                          ),
                          child: const Icon(Icons.auto_awesome_rounded, color: Colors.white, size: 28),
                        ),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 24),
                const Text(
                  '启动遇到问题',
                  style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                Text(
                  '请尝试重启应用，或检查后端服务是否正常运行。',
                  style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 14),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: () {
                    runApp(const XiaoLingApp());
                  },
                  child: const Text('重试'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class XiaoLingApp extends StatefulWidget {
  const XiaoLingApp({super.key});
  @override
  State<XiaoLingApp> createState() => _XiaoLingAppState();
}

class _XiaoLingAppState extends State<XiaoLingApp> with WidgetsBindingObserver {
  ThemeMode _mode = ThemeMode.dark;
  int _bootIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    try {
      PlatformDispatcher.instance;
    } catch (_) {}
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangePlatformBrightness() {}

  void toggleTheme() {
    setState(() {
      _mode = _mode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
      _bootIndex++;
    });
  }

  bool get isDark => _mode == ThemeMode.dark;

  @override
  Widget build(BuildContext context) {
    final routeBuilders = <String, WidgetBuilder>{
      '/home': (_) => HomeShell(onToggleTheme: toggleTheme, isDark: isDark),
    };
    return MaterialApp(
      title: '晓灵 v0.0.1',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: _mode,
      themeAnimationDuration: XlDuration.slow,
      themeAnimationCurve: XlCurve.standard,
      home: SplashPage(onToggleTheme: toggleTheme),
      routes: routeBuilders,
      onGenerateRoute: (settings) {
        final builder = routeBuilders[settings.name];
        if (builder != null) {
          return _FadeScaleRoute(builder: builder, settings: settings);
        }
        return null;
      },
      builder: (context, child) {
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(
              MediaQuery.of(context).textScaler.scale(1.0).clamp(0.9, 1.3),
            ),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}

class HomeShell extends StatefulWidget {
  final VoidCallback onToggleTheme;
  final bool isDark;
  const HomeShell({super.key, required this.onToggleTheme, this.isDark = false});
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> with TickerProviderStateMixin {
  int _index = 0;
  bool _sidebarCollapsed = false;
  bool _searchOpen = false;
  bool _notifOpen = false;
  bool _personaOpen = false;
  final _searchCtrl = TextEditingController();
  final _searchFocus = FocusNode();

  /// 铃铛红点用的未读提醒数。null =尚未拉到。
  int? _unreadReminders;
  Timer? _reminderTimer;
  late AnimationController _glowCtrl;
  late AnimationController _sidebarCtrl;
  late Animation<double> _sidebarAnim;
  final List<int> _history = [];

  static const _titles = ['聊天', '工作台', '训练', '成长', '设置'];
  static const _subtitles = [
    '和小凌说说话',
    '一眼看全所有状态',
    'LoRA 微调面板',
    '她的成长轨迹',
    '一切都可以调',
  ];
  static const _icons = [
    Icons.chat_bubble_outline_rounded,
    Icons.grid_view_outlined,
    Icons.auto_graph_rounded,
    Icons.favorite_outline_rounded,
    Icons.tune_rounded,
  ];
  static const _iconsActive = [
    Icons.chat_bubble_rounded,
    Icons.grid_view_rounded,
    Icons.auto_graph_rounded,
    Icons.favorite_rounded,
    Icons.tune_rounded,
  ];
  static const _iconColors = ['pink', 'gold', 'violet', 'green', 'pink'];
  static const _keys = ['1', '2', '3', '4', '5'];

  @override
  void initState() {
    super.initState();
    _glowCtrl = AnimationController(
      duration: const Duration(seconds: 20),
      vsync: this,
    )..repeat(reverse: true);
    _sidebarCtrl = AnimationController(
      duration: XlDuration.slow,
      vsync: this,
      value: 1.0,
    );
    _sidebarAnim = CurvedAnimation(
      parent: _sidebarCtrl,
      curve: XlCurve.springSoft,
    );
    // 轮询未读提醒，驱动铃铛红点
    _refreshUnread();
    _reminderTimer = Timer.periodic(
      const Duration(seconds: 30),
      (_) => _refreshUnread(),
    );
  }

  @override
  void dispose() {
    _reminderTimer?.cancel();
    _glowCtrl.dispose();
    _sidebarCtrl.dispose();
    _searchCtrl.dispose();
    _searchFocus.dispose();
    super.dispose();
  }

  /// 拉取未读提醒数。红点是否亮完全由真实数据决定，不再是静态装饰。
  Future<void> _refreshUnread() async {
    try {
      final r = await XlClient.stub.safe(() => XlClient.stub.fetchReminders());
      if (!mounted || r == null) return;
      if (r.unread != _unreadReminders) {
        setState(() => _unreadReminders = r.unread);
      }
    } catch (_) {
      // 后端还没起来时静默失败，下次轮询再试
    }
  }

  void _closeOverlays() {
    setState(() {
      _searchOpen = false;
      _notifOpen = false;
      _personaOpen = false;
    });
  }

  void _navigate(int i) {
    if (i == _index) return;
    _history.add(_index);
    setState(() => _index = i);
  }

  void _toggleSidebar() {
    setState(() => _sidebarCollapsed = !_sidebarCollapsed);
    if (_sidebarCollapsed) {
      _sidebarCtrl.reverse();
    } else {
      _sidebarCtrl.forward();
    }
  }

  void _toggleSearch() {
    setState(() {
      _searchOpen = !_searchOpen;
      if (_searchOpen) {
        _notifOpen = false;
        _personaOpen = false;
      }
    });
    if (_searchOpen) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _searchFocus.requestFocus();
      });
    }
  }

  Color _colorOf(XlPalette p, String name) {
    switch (name) {
      case 'pink':
        return p.pink;
      case 'gold':
        return p.gold;
      case 'violet':
        return p.violet;
      case 'green':
        return p.green;
      default:
        return p.pink;
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final pages = <Widget>[
      const ChatPage(),
      DashboardPage(
        onNavigate: _navigate,
        onOpenModelStore: () => _navigate(5),
        onOpenPlugins: () => _navigate(6),
      ),
      const TrainingPage(),
      const GrowthPage(),
      const SettingsPage(),
      const ModelStorePage(),
      const PluginsPage(),
    ];

    return Shortcuts(
      shortcuts: <ShortcutActivator, Intent>{
        const SingleActivator(LogicalKeyboardKey.digit1, control: true): const _NavIntent(0),
        const SingleActivator(LogicalKeyboardKey.digit2, control: true): const _NavIntent(1),
        const SingleActivator(LogicalKeyboardKey.digit3, control: true): const _NavIntent(2),
        const SingleActivator(LogicalKeyboardKey.digit4, control: true): const _NavIntent(3),
        const SingleActivator(LogicalKeyboardKey.digit5, control: true): const _NavIntent(4),
        const SingleActivator(LogicalKeyboardKey.keyB, control: true): const _ToggleSidebarIntent(),
        const SingleActivator(LogicalKeyboardKey.keyK, control: true): const _SearchIntent(),
        const SingleActivator(LogicalKeyboardKey.keyT, control: true): const _ThemeIntent(),
        const SingleActivator(LogicalKeyboardKey.escape): const _CloseOverlayIntent(),
      },
      child: Actions(
        actions: <Type, Action<Intent>>{
          _NavIntent: CallbackAction<_NavIntent>(
            onInvoke: (intent) {
              _navigate(intent.index);
              return null;
            },
          ),
          _ToggleSidebarIntent: CallbackAction<_ToggleSidebarIntent>(
            onInvoke: (_) {
              _toggleSidebar();
              return null;
            },
          ),
          _SearchIntent: CallbackAction<_SearchIntent>(
            onInvoke: (_) {
              _toggleSearch();
              return null;
            },
          ),
          _ThemeIntent: CallbackAction<_ThemeIntent>(
            onInvoke: (_) {
              widget.onToggleTheme();
              return null;
            },
          ),
          _CloseOverlayIntent: CallbackAction<_CloseOverlayIntent>(
            onInvoke: (_) {
              if (_searchOpen || _notifOpen || _personaOpen) {
                _closeOverlays();
              }
              return null;
            },
          ),
        },
        child: Focus(
          autofocus: true,
          child: Scaffold(
            backgroundColor: p.bg,
            body: Stack(
              children: [
                _ambientBackground(p),
                Row(
                  children: [
                    AnimatedBuilder(
                      animation: _sidebarAnim,
                      builder: (context, _) => _sidebar(p, pages),
                    ),
                    Expanded(child: _mainArea(p, pages)),
                  ],
                ),
                if (_searchOpen) _searchOverlay(p),
                if (_notifOpen)
                  NotifPanel(
                    onClose: _closeOverlays,
                    onOpenTraining: () => _navigate(2),
                  ),
                if (_personaOpen)
                  PersonaPanel(onClose: _closeOverlays),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _ambientBackground(XlPalette p) {
    return AnimatedBuilder(
      animation: _glowCtrl,
      builder: (context, _) {
        final t = _glowCtrl.value;
        return Positioned.fill(
          child: IgnorePointer(
            child: CustomPaint(
              painter: _AmbientPainter(p: p, t: t),
            ),
          ),
        );
      },
    );
  }

  Widget _sidebar(XlPalette p, List<Widget> pages) {
    final width = lerpDouble(220, 78, 1 - _sidebarAnim.value)!.toDouble();
    return Container(
      width: width,
      decoration: BoxDecoration(
        gradient: p.sidebarFace,
        border: Border(right: BorderSide(color: p.edge, width: 1)),
      ),
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _sidebarHeader(p),
            const SizedBox(height: 12),
            _sidebarDivider(p),
            const SizedBox(height: 12),
            Expanded(child: _sidebarNav(p)),
            const SizedBox(height: 12),
            _sidebarDivider(p),
            _sidebarFooter(p),
          ],
        ),
      ),
    );
  }

  Widget _sidebarHeader(XlPalette p) {
    final collapsed = _sidebarAnim.value < 0.5;
    return Padding(
      padding: EdgeInsets.fromLTRB(collapsed ? 16 : 18, 22, collapsed ? 16 : 18, 12),
      child: Row(
        mainAxisAlignment: collapsed ? MainAxisAlignment.center : MainAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              gradient: p.gradBrand,
              borderRadius: BorderRadius.circular(XlRadius.md),
              border: Border.all(color: Colors.white.withOpacity(0.35), width: 1),
              boxShadow: [...p.raisedXs, BoxShadow(color: p.pink.withOpacity(0.4), blurRadius: 16, spreadRadius: -3)],
            ),
            child: Icon(Icons.auto_awesome_rounded, color: p.btnInk, size: 18),
          ),
          if (!collapsed) ...[
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('小凌', style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.normal)),
                  const SizedBox(height: 2),
                  Text('XIAOLING', style: TextStyle(fontSize: XlFont.micro, fontWeight: FontWeight.w700, color: p.gold, letterSpacing: XlLetterSpacing.mega)),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _sidebarDivider(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Container(height: 1, decoration: BoxDecoration(gradient: p.dividerGrad)),
    );
  }

  Widget _sidebarNav(XlPalette p) {
    final collapsed = _sidebarAnim.value < 0.5;
    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 10),
      children: [
        for (int i = 0; i < _titles.length; i++) _navItem(p, i, collapsed),
        const SizedBox(height: 8),
        if (!collapsed) Padding(
          padding: const EdgeInsets.fromLTRB(8, 12, 8, 6),
          child: Text('MORE', style: TextStyle(fontSize: XlFont.micro, fontWeight: FontWeight.w800, color: p.decor, letterSpacing: XlLetterSpacing.ultra)),
        ),
        _extraNavItem(p, 5, Icons.shopping_bag_outlined, '模型商店', p.gold, collapsed),
        _extraNavItem(p, 6, Icons.extension_outlined, '插件管理', p.green, collapsed),
      ],
    );
  }

  Widget _navItem(XlPalette p, int i, bool collapsed) {
    final selected = _index == i;
    final color = _colorOf(p, _iconColors[i]);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => _navigate(i),
          borderRadius: BorderRadius.circular(XlRadius.ml),
          splashColor: p.pink.withOpacity(0.08),
          highlightColor: p.pink.withOpacity(0.04),
          child: AnimatedContainer(
            duration: XlDuration.fast,
            curve: XlCurve.standard,
            padding: EdgeInsets.symmetric(horizontal: collapsed ? 0 : 14, vertical: 12),
            decoration: selected
                ? BoxDecoration(
                    color: p.surfaceLo,
                    borderRadius: BorderRadius.circular(XlRadius.ml),
                    border: Border.all(color: p.shDark.withOpacity(p.isDark ? 0.35 : 0.15), width: 1),
                    boxShadow: p.sunkenSm,
                  )
                : const BoxDecoration(),
            child: collapsed
                ? Center(
                    child: _navIcon(p, selected, i, color, 20),
                  )
                : Row(
                    children: [
                      _navIcon(p, selected, i, color, 18),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          _titles[i],
                          style: TextStyle(
                            fontSize: XlFont.bodySm,
                            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                            color: selected ? color : p.text2,
                            letterSpacing: XlLetterSpacing.wide,
                          ),
                        ),
                      ),
                      if (selected)
                        Container(
                          width: 6,
                          height: 6,
                          decoration: BoxDecoration(color: color, shape: BoxShape.circle, boxShadow: [BoxShadow(color: color.withOpacity(0.6), blurRadius: 8, spreadRadius: -1)]),
                        ),
                    ],
                  ),
          ),
        ),
      ),
    );
  }

  Widget _navIcon(XlPalette p, bool selected, int i, Color color, double size) {
    if (selected) {
      return Stack(
        alignment: Alignment.center,
        children: [
          Container(
            width: size + 14,
            height: size + 14,
            decoration: BoxDecoration(
              color: color.withOpacity(p.isDark ? 0.14 : 0.12),
              shape: BoxShape.circle,
            ),
          ),
          Icon(_iconsActive[i], size: size, color: color),
        ],
      );
    }
    return SizedBox(
      width: size + 14,
      height: size + 14,
      child: Icon(_icons[i], size: size, color: p.text2),
    );
  }

  Widget _extraNavItem(XlPalette p, int i, IconData icon, String label, Color color, bool collapsed) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => _navigate(i),
          borderRadius: BorderRadius.circular(XlRadius.ml),
          child: AnimatedContainer(
            duration: XlDuration.fast,
            padding: EdgeInsets.symmetric(horizontal: collapsed ? 0 : 14, vertical: 11),
            child: collapsed
                ? Center(child: Icon(icon, size: 18, color: p.text3))
                : Row(
                    children: [
                      SizedBox(
                        width: 32,
                        height: 32,
                        child: Icon(icon, size: 18, color: color.withOpacity(p.isDark ? 0.85 : 0.75)),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          label,
                          style: TextStyle(fontSize: XlFont.caption, color: p.text3, fontWeight: FontWeight.w500, letterSpacing: XlLetterSpacing.wide),
                        ),
                      ),
                    ],
                  ),
          ),
        ),
      ),
    );
  }

  Widget _sidebarFooter(XlPalette p) {
    final collapsed = _sidebarAnim.value < 0.5;
    return Padding(
      padding: EdgeInsets.fromLTRB(collapsed ? 12 : 16, 12, collapsed ? 12 : 16, 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!collapsed) ...[
            _sidebarThemeToggle(p),
            const SizedBox(height: 10),
          ],
          if (collapsed)
            Center(
              child: GestureDetector(
                onTap: widget.onToggleTheme,
                child: Container(
                  width: 42,
                  height: 42,
                  decoration: AppTheme.neuXs(context, r: XlRadius.md),
                  child: Icon(
                    widget.isDark ? Icons.light_mode_rounded : Icons.dark_mode_rounded,
                    size: 17,
                    color: p.gold,
                  ),
                ),
              ),
            ),
          if (!collapsed) ...[
            _sidebarVersion(p),
          ],
        ],
      ),
    );
  }

  Widget _sidebarThemeToggle(XlPalette p) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: widget.onToggleTheme,
        borderRadius: BorderRadius.circular(XlRadius.md),
        child: AnimatedContainer(
          duration: XlDuration.fast,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          decoration: AppTheme.neuXs(context, r: XlRadius.md),
          child: Row(
            children: [
              AnimatedSwitcher(
                duration: XlDuration.fast,
                transitionBuilder: (child, anim) => RotationTransition(
                  turns: Tween<double>(begin: 0.75, end: 1.0).animate(anim),
                  child: FadeTransition(opacity: anim, child: child),
                ),
                child: Icon(
                  widget.isDark ? Icons.light_mode_rounded : Icons.dark_mode_rounded,
                  key: ValueKey(widget.isDark),
                  size: 16,
                  color: p.gold,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  widget.isDark ? '浅色主题' : '深色主题',
                  style: TextStyle(fontSize: XlFont.captionSm, color: p.text2, fontWeight: FontWeight.w600),
                ),
              ),
              Icon(Icons.chevron_right_rounded, size: 14, color: p.decor),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sidebarVersion(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Row(
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: p.green, shape: BoxShape.circle, boxShadow: [BoxShadow(color: p.green.withOpacity(0.6), blurRadius: 8, spreadRadius: -1)]),
          ),
          const SizedBox(width: 8),
          Text('v0.0.1 · Flutter+gRPC', style: TextStyle(fontSize: XlFont.micro, color: p.decor, letterSpacing: XlLetterSpacing.wider, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _mainArea(XlPalette p, List<Widget> pages) {
    return Column(
      children: [
        _topBar(p),
        Expanded(
          child: AnimatedSwitcher(
            duration: XlDuration.slow,
            switchInCurve: XlCurve.easeOut,
            switchOutCurve: XlCurve.standard,
            transitionBuilder: (child, anim) => FadeTransition(
              opacity: anim,
              child: SlideTransition(
                position: Tween<Offset>(begin: const Offset(0.02, 0), end: Offset.zero).animate(anim),
                child: child,
              ),
            ),
            child: KeyedSubtree(
              key: ValueKey(_index),
              child: pages[_index.clamp(0, pages.length - 1)],
            ),
          ),
        ),
      ],
    );
  }

  Widget _topBar(XlPalette p) {
    return Container(
      height: 76,
      padding: const EdgeInsets.fromLTRB(24, 18, 24, 8),
      child: Row(
        children: [
          _menuBtn(p),
          const SizedBox(width: 12),
          _breadcrumb(p),
          const Spacer(),
          _topSearch(p),
          const SizedBox(width: 10),
          _topNotif(p),
          const SizedBox(width: 10),
          _topAvatar(p),
        ],
      ),
    );
  }

  Widget _menuBtn(XlPalette p) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: _toggleSidebar,
        borderRadius: BorderRadius.circular(XlRadius.md),
        child: Container(
          width: 42,
          height: 42,
          decoration: AppTheme.neuXs(context, r: XlRadius.md),
          child: AnimatedRotation(
            turns: _sidebarCollapsed ? 0.5 : 0,
            duration: XlDuration.normal,
            curve: XlCurve.springSoft,
            child: Icon(Icons.menu_rounded, size: 18, color: p.text2),
          ),
        ),
      ),
    );
  }

  Widget _breadcrumb(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(_titles[_index.clamp(0, _titles.length - 1)], style: TextStyle(fontSize: XlFont.h4, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.normal)),
        const SizedBox(height: 2),
        Text(_subtitles[_index.clamp(0, _subtitles.length - 1)], style: TextStyle(fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w500, letterSpacing: XlLetterSpacing.wider)),
      ],
    );
  }

  Widget _topSearch(XlPalette p) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: _toggleSearch,
        borderRadius: BorderRadius.circular(XlRadius.md),
        child: Container(
          width: 42,
          height: 42,
          decoration: AppTheme.neuXs(context, r: XlRadius.md),
          child: Icon(Icons.search_rounded, size: 18, color: p.text2),
        ),
      ),
    );
  }

  Widget _topNotif(XlPalette p) {
    // 未读提醒数（已到期未确认）。null = 还没拉到，按 0 处理（不显示红点）。
    final unread = _unreadReminders ?? 0;
    return Stack(
      children: [
        Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: () {
              setState(() {
                _notifOpen = true;
                _searchOpen = false;
                _personaOpen = false;
              });
            },
            borderRadius: BorderRadius.circular(XlRadius.md),
            child: Container(
              width: 42,
              height: 42,
              decoration: AppTheme.neuXs(context, r: XlRadius.md),
              child: Icon(Icons.notifications_none_rounded, size: 18, color: p.text2),
            ),
          ),
        ),
        // 红点只在真有未读提醒时显示（此前是写死的静态装饰）
        if (unread > 0)
          Positioned(
            top: 8,
            right: 8,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
              constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
              decoration: BoxDecoration(
                color: p.pink,
                shape: BoxShape.circle,
                border: Border.all(color: p.bg, width: 1.5),
                boxShadow: [
                  BoxShadow(
                      color: p.pink.withOpacity(0.6),
                      blurRadius: 8,
                      spreadRadius: -1)
                ],
              ),
              child: Center(
                child: Text(unread > 99 ? '99+' : '$unread',
                    style: TextStyle(
                        fontSize: 9,
                        height: 1.1,
                        fontWeight: FontWeight.w800,
                        color: p.btnInk)),
              ),
            ),
          ),
      ],
    );
  }

  Widget _topAvatar(XlPalette p) {
    // 此前这里只是个装饰性 Container，连 InkWell 都没有，点击完全无响应
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () {
          setState(() {
            _personaOpen = true;
            _searchOpen = false;
            _notifOpen = false;
          });
        },
        borderRadius: BorderRadius.circular(XlRadius.md),
        child: Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            gradient: p.gradBrand,
            borderRadius: BorderRadius.circular(XlRadius.md),
            border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.35 : 0.5), width: 1.5),
            boxShadow: [
              ...p.raisedXs,
              BoxShadow(color: p.pink.withOpacity(0.35), blurRadius: 14, spreadRadius: -3)
            ],
          ),
          child: Center(
            child: Text('凌',
                style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.btnInk)),
          ),
        ),
      ),
    );
  }

  Widget _searchOverlay(XlPalette p) {
    final items = <_SearchItem>[
      _SearchItem('聊天', '和小凌说话', Icons.chat_bubble_outline_rounded, () => _navigate(0)),
      _SearchItem('工作台', '状态总览', Icons.grid_view_outlined, () => _navigate(1)),
      _SearchItem('训练', 'LoRA 微调', Icons.auto_graph_rounded, () => _navigate(2)),
      _SearchItem('成长', '成长轨迹', Icons.favorite_outline_rounded, () => _navigate(3)),
      _SearchItem('设置', '偏好调整', Icons.tune_rounded, () => _navigate(4)),
      _SearchItem('模型商店', '推荐模型', Icons.shopping_bag_outlined, () => _navigate(5)),
      _SearchItem('插件管理', '扩展功能', Icons.extension_outlined, () => _navigate(6)),
      _SearchItem('切换主题', '深色 / 浅色', Icons.brightness_6_outlined, widget.onToggleTheme),
      _SearchItem('折叠侧边栏', 'Ctrl + B', Icons.view_sidebar_outlined, _toggleSidebar),
    ];
    final q = _searchCtrl.text.trim().toLowerCase();
    final filtered = q.isEmpty
        ? items
        : items.where((it) => it.title.toLowerCase().contains(q) || it.desc.toLowerCase().contains(q)).toList();

    return Positioned.fill(
      child: GestureDetector(
        onTap: () => setState(() => _searchOpen = false),
        child: Container(
          color: p.scrim,
          child: Center(
            child: GestureDetector(
              onTap: () {},
              child: Container(
                width: 520,
                constraints: const BoxConstraints(maxHeight: 520),
                margin: const EdgeInsets.all(24),
                decoration: AppTheme.neuLg(context, r: XlRadius.xxl),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _searchField(p),
                    AppTheme.divider(context),
                    Flexible(
                      child: filtered.isEmpty
                          ? Padding(
                              padding: const EdgeInsets.all(32),
                              child: Text('没有匹配项', style: TextStyle(color: p.text3, fontSize: XlFont.caption)),
                            )
                          : ListView.builder(
                              shrinkWrap: true,
                              padding: const EdgeInsets.all(8),
                              itemCount: filtered.length,
                              itemBuilder: (_, i) => _searchItemTile(p, filtered[i]),
                            ),
                    ),
                    AppTheme.divider(context),
                    _searchFooter(p),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _searchField(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Icon(Icons.search_rounded, size: 20, color: p.pink),
          const SizedBox(width: 12),
          Expanded(
            child: TextField(
              controller: _searchCtrl,
              focusNode: _searchFocus,
              onChanged: (_) => setState(() {}),
              style: TextStyle(fontSize: XlFont.body, color: p.text1),
              decoration: InputDecoration(
                hintText: '搜索页面、功能或操作…',
                hintStyle: TextStyle(color: p.decor, fontSize: XlFont.bodySm),
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.zero,
              ),
            ),
          ),
          GestureDetector(
            onTap: () => setState(() => _searchOpen = false),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: p.surfaceLo,
                borderRadius: BorderRadius.circular(XlRadius.xs),
                border: Border.all(color: p.edge, width: 1),
              ),
              child: Text('ESC', style: TextStyle(fontSize: XlFont.micro, color: p.text3, fontWeight: FontWeight.w700, letterSpacing: XlLetterSpacing.wider)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _searchItemTile(XlPalette p, _SearchItem item) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () {
          item.onTap();
          setState(() => _searchOpen = false);
        },
        borderRadius: BorderRadius.circular(XlRadius.md),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: AppTheme.neuXxs(context, r: XlRadius.sm),
                child: Icon(item.icon, size: 16, color: p.pink),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(item.title, style: TextStyle(fontSize: XlFont.bodySm, color: p.text1, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 1),
                    Text(item.desc, style: TextStyle(fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w500)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, size: 16, color: p.decor),
            ],
          ),
        ),
      ),
    );
  }

  Widget _searchFooter(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          _kbd(p, '↑'),
          const SizedBox(width: 4),
          _kbd(p, '↓'),
          const SizedBox(width: 8),
          Text('选择', style: TextStyle(fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w500)),
          const SizedBox(width: 16),
          _kbd(p, '↵'),
          const SizedBox(width: 8),
          Text('执行', style: TextStyle(fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w500)),
          const Spacer(),
          Text('小凌 · v0.0.1', style: TextStyle(fontSize: XlFont.micro, color: p.decor, letterSpacing: XlLetterSpacing.wider)),
        ],
      ),
    );
  }

  Widget _kbd(XlPalette p, String s) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: p.surfaceHi,
        borderRadius: BorderRadius.circular(XlRadius.micro),
        border: Border.all(color: p.edge, width: 1),
        boxShadow: p.raisedHair,
      ),
      child: Text(s, style: TextStyle(fontSize: XlFont.micro, color: p.text2, fontWeight: FontWeight.w800)),
    );
  }
}

class _NavIntent extends Intent {
  final int index;
  const _NavIntent(this.index);
}

class _ToggleSidebarIntent extends Intent {
  const _ToggleSidebarIntent();
}

class _SearchIntent extends Intent {
  const _SearchIntent();
}

class _ThemeIntent extends Intent {
  const _ThemeIntent();
}

class _CloseOverlayIntent extends Intent {
  const _CloseOverlayIntent();
}

class _SearchItem {
  final String title;
  final String desc;
  final IconData icon;
  final VoidCallback onTap;
  _SearchItem(this.title, this.desc, this.icon, this.onTap);
}

class _AmbientPainter extends CustomPainter {
  final XlPalette p;
  final double t;
  _AmbientPainter({required this.p, required this.t});

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    _blob(canvas, Offset(w * (0.08 + t * 0.06), h * 0.08), w * 0.42, p.glow1);
    _blob(canvas, Offset(w * (0.92 - t * 0.08), h * 0.22), w * 0.36, p.glow2);
    _blob(canvas, Offset(w * (0.24 + t * 0.05), h * (0.94 - t * 0.04)), w * 0.46, p.glow3);
    _blob(canvas, Offset(w * (0.76 - t * 0.06), h * 0.82), w * 0.32, p.glow4);
    _blob(canvas, Offset(w * 0.52, h * (0.52 + t * 0.08)), w * 0.24, p.glow5);
  }

  void _blob(Canvas canvas, Offset center, double radius, Color color) {
    final paint = Paint()
      ..shader = RadialGradient(colors: [color, color.withOpacity(0)])
          .createShader(Rect.fromCircle(center: center, radius: radius));
    canvas.drawCircle(center, radius, paint);
  }

  @override
  bool shouldRepaint(covariant _AmbientPainter old) => old.t != t || old.p != p;
}