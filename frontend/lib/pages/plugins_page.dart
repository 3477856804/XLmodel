import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;
import '../widgets/plugin_store.dart';
import 'plugin_community.dart';

class PluginsPage extends StatefulWidget {
  const PluginsPage({super.key});
  @override
  State<PluginsPage> createState() => _PluginsPageState();
}

class _PluginsPageState extends State<PluginsPage> with TickerProviderStateMixin {
  List<pb.PluginInfo> _remote = [];
  final List<_Plugin> _local = [];
  bool _loading = true;
  String? _error;
  String _category = 'all';
  String _sort = 'default';
  final _searchCtrl = TextEditingController();
  String _query = '';
  final Set<String> _busy = {};
  final Set<String> _expanded = {};
  late AnimationController _enterCtrl;
  late AnimationController _listCtrl;
  late AnimationController _shimmerCtrl;
  late Animation<double> _enterAnim;
  late Animation<double> _listAnim;
  late TabController _tabCtrl;

  static const _topTabs = <String>['已安装', '商店', '社区'];

  static const _categories = <String, String>{
    'all': '全部',
    'enabled': '已启用',
    'core': '核心',
    'ai': '智能',
    'tool': '工具',
    'fun': '娱乐',
    'system': '系统',
  };

  static const _sorts = <String, String>{
    'default': '默认排序',
    'state': '启用优先',
    'name': '按名称',
    'category': '按分类',
  };

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 700), vsync: this);
    _listCtrl = AnimationController(duration: const Duration(milliseconds: 900), vsync: this);
    _shimmerCtrl = AnimationController(duration: const Duration(milliseconds: 1400), vsync: this)..repeat();
    _enterAnim = CurvedAnimation(parent: _enterCtrl, curve: XlCurve.easeOut);
    _listAnim = CurvedAnimation(parent: _listCtrl, curve: XlCurve.easeOut);
    _tabCtrl = TabController(length: _topTabs.length, vsync: this);
    _enterCtrl.forward();
    _listCtrl.forward();
    _load();
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    _enterCtrl.dispose();
    _listCtrl.dispose();
    _shimmerCtrl.dispose();
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await XlClient.stub.plugins();
      if (!mounted) return;
      setState(() {
        _remote = r.plugins;
        _local.clear();
        for (final it in _remote) {
          _local.add(_Plugin(
            it.displayName,
            it.displayDesc,
            it.displayVersion,
            it.enabled,
            it.category.isEmpty ? 'core' : it.category,
            _iconFor(it.name),
            _colorKeyFor(it.name),
          ));
        }
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _local.clear();
        _loading = false;
      });
    }
  }

  IconData _iconFor(String name) {
    if (name.contains('对话')) return Icons.chat_bubble_outline_rounded;
    if (name.contains('搜索') || name.contains('联网')) return Icons.travel_explore_rounded;
    if (name.contains('图谱') || name.contains('记忆')) return Icons.hub_outlined;
    if (name.contains('定时') || name.contains('提醒')) return Icons.schedule_rounded;
    if (name.contains('语音') || name.contains('播报')) return Icons.volume_up_rounded;
    if (name.contains('LoRA') || name.contains('训练')) return Icons.auto_awesome_rounded;
    if (name.contains('目标')) return Icons.flag_outlined;
    if (name.contains('更新')) return Icons.system_update_alt_rounded;
    if (name.contains('指令') || name.contains('快捷')) return Icons.bolt_rounded;
    if (name.contains('隐私') || name.contains('沙箱')) return Icons.shield_outlined;
    if (name.contains('情绪') || name.contains('分析')) return Icons.psychology_outlined;
    if (name.contains('自定义')) return Icons.extension_outlined;
    return Icons.widgets_outlined;
  }

  String _colorKeyFor(String name) {
    if (name.contains('训练') || name.contains('图谱')) return 'gold';
    if (name.contains('语音') || name.contains('对话')) return 'pink';
    if (name.contains('搜索') || name.contains('定时')) return 'green';
    if (name.contains('隐私') || name.contains('情绪')) return 'violet';
    return 'pink';
  }

  Color _colorOf(XlPalette p, String key) {
    switch (key) {
      case 'pink': return p.pink;
      case 'gold': return p.gold;
      case 'violet': return p.violet;
      case 'green': return p.green;
      case 'red': return p.red;
      case 'blue': return p.blue;
      default: return p.pink;
    }
  }

  List<_Plugin> get _filtered {
    final q = _query.trim().toLowerCase();
    var list = _local.where((it) {
      if (_category == 'enabled' && !it.enabled) return false;
      if (_category != 'all' && _category != 'enabled' && it.category != _category) return false;
      if (q.isEmpty) return true;
      return it.name.toLowerCase().contains(q) || it.desc.toLowerCase().contains(q);
    }).toList();

    switch (_sort) {
      case 'state':
        list.sort((a, b) {
          if (a.enabled != b.enabled) return a.enabled ? -1 : 1;
          return a.name.compareTo(b.name);
        });
        break;
      case 'name':
        list.sort((a, b) => a.name.compareTo(b.name));
        break;
      case 'category':
        list.sort((a, b) => a.category.compareTo(b.category));
        break;
      default:
        break;
    }
    return list;
  }

  int get _enabledCount => _local.where((it) => it.enabled).length;
  int get _totalCount => _local.length;

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Stack(
      children: [
        Positioned.fill(child: AppTheme.aurora(context, child: const SizedBox.shrink())),
        Column(
          children: [
            _buildTopTabs(p),
            Expanded(
              child: TabBarView(
                controller: _tabCtrl,
                children: [
                  SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(26, 6, 26, 30),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildHeader(p),
                        const SizedBox(height: 22),
                        _buildStats(p),
                        const SizedBox(height: 22),
                        _buildToolbar(p),
                        const SizedBox(height: 18),
                        _buildGrid(p),
                        const SizedBox(height: 24),
                        _buildFooter(p),
                      ],
                    ),
                  ),
                  const SingleChildScrollView(
                    padding: EdgeInsets.fromLTRB(26, 6, 26, 30),
                    child: PluginStore(),
                  ),
                  _buildCommunityTab(p),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildTopTabs(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 10),
      child: Container(
        padding: const EdgeInsets.all(4),
        decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
        child: LayoutBuilder(
          builder: (context, c) {
            final cell = c.maxWidth / _topTabs.length;
            return AnimatedBuilder(
              animation: _tabCtrl,
              builder: (_, __) {
                final idx = _tabCtrl.index;
                return SizedBox(
                  height: 38,
                  child: Stack(
                    children: [
                      AnimatedPositioned(
                        duration: XlDuration.normal,
                        curve: XlCurve.spring,
                        left: idx * cell,
                        top: 0,
                        bottom: 0,
                        width: cell,
                        child: Container(decoration: AppTheme.brand(context, r: XlRadius.pill)),
                      ),
                      Row(
                        children: [
                          for (int i = 0; i < _topTabs.length; i++)
                            Expanded(
                              child: Material(
                                color: Colors.transparent,
                                child: InkWell(
                                  onTap: () => _tabCtrl.animateTo(i),
                                  borderRadius: BorderRadius.circular(XlRadius.pill),
                                  child: Center(
                                    child: Text(_topTabs[i],
                                        style: TextStyle(
                                          fontSize: XlFont.captionSm,
                                          fontWeight: i == idx ? FontWeight.w800 : FontWeight.w600,
                                          color: i == idx ? p.btnInk : p.text2,
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
                );
              },
            );
          },
        ),
      ),
    );
  }

  Widget _buildCommunityTab(XlPalette p) {
    final totalDl = kCommunityPlugins.fold<int>(0, (s, e) => s + e.downloads);
    final dshCount = kCommunityPlugins.where((e) => e.dshCompatible).length;
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 30),
      child: Container(
        padding: const EdgeInsets.all(26),
        decoration: AppTheme.neuLg(context, r: XlRadius.xxl),
        child: Column(
          children: [
            Container(
              width: 76,
              height: 76,
              decoration: AppTheme.brandOrbLg(context, size: 76),
              child: Icon(Icons.forum_rounded, size: 34, color: p.btnInk),
            ),
            const SizedBox(height: 18),
            ShaderMask(
              shaderCallback: (b) => p.gradText.createShader(b),
              child: const Text('小凌社区',
                  style: TextStyle(
                    fontSize: XlFont.h3,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
            ),
            const SizedBox(height: 8),
            Text('精选插件 · 分类浏览 · DSH 兼容生态',
                style: TextStyle(
                  fontSize: XlFont.caption,
                  color: p.text2,
                  fontWeight: FontWeight.w500,
                  letterSpacing: XlLetterSpacing.wide,
                )),
            const SizedBox(height: 22),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _communityStat(p, '${kCommunityPlugins.length}+', '插件'),
                _communityDivider(p),
                _communityStat(p, '${formatDownloads(totalDl)}+', '累计下载'),
                _communityDivider(p),
                _communityStat(p, '$dshCount', 'DSH 兼容'),
              ],
            ),
            const SizedBox(height: 26),
            _Pressable(
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const PluginCommunityPage()),
              ),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 13),
                decoration: AppTheme.btn(context, r: XlRadius.pill),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('进入小凌社区',
                        style: TextStyle(
                          fontSize: XlFont.caption,
                          fontWeight: FontWeight.w800,
                          color: p.btnInk,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                    const SizedBox(width: 8),
                    Icon(Icons.arrow_forward_rounded, size: 16, color: p.btnInk),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _communityStat(XlPalette p, String value, String label) {
    return Column(
      children: [
        Text(value,
            style: TextStyle(
              fontSize: XlFont.h4,
              fontWeight: FontWeight.w800,
              color: p.text1,
              letterSpacing: XlLetterSpacing.tight,
              fontFeatures: const [FontFeature.tabularFigures()],
            )),
        const SizedBox(height: 4),
        Text(label,
            style: TextStyle(
              fontSize: XlFont.label,
              color: p.decor,
              fontWeight: FontWeight.w700,
              letterSpacing: XlLetterSpacing.wider,
            )),
      ],
    );
  }

  Widget _communityDivider(XlPalette p) {
    return Container(
      width: 1,
      height: 28,
      margin: const EdgeInsets.symmetric(horizontal: 20),
      color: p.edgeSoft,
    );
  }

  Widget _buildHeader(XlPalette p) {
    return AnimatedBuilder(
      animation: _enterAnim,
      builder: (_, child) => Opacity(
        opacity: _enterAnim.value,
        child: Transform.translate(
          offset: Offset(0, (1 - _enterAnim.value) * 14),
          child: child,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('插件管理',
                        style: TextStyle(
                          fontSize: XlFont.h2,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.normal,
                        )),
                    const SizedBox(width: 12),
                    _enabledChip(p),
                  ],
                ),
                const SizedBox(height: 6),
                Text('每个功能都可插拔，像搭积木一样组合你的数字生命',
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
          _actionBtn(p, Icons.refresh_rounded, '刷新', _load),
          const SizedBox(width: 8),
          _actionBtn(p, Icons.add_rounded, '安装插件', () => _showInstallDialog(p)),
        ],
      ),
    );
  }

  Widget _enabledChip(XlPalette p) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: p.green.withOpacity(p.isDark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: p.green.withOpacity(0.32), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: p.green,
              shape: BoxShape.circle,
              boxShadow: [BoxShadow(color: p.green.withOpacity(0.6), blurRadius: 6, spreadRadius: -1)],
            ),
          ),
          const SizedBox(width: 6),
          Text('$_enabledCount / $_totalCount 已启用',
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

  Widget _actionBtn(XlPalette p, IconData icon, String label, VoidCallback onTap) {
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
                  letterSpacing: XlLetterSpacing.wide,
                )),
          ],
        ),
      ),
    );
  }

  Widget _buildStats(XlPalette p) {
    final enabledPct = _totalCount == 0 ? 0.0 : _enabledCount / _totalCount;
    final coreCount = _local.where((it) => it.category == 'core').length;
    final aiCount = _local.where((it) => it.category == 'ai').length;
    final stats = <_Stat>[
      _Stat('已启用', '$_enabledCount', Icons.check_circle_outline_rounded, p.green, enabledPct),
      _Stat('总数', '$_totalCount', Icons.widgets_outlined, p.pink, 1.0),
      _Stat('核心', '$coreCount', Icons.star_outline_rounded, p.gold, _totalCount == 0 ? 0.0 : coreCount / _totalCount),
      _Stat('智能', '$aiCount', Icons.psychology_outlined, p.violet, _totalCount == 0 ? 0.0 : aiCount / _totalCount),
    ];
    return AnimatedBuilder(
      animation: _listAnim,
      builder: (_, __) {
        return Row(
          children: [
            for (int i = 0; i < stats.length; i++) ...[
              Expanded(
                child: Transform.translate(
                  offset: Offset(0, (1 - _listAnim.value) * 20),
                  child: Opacity(
                    opacity: _listAnim.value.clamp(0.0, 1.0),
                    child: _statCard(p, stats[i]),
                  ),
                ),
              ),
              if (i != stats.length - 1) const SizedBox(width: 12),
            ],
          ],
        );
      },
    );
  }

  Widget _statCard(XlPalette p, _Stat s) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: s.color.withOpacity(p.isDark ? 0.14 : 0.10),
                  borderRadius: BorderRadius.circular(XlRadius.sm),
                  border: Border.all(color: s.color.withOpacity(0.28), width: 1),
                ),
                child: Icon(s.icon, size: 15, color: s.color),
              ),
              const Spacer(),
              Text(s.label,
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.text3,
                    fontWeight: FontWeight.w700,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
          const SizedBox(height: 14),
          Text(s.value,
              style: TextStyle(
                fontSize: XlFont.h3,
                fontWeight: FontWeight.w800,
                color: p.text1,
                letterSpacing: XlLetterSpacing.tight,
                fontFeatures: const [FontFeature.tabularFigures()],
              )),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: s.progress,
              minHeight: 4,
              backgroundColor: p.surfaceLo,
              valueColor: AlwaysStoppedAnimation(s.color),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToolbar(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
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
                          onChanged: (v) => setState(() => _query = v),
                          style: TextStyle(fontSize: XlFont.caption, color: p.text1),
                          decoration: InputDecoration(
                            hintText: '搜索插件名称或描述…',
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

  Widget _buildGrid(XlPalette p) {
    if (_loading) return _loadingView(p);
    if (_error != null) return _errorView(p);
    final list = _filtered;
    if (list.isEmpty) return _emptyView(p);
    return LayoutBuilder(
      builder: (context, constraints) {
        final cols = constraints.maxWidth > 1180
            ? 4
            : constraints.maxWidth > 860
                ? 3
                : constraints.maxWidth > 560
                    ? 2
                    : 1;
        return AnimatedBuilder(
          animation: _listAnim,
          builder: (_, __) {
            return GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              padding: EdgeInsets.zero,
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: cols,
                mainAxisSpacing: 14,
                crossAxisSpacing: 14,
                childAspectRatio: cols == 1 ? 3.0 : (cols == 2 ? 1.55 : 1.35),
              ),
              itemCount: list.length,
              itemBuilder: (_, i) {
                final delay = (i.clamp(0, 8)) * 0.06;
                final t = ((_listAnim.value - delay) / (1 - delay)).clamp(0.0, 1.0);
                return Transform.translate(
                  offset: Offset(0, (1 - t) * 18),
                  child: Opacity(opacity: t, child: _pluginCard(p, list[i])),
                );
              },
            );
          },
        );
      },
    );
  }

  Widget _pluginCard(XlPalette p, _Plugin plugin) {
    final color = _colorOf(p, plugin.color);
    final isBusy = _busy.contains(plugin.name);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                  borderRadius: BorderRadius.circular(XlRadius.md),
                  border: Border.all(color: color.withOpacity(0.28), width: 1),
                  boxShadow: plugin.enabled
                      ? [BoxShadow(color: color.withOpacity(0.24), blurRadius: 16, spreadRadius: -4)]
                      : null,
                ),
                child: Icon(plugin.icon, size: 19, color: color),
              ),
              const Spacer(),
              _toggleSwitch(p, plugin.enabled, isBusy, (v) => _togglePlugin(plugin, v)),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: Text(
                  plugin.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: XlFont.body,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.normal,
                  ),
                ),
              ),
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: p.surfaceLo,
                  borderRadius: BorderRadius.circular(XlRadius.xs),
                  border: Border.all(color: p.edgeSoft, width: 1),
                ),
                child: Text(plugin.version,
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      fontWeight: FontWeight.w800,
                      color: p.decor,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(
            child: GestureDetector(
              onTap: () => setState(() {
                if (_expanded.contains(plugin.name)) {
                  _expanded.remove(plugin.name);
                } else {
                  _expanded.add(plugin.name);
                }
              }),
              child: AnimatedCrossFade(
                duration: XlDuration.normal,
                crossFadeState: _expanded.contains(plugin.name)
                    ? CrossFadeState.showSecond
                    : CrossFadeState.showFirst,
                firstChild: Text(
                  plugin.desc,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    color: p.text2,
                    height: XlLineHeight.relaxed,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                secondChild: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: SingleChildScrollView(
                        child: Text(
                          plugin.desc,
                          style: TextStyle(
                            fontSize: XlFont.captionSm,
                            color: p.text1,
                            height: XlLineHeight.relaxed,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ),
                    Text('收起 ▲',
                        style: TextStyle(
                          fontSize: XlFont.micro,
                          color: p.pink,
                          fontWeight: FontWeight.w700,
                        )),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: plugin.enabled ? p.green : p.decorSoft,
                  shape: BoxShape.circle,
                  boxShadow: plugin.enabled
                      ? [BoxShadow(color: p.green.withOpacity(0.6), blurRadius: 6, spreadRadius: -1)]
                      : null,
                ),
              ),
              const SizedBox(width: 6),
              Text(plugin.enabled ? '已启用' : '已禁用',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w800,
                    color: plugin.enabled ? p.green : p.decor,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
              const Spacer(),
              _miniBtn(p, Icons.tune_rounded, () => _showConfigDialog(p, plugin)),
              const SizedBox(width: 6),
              _miniBtn(p, Icons.info_outline_rounded, () => _showInfoDialog(p, plugin)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _toggleSwitch(XlPalette p, bool on, bool busy, ValueChanged<bool> onChanged) {
    return GestureDetector(
      onTap: busy ? null : () => onChanged(!on),
      child: AnimatedContainer(
        duration: XlDuration.normal,
        curve: XlCurve.springSoft,
        width: 50,
        height: 28,
        decoration: BoxDecoration(
          gradient: on ? LinearGradient(colors: [p.pink, p.pink.withOpacity(0.8)]) : null,
          color: on ? null : p.surfaceLo,
          borderRadius: BorderRadius.circular(XlRadius.pill),
          border: Border.all(
            color: on
                ? Colors.white.withOpacity(p.isDark ? 0.34 : 0.22)
                : p.shDark.withOpacity(p.isDark ? 0.32 : 0.14),
            width: 1,
          ),
          boxShadow: on
              ? [...p.raisedXxs, BoxShadow(color: p.pink.withOpacity(0.35), blurRadius: 12, spreadRadius: -2)]
              : p.sunkenXs,
        ),
        child: AnimatedAlign(
          duration: XlDuration.normal,
          curve: XlCurve.springSoft,
          alignment: on ? Alignment.centerRight : Alignment.centerLeft,
          child: busy
              ? Padding(
                  padding: const EdgeInsets.all(4),
                  child: _BusySpinner(color: on ? p.surfaceHi : p.pink),
                )
              : Container(
                  margin: const EdgeInsets.all(3),
                  width: 20,
                  height: 20,
                  decoration: BoxDecoration(
                    color: p.surfaceHi,
                    shape: BoxShape.circle,
                    boxShadow: p.raisedXxs,
                  ),
                ),
        ),
      ),
    );
  }

  Widget _miniBtn(XlPalette p, IconData icon, VoidCallback onTap) {
    return _Pressable(
      onTap: onTap,
      child: Container(
        width: 28,
        height: 28,
        decoration: AppTheme.neuXxs(context, r: XlRadius.xs),
        child: Icon(icon, size: 13, color: p.text2),
      ),
    );
  }

  void _showPluginSnack(String message, Color color) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: XlPalette.of(context).surface,
        elevation: 0,
        duration: const Duration(milliseconds: 1600),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.md)),
        content: Row(
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(message,
                  style: TextStyle(
                    color: XlPalette.of(context).text1,
                    fontWeight: FontWeight.w700,
                    fontSize: XlFont.captionSm,
                  )),
            ),
          ],
        ),
      ));
  }

  Future<void> _togglePlugin(_Plugin plugin, bool next) async {
    setState(() => _busy.add(plugin.name));
    try {
      final req = pb.PluginToggleRequest(name: plugin.name);
      final r = next
          ? await XlClient.stub.enablePlugin(req)
          : await XlClient.stub.disablePlugin(req);
      if (!mounted) return;
      if (r.ok) {
        setState(() {
          final idx = _local.indexWhere((it) => it.name == plugin.name);
          if (idx >= 0) _local[idx] = _local[idx].copyWith(enabled: next);
          _busy.remove(plugin.name);
        });
        _showPluginSnack('${plugin.name} ${next ? "已启用" : "已禁用"}', XlPalette.of(context).green);
      } else {
        setState(() => _busy.remove(plugin.name));
        _showPluginSnack(r.message.isNotEmpty ? r.message : '操作失败', XlPalette.of(context).red);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy.remove(plugin.name));
      _showPluginSnack('操作失败：$e', XlPalette.of(context).red);
    }
  }

  Widget _loadingView(XlPalette p) {
    return LayoutBuilder(
      builder: (context, c) {
        final cols = c.maxWidth > 1180 ? 3 : c.maxWidth > 780 ? 2 : 1;
        return GridView.count(
          crossAxisCount: cols,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 14,
          crossAxisSpacing: 14,
          childAspectRatio: cols == 1 ? 3.0 : 1.35,
          children: [
            for (int i = 0; i < 6; i++) _skeletonCard(p),
          ],
        );
      },
    );
  }

  Widget _skeletonCard(XlPalette p) {
    return AnimatedBuilder(
      animation: _shimmerCtrl,
      builder: (_, __) {
        final t = _shimmerCtrl.value;
        final base = BoxDecoration(
          borderRadius: BorderRadius.circular(XlRadius.xl),
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
        );
        return Container(
          padding: const EdgeInsets.all(18),
          decoration: base,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(width: 42, height: 42, decoration: base.copyWith(borderRadius: BorderRadius.circular(XlRadius.md))),
                  const Spacer(),
                  Container(width: 46, height: 28, decoration: base.copyWith(borderRadius: BorderRadius.circular(XlRadius.pill))),
                ],
              ),
              const SizedBox(height: 16),
              Container(width: 120, height: 12, decoration: base.copyWith(borderRadius: BorderRadius.circular(6))),
              const SizedBox(height: 10),
              Container(width: double.infinity, height: 8, decoration: base.copyWith(borderRadius: BorderRadius.circular(4))),
              const SizedBox(height: 6),
              Container(width: 160, height: 8, decoration: base.copyWith(borderRadius: BorderRadius.circular(4))),
            ],
          ),
        );
      },
    );
  }

  Widget _emptyView(XlPalette p) {
    final searching = _query.trim().isNotEmpty || _category != 'all';
    return Container(
      padding: const EdgeInsets.all(48),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Column(
        children: [
          AnimatedBuilder(
            animation: _shimmerCtrl,
            builder: (_, __) {
              final t = _shimmerCtrl.value;
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
                    child: Icon(Icons.extension_outlined, size: 26, color: p.btnInk),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 18),
          Text(searching ? '没有找到匹配的插件' : '暂无已安装插件',
              style: TextStyle(
                fontSize: XlFont.h6,
                fontWeight: FontWeight.w800,
                color: p.text1,
              )),
          const SizedBox(height: 6),
          Text(searching ? '换个关键词或分类试试' : '去插件商店挑选喜欢的功能吧',
              style: TextStyle(
                fontSize: XlFont.captionSm,
                color: p.text2,
                fontWeight: FontWeight.w500,
              )),
          if (!searching) ...[
            const SizedBox(height: 20),
            _Pressable(
              onTap: () => _tabCtrl.animateTo(1),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 11),
                decoration: AppTheme.btn(context, r: XlRadius.pill),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.storefront_rounded, size: 15, color: p.btnInk),
                    const SizedBox(width: 8),
                    Text('去商店看看',
                        style: TextStyle(
                          fontSize: XlFont.captionSm,
                          fontWeight: FontWeight.w800,
                          color: p.btnInk,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _errorView(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(48),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Column(
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: p.red.withOpacity(p.isDark ? 0.14 : 0.10),
              shape: BoxShape.circle,
              border: Border.all(color: p.red.withOpacity(0.32), width: 1),
            ),
            child: Icon(Icons.error_outline_rounded, size: 26, color: p.red),
          ),
          const SizedBox(height: 18),
          Text('加载插件列表失败',
              style: TextStyle(
                fontSize: XlFont.h6,
                fontWeight: FontWeight.w800,
                color: p.text1,
              )),
          const SizedBox(height: 6),
          Text('请检查后端连接后重试',
              style: TextStyle(
                fontSize: XlFont.captionSm,
                color: p.text2,
                fontWeight: FontWeight.w500,
              )),
          const SizedBox(height: 20),
          _Pressable(
            onTap: _load,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 11),
              decoration: AppTheme.btn(context, r: XlRadius.pill),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.refresh_rounded, size: 15, color: p.btnInk),
                  const SizedBox(width: 8),
                  Text('重试',
                      style: TextStyle(
                        fontSize: XlFont.captionSm,
                        fontWeight: FontWeight.w800,
                        color: p.btnInk,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFooter(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: AppTheme.neuXs(context, r: XlRadius.md),
            child: Icon(Icons.lightbulb_outline_rounded, size: 19, color: p.gold),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('想自己写一个？',
                    style: TextStyle(
                      fontSize: XlFont.caption,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                const SizedBox(height: 3),
                Text('一个 Python 文件实现钩子函数，放进插件目录即可被识别',
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text2,
                      fontWeight: FontWeight.w500,
                      height: XlLineHeight.relaxed,
                    )),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: () => _showDocDialog(p),
              borderRadius: BorderRadius.circular(XlRadius.pill),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
                decoration: AppTheme.ghost(context, r: XlRadius.pill),
                child: Row(
                  children: [
                    Text('查看文档',
                        style: TextStyle(
                          fontSize: XlFont.captionSm,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                    const SizedBox(width: 6),
                    Icon(Icons.arrow_forward_rounded, size: 14, color: p.pink),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showInstallDialog(XlPalette p) {
    _showDialog(p, '安装插件', '从文件或 URL 导入一个 Python 插件包', [
      _dialogRow(p, Icons.file_open_outlined, '从本地文件导入', '选择 .py 或 .zip', () => Navigator.pop(context)),
      _dialogRow(p, Icons.link_rounded, '从 URL 安装', '粘贴插件下载链接', () => Navigator.pop(context)),
      _dialogRow(p, Icons.folder_outlined, '打开插件目录', '手动放入文件', () => Navigator.pop(context)),
    ]);
  }

  void _showConfigDialog(XlPalette p, _Plugin plugin) {
    final color = _colorOf(p, plugin.color);
    final ctrl = TextEditingController(text: plugin.name == '联网搜索' ? 'duckduckgo' : 'default');
    _showDialog(p, plugin.name, '插件配置', [
      _settingRow(p, '启用状态', plugin.enabled ? '已启用' : '已禁用', color),
      _settingRow(p, '版本', plugin.version, p.gold),
      _settingRow(p, '分类', _categories[plugin.category] ?? plugin.category, p.violet),
      const SizedBox(height: 8),
      Container(
        padding: const EdgeInsets.all(12),
        decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
        child: TextField(
          controller: ctrl,
          style: TextStyle(fontSize: XlFont.captionSm, color: p.text1),
          decoration: InputDecoration(
            labelText: '自定义参数',
            labelStyle: TextStyle(fontSize: XlFont.label, color: p.decor),
            border: InputBorder.none,
            isDense: true,
          ),
        ),
      ),
      const SizedBox(height: 6),
      _dialogRow(p, Icons.restart_alt_rounded, '重启插件', '重新加载配置', () => Navigator.pop(context)),
      _dialogRow(p, Icons.delete_outline_rounded, '卸载插件', '从本地移除（不可撤销）', () => Navigator.pop(context)),
    ]);
  }

  void _showInfoDialog(XlPalette p, _Plugin plugin) {
    final color = _colorOf(p, plugin.color);
    _showDialog(p, plugin.name, '插件信息', [
      _settingRow(p, '描述', plugin.desc, color),
      _settingRow(p, '版本', plugin.version, p.gold),
      _settingRow(p, '分类', _categories[plugin.category] ?? plugin.category, p.violet),
      _settingRow(p, '状态', plugin.enabled ? '运行中' : '已停止', plugin.enabled ? p.green : p.decor),
      const SizedBox(height: 6),
      _dialogRow(p, Icons.code_rounded, '查看源码', '打开插件目录', () => Navigator.pop(context)),
      _dialogRow(p, Icons.bug_report_outlined, '反馈问题', '提交到 GitHub', () => Navigator.pop(context)),
    ]);
  }

  void _showDocDialog(XlPalette p) {
    _showDialog(p, '插件开发', '三步写一个自己的插件', [
      _settingRow(p, '① 创建文件', 'plugins/my_plugin.py', p.pink),
      _settingRow(p, '② 实现钩子', 'def on_chat(text): ...', p.gold),
      _settingRow(p, '③ 重启加载', '自动被识别并启用', p.green),
      const SizedBox(height: 6),
      _dialogRow(p, Icons.menu_book_rounded, '完整 API 文档', '查看所有钩子与示例', () => Navigator.pop(context)),
    ]);
  }

  Widget _dialogRow(XlPalette p, IconData icon, String title, String sub, VoidCallback onTap) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(XlRadius.md),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: AppTheme.neuXs(context, r: XlRadius.md),
            child: Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: p.pink.withOpacity(p.isDark ? 0.14 : 0.10),
                    borderRadius: BorderRadius.circular(XlRadius.sm),
                    border: Border.all(color: p.pink.withOpacity(0.28), width: 1),
                  ),
                  child: Icon(icon, size: 14, color: p.pink),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title,
                          style: TextStyle(
                            fontSize: XlFont.captionSm,
                            color: p.text1,
                            fontWeight: FontWeight.w700,
                            letterSpacing: XlLetterSpacing.wide,
                          )),
                      const SizedBox(height: 2),
                      Text(sub,
                          style: TextStyle(
                            fontSize: XlFont.label,
                            color: p.text3,
                            fontWeight: FontWeight.w500,
                          )),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right_rounded, size: 15, color: p.decor),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _settingRow(XlPalette p, String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 10),
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
          Flexible(
            child: Text(value,
                textAlign: TextAlign.right,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: color,
                  fontWeight: FontWeight.w800,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          ),
        ],
      ),
    );
  }

  void _showDialog(XlPalette p, String title, String sub, List<Widget> children) {
    showDialog(
      context: context,
      barrierColor: p.scrim,
      builder: (ctx) {
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
                Text(title,
                    style: TextStyle(
                      fontSize: XlFont.h5,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.normal,
                    )),
                const SizedBox(height: 4),
                Text(sub,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.text2,
                      fontWeight: FontWeight.w500,
                    )),
                const SizedBox(height: 20),
                AppTheme.divider(context, inset: 0),
                const SizedBox(height: 14),
                ...children,
                const SizedBox(height: 10),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    _Pressable(
                      onTap: () => Navigator.pop(ctx),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 11),
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
}

class _Plugin {
  final String name;
  final String desc;
  final String version;
  final bool enabled;
  final String category;
  final IconData icon;
  final String color;
  const _Plugin(this.name, this.desc, this.version, this.enabled, this.category, this.icon, this.color);
  _Plugin copyWith({bool? enabled}) => _Plugin(name, desc, version, enabled ?? this.enabled, category, icon, color);
}

class _Stat {
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  final double progress;
  const _Stat(this.label, this.value, this.icon, this.color, this.progress);
}

class _BusySpinner extends StatefulWidget {
  final Color color;
  const _BusySpinner({required this.color});
  @override
  State<_BusySpinner> createState() => _BusySpinnerState();
}

class _BusySpinnerState extends State<_BusySpinner> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 800))..repeat();
  @override
  void dispose() { _c.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    return RotationTransition(
      turns: _c,
      child: Icon(Icons.sync_rounded, size: 16, color: widget.color),
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