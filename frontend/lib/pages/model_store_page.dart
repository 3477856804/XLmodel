import 'package:flutter/material.dart';
import '../theme/theme.dart';

/// 模型商店 - 智能推荐 + 下载
class ModelStorePage extends StatelessWidget {
  const ModelStorePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('模型商店'),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: Container(
        decoration: AppTheme.gradientBackground,
        child: Column(
          children: [
            _buildHardwareCard(),
            Expanded(child: _buildModelList()),
          ],
        ),
      ),
    );
  }

  Widget _buildHardwareCard() {
    return Container(
      margin: const EdgeInsets.all(20),
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.glassCard,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.memory, color: AppTheme.primaryPink, size: 20),
              SizedBox(width: 8),
              Text(
                '你的硬件',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildHardwareItem('显卡', 'CPU'),
              _buildHardwareItem('显存', '0 GB'),
              _buildHardwareItem('内存', '8 GB'),
              _buildHardwareItem('磁盘', '剩余 50 GB'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHardwareItem(String label, String value) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: AppTheme.primaryPink,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
        ),
      ],
    );
  }

  Widget _buildModelList() {
    final models = [
      _ModelInfo('Qwen3-1.7B', '1.7B', 'Q4_K_M', '2.5 GB', 72, true),
      _ModelInfo('Qwen3-4B', '4B', 'Q4_K_M', '3.5 GB', 85, true),
      _ModelInfo('Qwen3-8B', '8B', 'Q4_K_M', '5.5 GB', 92, false),
      _ModelInfo('DeepSeek-R1-7B', '7B', 'Q4_K_M', '5.0 GB', 90, false),
    ];

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      itemCount: models.length,
      itemBuilder: (context, index) => _buildModelCard(models[index]),
    );
  }

  Widget _buildModelCard(_ModelInfo model) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.glassCard,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                model.name,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
              if (model.recommended)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryPink,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text(
                    '推荐',
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _buildTag('参数量: ${model.params}'),
              const SizedBox(width: 8),
              _buildTag('量化: ${model.quant}'),
              const SizedBox(width: 8),
              _buildTag('质量: ${model.quality}/100'),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '需要 ${model.vram} 显存',
                style: const TextStyle(
                  fontSize: 13,
                  color: AppTheme.textSecondary,
                ),
              ),
              ElevatedButton(
                onPressed: model.canRun ? () {} : null,
                child: Text(model.canRun ? '下载' : '硬件不足'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTag(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppTheme.soft,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style: const TextStyle(fontSize: 11, color: AppTheme.primaryPink),
      ),
    );
  }
}

class _ModelInfo {
  final String name;
  final String params;
  final String quant;
  final String vram;
  final int quality;
  final bool recommended;
  final bool canRun;

  _ModelInfo(this.name, this.params, this.quant, this.vram, this.quality, this.canRun)
      : recommended = canRun && quality >= 80;
}
