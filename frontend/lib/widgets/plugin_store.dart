import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';

IconData communityCategoryIcon(String category) {
  switch (category) {
    case 'core':
    case 'ai':
      return Icons.psychology_outlined;
    case 'tool':
      return Icons.build_rounded;
    case 'fun':
      return Icons.sports_esports_rounded;
    case 'system':
      return Icons.tune_rounded;
    case 'community':
    case 'custom':
      return Icons.extension_outlined;
    case '开发':
      return Icons.code_rounded;
    case '效率':
      return Icons.bolt_rounded;
    case '娱乐':
      return Icons.sports_esports_rounded;
    case '工具':
      return Icons.build_rounded;
    case '社交':
      return Icons.people_alt_rounded;
    case '游戏':
      return Icons.videogame_asset_rounded;
    default:
      return Icons.extension_outlined;
  }
}

class PluginStore extends StatefulWidget {
  final String? initialCategory;
  final bool showFeatured;
  const PluginStore({super.key, this.initialCategory, this.showFeatured = true});
  @override
  State<PluginStore> createState() => _PluginStoreState();
}

class _PluginStoreState extends State<PluginStore> {
  final _searchCtrl = TextEditingController();
  String _query = '';
  String _category = '全部';
  bool _loading = true;
  bool _online = false;
  final List<Map<String, dynamic>> _plugins = [];
  final Set<String> _toggling = {};

  @override
  void initState() {
    super.initState();
    if (widget.initialCategory != null) _category = widget.initialCategory!;
    _load();
  }

  Future<void> _load() async {
    try {
      final reply = await XlClient.stub.command('plugin:market');
      final decoded = jsonDecode(reply.output);
      final list = (decoded['plugins'] as List?) ?? [];
      if (!mounted) return;
      setState(() {
        _online = true;
        _plugins
          ..clear()
          ..addAll(list.map((e) => Map<String, dynamic>.from(e as Map)));
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _online = false;
        _loading = false;
      });
    }
  }

  Future<void> _toggle(Map<String, dynamic> plugin) async {
    final name = (plugin['name'] ?? '').toString();
    if (name.isEmpty || _toggling.contains(name)) return;
    final next = plugin['enabled'] != true;
    setState(() {
      plugin['enabled'] = next;
      _toggling.add(name);
    });
    try {
      await XlClient.stub.safe(() => XlClient.stub
          .command(next ? 'plugin:enable $name' : 'plugin:disable $name'));
    } catch (_) {
      if (mounted) setState(() => plugin['enabled'] = !next);
    }
    if (mounted) setState(() => _toggling.remove(name));
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  List<String> get _categories {
    final set = <String>{'全部'};
    for (final p in _plugins) {
      final c = (p['category'] ?? '').toString();
      if (c.isNotEmpty) set.add(c);
    }
    return set.toList();
  }

  List<Map<String, dynamic>> get _filtered {
    final q = _query.trim().toLowerCase();
    return _plugins.where((p) {
      if (_category != '全部' &&
          (p['category'] ?? '').toString() != _category) return false;
      if (q.isEmpty) return true;
      final name = (p['name'] ?? '').toString().toLowerCase();
      final desc = (p['description'] ?? '').toString().toLowerCase();
      return name.contains(q) || desc.contains(q);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _searchBox(p),
        const SizedBox(height: 14),
        _categoryChips(p),
        const SizedBox(height: 20),
        _gridHeader(p),
        const SizedBox(height: 14),
        _grid(p),
      ],
    );
  }

  Widget _searchBox(XlPalette p) {
    return Container(
      height: 44,
      decoration: AppTheme.sunkenXs(context, r: XlRadius.lg),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      child: Row(
        children: [
          Icon(Icons.search_rounded, size: 17, color: p.decor),
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
    );
  }

  Widget _categoryChips(XlPalette p) {
    final cats = _categories;
    return SizedBox(
      height: 34,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: EdgeInsets.zero,
        itemCount: cats.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (_, i) {
          final c = cats[i];
          final sel = c == _category;
          return GestureDetector(
            onTap: () => setState(() => _category = c),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              decoration: sel
                  ? AppTheme.brand(context, r: XlRadius.pill)
                  : AppTheme.neuXs(context, r: XlRadius.pill),
              child: Text(c,
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: sel ? FontWeight.w800 : FontWeight.w600,
                    color: sel ? p.btnInk : p.text2,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
            ),
          );
        },
      ),
    );
  }

  Widget _gridHeader(XlPalette p) {
    final list = _filtered;
    return Row(
      children: [
        Container(
          width: 4,
          height: 16,
          decoration: BoxDecoration(gradient: p.gradBrand, borderRadius: BorderRadius.circular(2)),
        ),
        const SizedBox(width: 10),
        Text(_category == '全部' ? '插件' : _category,
            style: TextStyle(
              fontSize: XlFont.h6,
              fontWeight: FontWeight.w800,
              color: p.text1,
              letterSpacing: XlLetterSpacing.normal,
            )),
        const Spacer(),
        if (!_online)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: p.gold.withOpacity(0.14),
              borderRadius: BorderRadius.circular(XlRadius.pill),
              border: Border.all(color: p.gold.withOpacity(0.32), width: 1),
            ),
            child: Text('未连接',
                style: TextStyle(fontSize: XlFont.micro, fontWeight: FontWeight.w800, color: p.gold, letterSpacing: XlLetterSpacing.wider)),
          )
        else
          Text('${list.length} 个',
              style: TextStyle(
                fontSize: XlFont.label,
                fontWeight: FontWeight.w700,
                color: p.decor,
                letterSpacing: XlLetterSpacing.wider,
              )),
      ],
    );
  }

