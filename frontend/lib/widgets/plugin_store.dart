import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../services/local_store.dart';

class CommunityPlugin {
  final String name;
  final String title;
  final String description;
  final String author;
  final String category;
  final int downloads;
  final double rating;
  final String icon;
  final bool dshCompatible;
  const CommunityPlugin({
    required this.name,
    required this.title,
    required this.description,
    required this.author,
    required this.category,
    required this.downloads,
    required this.rating,
    required this.icon,
    required this.dshCompatible,
  });
}

const List<CommunityPlugin> kCommunityPlugins = [
  CommunityPlugin(name: 'code_reviewer', title: '代码审查', description: '自动审查代码质量，发现潜在问题与坏味道', author: 'xiaoling', category: '开发', downloads: 1234, rating: 4.8, icon: 'code', dshCompatible: true),
  CommunityPlugin(name: 'translator', title: '智能翻译', description: '多语言互译，支持文档批量翻译', author: 'xiaoling', category: '效率', downloads: 5678, rating: 4.9, icon: 'translate', dshCompatible: false),
  CommunityPlugin(name: 'pomodoro', title: '番茄钟', description: '专注计时，25分钟工作5分钟休息', author: 'xiaoling', category: '效率', downloads: 3421, rating: 4.7, icon: 'timer', dshCompatible: false),
  CommunityPlugin(name: 'weather', title: '天气查询', description: '实时天气与未来七天预报，覆盖全国城市', author: 'xiaoling', category: '工具', downloads: 8934, rating: 4.6, icon: 'weather', dshCompatible: false),
  CommunityPlugin(name: 'mindmap', title: '思维导图', description: '把想法一键转成可视化思维导图', author: 'community', category: '效率', downloads: 2156, rating: 4.5, icon: 'mindmap', dshCompatible: false),
  CommunityPlugin(name: 'code_formatter', title: '代码格式化', description: '统一缩进与风格，支持多种语言', author: 'xiaoling', category: '开发', downloads: 1876, rating: 4.7, icon: 'format', dshCompatible: true),
  CommunityPlugin(name: 'git_assistant', title: 'Git助手', description: '生成提交信息，解释 diff，管理分支', author: 'xiaoling', category: '开发', downloads: 4233, rating: 4.8, icon: 'git', dshCompatible: true),
  CommunityPlugin(name: 'db_manager', title: '数据库管理', description: '可视化查询与管理本地数据库', author: 'community', category: '开发', downloads: 1543, rating: 4.4, icon: 'database', dshCompatible: false),
  CommunityPlugin(name: 'api_tester', title: 'API测试', description: '构造请求、查看响应、保存用例集', author: 'community', category: '开发', downloads: 2674, rating: 4.6, icon: 'api', dshCompatible: true),
  CommunityPlugin(name: 'regex_helper', title: '正则助手', description: '测试正则表达式，实时高亮匹配', author: 'xiaoling', category: '开发', downloads: 1987, rating: 4.5, icon: 'regex', dshCompatible: false),
  CommunityPlugin(name: 'json_formatter', title: 'JSON格式化', description: '校验、压缩、美化与排序 JSON', author: 'xiaoling', category: '工具', downloads: 7654, rating: 4.9, icon: 'json', dshCompatible: false),
  CommunityPlugin(name: 'markdown_preview', title: 'Markdown预览', description: '边写边渲染，支持导出 HTML', author: 'community', category: '工具', downloads: 3210, rating: 4.6, icon: 'markdown', dshCompatible: false),
  CommunityPlugin(name: 'color_picker', title: '颜色选择器', description: '取色、调色板与渐变生成', author: 'community', category: '工具', downloads: 1432, rating: 4.3, icon: 'color', dshCompatible: false),
  CommunityPlugin(name: 'regex_generator', title: '正则生成器', description: '用自然语言描述自动生成正则', author: 'xiaoling', category: '开发', downloads: 1120, rating: 4.7, icon: 'regex_gen', dshCompatible: false),
  CommunityPlugin(name: 'file_renamer', title: '文件重命名', description: '批量重命名，支持规则与序号', author: 'community', category: '工具', downloads: 2289, rating: 4.5, icon: 'rename', dshCompatible: false),
  CommunityPlugin(name: 'image_compressor', title: '图片压缩', description: '批量压缩图片，保持清晰度', author: 'community', category: '工具', downloads: 3567, rating: 4.6, icon: 'image', dshCompatible: false),
  CommunityPlugin(name: 'pdf_tool', title: 'PDF工具', description: '合并、拆分与提取 PDF 文本', author: 'xiaoling', category: '效率', downloads: 4421, rating: 4.8, icon: 'pdf', dshCompatible: true),
];

