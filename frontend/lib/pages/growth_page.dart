import 'package:flutter/material.dart';
import 'package:grpc/grpc.dart';
import '../theme/theme.dart';
import '../rpc/xiaoling.pbgrpc.dart';

/// 成长页 — 成长状态可视化
class GrowthPage extends StatefulWidget {
  const GrowthPage({super.key});

  @override
  State<GrowthPage> createState() => _GrowthPageState();
}

class _GrowthPageState extends State<GrowthPage> {
  late ClientChannel _chan;
  late XiaoLingClient _stub;
  GrowthStatusReply? _data;
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
      final r = await _stub.getGrowthStatus(Empty());
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
          const Text('成长记录',
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
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: [
          _heroCard(),
          const SizedBox(height: 16),
          _progressCard(),
          const SizedBox(height: 16),
          _statsGrid(),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Widget _heroCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppTheme.primaryPink, AppTheme.lightPink],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.gold, width: 1.5),
        boxShadow: [BoxShadow(color: AppTheme.primaryPink.withOpacity(0.3),
            blurRadius: 16, offset: const Offset(0, 8))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.gold,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(_data!.currentRank,
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700,
                        color: AppTheme.black)),
              ),
              const SizedBox(width: 8),
              Text(_data!.stage,
                  style: const TextStyle(fontSize: 14, color: Colors.white70)),
            ],
          ),
          const SizedBox(height: 14),
          Text('${_data!.progressPercent.toStringAsFixed(1)}%',
              style: const TextStyle(fontSize: 42, fontWeight: FontWeight.w800,
                  color: Colors.white, height: 1)),
          const SizedBox(height: 4),
          const Text('成长进度', style: TextStyle(fontSize: 13, color: Colors.white70)),
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: _data!.progressPercent.clamp(0, 100) / 100,
              minHeight: 8,
              backgroundColor: Colors.white.withOpacity(0.25),
              valueColor: const AlwaysStoppedAnimation(AppTheme.gold),
            ),
          ),
        ],
      ),
    );
  }

  Widget _progressCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: AppTheme.glassCard,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('进化代数',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary)),
          const SizedBox(height: 12),
          Row(
            children: [
              _genCircle(_data!.currentGeneration, true),
              const SizedBox(width: 8),
              const Icon(Icons.arrow_forward, color: AppTheme.textLight, size: 16),
              const SizedBox(width: 8),
              _genCircle(_data!.totalGenerations, false),
            ],
          ),
          const SizedBox(height: 8),
          Text('当前第 ${_data!.currentGeneration} 代 / 共 ${_data!.totalGenerations} 代',
              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
        ],
      ),
    );
  }

  Widget _genCircle(int gen, bool current) {
    return Container(
      width: 44, height: 44,
      decoration: BoxDecoration(
        color: current ? AppTheme.primaryPink : AppTheme.soft,
        shape: BoxShape.circle,
        border: Border.all(color: current ? AppTheme.gold : Colors.transparent, width: 2),
      ),
      child: Center(
        child: Text('$gen',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700,
                color: current ? Colors.white : AppTheme.textSecondary)),
      ),
    );
  }

  Widget _statsGrid() {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.5,
      children: [
        _statCard(Icons.favorite, '交互次数', '${_data!.totalInteractions}'),
        _statCard(Icons.mood, '当前情绪', _data!.emotion),
        _statCard(Icons.auto_mode, '训练状态', _data!.trainingPaused ? '已暂停' : '进行中'),
        _statCard(Icons.emoji_events, '当前段位', _data!.currentRank),
      ],
    );
  }

  Widget _statCard(IconData icon, String label, String value) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.glassCard,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: AppTheme.primaryPink, size: 20),
          const SizedBox(height: 6),
          Text(value,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimary)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textLight)),
        ],
      ),
    );
  }
}