  Widget _grid(XlPalette p) {
    if (_loading) return _loadingView(p);
    if (!_online) return _offlineView(p);
    final list = _filtered;
    if (list.isEmpty) return _emptyView(p);
    return LayoutBuilder(
      builder: (context, c) {
        final cols = c.maxWidth > 900 ? 3 : 2;
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          padding: EdgeInsets.zero,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: cols,
            mainAxisSpacing: 14,
            crossAxisSpacing: 14,
            childAspectRatio: cols == 2 ? 1.5 : 1.4,
          ),
          itemCount: list.length,
          itemBuilder: (_, i) => _storeCard(p, list[i]),
        );
      },
    );
  }

  Widget _storeCard(XlPalette p, Map<String, dynamic> plugin) {
    final name = (plugin['name'] ?? '').toString();
    final version = (plugin['version'] ?? '').toString();
    final author = (plugin['author'] ?? '').toString();
    final category = (plugin['category'] ?? '').toString();
    final description = (plugin['description'] ?? '').toString();
    final enabled = plugin['enabled'] == true;
    final builtin = plugin['builtin'] == true;
    final toggling = _toggling.contains(name);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: AppTheme.brandOrb(context, size: 40),
                child: Icon(communityCategoryIcon(category), size: 18, color: p.btnInk),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: XlFont.body,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.normal,
                        )),
                    const SizedBox(height: 2),
                    Text(version.isNotEmpty ? 'v$version' : '未发布版本',
                        style: TextStyle(fontSize: XlFont.micro, color: p.decor, fontWeight: FontWeight.w600)),
                  ],
                ),
              ),
              if (builtin) AppTheme.badge(context, '内置', color: p.blue),
            ],
          ),
          const SizedBox(height: 10),
          Expanded(
            child: Text(description.isEmpty ? '暂无描述' : description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text2,
                  height: XlLineHeight.relaxed,
                  fontWeight: FontWeight.w500,
                )),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(Icons.person_outline_rounded, size: 12, color: p.decor),
              const SizedBox(width: 3),
              Expanded(
                child: Text(author.isEmpty ? '未知作者' : author,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: XlFont.micro, color: p.decor, fontWeight: FontWeight.w600)),
              ),
              _enableToggle(p, enabled, toggling, () => _toggle(plugin)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _enableToggle(XlPalette p, bool enabled, bool toggling, VoidCallback onTap) {
    return GestureDetector(
      onTap: toggling ? null : onTap,
      child: Container(
        width: 44,
        height: 24,
        decoration: BoxDecoration(
          color: enabled ? p.pink : p.surfaceLo,
          borderRadius: BorderRadius.circular(XlRadius.pill),
          border: Border.all(color: enabled ? p.pink : p.edgeSoft, width: 1),
        ),
        child: toggling
            ? Center(child: SizedBox(width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 2, color: p.btnInk)))
            : AnimatedAlign(
                duration: XlDuration.fast,
                alignment: enabled ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  margin: const EdgeInsets.all(2.5),
                  width: 17,
                  height: 17,
                  decoration: BoxDecoration(color: enabled ? p.btnInk : p.decor, shape: BoxShape.circle),
                ),
              ),
      ),
    );
  }

  Widget _loadingView(XlPalette p) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 14,
      crossAxisSpacing: 14,
      childAspectRatio: 1.5,
      children: [
        for (int i = 0; i < 4; i++)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: AppTheme.neu(context, r: XlRadius.xl),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(width: 40, height: 40, decoration: BoxDecoration(color: p.surfaceLo, shape: BoxShape.circle)),
                const SizedBox(height: 14),
                Container(width: 90, height: 12, decoration: BoxDecoration(color: p.surfaceLo, borderRadius: BorderRadius.circular(6))),
                const SizedBox(height: 8),
                Container(width: double.infinity, height: 8, decoration: BoxDecoration(color: p.surfaceLo, borderRadius: BorderRadius.circular(4))),
              ],
            ),
          ),
      ],
    );
  }

  Widget _offlineView(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(40),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Column(
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: AppTheme.brandOrb(context, size: 60),
            child: Icon(Icons.link_off_rounded, size: 26, color: p.btnInk),
          ),
          const SizedBox(height: 16),
          Text('插件服务未连接',
              style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
          const SizedBox(height: 6),
          Text('请确认后端已启动后重试',
              style: TextStyle(fontSize: XlFont.captionSm, color: p.text2, fontWeight: FontWeight.w500)),
          const SizedBox(height: 16),
          GestureDetector(
            onTap: () {
              setState(() => _loading = true);
              _load();
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 9),
              decoration: AppTheme.btn(context, r: XlRadius.pill),
              child: Text('重试',
                  style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w800, color: p.btnInk, letterSpacing: XlLetterSpacing.wider)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _emptyView(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(40),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Column(
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: AppTheme.brandOrb(context, size: 60),
            child: Icon(Icons.extension_outlined, size: 26, color: p.btnInk),
          ),
          const SizedBox(height: 16),
          Text('暂无插件',
              style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
          const SizedBox(height: 6),
          Text(_query.isNotEmpty ? '没有找到匹配的插件' : '后端尚未提供可用插件',
              style: TextStyle(fontSize: XlFont.captionSm, color: p.text2, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

class _StorePressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  const _StorePressable({required this.child, this.onTap});
  @override
  State<_StorePressable> createState() => _StorePressableState();
}

class _StorePressableState extends State<_StorePressable> {
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