const List<String> kCommunityCategories = ['全部', '工具', '娱乐', '效率', '开发', '社交', '游戏'];
const List<String> kCommunityFeatured = ['code_reviewer', 'translator', 'git_assistant'];

IconData communityIconForKey(String key) {
  switch (key) {
    case 'code': return Icons.code_rounded;
    case 'translate': return Icons.translate_rounded;
    case 'timer': return Icons.timer_rounded;
    case 'weather': return Icons.wb_sunny_rounded;
    case 'mindmap': return Icons.hub_outlined;
    case 'format': return Icons.format_shapes_rounded;
    case 'git': return Icons.merge_rounded;
    case 'database': return Icons.storage_rounded;
    case 'api': return Icons.api_rounded;
    case 'regex': return Icons.find_replace_rounded;
    case 'json': return Icons.data_object_rounded;
    case 'markdown': return Icons.description_rounded;
    case 'color': return Icons.color_lens_rounded;
    case 'regex_gen': return Icons.auto_fix_high_rounded;
    case 'rename': return Icons.drive_file_rename_outline_rounded;
    case 'image': return Icons.image_rounded;
    case 'pdf': return Icons.picture_as_pdf_rounded;
    default: return Icons.extension_outlined;
  }
}

IconData communityCategoryIcon(String category) {
  switch (category) {
    case '工具': return Icons.build_rounded;
    case '娱乐': return Icons.sports_esports_rounded;
    case '效率': return Icons.bolt_rounded;
    case '开发': return Icons.code_rounded;
    case '社交': return Icons.people_alt_rounded;
    case '游戏': return Icons.videogame_asset_rounded;
    default: return Icons.apps_rounded;
  }
}

