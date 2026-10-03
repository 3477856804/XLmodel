import 'package:flutter/material.dart';
import '../theme/theme.dart';

/// 工作台 - 中间3D模型预览 + 进度卡片 + 对话入口
class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: AppTheme.gradientBackground,
        child: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              Expanded(
                child: Row(
                  children: [
                    // 左侧：进度卡片
                    Expanded(
                      flex: 1,
                      child: _buildProgressCards(),
                    ),
                    // 中间：3D模型预览
                    Expanded(
                      flex: 2,
                      child: _buildModelPreview(),
                    ),
                    // 右侧：快捷入口
                    Expanded(
                      flex: 1,
                      child: _buildQuickActions(),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Text(
            '小凌工作台',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          Row(
            children: [
              _buildIconButton(Icons.settings),
              const SizedBox(width: 12),
              _buildIconButton(Icons.person),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildIconButton(IconData icon) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: AppTheme.glassCard,
      child: Icon(icon, color: AppTheme.primaryPink, size: 20),
    );
  }

  Widget _buildProgressCards() {
    final cards = [
      _ProgressItem('成长值', 0.65, '65%', Icons.trending_up),
      _ProgressItem('亲密度', 0.45, '45%', Icons.favorite),
      _ProgressItem('训练进度', 0.30, '30%', Icons.school),
      _ProgressItem('记忆数', 0.80, '128条', Icons.memory),
    ];

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: cards.map((c) => _buildProgressCard(c)).toList(),
      ),
    );
  }

  Widget _buildProgressCard(_ProgressItem item) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.glassCard,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(item.icon, size: 16, color: AppTheme.primaryPink),
              const SizedBox(width: 8),
              Text(
                item.label,
                style: const TextStyle(
                  fontSize: 13,
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: item.progress,
              minHeight: 6,
              backgroundColor: Colors.white.withOpacity(0.3),
              valueColor: const AlwaysStoppedAnimation(AppTheme.primaryPink),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            item.value,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModelPreview() {
    return Center(
      child: Container(
        width: 300,
        height: 400,
        decoration: AppTheme.glassCard,
        child: const Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.face_6,
              size: 120,
              color: AppTheme.primaryPink,
            ),
            SizedBox(height: 20),
            Text(
              '小凌',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
            SizedBox(height: 8),
            Text(
              '3D 模型预览',
              style: TextStyle(
                fontSize: 12,
                color: AppTheme.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickActions() {
    final actions = [
      _ActionItem(Icons.chat_bubble, '聊天'),
      _ActionItem(Icons.mic, '语音'),
      _ActionItem(Icons.download, '模型商店'),
      _ActionItem(Icons.extension, '插件'),
    ];

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: actions.map((a) => _buildActionButton(a)).toList(),
      ),
    );
  }

  Widget _buildActionButton(_ActionItem item) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {},
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: AppTheme.glassCard,
            child: Row(
              children: [
                Icon(item.icon, color: AppTheme.primaryPink, size: 20),
                const SizedBox(width: 12),
                Text(
                  item.label,
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppTheme.textPrimary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ProgressItem {
  final String label;
  final double progress;
  final String value;
  final IconData icon;

  _ProgressItem(this.label, this.progress, this.value, this.icon);
}

class _ActionItem {
  final IconData icon;
  final String label;

  _ActionItem(this.icon, this.label);
}
