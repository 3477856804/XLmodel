import 'package:flutter/material.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import '../theme/theme.dart';

/// 3D 模型展示 - 类似游戏选英雄界面
class ModelShowcase extends StatefulWidget {
  final String? modelPath;
  final double width;
  final double height;
  final String characterName;

  const ModelShowcase({
    super.key,
    this.modelPath,
    this.width = 300,
    this.height = 300,
    this.characterName = '小凌',
  });

  @override
  State<ModelShowcase> createState() => _ModelShowcaseState();
}

class _ModelShowcaseState extends State<ModelShowcase> {
  bool _hasError = false;
  bool _autoRotate = true;
  String? _currentPath;

  @override
  void initState() {
    super.initState();
    _currentPath = widget.modelPath;
  }

  @override
  void didUpdateWidget(ModelShowcase old) {
    super.didUpdateWidget(old);
    if (widget.modelPath != old.modelPath) {
      setState(() {
        _currentPath = widget.modelPath;
        _hasError = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: widget.width,
      height: widget.height,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [
            AppTheme.primaryPink.withOpacity(0.15),
            AppTheme.primaryPink.withOpacity(0.03),
          ],
        ),
        border: Border.all(
          color: AppTheme.primaryPink.withOpacity(0.3),
          width: 2,
        ),
      ),
      child: ClipOval(
        child: Stack(
          alignment: Alignment.center,
          children: [
            if (_currentPath != null && !_hasError)
              ModelViewer(
                src: 'file://$_currentPath',
                autoRotate: _autoRotate,
                autoRotateDelay: 0,
                cameraControls: true,
                exposure: 1.2,
                shadowIntensity: 0.5,
              )
            else
              Icon(
                Icons.face_6,
                size: widget.width * 0.4,
                color: AppTheme.primaryPink.withOpacity(0.5),
              ),
            // 底部信息浮层
            Positioned(
              bottom: 12,
              child: Column(
                children: [
                  Text(
                    widget.characterName,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF1a1a1a),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _circleBtn(Icons.refresh, () {
                        setState(() => _hasError = false);
                      }),
                      const SizedBox(width: 8),
                      _circleBtn(
                        _autoRotate ? Icons.pause : Icons.play_arrow,
                        () => setState(() => _autoRotate = !_autoRotate),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _circleBtn(IconData icon, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.8),
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: AppTheme.primaryPink.withOpacity(0.2),
              blurRadius: 4,
            ),
          ],
        ),
        child: Icon(icon, size: 14, color: AppTheme.primaryPink),
      ),
    );
  }
}
