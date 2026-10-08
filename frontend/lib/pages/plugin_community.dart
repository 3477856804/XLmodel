import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../widgets/plugin_store.dart';

class PluginCommunityPage extends StatefulWidget {
  const PluginCommunityPage({super.key});
  @override
  State<PluginCommunityPage> createState() => _PluginCommunityPageState();
}

class _PluginCommunityPageState extends State<PluginCommunityPage> with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  String? _browseCategory;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  int _countOf(String category) =>
      kCommunityPlugins.where((p) => p.category == category).length;

  int get _totalDownloads =>
      kCommunityPlugins.fold<int>(0, (sum, p) => sum + p.downloads);

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Scaffold(
      backgroundColor: p.bg,
      body: Stack(
        children: [
          Positioned.fill(child: AppTheme.aurora(context, child: const SizedBox.shrink())),
          Column(
            children: [
              _appBar(p),
              _tabBar(p),
              Expanded(
                child: TabBarView(
                  controller: _tabCtrl,
                  children: [
                    _featuredTab(p),
                    _categoryTab(p),
                    _dshTab(p),
                  ],
                ),
              ),
              _footer(p),
            ],
          ),
        ],
      ),
    );
  }

  Widget _appBar(XlPalette p) {
    return SafeArea(
      bottom: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(10, 8, 16, 8),
        child: Row(
          children: [
            _Pressable(
              onTap: () => Navigator.pop(context),
              child: Container(
                width: 38,
                height: 38,
                decoration: AppTheme.neuXs(context, r: XlRadius.md),
                child: Icon(Icons.arrow_back_rounded, size: 18, color: p.text1),
              ),
            ),
            const SizedBox(width: 12),
            ShaderMask(
              shaderCallback: (b) => p.gradText.createShader(b),
              child: const Text('小凌社区',
                  style: TextStyle(
                    fontSize: XlFont.h4,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: XlLetterSpacing.normal,
                  )),
            ),
            const Spacer(),
            Container(
              width: 38,
              height: 38,
              decoration: AppTheme.brandOrb(context, size: 38),
              child: Icon(Icons.forum_rounded, size: 17, color: p.btnInk),
            ),
          ],
        ),
      ),
    );
  }

  Widget _tabBar(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(26, 4, 26, 8),
      child: Container(
        padding: const EdgeInsets.all(4),
        decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
        child: LayoutBuilder(
          builder: (context, c) {
            const tabs = ['精选', '分类', 'DSH兼容'];
            final cell = c.maxWidth / tabs.length;
            return AnimatedBuilder(
              animation: _tabCtrl,
              builder: (_, __) {
                final idx = _tabCtrl.index;
                return SizedBox(
                  height: 36,
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
                          for (int i = 0; i < tabs.length; i++)
                            Expanded(
                              child: Material(
                                color: Colors.transparent,
                                child: InkWell(
                                  onTap: () => _tabCtrl.animateTo(i),
                                  borderRadius: BorderRadius.circular(XlRadius.pill),
                                  child: Center(
                                    child: Text(tabs[i],
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

  Widget _featuredTab(XlPalette p) {
    return const SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(26, 6, 26, 24),
      child: PluginStore(),
    );
  }

  Widget _categoryTab(XlPalette p) {
    if (_browseCategory != null) {
      final cat = _browseCategory!;
      return Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(26, 6, 26, 8),
            child: Row(
              children: [
                _Pressable(
                  onTap: () => setState(() => _browseCategory = null),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    decoration: AppTheme.neuXs(context, r: XlRadius.pill),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.arrow_back_rounded, size: 14, color: p.pink),
                        const SizedBox(width: 6),
                        Text('返回分类',
                            style: TextStyle(
                              fontSize: XlFont.captionSm,
                              fontWeight: FontWeight.w700,
                              color: p.text1,
                            )),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(26, 0, 26, 24),
              child: PluginStore(initialCategory: cat, showFeatured: false),
            ),
          ),
        ],
      );
    }
    final cats = kCommunityCategories.where((c) => c != '全部').toList();
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('按分类浏览',
              style: TextStyle(
                fontSize: XlFont.h6,
                fontWeight: FontWeight.w800,
                color: p.text1,
                letterSpacing: XlLetterSpacing.normal,
              )),
          const SizedBox(height: 4),
          Text('选择一个分类，查看该分类下的插件',
              style: TextStyle(
                fontSize: XlFont.captionSm,
                color: p.text2,
                fontWeight: FontWeight.w500,
              )),
          const SizedBox(height: 16),
          for (final c in cats) ...[
            _categoryRow(p, c),
            const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }

  Widget _categoryRow(XlPalette p, String category) {
    final count = _countOf(category);
    return _Pressable(
      onTap: () => setState(() => _browseCategory = category),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: AppTheme.neu(context, r: XlRadius.xl),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: AppTheme.neuXs(context, r: XlRadius.md),
              child: Icon(communityCategoryIcon(category), size: 20, color: p.pink),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(category,
                      style: TextStyle(
                        fontSize: XlFont.body,
                        fontWeight: FontWeight.w800,
                        color: p.text1,
                      )),
                  const SizedBox(height: 3),
                  Text('$count 个插件',
                      style: TextStyle(
                        fontSize: XlFont.label,
                        color: p.decor,
                        fontWeight: FontWeight.w600,
                      )),
                ],
              ),
            ),
            Icon(Icons.chevron_right_rounded, size: 18, color: p.decor),
          ],
        ),
      ),
    );
  }

  Widget _dshTab(XlPalette p) {
    final list = kCommunityPlugins.where((p) => p.dshCompatible).toList();
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: p.blue.withOpacity(p.isDark ? 0.10 : 0.08),
              borderRadius: BorderRadius.circular(XlRadius.xl),
              border: Border.all(color: p.blue.withOpacity(0.28), width: 1),
            ),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: p.blue.withOpacity(p.isDark ? 0.16 : 0.12),
                    borderRadius: BorderRadius.circular(XlRadius.md),
                    border: Border.all(color: p.blue.withOpacity(0.32), width: 1),
                  ),
                  child: Icon(Icons.extension_rounded, size: 19, color: p.blue),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Text('兼容 DeepSeek Harness 插件生态，标注 DSH 的插件可在跨端 Harness 中直接运行',
                      style: TextStyle(
                        fontSize: XlFont.captionSm,
                        color: p.text2,
                        height: XlLineHeight.relaxed,
                        fontWeight: FontWeight.w500,
                      )),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Container(width: 4, height: 16, decoration: BoxDecoration(color: p.blue, borderRadius: BorderRadius.circular(2))),
              const SizedBox(width: 10),
              Text('DSH 兼容插件',
                  style: TextStyle(
                    fontSize: XlFont.h6,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                  )),
            ],
          ),
          const SizedBox(height: 14),
          for (final it in list) ...[
            _dshRow(p, it),
            const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }

  Widget _dshRow(XlPalette p, CommunityPlugin plugin) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: AppTheme.brandOrb(context, size: 42),
            child: Icon(communityIconForKey(plugin.icon), size: 18, color: p.btnInk),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(plugin.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: XlFont.body,
                            fontWeight: FontWeight.w800,
                            color: p.text1,
                          )),
                    ),
                    const SizedBox(width: 8),
                    AppTheme.badge(context, 'DSH', color: p.blue),
                  ],
                ),
                const SizedBox(height: 4),
                Text(plugin.description,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.text2,
                      fontWeight: FontWeight.w500,
                    )),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Row(
                children: [
                  Icon(Icons.star_rounded, size: 12, color: p.gold),
                  const SizedBox(width: 2),
                  Text(plugin.rating.toString(),
                      style: TextStyle(fontSize: XlFont.micro, color: p.gold, fontWeight: FontWeight.w800)),
                ],
              ),
              const SizedBox(height: 4),
              Text('${formatDownloads(plugin.downloads)}下载',
                  style: TextStyle(fontSize: XlFont.micro, color: p.decor, fontWeight: FontWeight.w600)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _footer(XlPalette p) {
    final total = _totalDownloads;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 14),
      decoration: BoxDecoration(
        color: p.surface.withOpacity(p.isDark ? 0.6 : 0.8),
        border: Border(top: BorderSide(color: p.edgeSoft, width: 1)),
      ),
      child: Text(
        '社区插件 ${kCommunityPlugins.length}+ · 累计下载 ${formatDownloads(total)}+',
        textAlign: TextAlign.center,
        style: TextStyle(
          fontSize: XlFont.label,
          color: p.decor,
          fontWeight: FontWeight.w700,
          letterSpacing: XlLetterSpacing.wider,
        ),
      ),
    );
  }
}

class _Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  const _Pressable({required this.child, this.onTap});
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
        scale: _down ? 0.96 : 1.0,
        duration: const Duration(milliseconds: 100),
        child: widget.child,
      ),
    );
  }
}
