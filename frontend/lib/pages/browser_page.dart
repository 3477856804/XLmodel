import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../widgets/browser_panel.dart';

class BrowserPage extends StatelessWidget {
  const BrowserPage({super.key});

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
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: ShaderMask(
          shaderCallback: (bounds) => LinearGradient(
            colors: [p.pink, p.gold],
          ).createShader(bounds),
          child: const Text(
            '浏览器',
            style: TextStyle(
              fontSize: XlFont.h5,
              fontWeight: FontWeight.w800,
              color: Colors.white,
              letterSpacing: XlLetterSpacing.wide,
            ),
          ),
        ),
        centerTitle: false,
      ),
      body: const SafeArea(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: BrowserPanel(),
        ),
      ),
    );
  }
}
