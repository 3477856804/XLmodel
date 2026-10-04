import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/xiaoling.pbgrpc.dart';
import '../rpc/xiaoling.pb.dart';
import 'package:grpc/grpc.dart';

/// 模型商店 - 读取用户硬件配置推荐模型
class ModelStorePage extends StatefulWidget {
  const ModelStorePage({super.key});

  @override
  State<ModelStorePage> createState() => _ModelStorePageState();
}

class _ModelStorePageState extends State<ModelStorePage> {
  XiaoLingStub? _stub;
  HardwareInfo? _hw;
  List<RecommendedModel> _models = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final chan = ClientChannel('localhost', port: 50051,
        options: const ChannelOptions(credentials: ChannelCredentials.insecure()));
    _stub = XiaoLingStub(chan);
    try {
      final hw = await _stub.detectHardware(Empty());
      final recs = await _stub.listRecommendedModels(HardwareRequest());
      if (mounted) setState(() { _hw = hw; _models = recs.models; _loading = false; });
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

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
            Text('根据你的硬件自动推荐', style: TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
            const SizedBox(height: 20),
            if (_loading)
              const Center(child: Padding(padding: EdgeInsets.all(40), child: CircularProgressIndicator(color: AppTheme.primaryPink)))
            else ...[
              if (_hw != null) _hardwareCard(),
              const SizedBox(height: 16),
              ..._models.map((m) => _ModelCard(model: m)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _hardwareCard() {
    return AppTheme.glassCard(
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _hwItem('内存', '${_hw!.ramGb.toStringAsFixed(1)} GB'),
          _hwItem('CPU', '${_hw!.cpuCores} 核'),
          _hwItem('GPU', _hw!.hasCuda ? 'CUDA' : 'CPU'),
          _hwItem('系统', _hw!.platform),
        ],
      ),
    );
  }

  Widget _hwItem(String label, String value) {
    return Column(children: [
      Text(value, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppTheme.primaryPink)),
      const SizedBox(height: 4),
      Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
    ]);
  }
}

class _ModelCard extends StatelessWidget {
  final RecommendedModel model;
  const _ModelCard({required this.model});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: AppTheme.glassCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Expanded(child: Text(model.name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: AppTheme.textPrimary))),
              if (model.recommended)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(color: AppTheme.gold.withOpacity(0.15), borderRadius: BorderRadius.circular(8)),
                  child: const Text('推荐', style: TextStyle(fontSize: 11, color: AppTheme.gold, fontWeight: FontWeight.w700)),
                ),
            ]),
            const SizedBox(height: 8),
            Text('${(model.sizeMb/1024).toStringAsFixed(1)} GB · ${model.context} context',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
            const SizedBox(height: 12),
            Row(children: [
              Icon(model.canRun ? Icons.check_circle : Icons.cancel,
                  color: model.canRun ? Colors.green : Colors.red, size: 16),
              const SizedBox(width: 6),
              Text(model.canRun ? '可以运行 (需 ${model.ramGb.toStringAsFixed(1)}GB 内存)' : '内存不足',
                  style: TextStyle(fontSize: 12, color: model.canRun ? Colors.green : Colors.red)),
            ]),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: model.canRun ? () {} : null,
                child: Text(model.canRun ? '下载' : '硬件不足'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
