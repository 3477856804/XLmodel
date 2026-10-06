import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../main.dart';

class SplashPage extends StatefulWidget {
  final VoidCallback onToggleTheme;
  const SplashPage({super.key, required this.onToggleTheme});
  @override
  State<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends State<SplashPage> with SingleTickerProviderStateMixin {
  late AnimationController _c;
  late Animation<double> _fade, _scale;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(duration: const Duration(milliseconds: 1400), vsync: this);
    _fade = Tween<double>(begin: 0, end: 1).animate(
        CurvedAnimation(parent: _c, curve: Curves.easeIn));
    _scale = Tween<double>(begin: .82, end: 1).animate(
        CurvedAnimation(parent: _c, curve: Curves.easeOutBack));
    _c.forward();
    _go();
  }

  void _go() async {
    await Future.delayed(const Duration(milliseconds: 2000));
    if (mounted) {
      Navigator.pushReplacement(context,
          MaterialPageRoute(builder: (_) =>
              HomeShell(onToggleTheme: widget.onToggleTheme)));
    }
  }

  @override
  void dispose() { _c.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Scaffold(
      backgroundColor: p.bg,
      body: Center(
        child: FadeTransition(
          opacity: _fade,
          child: ScaleTransition(
            scale: _scale,
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Container(
                width: 124, height: 124,
                decoration: BoxDecoration(
                  gradient: p.gradBrand,
                  shape: BoxShape.circle,
                  boxShadow: p.raised,
                ),
                child: Icon(Icons.pets_rounded, size: 60, color: p.btnInk),
              ),
              const SizedBox(height: 34),
              Text('小凌', style: TextStyle(fontSize: 38, fontWeight: FontWeight.w800,
                  color: p.text1, letterSpacing: 8)),
              const SizedBox(height: 10),
              Text('你的专属 AI 伙伴', style: TextStyle(fontSize: 13,
                  color: p.text2, letterSpacing: 3, fontWeight: FontWeight.w500)),
              const SizedBox(height: 48),
              SizedBox(width: 200, child: ClipRRect(
                borderRadius: BorderRadius.circular(99),
                child: LinearProgressIndicator(
                  minHeight: 6,
                  backgroundColor: p.surfaceLo,
                  valueColor: AlwaysStoppedAnimation(p.pink),
                ),
              )),
            ]),
          ),
        ),
      ),
    );
  }
}