import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:grpc/grpc.dart';
import '../theme/theme.dart';
import '../rpc/xiaoling.pbgrpc.dart';

/// 训练页 — 五维能力雷达 + 训练状态
class TrainingPage extends StatefulWidget {
  const TrainingPage({super.key});

  @override
  State<TrainingPage> createState() => _TrainingPageState();
}

class _TrainingPageState extends State<TrainingPage> {
  late ClientChannel _chan;
  late XiaoLingClient _stub;
  TrainingStatusReply? _data;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _chan = ClientChannel('localhost', port: 50051,
        options: const ChannelOptions(connectTimeout: Duration(seconds: 2)));
    _stub = XiaoLingClient(_chan);
    _refresh();
  }

  @override
  void dispose() {
    _chan.shutdown();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() => _loading = true);
    try {
      final r = await _stub.getTrainingStatus(Empty());
      setState(() => _data = r);
    } catch (_) {
      setState(() => _data = null);
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _header(),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator(color: AppTheme.primaryPink))
              : _data == null
                  ? _errorView()
                  : _content(),
        ),
      ],
    );
  }

  Widget _header() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Text('能力训练',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary, letterSpacing: 1)),
          IconButton(
            onPressed: _refresh,
            icon: const Icon(Icons.refresh, color: AppTheme.primaryPink),
          ),
        ],
      ),
    );
  }

  Widget _errorView() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.cloud_off, size: 48, color: AppTheme.textLight),
          const SizedBox(height: 12),
          const Text('后端未连接', style: TextStyle(color: AppTheme.textSecondary)),
          const SizedBox(height: 16),
          ElevatedButton(onPressed: _refresh, child: const Text('重试')),
        ],
      ),
    );
  }

  Widget _content() {
    final dims = _data!.dimensions;
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: [
          _statusCard(),
          const SizedBox(height: 16),
          _radarCard(dims),
          const SizedBox(height: 16),
          _dimBars(dims),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Widget _statusCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: AppTheme.glassDecoration,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 10, height: 10,
                decoration: BoxDecoration(
                  color: _data!.isTraining ? Colors.green : AppTheme.gold,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(_data!.isTraining ? '训练中' : '待机',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimary)),
            ],
          ),
          const SizedBox(height: 8),
          Text(_data!.statusText,
              style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
        ],
      ),
    );
  }

  Widget _radarCard(List<TrainingDimension> dims) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: AppTheme.glassDecoration,
      child: Column(
        children: [
          const Text('五维能力',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary)),
          const SizedBox(height: 12),
          SizedBox(
            width: 240, height: 240,
            child: CustomPaint(
              painter: _RadarPainter(dims: dims),
            ),
          ),
        ],
      ),
    );
  }

  Widget _dimBars(List<TrainingDimension> dims) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: AppTheme.glassDecoration,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('详细数值',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary)),
          const SizedBox(height: 12),
          ...dims.map((d) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(d.name, style: const TextStyle(fontSize: 13,
                        fontWeight: FontWeight.w500, color: AppTheme.textPrimary)),
                    Text('${d.value.toStringAsFixed(1)}%',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ],
                ),
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: d.value.clamp(0, 100) / 100,
                    minHeight: 6,
                    backgroundColor: AppTheme.soft,
                    valueColor: const AlwaysStoppedAnimation(AppTheme.primaryPink),
                  ),
                ),
              ],
            ),
          )),
        ],
      ),
    );
  }
}

/// 五边形雷达图绘制
class _RadarPainter extends CustomPainter {
  final List<TrainingDimension> dims;
  _RadarPainter({required this.dims});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 20;
    final n = dims.length;
    if (n == 0) return;

    // 网格
    final gridPaint = Paint()
      ..color = AppTheme.textLight.withOpacity(0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    for (var ring = 1; ring <= 4; ring++) {
      final r = radius * ring / 4;
      final path = Path();
      for (var i = 0; i < n; i++) {
        final angle = -math.pi / 2 + 2 * math.pi * i / n;
        final p = Offset(center.dx + r * math.cos(angle),
            center.dy + r * math.sin(angle));
        if (i == 0) path.moveTo(p.dx, p.dy);
        else path.lineTo(p.dx, p.dy);
      }
      path.close();
      canvas.drawPath(path, gridPaint);
    }

    // 轴线
    for (var i = 0; i < n; i++) {
      final angle = -math.pi / 2 + 2 * math.pi * i / n;
      final p = Offset(center.dx + radius * math.cos(angle),
          center.dy + radius * math.sin(angle));
      canvas.drawLine(center, p, gridPaint);
    }

    // 数据多边形
    final dataPath = Path();
    for (var i = 0; i < n; i++) {
      final angle = -math.pi / 2 + 2 * math.pi * i / n;
      final v = dims[i].value.clamp(0, 100) / 100;
      final r = radius * v;
      final p = Offset(center.dx + r * math.cos(angle),
          center.dy + r * math.sin(angle));
      if (i == 0) dataPath.moveTo(p.dx, p.dy);
      else dataPath.lineTo(p.dx, p.dy);
    }
    dataPath.close();
    canvas.drawPath(
      dataPath,
      Paint()..color = AppTheme.primaryPink.withOpacity(0.25),
    );
    canvas.drawPath(
      dataPath,
      Paint()..color = AppTheme.primaryPink..style = PaintingStyle.stroke..strokeWidth = 2,
    );

    // 数据点
    for (var i = 0; i < n; i++) {
      final angle = -math.pi / 2 + 2 * math.pi * i / n;
      final v = dims[i].value.clamp(0, 100) / 100;
      final r = radius * v;
      final p = Offset(center.dx + r * math.cos(angle),
          center.dy + r * math.sin(angle));
      canvas.drawCircle(p, 4, Paint()..color = AppTheme.gold);
      canvas.drawCircle(p, 2, Paint()..color = Colors.white);
    }

    // 标签
    final labelPaint = TextPainter(textDirection: TextDirection.ltr);
    for (var i = 0; i < n; i++) {
      final angle = -math.pi / 2 + 2 * math.pi * i / n;
      final lr = radius + 14;
      final p = Offset(center.dx + lr * math.cos(angle),
          center.dy + lr * math.sin(angle));
      labelPaint.text = TextSpan(
        text: dims[i].name,
        style: const TextStyle(fontSize: 11, color: AppTheme.textPrimary,
            fontWeight: FontWeight.w600),
      );
      labelPaint.layout();
      labelPaint.paint(canvas,
          Offset(p.dx - labelPaint.width / 2, p.dy - labelPaint.height / 2));
    }
  }

  @override
  bool shouldRepaint(covariant _RadarPainter old) => old.dims != dims;
}
