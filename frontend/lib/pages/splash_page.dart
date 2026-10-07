import 'dart:math' as math;
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
  late AnimationController _rotateCtrl;
  late AnimationController _ringCtrl;
  late AnimationController _floatCtrl;
  late AnimationController _textCtrl;
  late AnimationController _shimmerCtrl;
  late Animation<double> _scaleAnim;
  late Animation<double> _glowAnim;
  late Animation<double> _progressAnim;
  late Animation<double> _rotateAnim;
  late Animation<double> _textAnim;

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
    _rotateCtrl = AnimationController(
      duration: const Duration(milliseconds: 4000),
      vsync: this,
    )..repeat(reverse: true);
    _ringCtrl = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat();
    _floatCtrl = AnimationController(
      duration: const Duration(milliseconds: 6000),
      vsync: this,
    )..repeat();
    _textCtrl = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _shimmerCtrl = AnimationController(
      duration: const Duration(milliseconds: 1800),
      vsync: this,
    )..repeat();
    _scaleAnim = Tween<double>(begin: 0.94, end: 1.05).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );
    _glowAnim = Tween<double>(begin: 0.55, end: 1.0).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );
    _progressAnim = CurvedAnimation(parent: _progressCtrl, curve: XlCurve.easeOut);
    _rotateAnim = Tween<double>(begin: -0.05, end: 0.05).animate(
      CurvedAnimation(parent: _rotateCtrl, curve: Curves.easeInOut),
    );
    _textAnim = CurvedAnimation(parent: _textCtrl, curve: Curves.easeOut);
    _fadeCtrl.forward();
    _progressCtrl.forward();
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) _textCtrl.forward();
    });
    _go();
  }

  Future<void> _go() async {
    await Future.delayed(const Duration(milliseconds: 2600));
    if (mounted) {
      await _fadeCtrl.reverse();
    }
    if (mounted) {
      Navigator.pushReplacement(
        context,
        PageRouteBuilder(
          transitionDuration: const Duration(milliseconds: 400),
          pageBuilder: (_, __, ___) => HomeShell(onToggleTheme: widget.onToggleTheme),
          transitionsBuilder: (_, anim, __, child) => FadeTransition(opacity: anim, child: child),
        ),
      );
    }
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    _progressCtrl.dispose();
    _fadeCtrl.dispose();
    _rotateCtrl.dispose();
    _ringCtrl.dispose();
    _floatCtrl.dispose();
    _textCtrl.dispose();
    _shimmerCtrl.dispose();
    super.dispose();
  }

  Widget _floatingOrb(double baseX, double baseY, double size, Color color, double phase) {
    return AnimatedBuilder(
      animation: _floatCtrl,
      builder: (_, __) {
        final t = _floatCtrl.value * 2 * math.pi + phase;
        final dx = math.sin(t) * 14;
        final dy = math.cos(t * 0.8) * 18;
        return Positioned(
          left: baseX + dx,
          top: baseY + dy,
          child: Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [color.withOpacity(0.14), color.withOpacity(0.0)],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _glowRing(double delay) {
    return AnimatedBuilder(
      animation: _ringCtrl,
      builder: (_, __) {
        final t = (_ringCtrl.value + delay) % 1.0;
        final scale = 0.8 + t * 1.6;
        final opacity = (1 - t) * 0.5;
        return Transform.scale(
          scale: scale,
          child: Opacity(
            opacity: opacity,
            child: Container(
              width: 124,
              height: 124,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: Theme.of(context).extension<XlPalette>()!.pink.withOpacity(0.6),
                  width: 1.5,
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Scaffold(
      backgroundColor: p.bg,
      body: FadeTransition(
        opacity: _fadeCtrl,
        child: Stack(
          children: [
            Positioned.fill(
              child: AppTheme.aurora(context, child: const SizedBox.shrink()),
            ),
            _floatingOrb(60, 120, 160, p.pink, 0),
            _floatingOrb(220, 380, 140, p.gold, 1.5),
            _floatingOrb(100, 500, 180, p.pink2, 3.0),
            Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: 180,
                    height: 180,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        _glowRing(0.0),
                        _glowRing(0.4),
                        AnimatedBuilder(
                          animation: _pulseCtrl,
                          builder: (_, __) {
                            return Transform.rotate(
                              angle: _rotateAnim.value,
                              child: Transform.scale(
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
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 42),
                  FadeTransition(
                    opacity: _textAnim,
                    child: Column(
                      children: [
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
                          'XiaoLing AI Companion',
                          style: TextStyle(
                            fontSize: 13,
                            color: p.gold,
                            letterSpacing: 4,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 54),
                  SizedBox(
                    width: 220,
                    height: 14,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
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
                        ClipRRect(
                          borderRadius: BorderRadius.circular(XlRadius.pill),
                          child: AnimatedBuilder(
                            animation: _shimmerCtrl,
                            builder: (_, __) {
                              final t = _shimmerCtrl.value;
                              return Align(
                                alignment: Alignment.centerLeft,
                                child: FractionallySizedBox(
                                  widthFactor: 220 / 220,
                                  child: Container(
                                    height: 12,
                                    decoration: BoxDecoration(
                                      gradient: LinearGradient(
                                        begin: Alignment(-1.0 + t * 2.5, 0),
                                        end: Alignment(-0.4 + t * 2.5, 0),
                                        colors: [
                                          Colors.white.withOpacity(0),
                                          Colors.white.withOpacity(0.35),
                                          Colors.white.withOpacity(0),
                                        ],
                                      ),
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
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
