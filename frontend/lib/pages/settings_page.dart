import 'package:flutter/material.dart';
import '../theme/theme.dart';

/// 设置页面
class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('设置'),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: Container(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            _buildSection('模型设置'),
            _buildSettingItem('角色模型', '小凌', Icons.face),
            _buildSettingItem('音色', '晓晓', Icons.mic),
            _buildSettingItem('推理后端', 'CPU', Icons.memory),
            const SizedBox(height: 24),
            _buildSection('渲染设置'),
            _buildSettingItem('渲染模式', '软件光栅', Icons.memory),
            _buildSettingItem('窗口置顶', true, Icons.push_pin),
            _buildSettingItem('开机自启', false, Icons.power),
            const SizedBox(height: 24),
            _buildSection('语音设置'),
            _buildSettingItem('语音识别', true, Icons.record_voice_over),
            _buildSettingItem('语音朗读', true, Icons.volume_up),
            _buildSettingItem('阅读模式', false, Icons.menu_book),
            const SizedBox(height: 24),
            _buildSection('关于'),
            _buildSettingItem('版本', 'v0.0.1', Icons.info),
            _buildSettingItem('检查更新', '', Icons.update),
          ],
        ),
      ),
    );
  }

  Widget _buildSection(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12, left: 4),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.bold,
          color: AppTheme.primaryPink,
        ),
      ),
    );
  }

  Widget _buildSettingItem(String label, dynamic value, IconData icon) {
    final isSwitch = value is bool;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: AppTheme.glassDecoration,
      child: Row(
        children: [
          Icon(icon, size: 20, color: AppTheme.primaryPink),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary),
            ),
          ),
          if (isSwitch)
            Switch(
              value: value,
              activeColor: AppTheme.primaryPink,
              onChanged: (v) {},
            )
          else
            Text(
              value,
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
            ),
        ],
      ),
    );
  }
}
