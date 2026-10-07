import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../main.dart';

class SplashPage extends StatefulWidget {
  final VoidCallback onToggleTheme;
  const SplashPage({super.key, required this.onToggleTheme});
  @override
  State<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends State<SplashPage> with TickerProviderStateMixin {
  late AnimationController _pulseCtrl;
  late AnimationController _progressCtrl;
  late AnimationController _fadeCtrl;
  late Animation<double> _scaleAnim;
  late Animation<double> _glowAnim;
  late Animation<double> _progressAnim;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);
    _progressCtrl = AnimationController(
      duration: const Duration(milliseconds: 2400),
      vsync: this,
    );
    _fadeCtrl = AnimationController(
      duration: const Duration(milliseconds: 700),
      vsync: this,
    );
    _scaleAnim = Tween<double>(begin: 0.94, end: 1.05).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );
    _glowAnim = Tween<double>(begin: 0.55, end: 1.0).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );
    _progressAnim = CurvedAnimation(parent: _progressCtrl, curve: XlCurve.easeOut);
    _fadeCtrl.forward();
    _progressCtrl.forward();
    _go();
  }

  Future<void> _go() async {
    await Future.delayed(const Duration(milliseconds: 2600));
    if (mounted) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => HomeShell(onToggleTheme: widget.onToggleTheme),
        ),
      );
    }
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    _progressCtrl.dispose();
    _fadeCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Scaffold(
      backgroundColor: p.bg,
      body: Stack(
        children: [
          Positioned.fill(
            child: AppTheme.aurora(context, child: const SizedBox.shrink()),
          ),
          Center(
            child: FadeTransition(
              opacity: _fadeCtrl,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  AnimatedBuilder(
                    animation: _pulseCtrl,
                    builder: (_, __) {
                      return Transform.scale(
                        scale: _scaleAnim.value,
                        child: Container(
                          width: 124,
                          height: 124,
                          decoration: BoxDecoration(
                            gradient: p.gradBrand,
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: Colors.white.withOpacity(p.isDark ? 0.40 : 0.55),
                              width: 3,
                            ),
                            boxShadow: [
                              ...p.raised,
                              BoxShadow(
                                color: p.pink.withOpacity(0.5 * _glowAnim.value),
                                blurRadius: 34,
                                spreadRadius: -4,
                              ),
                            ],
                          ),
                          child: Icon(Icons.favorite_rounded, size: 54, color: p.btnInk),
                        ),
                      );
                    },
                  ),
                  const SizedBox(height: 42),
                  Text(
                    '晓灵',
                    style: TextStyle(
                      fontSize: 42,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: 10,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'XiaoLing',
                    style: TextStyle(
                      fontSize: 13,
                      color: p.text3,
                      letterSpacing: 6,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 54),
                  Container(
                    width: 220,
                    height: 12,
                    padding: const EdgeInsets.all(2),
                    decoration: AppTheme.sunkenSm(context, r: XlRadius.pill),
                    child: AnimatedBuilder(
                      animation: _progressAnim,
                      builder: (_, __) {
                        return Align(
                          alignment: Alignment.centerLeft,
                          child: FractionallySizedBox(
                            widthFactor: _progressAnim.value.clamp(0.0, 1.0),
                            child: Container(
                              decoration: BoxDecoration(
                                gradient: p.gradBrand,
                                borderRadius: BorderRadius.circular(XlRadius.pill),
                                boxShadow: [
                                  BoxShadow(
                                    color: p.pink.withOpacity(0.45),
                                    blurRadius: 8,
                                    spreadRadius: -2,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
