import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;
import '../services/sandbox.dart';

class ModelStorePage extends StatefulWidget {
  const ModelStorePage({super.key});
  @override
  State<ModelStorePage> createState() => _ModelStorePageState();
}

class _ModelStorePageState extends State<ModelStorePage> with TickerProviderStateMixin {
  pb.HardwareInfo? _hw;
  List<pb.RecommendedModel> _models = [];
  pb.ModelList? _installed;
  bool _loading = true;
  String? _error;
  String _category = 'all';
  String _sort = 'recommended';
  final _searchCtrl = TextEditingController();
  String _query = '';
  final Set<String> _downloading = {};
  final Map<String, _DlInfo> _dlInfo = {};
  final Map<String, StreamSubscription<pb.DownloadProgress>> _dlSubs = {};
  final Map<String, double> _dlSpeed = {};
  final Map<String, int> _lastDlTick = {};
  final Set<String> _compareSelected = {};
  final Set<String> _favorites = {};
  bool _favOnly = false;
  String _quantFilter = 'all';
  String? _installedName;
  late AnimationController _enterCtrl;
  late AnimationController _pulseCtrl;
  late AnimationController _scanCtrl;
  late Animation<double> _enterAnim;

  static const _categories = <String, String>{
    'all': '全部',
    'tiny': '轻量',
    'balanced': '均衡',
    'quality': '高质',
    'cuda': 'GPU 加速',
  };

  static const _sorts = <String, String>{
    'recommended': '智能推荐',
    'size': '体积优先',
    'quality': '质量优先',
    'ram': '省内存',
  };

  static const _fallbackHw = _HwSnapshot(
    ram: 16.0,
    vram: 8.0,
    cores: 8,
    diskFree: 240.0,
    gpu: 'Integrated',
    platform: 'Windows',
    hasCuda: false,
    hasMetal: false,
  );

