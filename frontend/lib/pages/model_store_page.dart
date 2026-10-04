import 'package:flutter/material.dart';
import '../theme/theme.dart';

/// 模型商店 - CanIRun.ai 风格卡片
class ModelStorePage extends StatelessWidget {
  const ModelStorePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: AppTheme.auroraBackground(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const Text('模型商店', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: AppTheme.textPrimary)),
            const SizedBox(height: 4),
            Text('按最小但跑分最高排序推荐', style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
            const SizedBox(height: 20),
            ..._models.map((m) => _ModelCard(model: m)),
          ],
        ),
      ),
    );
  }

  static final _models = [
    _ModelData(
      name: 'Qwen2.5-0.5B-Instruct',
      publisher: 'Qwen',
      params: '0.5B',
      type: 'Dense',
      desc: '最小中文模型，CPU秒跑',
      hfRepo: 'Qwen/Qwen2.5-0.5B-Instruct',
      downloads: '12.4K',
      likes: 342,
      date: '2024-11',
      context: '32K',
      useCases: ['chat', 'zh'],
      quants: [
        _Quant('Q4_K_M', 4, '1.2 GB', 'Good', 'Fast'),
        _Quant('Q8_0', 8, '1.9 GB', 'Best', 'Medium'),
      ],
      recommended: true,
    ),
    _ModelData(
      name: 'Qwen2.5-1.5B-Instruct',
      publisher: 'Qwen',
      params: '1.5B',
      type: 'Dense',
      desc: '性价比最高，中文流畅',
      hfRepo: 'Qwen/Qwen2.5-1.5B-Instruct',
      downloads: '8.1K',
      likes: 218,
      date: '2024-11',
      context: '32K',
      useCases: ['chat', 'zh', 'code'],
      quants: [
        _Quant('Q4_K_M', 4, '2.5 GB', 'Good', 'Medium'),
        _Quant('Q8_0', 8, '3.8 GB', 'Best', 'Slow'),
      ],
      recommended: false,
    ),
    _ModelData(
      name: 'Phi-3.5-mini-instruct',
      publisher: 'Microsoft',
      params: '3.8B',
      type: 'Dense',
      desc: '微软小钢炮，推理快',
      hfRepo: 'microsoft/Phi-3.5-mini-instruct',
      downloads: '15.2K',
      likes: 567,
      date: '2024-08',
      context: '128K',
      useCases: ['reasoning', 'code'],
      quants: [
        _Quant('Q4_K_M', 4, '2.3 GB', 'Good', 'Medium'),
        _Quant('Q8_0', 8, '3.8 GB', 'Best', 'Slow'),
      ],
      recommended: false,
    ),
    _ModelData(
      name: 'Qwen2.5-3B-Instruct',
      publisher: 'Qwen',
      params: '3B',
      type: 'Dense',
      desc: '能力强，需4GB内存',
      hfRepo: 'Qwen/Qwen2.5-3B-Instruct',
      downloads: '5.6K',
      likes: 189,
      date: '2024-11',
      context: '32K',
      useCases: ['chat', 'zh', 'reasoning'],
      quants: [
        _Quant('Q4_K_M', 4, '3.8 GB', 'Good', 'Slow'),
        _Quant('Q8_0', 8, '6.1 GB', 'Best', 'Very Slow'),
      ],
      recommended: false,
    ),
  ];
}

