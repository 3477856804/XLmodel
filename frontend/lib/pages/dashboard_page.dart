import 'package:flutter/material.dart';
import 'package:grpc/grpc.dart';
import '../theme/theme.dart';
import '../rpc/xiaoling.pbgrpc.dart';
import '../rpc/xiaoling.pb.dart' as pb;

/// 工作台 - 真实 gRPC 数据
class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  late ClientChannel _chan;
  late XiaoLingClient _stub;
  GrowthStatusReply? _growth;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _chan = ClientChannel('localhost',
        port: 50051,
        options: const ChannelOptions(connectTimeout: Duration(seconds: 2)));
    _stub = XiaoLingClient(_chan);
    _load();
  }

  @override
  void dispose() {
    _chan.shutdown();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final g = await _stub.getGrowthStatus(pb.Empty(),
          options: CallOptions(timeout: const Duration(seconds: 3)));
      if (mounted) setState(() { _growth = g; _loading = false; });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final prog = _growth?.progressPercent ?? 0.0;
    final inter = _growth?.totalInteractions ?? 0;
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('工作台', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFF1a1a1a))),
                Row(children: [
                  IconButton(icon: const Icon(Icons.settings, color: AppTheme.primaryPink), onPressed: () {}),
                  IconButton(icon: const Icon(Icons.person, color: AppTheme.primaryPink), onPressed: () {}),
                ]),
              ],
            ),
            const SizedBox(height: 20),
            Expanded(
              child: Row(
                children: [
                  Expanded(flex: 1, child: _buildStats(prog, inter)),
                  const SizedBox(width: 16),
                  Expanded(flex: 2, child: _buildModelPreview()),
                  const SizedBox(width: 16),
                  Expanded(flex: 1, child: _buildActions()),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStats(double prog, int inter) {
    final cards = [
      ('成长值', prog / 100.0, '${prog.toStringAsFixed(0)}%', Icons.trending_up),
      ('亲密度', (prog * 0.7) / 100.0, '${(prog * 0.7).toStringAsFixed(0)}%', Icons.favorite),
      ('训练进度', (prog * 0.5) / 100.0, '${(prog * 0.5).toStringAsFixed(0)}%', Icons.school),
      ('记忆数', inter / 200.0, '$inter 条', Icons.memory),
    ];
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: cards.map((c) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.6),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppTheme.primaryPink.withOpacity(0.1)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [Icon(c.$4, size: 14, color: AppTheme.primaryPink), const SizedBox(width: 6), Text(c.$1, style: const TextStyle(fontSize: 12, color: Color(0xFF666)))]),
            const SizedBox(height: 8),
            ClipRRect(borderRadius: BorderRadius.circular(3), child: LinearProgressIndicator(value: c.$2.clamp(0,1), minHeight: 5, backgroundColor: AppTheme.primaryPink.withOpacity(0.1), valueColor: const AlwaysStoppedAnimation(AppTheme.primaryPink))),
            const SizedBox(height: 6),
            Text(c.$3, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Color(0xFF1a1a1a))),
          ],
        ),
      )).toList(),
    );
  }

  Widget _buildModelPreview() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.5),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.primaryPink.withOpacity(0.1)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 100, height: 100,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppTheme.primaryPink.withOpacity(0.1),
              border: Border.all(color: AppTheme.primaryPink.withOpacity(0.2)),
            ),
            child: const Icon(Icons.face_6, size: 50, color: AppTheme.primaryPink),
          ),
          const SizedBox(height: 16),
          const Text('小凌', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF1a1a1a))),
          const SizedBox(height: 4),
          Text(_growth?.stage ?? '3D 模型预览', style: const TextStyle(fontSize: 12, color: Color(0xFF999))),
        ],
      ),
    );
  }

  Widget _buildActions() {
    final actions = [
      (Icons.chat_bubble, '聊天'),
      (Icons.mic, '语音对话'),
      (Icons.shopping_bag_outlined, '模型商店'),
      (Icons.extension, '插件管理'),
    ];
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: actions.map((a) => Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.6),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.primaryPink.withOpacity(0.1)),
        ),
        child: Row(children: [Icon(a.$1, color: AppTheme.primaryPink, size: 18), const SizedBox(width: 10), Text(a.$2, style: const TextStyle(fontSize: 13, color: Color(0xFF333)))]),
      )).toList(),
    );
  }
}