  static const _fallbackModels = <_ModelItem>[
    _ModelItem('Qwen2.5-0.5B-Instruct-Q4', '0.5B', 'Q4_K_M', 0.5, 3.2, 42, '8K', 352.0, true, false, 'tiny', 'pink'),
    _ModelItem('Qwen2.5-1.5B-Instruct-Q4', '1.5B', 'Q4_K_M', 1.2, 5.8, 68, '16K', 986.0, true, true, 'balanced', 'gold'),
    _ModelItem('Qwen2.5-1.5B-Instruct-Q8', '1.5B', 'Q8_0', 2.0, 7.4, 74, '16K', 1620.0, true, false, 'balanced', 'gold'),
    _ModelItem('Qwen2.5-3B-Instruct-Q4', '3B', 'Q4_K_M', 2.8, 9.6, 82, '32K', 1980.0, true, false, 'quality', 'violet'),
    _ModelItem('Qwen2.5-7B-Instruct-Q4', '7B', 'Q4_K_M', 5.4, 12.8, 90, '32K', 4460.0, false, false, 'quality', 'violet'),
    _ModelItem('Qwen2.5-14B-Instruct-Q4', '14B', 'Q4_K_M', 10.2, 20.4, 94, '32K', 8820.0, false, false, 'cuda', 'green'),
    _ModelItem('Llama-3.2-1B-Instruct-Q4', '1B', 'Q4_K_M', 1.0, 4.8, 62, '8K', 810.0, true, false, 'tiny', 'pink'),
    _ModelItem('Llama-3.2-3B-Instruct-Q4', '3B', 'Q4_K_M', 2.6, 8.6, 78, '8K', 2020.0, true, false, 'balanced', 'gold'),
    _ModelItem('Phi-3.5-mini-Q4', '3.8B', 'Q4_K_M', 3.0, 9.2, 80, '128K', 2340.0, true, false, 'quality', 'blue'),
    _ModelItem('Gemma-2-2B-Instruct-Q4', '2B', 'Q4_K_M', 1.8, 6.4, 71, '8K', 1610.0, true, false, 'balanced', 'pink'),
    _ModelItem('Gemma-2-9B-Instruct-Q4', '9B', 'Q4_K_M', 6.6, 14.2, 91, '8K', 5380.0, false, false, 'cuda', 'violet'),
    _ModelItem('DeepSeek-R1-Distill-1.5B', '1.5B', 'Q4_K_M', 1.4, 5.4, 70, '64K', 1120.0, true, false, 'balanced', 'green'),
  ];

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 900), vsync: this);
    _pulseCtrl = AnimationController(duration: const Duration(seconds: 4), vsync: this)..repeat();
    _scanCtrl = AnimationController(duration: const Duration(seconds: 3), vsync: this)..repeat();
    _enterAnim = CurvedAnimation(parent: _enterCtrl, curve: XlCurve.easeOut);
    _enterCtrl.forward();
    _load();
  }

  @override
  void dispose() {
    for (final s in _dlSubs.values) {
      s.cancel();
    }
    _enterCtrl.dispose();
    _pulseCtrl.dispose();
    _scanCtrl.dispose();
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final pair = await XlClient.stub.refreshHardware();
      final inst = await XlClient.stub.safe(() => XlClient.stub.installedModels());
      if (!mounted) return;
      setState(() {
        _hw = pair.hw;
        _models = pair.models?.models ?? [];
        _installed = inst;
        if (inst != null && inst.models.isNotEmpty) {
          _installedName = inst.models.first.name;
        }
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Color _colorOf(XlPalette p, String key) {
    switch (key) {
      case 'pink': return p.pink;
      case 'gold': return p.gold;
      case 'violet': return p.violet;
      case 'green': return p.green;
      case 'blue': return p.blue;
      case 'red': return p.red;
      default: return p.pink;
    }
  }

  _HwSnapshot get _hwSnap {
    final hw = _hw;
    if (hw == null) return _fallbackHw;
    return _HwSnapshot(
      ram: hw.ramGb,
      vram: hw.vramGb,
      cores: hw.cpuCores,
      diskFree: hw.diskFreeGb,
      gpu: hw.displayGpu,
      platform: hw.displayPlatform,
      hasCuda: hw.hasCuda,
      hasMetal: hw.hasMetal,
    );
  }

  List<_ModelItem> get _source {
    if (_models.isEmpty) return _fallbackModels;
    return _models.map((m) {
      final category = m.tier == '轻量'
          ? 'tiny'
          : m.tier == '均衡'
              ? 'balanced'
              : m.tier == '旗舰'
                  ? 'cuda'
                  : 'quality';
      final color = category == 'tiny'
          ? 'pink'
          : category == 'balanced'
              ? 'gold'
              : category == 'cuda'
                  ? 'green'
                  : 'violet';
      return _ModelItem(
        m.displayName,
        m.displayParams,
        m.displayQuant,
        m.vramGb,
        m.ramGb,
        m.quality,
        m.displayContext,
        m.sizeMb,
        m.canRun,
        m.recommended,
        category,
        color,
      );
    }).toList();
  }

  List<_ModelItem> get _filtered {
    var list = _source.where((it) {
      if (_category != 'all' && it.category != _category) return false;
      if (_favOnly && !_favorites.contains(it.name)) return false;
      if (_quantFilter != 'all' && !it.quant.toUpperCase().startsWith(_quantFilter)) return false;
      if (_query.isEmpty) return true;
      return it.name.toLowerCase().contains(_query) ||
          it.params.toLowerCase().contains(_query) ||
          it.quant.toLowerCase().contains(_query);
    }).toList();

    switch (_sort) {
      case 'size':
        list.sort((a, b) => a.sizeMb.compareTo(b.sizeMb));
        break;
      case 'quality':
        list.sort((a, b) => b.quality.compareTo(a.quality));
        break;
      case 'ram':
        list.sort((a, b) => a.ramGb.compareTo(b.ramGb));
        break;
      default:
        list.sort((a, b) {
          if (a.recommended != b.recommended) return a.recommended ? -1 : 1;
          return b.quality.compareTo(a.quality);
        });
    }
    return list;
  }

  int get _runnableCount => _source.where((it) => it.canRun).length;

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    if (_loading) return _loadingView(p);
    return Stack(
      children: [
        Positioned.fill(child: AppTheme.aurora(context, child: const SizedBox.shrink())),
        AnimatedBuilder(
          animation: _enterAnim,
          builder: (_, __) => Opacity(
            opacity: _enterAnim.value,
            child: Transform.translate(
              offset: Offset(0, (1 - _enterAnim.value) * 16),
              child: _body(p),
            ),
          ),
        ),
      ],
    );
  }

  Widget _body(XlPalette p) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _heroRow(p),
          const SizedBox(height: 22),
          _hwCard(p),
          const SizedBox(height: 20),
          _statsRow(p),
          const SizedBox(height: 20),
          _toolbar(p),
          const SizedBox(height: 14),
          if (_downloading.isNotEmpty) ...[
            _downloadQueueBar(p),
            const SizedBox(height: 14),
          ],
          if (_compareSelected.length >= 2) _compareBar(p),
          const SizedBox(height: 18),
          _grid(p),
          const SizedBox(height: 20),
          _footerNote(p),
        ],
      ),
    );
  }

  Widget _heroRow(XlPalette p) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text('模型商店',
                      style: TextStyle(
                        fontSize: XlFont.h2,
                        fontWeight: FontWeight.w800,
                        color: p.text1,
                        letterSpacing: XlLetterSpacing.normal,
                      )),
                  const SizedBox(width: 12),
                  _chip(p, '$_runnableCount 个可运行', p.green),
                ],
              ),
              const SizedBox(height: 6),
              Text('根据你的硬件自动推荐最合适的本地模型',
                  style: TextStyle(
                    fontSize: XlFont.caption,
                    color: p.text2,
                    fontWeight: FontWeight.w500,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
            ],
          ),
        ),
        const SizedBox(width: 16),
        _iconBtn(p, Icons.refresh_rounded, '重新扫描', _load),
      ],
    );
  }

  Widget _iconBtn(XlPalette p, IconData icon, String label, VoidCallback onTap) {
    return _Pressable(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: AppTheme.neuXs(context, r: XlRadius.lg),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 15, color: p.pink),
            const SizedBox(width: 8),
            Text(label,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w700,
                  color: p.text1,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _hwCard(XlPalette p) {
    final hw = _hwSnap;
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              AnimatedBuilder(
                animation: _scanCtrl,
                builder: (_, __) {
                  final t = _scanCtrl.value;
                  return Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: p.green,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: p.green.withOpacity(0.5 + t * 0.4),
                          blurRadius: 8 + t * 4,
                          spreadRadius: -1,
                        ),
                      ],
                    ),
                  );
                },
              ),
              const SizedBox(width: 10),
              Text('硬件检测',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
              const SizedBox(width: 10),
              _chip(p, 'SCANNED', p.green),
              const Spacer(),
              Text('实时读取',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w600,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
          const SizedBox(height: 18),
          LayoutBuilder(
            builder: (context, c) {
              final cols = c.maxWidth > 1000 ? 4 : c.maxWidth > 620 ? 2 : 1;
              final items = <_HwStat>[
                _HwStat('系统内存', '${hw.ram.toStringAsFixed(1)}', 'GB', Icons.memory_rounded, 'pink', (hw.ram / 32).clamp(0.0, 1.0)),
                _HwStat('显存', hw.vram <= 0 ? '共享' : hw.vram.toStringAsFixed(1), hw.vram <= 0 ? '' : 'GB', Icons.videogame_asset_rounded, 'gold', (hw.vram / 16).clamp(0.0, 1.0)),
                _HwStat('CPU 核心', '${hw.cores}', '核', Icons.speed_rounded, 'violet', (hw.cores / 16).clamp(0.0, 1.0)),
                _HwStat('可用磁盘', '${hw.diskFree.toStringAsFixed(0)}', 'GB', Icons.storage_rounded, 'green', (hw.diskFree / 500).clamp(0.0, 1.0)),
              ];
              return GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: cols,
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  childAspectRatio: cols == 4 ? 2.2 : (cols == 2 ? 2.6 : 4.0),
                ),
                itemCount: items.length,
                itemBuilder: (_, i) => _hwStat(p, items[i], i),
              );
            },
          ),
          const SizedBox(height: 16),
          _accelPanel(p, hw),
        ],
      ),
    );
  }

  Widget _hwStat(XlPalette p, _HwStat s, int i) {
    final color = _colorOf(p, s.color);
    return TweenAnimationBuilder<double>(
      duration: Duration(milliseconds: 400 + i * 80),
      curve: XlCurve.easeOut,
      tween: Tween(begin: 0.0, end: 1.0),
      builder: (_, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, (1 - t) * 10), child: child),
      ),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: AppTheme.neuXs(context, r: XlRadius.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                    borderRadius: BorderRadius.circular(XlRadius.xs),
                    border: Border.all(color: color.withOpacity(0.28), width: 1),
                  ),
                  child: Icon(s.icon, size: 13, color: color),
                ),
                const Spacer(),
                Text(s.label,
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.text3,
                      fontWeight: FontWeight.w700,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(s.value,
                    style: TextStyle(
                      fontSize: XlFont.h5,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.tight,
                      fontFeatures: const [FontFeature.tabularFigures()],
                      height: 1.0,
                    )),
                if (s.unit.isNotEmpty) ...[
                  const SizedBox(width: 2),
                  Text(s.unit,
                      style: TextStyle(
                        fontSize: XlFont.label,
                        fontWeight: FontWeight.w700,
                        color: p.text3,
                      )),
                ],
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: s.progress,
                minHeight: 3,
                backgroundColor: p.surfaceLo,
                valueColor: AlwaysStoppedAnimation(color),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _accelPanel(XlPalette p, _HwSnapshot hw) {
    final color = hw.hasCuda ? p.green : (hw.hasMetal ? p.violet : p.blue);
    final label = hw.hasCuda ? 'CUDA' : (hw.hasMetal ? 'METAL' : 'CPU');
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: AppTheme.neuXs(context, r: XlRadius.md),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: [color, color.withOpacity(0.75)]),
              borderRadius: BorderRadius.circular(XlRadius.sm),
              border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.32 : 0.48), width: 1),
              boxShadow: p.raisedXxs,
            ),
            child: Icon(
              hw.hasCuda ? Icons.flash_on_rounded : (hw.hasMetal ? Icons.apple_rounded : Icons.laptop_rounded),
              size: 15,
              color: p.isDark ? p.btnInk : Colors.white,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(hw.gpu,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                const SizedBox(height: 2),
                Text('${hw.platform} · ${hw.hasCuda ? "CUDA 加速可用" : hw.hasMetal ? "Metal 加速可用" : "仅 CPU 推理"}',
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text3,
                      fontWeight: FontWeight.w500,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: color.withOpacity(p.isDark ? 0.14 : 0.10),
              borderRadius: BorderRadius.circular(XlRadius.pill),
              border: Border.all(color: color.withOpacity(0.30), width: 1),
            ),
            child: Text(label,
                style: TextStyle(
                  fontSize: XlFont.micro,
                  fontWeight: FontWeight.w800,
                  color: color,
                  letterSpacing: XlLetterSpacing.ultra,
                )),
          ),
        ],
      ),
    );
  }

  Widget _statsRow(XlPalette p) {
    final models = _source;
    final runnable = models.where((m) => m.canRun).length;
    final rec = models.where((m) => m.recommended).length;
    final best = models.where((m) => m.canRun).fold<double>(0, (a, b) => a > b.quality.toDouble() ? a : b.quality.toDouble());
    final installedCount = _installed?.models.length ?? 0;
    return LayoutBuilder(
      builder: (context, c) {
        final cols = c.maxWidth > 1180 ? 4 : c.maxWidth > 780 ? 2 : 1;
        final items = <_Sum>[
          _Sum('可选模型', '${models.length}', '个', Icons.inventory_2_outlined, 'pink', 1.0),
          _Sum('可运行', '$runnable', '个', Icons.check_circle_outline_rounded, 'green', models.isEmpty ? 0.0 : runnable / models.length),
          _Sum('推荐', '$rec', '个', Icons.star_outline_rounded, 'gold', models.isEmpty ? 0.0 : rec / models.length),
          _Sum('已安装', '$installedCount', '个', Icons.download_done_rounded, 'violet', installedCount == 0 ? 0.0 : (installedCount / 5).clamp(0.0, 1.0)),
        ];
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: cols,
            mainAxisSpacing: 14,
            crossAxisSpacing: 14,
            childAspectRatio: cols == 4 ? 2.4 : (cols == 2 ? 3.0 : 4.4),
          ),
          itemCount: items.length,
          itemBuilder: (_, i) => _sumCard(p, items[i], i, best),
        );
      },
    );
  }

  Widget _sumCard(XlPalette p, _Sum s, int i, double best) {
    final color = _colorOf(p, s.color);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: color.withOpacity(p.isDark ? 0.14 : 0.10),
              borderRadius: BorderRadius.circular(XlRadius.md),
              border: Border.all(color: color.withOpacity(0.28), width: 1),
            ),
            child: Icon(s.icon, size: 17, color: color),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.label,
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text3,
                      fontWeight: FontWeight.w700,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
                const SizedBox(height: 3),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(s.value,
                        style: TextStyle(
                          fontSize: XlFont.h4,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.tight,
                          fontFeatures: const [FontFeature.tabularFigures()],
                          height: 1.0,
                        )),
                    const SizedBox(width: 3),
                    Text(s.unit,
                        style: TextStyle(
                          fontSize: XlFont.label,
                          fontWeight: FontWeight.w700,
                          color: p.text3,
                        )),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _toolbar(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Container(
                  height: 42,
                  decoration: AppTheme.sunkenXs(context, r: XlRadius.lg),
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  child: Row(
                    children: [
                      Icon(Icons.search_rounded, size: 16, color: p.decor),
                      const SizedBox(width: 10),
                      Expanded(
                        child: TextField(
                          controller: _searchCtrl,
                          onChanged: (v) => setState(() => _query = v.trim().toLowerCase()),
                          style: TextStyle(fontSize: XlFont.caption, color: p.text1),
                          decoration: InputDecoration(
                            hintText: '搜索模型名称、参数量或量化方式…',
                            hintStyle: TextStyle(fontSize: XlFont.caption, color: p.decor),
                            border: InputBorder.none,
                            isDense: true,
                            contentPadding: EdgeInsets.zero,
                          ),
                        ),
                      ),
                      if (_query.isNotEmpty)
                        GestureDetector(
                          onTap: () {
                            _searchCtrl.clear();
                            setState(() => _query = '');
                          },
                          child: Icon(Icons.close_rounded, size: 16, color: p.decor),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 12),
              _sortPicker(p),
            ],
          ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerLeft,
            child: LayoutBuilder(
              builder: (context, c) {
                final entries = _categories.entries.toList();
                final n = entries.length;
                final cell = c.maxWidth / n;
                final selIdx = entries.indexWhere((e) => e.key == _category);
                return Container(
                  padding: const EdgeInsets.all(4),
                  decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
                  child: SizedBox(
                    height: 32,
                    child: Stack(
                      children: [
                        AnimatedPositioned(
                          duration: XlDuration.normal,
                          curve: XlCurve.spring,
                          left: selIdx < 0 ? 0 : selIdx * cell,
                          top: 0,
                          bottom: 0,
                          width: cell,
                          child: Container(
                            decoration: AppTheme.brand(context, r: XlRadius.pill),
                          ),
                        ),
                        Row(
                          children: [
                            for (final e in entries)
                              Expanded(
                                child: Material(
                                  color: Colors.transparent,
                                  child: InkWell(
                                    onTap: () => setState(() => _category = e.key),
                                    borderRadius: BorderRadius.circular(XlRadius.pill),
                                    child: Center(
                                      child: Text(e.value,
                                          style: TextStyle(
                                            fontSize: XlFont.captionSm,
                                            fontWeight: _category == e.key ? FontWeight.w800 : FontWeight.w600,
                                            color: _category == e.key ? p.btnInk : p.text2,
                                            letterSpacing: XlLetterSpacing.wide,
                                          )),
                                    ),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 12),
          Align(alignment: Alignment.centerLeft, child: _filterExtras(p)),
        ],
      ),
    );
  }

  Widget _sortPicker(XlPalette p) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: _sort,
          isDense: true,
          icon: Icon(Icons.sort_rounded, size: 16, color: p.pink),
          dropdownColor: p.surfaceHi,
          borderRadius: BorderRadius.circular(XlRadius.md),
          style: TextStyle(
            fontSize: XlFont.captionSm,
            fontWeight: FontWeight.w700,
            color: p.text1,
            letterSpacing: XlLetterSpacing.wide,
          ),
          items: _sorts.entries.map((e) => DropdownMenuItem<String>(
            value: e.key,
            child: Text(e.value,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w700,
                  color: e.key == _sort ? p.pink : p.text1,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          )).toList(),
          onChanged: (v) {
            if (v != null) setState(() => _sort = v);
          },
        ),
      ),
    );
  }

  Widget _grid(XlPalette p) {
    final list = _filtered;
    if (list.isEmpty) return _emptyView(p);
    return LayoutBuilder(
      builder: (context, c) {
        final cols = c.maxWidth > 1180 ? 3 : c.maxWidth > 780 ? 2 : 1;
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          padding: EdgeInsets.zero,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: cols,
            mainAxisSpacing: 16,
            crossAxisSpacing: 16,
            childAspectRatio: cols == 1 ? 1.9 : 1.15,
          ),
          itemCount: list.length,
          itemBuilder: (_, i) => _modelCard(p, list[i], i),
        );
      },
    );
  }

  Widget _modelCard(XlPalette p, _ModelItem m, int i) {
    final color = _colorOf(p, m.color);
    final downloading = _downloading.contains(m.name);
    final dl = _dlInfo[m.name];
    final progress = dl?.ratio ?? 0.0;
    final dlError = dl?.error;
    final installed = _installedName == m.name;
    return TweenAnimationBuilder<double>(
      duration: Duration(milliseconds: 400 + i * 60),
      curve: XlCurve.easeOut,
      tween: Tween(begin: 0.0, end: 1.0),
      builder: (_, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, (1 - t) * 16), child: child),
      ),
      child: GestureDetector(
        onLongPress: () => setState(() {
          if (_compareSelected.contains(m.name)) {
            _compareSelected.remove(m.name);
          } else {
            _compareSelected.add(m.name);
          }
        }),
        child: _HoverGlow(
        color: color,
        child: Stack(
          children: [
          Container(
          padding: const EdgeInsets.all(20),
          decoration: AppTheme.neu(context, r: XlRadius.xxl),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(colors: [color, color.withOpacity(0.72)]),
                      borderRadius: BorderRadius.circular(XlRadius.md),
                      border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.32 : 0.48), width: 1.2),
                      boxShadow: [...p.raisedXs, BoxShadow(color: color.withOpacity(0.35), blurRadius: 16, spreadRadius: -3)],
                    ),
                    child: Icon(Icons.auto_awesome_rounded, size: 20, color: p.isDark ? p.btnInk : Colors.white),
                  ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(m.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: XlFont.caption,
                            fontWeight: FontWeight.w800,
                            color: p.text1,
                            letterSpacing: XlLetterSpacing.wide,
                          )),
                      const SizedBox(height: 3),
                      Row(
                        children: [
                          Text('${m.params} · ${m.quant}',
                              style: TextStyle(
                                fontSize: XlFont.label,
                                color: p.text3,
                                fontWeight: FontWeight.w600,
                                letterSpacing: XlLetterSpacing.wider,
                              )),
                          const SizedBox(width: 8),
                          if (m.recommended)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                              decoration: BoxDecoration(
                                color: p.gold.withOpacity(p.isDark ? 0.18 : 0.12),
                                borderRadius: BorderRadius.circular(XlRadius.xs),
                                border: Border.all(color: p.gold.withOpacity(0.35), width: 1),
                              ),
                              child: Text('推荐',
                                  style: TextStyle(
                                    fontSize: XlFont.micro,
                                    fontWeight: FontWeight.w800,
                                    color: p.gold,
                                    letterSpacing: XlLetterSpacing.wider,
                                  )),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                _favHeart(p, m),
                _statusPill(p, m.canRun, installed, downloading),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(child: _miniStat(p, '质量', '${m.quality}', p.pink, m.quality / 100)),
                const SizedBox(width: 10),
                Expanded(child: _miniStat(p, '上下文', m.context, p.gold, m.context.contains('128') ? 1.0 : (m.context.contains('64') ? 0.7 : (m.context.contains('32') ? 0.5 : 0.3)))),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(child: _miniStat(p, '内存', '${m.ramGb.toStringAsFixed(1)} GB', p.violet, (m.ramGb / 20).clamp(0.0, 1.0))),
                const SizedBox(width: 10),
                Expanded(child: _miniStat(p, '体积', '${(m.sizeMb / 1024).toStringAsFixed(1)} GB', p.green, (m.sizeMb / 8000).clamp(0.0, 1.0))),
              ],
            ),
            const SizedBox(height: 16),
            if (downloading) ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: AppTheme.screenSoft(context, r: XlRadius.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      height: 8,
                      decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
                      child: FractionallySizedBox(
                        alignment: Alignment.centerLeft,
                        widthFactor: progress.clamp(0.0, 1.0),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(XlRadius.pill),
                          child: Stack(
                            children: [
                              Container(
                                decoration: BoxDecoration(
                                  gradient: p.gradBrand,
                                  borderRadius: BorderRadius.circular(XlRadius.pill),
                                  boxShadow: [BoxShadow(color: p.pink.withOpacity(0.4), blurRadius: 8, spreadRadius: -2)],
                                ),
                              ),
                              Positioned.fill(
                                child: AnimatedBuilder(
                                  animation: _scanCtrl,
                                  builder: (_, __) {
                                    final t = _scanCtrl.value;
                                    return FractionallySizedBox(
                                      alignment: Alignment(-1 + t * 3 - 1, 0),
                                      widthFactor: 0.4,
                                      child: DecoratedBox(
                                        decoration: BoxDecoration(
                                          gradient: LinearGradient(
                                            colors: [
                                              Colors.white.withOpacity(0),
                                              Colors.white.withOpacity(0.35),
                                              Colors.white.withOpacity(0),
                                            ],
                                          ),
                                        ),
                                      ),
                                    );
                                  },
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Icon(Icons.download_rounded, size: 12, color: color),
                        const SizedBox(width: 6),
                        TweenAnimationBuilder<double>(
                          tween: Tween(begin: 0, end: (progress * 100)),
                          duration: const Duration(milliseconds: 200),
                          curve: Curves.linear,
                          builder: (_, v, __) => Text('${v.toStringAsFixed(0)}%',
                              style: TextStyle(
                                fontSize: XlFont.micro,
                                fontWeight: FontWeight.w800,
                                color: color,
                                letterSpacing: XlLetterSpacing.wider,
                                fontFeatures: const [FontFeature.tabularFigures()],
                              )),
                        ),
                        const Spacer(),
                        TweenAnimationBuilder<double>(
                          tween: Tween(begin: 0, end: dl?.downloadedMb ?? 0),
                          duration: const Duration(milliseconds: 200),
                          curve: Curves.linear,
                          builder: (_, v, __) => Text(
                              dl != null
                                  ? '${v.toStringAsFixed(1)} / ${dl.totalMb.toStringAsFixed(1)} MB'
                                  : '',
                              style: TextStyle(
                                fontSize: XlFont.micro,
                                fontWeight: FontWeight.w700,
                                color: p.text3,
                                fontFeatures: const [FontFeature.tabularFigures()],
                                letterSpacing: XlLetterSpacing.wider,
                              )),
                        ),
                      ],
                    ),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            Text('${(_dlSpeed[m.name] ?? 0).toStringAsFixed(1)} MB/s',
                                style: TextStyle(
                                  fontSize: XlFont.micro,
                                  fontWeight: FontWeight.w800,
                                  color: p.gold,
                                  letterSpacing: XlLetterSpacing.wider,
                                )),
                            const Spacer(),
                            if (dl != null && dl.status.isNotEmpty)
                          Expanded(
                            child: Text(dl.status,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: XlFont.micro,
                                  fontWeight: FontWeight.w600,
                                  color: p.text3,
                                  letterSpacing: XlLetterSpacing.wider,
                                )),
                          ),
                        const Spacer(),
                        GestureDetector(
                          onTap: () {
                            _dlSubs[m.name]?.cancel();
                            _dlSubs.remove(m.name);
                            setState(() {
                              _downloading.remove(m.name);
                            });
                          },
                          child: Text('取消',
                              style: TextStyle(
                                fontSize: XlFont.micro,
                                fontWeight: FontWeight.w800,
                                color: p.red,
                                letterSpacing: XlLetterSpacing.wider,
                              )),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ] else if (dlError != null) ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: p.red.withOpacity(p.isDark ? 0.12 : 0.08),
                  borderRadius: BorderRadius.circular(XlRadius.lg),
                  border: Border.all(color: p.red.withOpacity(0.30), width: 1),
                ),
                child: Row(
                  children: [
                    Icon(Icons.error_outline_rounded, size: 14, color: p.red),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(dlError,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: XlFont.micro,
                            fontWeight: FontWeight.w700,
                            color: p.red,
                            letterSpacing: XlLetterSpacing.wider,
                          )),
                    ),
                    GestureDetector(
                      onTap: () => setState(() => _dlInfo.remove(m.name)),
                      child: Icon(Icons.close_rounded, size: 14, color: p.text3),
                    ),
                  ],
                ),
              ),
            ] else
              AnimatedSwitcher(
                duration: XlDuration.normal,
                switchInCurve: XlCurve.spring,
                transitionBuilder: (child, anim) => ScaleTransition(
                  scale: anim,
                  child: FadeTransition(opacity: anim, child: child),
                ),
                child: KeyedSubtree(
                  key: ValueKey('btn_${installed ? 1 : 0}_${m.canRun ? 1 : 0}'),
                  child: _actionBtn(p, m, installed, color),
                ),
              ),
          ],
        ),
          ),
          if (installed)
            Positioned(
              top: 0,
              left: 0,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: [p.gold, p.gold.withOpacity(0.8)]),
                  borderRadius: const BorderRadius.only(topLeft: Radius.circular(XlRadius.xxl), bottomRight: Radius.circular(XlRadius.md)),
                  boxShadow: [BoxShadow(color: p.gold.withOpacity(0.4), blurRadius: 8, spreadRadius: -2)],
                ),
                child: Text('已安装',
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      fontWeight: FontWeight.w800,
                      color: p.btnInk,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ),
            ),
          ],
        ),
      ),
      ),
    );
  }

  Widget _statusPill(XlPalette p, bool canRun, bool installed, bool downloading) {
    if (installed) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
        decoration: BoxDecoration(
          color: p.green.withOpacity(p.isDark ? 0.14 : 0.10),
          borderRadius: BorderRadius.circular(XlRadius.pill),
          border: Border.all(color: p.green.withOpacity(0.30), width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.check_rounded, size: 11, color: p.green),
            const SizedBox(width: 4),
            Text('已装',
                style: TextStyle(
                  fontSize: XlFont.micro,
                  fontWeight: FontWeight.w800,
                  color: p.green,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      );
    }
    if (downloading) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
        decoration: BoxDecoration(
          color: p.pink.withOpacity(p.isDark ? 0.14 : 0.10),
          borderRadius: BorderRadius.circular(XlRadius.pill),
          border: Border.all(color: p.pink.withOpacity(0.30), width: 1),
        ),
        child: Text('下载中',
            style: TextStyle(
              fontSize: XlFont.micro,
              fontWeight: FontWeight.w800,
              color: p.pink,
              letterSpacing: XlLetterSpacing.wider,
            )),
      );
    }
    if (!canRun) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
        decoration: BoxDecoration(
          color: p.red.withOpacity(p.isDark ? 0.14 : 0.10),
          borderRadius: BorderRadius.circular(XlRadius.pill),
          border: Border.all(color: p.red.withOpacity(0.30), width: 1),
        ),
        child: Text('不足',
            style: TextStyle(
              fontSize: XlFont.micro,
              fontWeight: FontWeight.w800,
              color: p.red,
              letterSpacing: XlLetterSpacing.wider,
            )),
      );
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: p.green.withOpacity(p.isDark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: p.green.withOpacity(0.30), width: 1),
      ),
      child: Text('可运行',
          style: TextStyle(
            fontSize: XlFont.micro,
            fontWeight: FontWeight.w800,
            color: p.green,
            letterSpacing: XlLetterSpacing.wider,
          )),
    );
  }

  Widget _miniStat(XlPalette p, String label, String value, Color color, double progress) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(label,
                style: TextStyle(
                  fontSize: XlFont.micro,
                  color: p.text3,
                  fontWeight: FontWeight.w700,
                  letterSpacing: XlLetterSpacing.wider,
                )),
            const Spacer(),
            Flexible(
              child: Text(value,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w800,
                    color: color,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  )),
            ),
          ],
        ),
        const SizedBox(height: 5),
        ClipRRect(
          borderRadius: BorderRadius.circular(2),
          child: LinearProgressIndicator(
            value: progress.clamp(0.0, 1.0),
            minHeight: 3,
            backgroundColor: p.surfaceLo,
            valueColor: AlwaysStoppedAnimation(color),
          ),
        ),
      ],
    );
  }

  Widget _actionBtn(XlPalette p, _ModelItem m, bool installed, Color color) {
    if (installed) {
      return Row(
        children: [
          Expanded(child: _btn(p, Icons.check_circle_rounded, '已安装', () => setState(() => _installedName = null))),
          const SizedBox(width: 8),
          _iconAction(p, Icons.delete_outline_rounded, p.red, () => setState(() => _installedName = null)),
        ],
      );
    }
    if (!m.canRun) {
      return Container(
        padding: const EdgeInsets.symmetric(vertical: 13),
        decoration: AppTheme.sunkenSm(context, r: XlRadius.pill),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.lock_outline_rounded, size: 14, color: p.decor),
            const SizedBox(width: 8),
            Text('硬件不足 · 需要 ${m.ramGb.toStringAsFixed(1)} GB 内存',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  color: p.decor,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          ],
        ),
      );
    }
    return Row(
      children: [
        Expanded(child: _btn(p, Icons.download_rounded, '下载', () => _startDownload(m))),
        const SizedBox(width: 8),
        _iconAction(p, Icons.info_outline_rounded, p.text2, () => _showInfo(p, m)),
      ],
    );
  }

  Widget _btn(XlPalette p, IconData icon, String label, VoidCallback onTap) {
    return _Pressable(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 13),
        decoration: AppTheme.btn(context, r: XlRadius.pill),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 14, color: p.btnInk),
            const SizedBox(width: 6),
            Text(label,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  color: p.btnInk,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _iconAction(XlPalette p, IconData icon, Color color, VoidCallback onTap) {
    return _Pressable(
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: AppTheme.neuXs(context, r: XlRadius.pill),
        child: Icon(icon, size: 15, color: color),
      ),
    );
  }

  void _startDownload(_ModelItem m) {
    if (_downloading.contains(m.name)) return;
    if (Platform.isAndroid) {
      _startSandboxDownload(m);
      return;
    }
    setState(() {
      _downloading.add(m.name);
      _dlInfo[m.name] = const _DlInfo(percent: 0);
    });
    final sub = XlClient.stub.download(m.name, quant: m.quant).listen(
      (p) {
        if (!mounted) return;
        final nowMs = DateTime.now().millisecondsSinceEpoch;
        final prevTick = _lastDlTick[m.name];
        final prevInfo = _dlInfo[m.name];
        if (prevTick != null && prevInfo != null) {
          final dt = (nowMs - prevTick) / 1000.0;
          if (dt >= 0.5) {
            final dm = p.downloadedMb - prevInfo.downloadedMb;
            final speed = dm / dt;
            _dlSpeed[m.name] = speed.clamp(0.0, 999.0);
            _lastDlTick[m.name] = nowMs;
          }
        } else {
          _lastDlTick[m.name] = nowMs;
        }
        setState(() {
          _dlInfo[m.name] = _DlInfo(
            percent: p.percent,
            downloadedMb: p.downloadedMb,
            totalMb: p.totalMb,
            status: p.status,
          );
        });
      },
      onError: (e) {
        if (!mounted) return;
        _dlSubs.remove(m.name);
        setState(() {
          _downloading.remove(m.name);
          _dlInfo[m.name] = _DlInfo(percent: 0, error: e.toString());
        });
      },
      onDone: () {
        if (!mounted) return;
        _dlSubs.remove(m.name);
        final hadError = _dlInfo[m.name]?.error != null;
        if (!hadError && _downloading.contains(m.name)) {
          setState(() {
            _downloading.remove(m.name);
            _installedName = m.name;
          });
          ScaffoldMessenger.of(context).clearSnackBars();
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            behavior: SnackBarBehavior.floating,
            backgroundColor: XlPalette.of(context).surface,
            elevation: 0,
            duration: const Duration(milliseconds: 1600),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.md)),
            content: Row(
              children: [
                Icon(Icons.check_circle_rounded, size: 16, color: XlPalette.of(context).green),
                const SizedBox(width: 10),
                Expanded(
                  child: Text('${m.name} 下载完成',
                      style: TextStyle(
                        color: XlPalette.of(context).text1,
                        fontSize: XlFont.captionSm,
                        fontWeight: FontWeight.w700,
                      )),
                ),
              ],
            ),
          ));
        }
      },
    );
    _dlSubs[m.name] = sub;
  }

  void _startSandboxDownload(_ModelItem m) async {
    if (_downloading.contains(m.name)) return;
    setState(() {
      _downloading.add(m.name);
      _dlInfo[m.name] = const _DlInfo(percent: 0, status: 'starting');
    });
    try {
      await SandboxService.downloadModel(m.name, quant: m.quant);
    } catch (e) {
      if (mounted) {
        setState(() {
          _downloading.remove(m.name);
          _dlInfo[m.name] = _DlInfo(percent: 0, error: e.toString());
        });
      }
      return;
    }
    for (int i = 0; i < 60 * 60; i++) {
      await Future.delayed(const Duration(milliseconds: 600));
      if (!mounted) return;
      final st = await SandboxService.status();
      final snap = st['snapshot'];
      Map<String, dynamic>? prog;
      if (snap is Map && snap['progress'] is Map) {
        final p = snap['progress'] as Map;
        final v = p[m.name];
        if (v is Map) prog = Map<String, dynamic>.from(v);
      }
      final status = prog?['status']?.toString() ?? '';
      if (status == 'error') {
        setState(() {
          _downloading.remove(m.name);
          _dlInfo[m.name] = _DlInfo(
            percent: (prog?['percent'] as num?)?.toDouble() ?? 0,
            error: prog?['error']?.toString() ?? '下载失败',
          );
        });
        return;
      }
      if (status == 'installed') {
        setState(() {
          _downloading.remove(m.name);
          _installedName = m.name;
          _dlInfo[m.name] = _DlInfo(
            percent: 100,
            downloadedMb: (prog?['downloaded_mb'] as num?)?.toDouble() ?? 0,
            totalMb: (prog?['total_mb'] as num?)?.toDouble() ?? 0,
            status: 'done',
          );
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('${m.name} 下载完成'),
            behavior: SnackBarBehavior.floating,
          ));
        }
        return;
      }
      setState(() {
        _dlInfo[m.name] = _DlInfo(
          percent: (prog?['percent'] as num?)?.toDouble() ?? 0,
          downloadedMb: (prog?['downloaded_mb'] as num?)?.toDouble() ?? 0,
          totalMb: (prog?['total_mb'] as num?)?.toDouble() ?? 0,
          status: status,
        );
      });
    }
  }

  Widget _downloadQueueBar(XlPalette p) {
    final active = _downloading.toList();
    final overall = active.isEmpty
        ? 0.0
        : active.map((n) => _dlInfo[n]?.ratio ?? 0.0).reduce((a, b) => a + b) / active.length;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.download_for_offline_rounded, size: 16, color: p.pink),
              const SizedBox(width: 10),
              Text('下载队列',
                  style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide)),
              const Spacer(),
              _chip(p, '${active.length} 个任务', p.gold),
              const SizedBox(width: 8),
              _chip(p, '${(overall * 100).toStringAsFixed(0)}%', p.green),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(99),
            child: Container(
              height: 6,
              color: p.surfaceLo,
              child: FractionallySizedBox(
                alignment: Alignment.centerLeft,
                widthFactor: overall.clamp(0.0, 1.0),
                child: Container(
                  decoration: BoxDecoration(gradient: p.gradBrand, borderRadius: BorderRadius.circular(99)),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          for (final name in active)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Container(
                    width: 6,
                    height: 6,
                    decoration: AppTheme.glowDot(p.pink, size: 6),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                            fontSize: XlFont.label,
                            color: p.text2,
                            fontWeight: FontWeight.w700,
                            letterSpacing: XlLetterSpacing.wide)),
                  ),
                  Text(_dlInfo[name]?.sizeLabel ?? '',
                      style: TextStyle(
                          fontSize: XlFont.micro,
                          color: p.decor,
                          fontWeight: FontWeight.w700,
                          fontFeatures: const [FontFeature.tabularFigures()])),
                  const SizedBox(width: 8),
                  Text('${((_dlInfo[name]?.ratio ?? 0) * 100).toStringAsFixed(0)}%',
                      style: TextStyle(
                          fontSize: XlFont.label,
                          color: p.pink,
                          fontWeight: FontWeight.w800,
                          fontFeatures: const [FontFeature.tabularFigures()])),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _favHeart(XlPalette p, _ModelItem m) {
    final fav = _favorites.contains(m.name);
    return _Pressable(
      onTap: () => setState(() {
        if (fav) {
          _favorites.remove(m.name);
        } else {
          _favorites.add(m.name);
        }
      }),
      child: Padding(
        padding: const EdgeInsets.only(left: 8),
        child: Icon(
          fav ? Icons.favorite_rounded : Icons.favorite_border_rounded,
          size: 18,
          color: fav ? p.pink : p.decor,
        ),
      ),
    );
  }

  Widget _filterExtras(XlPalette p) {
    return Row(
      children: [
        _Pressable(
          onTap: () => setState(() => _favOnly = !_favOnly),
          child: AnimatedContainer(
            duration: XlDuration.fast,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: _favOnly
                ? BoxDecoration(gradient: p.gradBrand, borderRadius: BorderRadius.circular(XlRadius.pill))
                : AppTheme.neuXs(context, r: XlRadius.pill),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.favorite_rounded, size: 13, color: _favOnly ? p.btnInk : p.pink),
                const SizedBox(width: 6),
                Text('收藏 ${_favorites.length}',
                    style: TextStyle(
                        fontSize: XlFont.captionSm,
                        fontWeight: FontWeight.w800,
                        color: _favOnly ? p.btnInk : p.text2,
                        letterSpacing: XlLetterSpacing.wider)),
              ],
            ),
          ),
        ),
        const SizedBox(width: 10),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
          decoration: AppTheme.neuXs(context, r: XlRadius.pill),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: _quantFilter,
              isDense: true,
              icon: Icon(Icons.filter_alt_outlined, size: 15, color: p.gold),
              dropdownColor: p.surfaceHi,
              borderRadius: BorderRadius.circular(XlRadius.md),
              style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w700,
                  color: p.text1,
                  letterSpacing: XlLetterSpacing.wide),
              items: const [
                DropdownMenuItem(value: 'all', child: Text('全部量化')),
                DropdownMenuItem(value: 'Q4', child: Text('Q4 量化')),
                DropdownMenuItem(value: 'Q8', child: Text('Q8 量化')),
              ],
              onChanged: (v) {
                if (v != null) setState(() => _quantFilter = v);
              },
            ),
          ),
        ),
      ],
    );
  }

  Widget _compareBar(XlPalette p) {
    final selected = _source.where((m) => _compareSelected.contains(m.name)).toList();
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: p.gradBrand,
        borderRadius: BorderRadius.circular(XlRadius.lg),
        boxShadow: [BoxShadow(color: p.pink.withOpacity(0.3), blurRadius: 16, spreadRadius: -4)],
      ),
      child: Row(
        children: [
          Icon(Icons.compare_arrows_rounded, size: 16, color: p.btnInk),
          const SizedBox(width: 10),
          Expanded(
            child: Text('已选 ${selected.length} 个模型 · 长按卡片可取消',
                style: TextStyle(fontSize: XlFont.label, fontWeight: FontWeight.w700, color: p.btnInk, letterSpacing: XlLetterSpacing.wide)),
          ),
          _Pressable(
            onTap: () => setState(() => _compareSelected.clear()),
            child: Text('清除',
                style: TextStyle(fontSize: XlFont.label, fontWeight: FontWeight.w800, color: p.btnInk.withOpacity(0.8))),
          ),
          const SizedBox(width: 12),
          _Pressable(
            onTap: selected.length >= 2 ? () => _showCompareDialog(p, selected[0], selected[1]) : null,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.2),
                borderRadius: BorderRadius.circular(XlRadius.pill),
              ),
              child: Text('对比',
                  style: TextStyle(fontSize: XlFont.label, fontWeight: FontWeight.w800, color: p.btnInk, letterSpacing: XlLetterSpacing.wider)),
            ),
          ),
        ],
      ),
    );
  }

  void _showCompareDialog(XlPalette p, _ModelItem a, _ModelItem b) {
    showDialog(
      context: context,
      barrierColor: p.scrim,
      builder: (ctx) => Dialog(
        backgroundColor: Colors.transparent,
        elevation: 0,
        child: Container(
          width: 520,
          padding: const EdgeInsets.all(24),
          decoration: AppTheme.neuLg(context, r: XlRadius.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('模型对比', style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
              const SizedBox(height: 16),
              _compareRow(p, '参数量', a.params, b.params),
              _compareRow(p, '量化', a.quant, b.quant),
              _compareRow(p, '质量评分', '${a.quality}', '${b.quality}'),
              _compareRow(p, '需求内存', '${a.ramGb} GB', '${b.ramGb} GB'),
              _compareRow(p, '下载体积', '${(a.sizeMb/1024).toStringAsFixed(1)} GB', '${(b.sizeMb/1024).toStringAsFixed(1)} GB'),
              _compareRow(p, '上下文', a.context, b.context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _compareRow(XlPalette p, String label, String va, String vb) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          SizedBox(width: 80, child: Text(label, style: TextStyle(fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w600))),
          Expanded(child: Text(va, textAlign: TextAlign.center, style: TextStyle(fontSize: XlFont.captionSm, color: p.pink, fontWeight: FontWeight.w800))),
          Text('vs', style: TextStyle(fontSize: XlFont.micro, color: p.decor, fontWeight: FontWeight.w700)),
          Expanded(child: Text(vb, textAlign: TextAlign.center, style: TextStyle(fontSize: XlFont.captionSm, color: p.gold, fontWeight: FontWeight.w800))),
        ],
      ),
    );
  }

  void _showInfo(XlPalette p, _ModelItem m) {
    showDialog(
      context: context,
      barrierColor: p.scrim,
      builder: (ctx) {
        final color = _colorOf(p, m.color);
        return Dialog(
          backgroundColor: Colors.transparent,
          elevation: 0,
          insetPadding: const EdgeInsets.all(24),
          child: Container(
            width: 460,
            padding: const EdgeInsets.all(26),
            decoration: AppTheme.neuLg(context, r: XlRadius.xxl),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 46,
                      height: 46,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(colors: [color, color.withOpacity(0.72)]),
                        borderRadius: BorderRadius.circular(XlRadius.md),
                        border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.32 : 0.48), width: 1.2),
                      ),
                      child: Icon(Icons.auto_awesome_rounded, size: 20, color: p.isDark ? p.btnInk : Colors.white),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(m.name,
                              style: TextStyle(
                                fontSize: XlFont.h6,
                                fontWeight: FontWeight.w800,
                                color: p.text1,
                                letterSpacing: XlLetterSpacing.normal,
                              )),
                          const SizedBox(height: 3),
                          Text('${m.params} · ${m.quant}',
                              style: TextStyle(
                                fontSize: XlFont.label,
                                color: p.text3,
                                fontWeight: FontWeight.w600,
                                letterSpacing: XlLetterSpacing.wider,
                              )),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                AppTheme.divider(context, inset: 0),
                const SizedBox(height: 14),
                _infoRow(p, '参数量', m.params, p.pink),
                const SizedBox(height: 10),
                _infoRow(p, '量化方式', m.quant, p.gold),
                const SizedBox(height: 10),
                _infoRow(p, '上下文', m.context, p.violet),
                const SizedBox(height: 10),
                _infoRow(p, '质量评分', '${m.quality} / 100', p.green),
                const SizedBox(height: 10),
                _infoRow(p, '需求内存', '${m.ramGb.toStringAsFixed(1)} GB', p.pink),
                const SizedBox(height: 10),
                _infoRow(p, '需求显存', m.vramGb <= 0 ? '共享' : '${m.vramGb.toStringAsFixed(1)} GB', p.gold),
                const SizedBox(height: 10),
                _infoRow(p, '下载体积', '${(m.sizeMb / 1024).toStringAsFixed(2)} GB', p.violet),
                const SizedBox(height: 20),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    _Pressable(
                      onTap: () => Navigator.pop(ctx),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                        decoration: AppTheme.btn(context, r: XlRadius.pill),
                        child: Text('知道了',
                            style: TextStyle(
                              fontSize: XlFont.captionSm,
                              fontWeight: FontWeight.w800,
                              color: p.btnInk,
                              letterSpacing: XlLetterSpacing.wider,
                            )),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _infoRow(XlPalette p, String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
      child: Row(
        children: [
          Text(label,
              style: TextStyle(
                fontSize: XlFont.captionSm,
                color: p.text2,
                fontWeight: FontWeight.w600,
                letterSpacing: XlLetterSpacing.wide,
              )),
          const Spacer(),
          Text(value,
              style: TextStyle(
                fontSize: XlFont.captionSm,
                color: color,
                fontWeight: FontWeight.w800,
                letterSpacing: XlLetterSpacing.wide,
                fontFeatures: const [FontFeature.tabularFigures()],
              )),
        ],
      ),
    );
  }

  Widget _chip(XlPalette p, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(p.isDark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: color.withOpacity(0.28), width: 1),
      ),
      child: Text(text,
          style: TextStyle(
            fontSize: XlFont.micro,
            fontWeight: FontWeight.w800,
            color: color,
            letterSpacing: XlLetterSpacing.ultra,
          )),
    );
  }

  Widget _emptyView(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(48),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        children: [
          AnimatedBuilder(
            animation: _pulseCtrl,
            builder: (_, __) {
              final t = _pulseCtrl.value;
              return Stack(
                alignment: Alignment.center,
                children: [
                  Container(
                    width: 72 + t * 14,
                    height: 72 + t * 14,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: p.pink.withOpacity((1 - t) * 0.16),
                    ),
                  ),
                  Container(
                    width: 64,
                    height: 64,
                    decoration: AppTheme.brandOrb(context, size: 64),
                    child: Icon(Icons.inventory_2_outlined, size: 26, color: p.btnInk),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 18),
          Text('暂无模型',
              style: TextStyle(
                fontSize: XlFont.h6,
                fontWeight: FontWeight.w800,
                color: p.text1,
              )),
          const SizedBox(height: 6),
          Text('换个关键词或分类试试',
              style: TextStyle(
                fontSize: XlFont.captionSm,
                color: p.text2,
                fontWeight: FontWeight.w500,
              )),
        ],
      ),
    );
  }

  Widget _footerNote(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: p.gold.withOpacity(p.isDark ? 0.14 : 0.10),
              borderRadius: BorderRadius.circular(XlRadius.md),
              border: Border.all(color: p.gold.withOpacity(0.28), width: 1),
            ),
            child: Icon(Icons.lightbulb_outline_rounded, size: 17, color: p.gold),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('模型选择建议',
                    style: TextStyle(
                      fontSize: XlFont.caption,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                const SizedBox(height: 3),
                Text('首次使用推荐选 0.5B ~ 1.5B 的小模型，跑顺了再升级。所有模型都从 HuggingFace 拉取，本地运行、数据不出本机。',
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text2,
                      fontWeight: FontWeight.w500,
                      height: XlLineHeight.relaxed,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _loadingView(XlPalette p) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(26, 10, 26, 30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _shimmerBar(p, 120, 22),
                  const SizedBox(height: 8),
                  _shimmerBar(p, 220, 12),
                ],
              ),
              const Spacer(),
              _shimmerBox(p, 110, 44, XlRadius.lg),
            ],
          ),
          const SizedBox(height: 22),
          _shimmerBox(p, double.infinity, 150, XlRadius.xxl),
          const SizedBox(height: 20),
          LayoutBuilder(
            builder: (context, c) {
              final cols = c.maxWidth > 1180 ? 3 : c.maxWidth > 780 ? 2 : 1;
              return GridView.count(
                crossAxisCount: cols,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 16,
                crossAxisSpacing: 16,
                childAspectRatio: cols == 1 ? 1.9 : 1.15,
                children: [
                  for (int i = 0; i < 4; i++) _shimmerBox(p, double.infinity, 160, XlRadius.xxl),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _shimmerBox(XlPalette p, double w, double h, double r) {
    return AnimatedBuilder(
      animation: _scanCtrl,
      builder: (_, __) {
        final t = _scanCtrl.value;
        return Container(
          width: w,
          height: h,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(r),
            gradient: LinearGradient(
              begin: Alignment(-1.0 - t * 1.2 + t, 0),
              end: Alignment(-0.4 - t * 1.2 + t, 0),
              colors: [
                p.surfaceLo,
                p.surfaceLo,
                p.surfaceHi.withOpacity(0.9),
                p.surfaceLo,
                p.surfaceLo,
              ],
              stops: const [0.0, 0.35, 0.5, 0.65, 1.0],
            ),
          ),
        );
      },
    );
  }

  Widget _shimmerBar(XlPalette p, double w, double h) {
    return AnimatedBuilder(
      animation: _scanCtrl,
      builder: (_, __) {
        final t = _scanCtrl.value;
        return Container(
          width: w,
          height: h,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(99),
            gradient: LinearGradient(
              begin: Alignment(-1.2 - t * 1.2 + t, 0),
              end: Alignment(-0.5 - t * 1.2 + t, 0),
              colors: [
                p.surfaceLo,
                p.surfaceLo,
                p.surfaceHi.withOpacity(0.9),
                p.surfaceLo,
                p.surfaceLo,
              ],
              stops: const [0.0, 0.35, 0.5, 0.65, 1.0],
            ),
          ),
        );
      },
    );
  }
}

class _HwSnapshot {
  final double ram;
  final double vram;
  final int cores;
  final double diskFree;
  final String gpu;
  final String platform;
  final bool hasCuda;
  final bool hasMetal;
  const _HwSnapshot({
    required this.ram,
    required this.vram,
    required this.cores,
    required this.diskFree,
    required this.gpu,
    required this.platform,
    required this.hasCuda,
    required this.hasMetal,
  });
}

class _ModelItem {
  final String name;
  final String params;
  final String quant;
  final double vramGb;
  final double ramGb;
  final int quality;
  final String context;
  final double sizeMb;
  final bool canRun;
  final bool recommended;
  final String category;
  final String color;
  const _ModelItem(
    this.name,
    this.params,
    this.quant,
    this.vramGb,
    this.ramGb,
    this.quality,
    this.context,
    this.sizeMb,
    this.canRun,
    this.recommended,
    this.category,
    this.color,
  );
}

class _HwStat {
  final String label;
  final String value;
  final String unit;
  final IconData icon;
  final String color;
  final double progress;
  const _HwStat(this.label, this.value, this.unit, this.icon, this.color, this.progress);
}

class _Sum {
  final String label;
  final String value;
  final String unit;
  final IconData icon;
  final String color;
  final double progress;
  const _Sum(this.label, this.value, this.unit, this.icon, this.color, this.progress);
}

class _DlInfo {
  final double percent;
  final double downloadedMb;
  final double totalMb;
  final String status;
  final String? error;
  const _DlInfo({
    required this.percent,
    this.downloadedMb = 0,
    this.totalMb = 0,
    this.status = '',
    this.error,
  });
  double get ratio => (percent / 100).clamp(0.0, 1.0);
  String get sizeLabel {
    if (totalMb <= 0) return '';
    return '${downloadedMb.toStringAsFixed(1)} / ${totalMb.toStringAsFixed(1)} MB';
  }
}

class _HoverGlow extends StatefulWidget {
  final Widget child;
  final Color color;
  const _HoverGlow({required this.child, required this.color});
  @override
  State<_HoverGlow> createState() => _HoverGlowState();
}

class _HoverGlowState extends State<_HoverGlow> {
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: AnimatedScale(
        scale: _hover ? 1.015 : 1.0,
        duration: XlDuration.normal,
        curve: XlCurve.springSoft,
        child: AnimatedContainer(
          duration: XlDuration.normal,
          curve: XlCurve.standard,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(XlRadius.xxl),
            boxShadow: _hover
                ? [
                    BoxShadow(color: widget.color.withOpacity(0.30), blurRadius: 30, spreadRadius: -4),
                  ]
                : const [],
          ),
          child: widget.child,
        ),
      ),
    );
  }
}

class _Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  const _Pressable({required this.child, this.onTap, this.scale = 0.96});
  @override
  State<_Pressable> createState() => _PressableState();
}

class _PressableState extends State<_Pressable> {
  bool _down = false;
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: widget.onTap == null ? null : (_) => setState(() => _down = true),
      onTapUp: widget.onTap == null ? null : (_) => setState(() => _down = false),
      onTapCancel: widget.onTap == null ? null : () => setState(() => _down = false),
      onTap: widget.onTap,
      child: AnimatedScale(
        scale: _down ? widget.scale : 1.0,
        duration: const Duration(milliseconds: 100),
        child: widget.child,
      ),
    );
  }
}