class _ModelCard extends StatelessWidget {
  final _ModelData model;
  const _ModelCard({required this.model});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: AppTheme.glassCard(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 模型名 + 标签
            Row(
              children: [
                Expanded(
                  child: Text(model.name, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: AppTheme.textPrimary, letterSpacing: -0.5)),
                ),
                if (model.recommended)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(color: AppTheme.gold.withOpacity(0.15), borderRadius: BorderRadius.circular(8), border: Border.all(color: AppTheme.gold.withOpacity(0.3))),
                    child: const Text('推荐', style: TextStyle(fontSize: 11, color: AppTheme.gold, fontWeight: FontWeight.w700)),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            // 厂商 · 参数量 · 类型
            Text('${model.publisher} · ${model.params} · ${model.type}', style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
            const SizedBox(height: 12),
            // 描述
            Text(model.desc, style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary, height: 1.4)),
            const SizedBox(height: 16),
            // HuggingFace 按钮
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(color: Colors.black.withOpacity(0.85), borderRadius: BorderRadius.circular(20)),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.pets, color: Colors.white, size: 16),
                const SizedBox(width: 6),
                Text(model.hfRepo, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w500)),
              ]),
            ),
            const SizedBox(height: 16),
            // 下载/点赞/日期
            Row(children: [
              Icon(Icons.download_outlined, size: 14, color: AppTheme.textLight),
              const SizedBox(width: 4),
              Text('${model.downloads} downloads', style: TextStyle(fontSize: 12, color: AppTheme.textLight)),
              const SizedBox(width: 16),
              Icon(Icons.favorite_border, size: 14, color: AppTheme.textLight),
              const SizedBox(width: 4),
              Text('${model.likes} likes', style: TextStyle(fontSize: 12, color: AppTheme.textLight)),
              const SizedBox(width: 16),
              Icon(Icons.calendar_today_outlined, size: 14, color: AppTheme.textLight),
              const SizedBox(width: 4),
              Text(model.date, style: TextStyle(fontSize: 12, color: AppTheme.textLight)),
            ]),
            const SizedBox(height: 12),
            // context
            Row(children: [
              Icon(Icons.memory, size: 14, color: AppTheme.primaryPink),
              const SizedBox(width: 4),
              Text('${model.context} context', style: TextStyle(fontSize: 12, color: AppTheme.primaryPink, fontWeight: FontWeight.w600)),
            ]),
            const SizedBox(height: 16),
            // Use cases
            const Text('Use Cases', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, children: model.useCases.map((u) => Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(color: AppTheme.soft.withOpacity(0.5), borderRadius: BorderRadius.circular(8), border: Border.all(color: AppTheme.primaryPink.withOpacity(0.15))),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.label_outline, size: 12, color: AppTheme.primaryPink),
                const SizedBox(width: 4),
                Text(u, style: const TextStyle(fontSize: 11, color: AppTheme.primaryPink)),
              ]),
            )).toList()),
            const SizedBox(height: 20),
            // Quantization 表
            const Text('Quantization Options', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textSecondary)),
            const SizedBox(height: 8),
            Container(
              decoration: BoxDecoration(color: Colors.white.withOpacity(0.4), borderRadius: BorderRadius.circular(12)),
              child: Column(children: [
                // 表头
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Colors.black.withOpacity(0.06)))),
                  child: const Row(children: [
                    Expanded(flex: 2, child: Text('QUANT', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppTheme.textLight))),
                    Expanded(flex: 1, child: Text('BITS', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppTheme.textLight))),
                    Expanded(flex: 1, child: Text('VRAM', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppTheme.textLight))),
                    Expanded(flex: 1, child: Text('QUALITY', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppTheme.textLight))),
                  ]),
                ),
                ...model.quants.map((q) => Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                  decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Colors.black.withOpacity(0.04)))),
                  child: Row(children: [
                    Expanded(flex: 2, child: Text(q.name, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppTheme.textPrimary))),
                    Expanded(flex: 1, child: Text('${q.bits}', style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary))),
                    Expanded(flex: 1, child: Text(q.vram, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary))),
                    Expanded(flex: 1, child: Text(q.quality, style: TextStyle(fontSize: 13, color: q.quality == 'Best' ? AppTheme.gold : AppTheme.primaryPink, fontWeight: FontWeight.w600))),
                  ]),
                )),
              ]),
            ),
            const SizedBox(height: 16),
            // 下载按钮
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {},
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                child: const Text('下载模型', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ModelData {
  final String name, publisher, params, type, desc, hfRepo, downloads, date, context;
  final int likes;
  final List<String> useCases;
  final List<_Quant> quants;
  final bool recommended;

  _ModelData({required this.name, required this.publisher, required this.params, required this.type, required this.desc, required this.hfRepo, required this.downloads, required this.likes, required this.date, required this.context, required this.useCases, required this.quants, required this.recommended});
}

class _Quant {
  final String name, vram, quality;
  final int bits;
  _Quant(this.name, this.bits, this.vram, this.quality, String speed);
}