String formatDownloads(int n) {
  if (n >= 10000) return '${(n / 10000).toStringAsFixed(1)}w';
  if (n >= 1000) return '${(n / 1000).toStringAsFixed(1)}k';
  return '$n';
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
  late String _category;
  final Set<String> _installed = {};
  final Set<String> _installing = {};
  bool _loading = true;
  bool _backendOnline = false;
  final List<dynamic> _remotePlugins = [];

  @override
  void initState() {
    super.initState();
    _category = widget.initialCategory ?? '全部';
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    final saved = await LocalStore.readStringList('installed_plugins.json');
    if (!mounted) return;
    setState(() {
      _installed.addAll(saved);
      _loading = false;
    });
    _syncWithBackend();
  }

  Future<void> _syncWithBackend() async {
    try {
      final reply = await XlClient.stub.command('plugin:list');
      final decoded = jsonDecode(reply.output);
      final plugins = (decoded['plugins'] as List?) ?? [];
      if (!mounted) return;
      setState(() {
        _backendOnline = true;
        _remotePlugins
          ..clear()
          ..addAll(plugins);
        for (final p in plugins) {
          final name = (p['name'] ?? '').toString();
          final enabled = p['enabled'] == true;
          if (name.isNotEmpty && enabled) _installed.add(name);
        }
      });
      _persistInstalled();
    } catch (_) {
      if (!mounted) return;
      setState(() => _backendOnline = false);
    }
  }

  Future<void> _persistInstalled() async {
    await LocalStore.writeStringList('installed_plugins.json', _installed.toList());
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  List<CommunityPlugin> get _filtered {
    final q = _query.trim().toLowerCase();
    return kCommunityPlugins.where((p) {
      if (_category != '全部' && p.category != _category) return false;
      if (q.isEmpty) return true;
      return p.title.toLowerCase().contains(q) || p.description.toLowerCase().contains(q);
    }).toList();
  }

  List<CommunityPlugin> get _featuredPlugins {
    final result = <CommunityPlugin>[];
    for (final n in kCommunityFeatured) {
      for (final p in kCommunityPlugins) {
        if (p.name == n) {
          result.add(p);
          break;
        }
      }
    }
    return result;
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    final showFeatured = widget.showFeatured && _category == '全部' && _query.trim().isEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _searchBox(p),
        const SizedBox(height: 14),
        _categoryChips(p),
        if (showFeatured) ...[
          const SizedBox(height: 20),
          _featuredHeader(p),
          const SizedBox(height: 12),
          _featuredRail(p),
        ],
        if (showFeatured && _backendOnline && _remotePlugins.isNotEmpty) ...[
          const SizedBox(height: 24),
          _installedHeader(p),
          const SizedBox(height: 12),
          _installedSection(p),
        ],
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
    return SizedBox(
      height: 34,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: EdgeInsets.zero,
        itemCount: kCommunityCategories.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (_, i) {
          final c = kCommunityCategories[i];
          final sel = c == _category;
          return _StorePressable(
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

  Widget _featuredHeader(XlPalette p) {
    return Row(
      children: [
        Container(
          width: 4,
          height: 16,
          decoration: BoxDecoration(gradient: p.gradBrand, borderRadius: BorderRadius.circular(2)),
        ),
        const SizedBox(width: 10),
        Text('精选推荐',
            style: TextStyle(
              fontSize: XlFont.h6,
              fontWeight: FontWeight.w800,
              color: p.text1,
              letterSpacing: XlLetterSpacing.normal,
            )),
        if (!_backendOnline) ...[
          const SizedBox(width: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: p.gold.withOpacity(p.isDark ? 0.16 : 0.12),
              borderRadius: BorderRadius.circular(XlRadius.pill),
              border: Border.all(color: p.gold.withOpacity(0.32), width: 1),
            ),
            child: Text('离线精选',
                style: TextStyle(
                  fontSize: XlFont.micro,
                  fontWeight: FontWeight.w800,
                  color: p.gold,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ),
        ],
      ],
    );
  }

  Widget _installedHeader(XlPalette p) {
    return Row(
      children: [
        Container(
          width: 4,
          height: 16,
          decoration: BoxDecoration(
            color: p.green,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 10),
        Text('已安装',
            style: TextStyle(
              fontSize: XlFont.h6,
              fontWeight: FontWeight.w800,
              color: p.text1,
              letterSpacing: XlLetterSpacing.normal,
            )),
        const Spacer(),
        Text('${_remotePlugins.length} 个',
            style: TextStyle(
              fontSize: XlFont.label,
              fontWeight: FontWeight.w700,
              color: p.decor,
              letterSpacing: XlLetterSpacing.wider,
            )),
      ],
    );
  }

  Widget _installedSection(XlPalette p) {
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: _remotePlugins.map((raw) {
        final m = (raw as Map).cast<String, dynamic>();
        final name = (m['name'] ?? '').toString();
        final enabled = m['enabled'] == true;
        final version = (m['version'] ?? '').toString();
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: AppTheme.neuXs(context, r: XlRadius.pill),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: enabled ? p.green : p.decorSoft,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(name,
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w700,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
              if (version.isNotEmpty) ...[
                const SizedBox(width: 6),
                Text('v$version',
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      fontWeight: FontWeight.w600,
                      color: p.decor,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ],
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _featuredRail(XlPalette p) {
    final list = _featuredPlugins;
    return SizedBox(
      height: 150,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: EdgeInsets.zero,
        itemCount: list.length,
        separatorBuilder: (_, __) => const SizedBox(width: 14),
        itemBuilder: (_, i) => _featuredCard(p, list[i]),
      ),
    );
  }

  Widget _featuredCard(XlPalette p, CommunityPlugin plugin) {
    return Container(
      width: 250,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: p.gradBrand,
        borderRadius: BorderRadius.circular(XlRadius.xl),
        border: Border.all(color: Colors.white.withOpacity(p.isDark ? 0.30 : 0.45), width: 1),
        boxShadow: [...p.raisedSm, BoxShadow(color: p.pink.withOpacity(0.30), blurRadius: 22, spreadRadius: -6)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.22),
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.white.withOpacity(0.5), width: 1.5),
                ),
                child: Icon(communityIconForKey(plugin.icon), size: 18, color: p.btnInk),
              ),
              const Spacer(),
              Icon(Icons.star_rounded, size: 15, color: p.btnInk.withOpacity(0.9)),
              const SizedBox(width: 2),
              Text(plugin.rating.toString(),
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: p.btnInk,
                  )),
            ],
          ),
          const SizedBox(height: 12),
          Text(plugin.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: XlFont.body,
                fontWeight: FontWeight.w800,
                color: p.btnInk,
                letterSpacing: XlLetterSpacing.normal,
              )),
          const SizedBox(height: 4),
          Expanded(
            child: Text(plugin.description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.btnInk.withOpacity(0.85),
                  height: XlLineHeight.relaxed,
                  fontWeight: FontWeight.w500,
                )),
          ),
        ],
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
        Text(_category == '全部' ? '精选插件' : _category,
            style: TextStyle(
              fontSize: XlFont.h6,
              fontWeight: FontWeight.w800,
              color: p.text1,
              letterSpacing: XlLetterSpacing.normal,
            )),
        const Spacer(),
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
            childAspectRatio: cols == 2 ? 1.45 : 1.35,
          ),
          itemCount: list.length,
          itemBuilder: (_, i) => _storeCard(p, list[i]),
        );
      },
    );
  }

  Widget _storeCard(XlPalette p, CommunityPlugin plugin) {
    final installed = _installed.contains(plugin.name);
    final installing = _installing.contains(plugin.name);
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
                child: Icon(communityIconForKey(plugin.icon), size: 18, color: p.btnInk),
              ),
              const Spacer(),
              if (plugin.dshCompatible) AppTheme.badge(context, 'DSH', color: p.blue),
            ],
          ),
          const SizedBox(height: 12),
          Text(plugin.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: XlFont.body,
                fontWeight: FontWeight.w800,
                color: p.text1,
                letterSpacing: XlLetterSpacing.normal,
              )),
          const SizedBox(height: 6),
          Expanded(
            child: Text(plugin.description,
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
              Text(plugin.author,
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    color: p.decor,
                    fontWeight: FontWeight.w600,
                  )),
              const Spacer(),
              Icon(Icons.star_rounded, size: 12, color: p.gold),
              const SizedBox(width: 2),
              Text(plugin.rating.toString(),
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    color: p.gold,
                    fontWeight: FontWeight.w800,
                  )),
              const SizedBox(width: 6),
              Text('${formatDownloads(plugin.downloads)}下载',
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    color: p.decor,
                    fontWeight: FontWeight.w600,
                  )),
            ],
          ),
          const SizedBox(height: 10),
          _installBtn(p, plugin, installed, installing),
        ],
      ),
    );
  }

  Widget _installBtn(XlPalette p, CommunityPlugin plugin, bool installed, bool installing) {
    return _StorePressable(
      onTap: (installed || installing) ? null : () => _install(plugin),
      child: Container(
        height: 34,
        alignment: Alignment.center,
        decoration: installed
            ? AppTheme.neuXs(context, r: XlRadius.pill)
            : AppTheme.brand(context, r: XlRadius.pill),
        child: installing
            ? SizedBox(
                width: 15,
                height: 15,
                child: CircularProgressIndicator(strokeWidth: 2, color: p.btnInk),
              )
            : Text(
                installed ? '已安装' : '安装',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  color: installed ? p.text2 : p.btnInk,
                  letterSpacing: XlLetterSpacing.wider,
                ),
              ),
      ),
    );
  }

  Future<void> _install(CommunityPlugin plugin) async {
    setState(() => _installing.add(plugin.name));
    final pink = XlPalette.of(context).pink;
    final green = XlPalette.of(context).green;
    final red = XlPalette.of(context).red;
    _showSnack('正在下载 ${plugin.title}…', pink);
    String? error;
    try {
      final reply = await XlClient.stub.command('plugin:install ${plugin.name}');
      final decoded = jsonDecode(reply.output);
      if (decoded['ok'] != true) {
        error = (decoded['error'] ?? '安装失败').toString();
      }
    } catch (e) {
      error = e.toString();
    }
    if (!mounted) return;
    if (error == null) {
      setState(() {
        _installed.add(plugin.name);
        _installing.remove(plugin.name);
      });
      _persistInstalled();
      _showSnack('${plugin.title} 安装成功并已启用', green);
    } else {
      setState(() => _installing.remove(plugin.name));
      _showSnack('安装失败：$error', red);
    }
  }

  void _showSnack(String message, Color color) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: XlPalette.of(context).surface,
        elevation: 0,
        duration: const Duration(milliseconds: 1500),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.md)),
        content: Row(
          children: [
            Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
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

  Widget _loadingView(XlPalette p) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 14,
      crossAxisSpacing: 14,
      childAspectRatio: 1.45,
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
            child: Icon(Icons.search_off_rounded, size: 26, color: p.btnInk),
          ),
          const SizedBox(height: 16),
          Text('没有找到相关插件',
              style: TextStyle(fontSize: XlFont.h6, fontWeight: FontWeight.w800, color: p.text1)),
          const SizedBox(height: 6),
          Text('换个关键词或分类试试',
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
