import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../widgets/git_panel.dart';

class GitPage extends StatelessWidget {
  final String repoPath;
  const GitPage({super.key, this.repoPath = '.'});

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
              child: Icon(Icons.commit_rounded, size: 16, color: p.btnInk),
            ),
            const SizedBox(width: 12),
            ShaderMask(
              shaderCallback: (b) => p.gradBrandH.createShader(b),
              child: Text('版本控制',
                  style: TextStyle(
                    fontSize: XlFont.h5,
                    fontWeight: FontWeight.w800,
                    color: p.isDark ? Colors.white : p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
            ),
          ],
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: GitPanel(repoPath: repoPath),
      ),
    );
  }
}
