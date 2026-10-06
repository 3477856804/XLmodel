import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/theme.dart';
import '../updater.dart';

class UpdateDialog extends StatefulWidget {
  final UpdateInfo info;
  const UpdateDialog({super.key, required this.info});
  @override
  State<UpdateDialog> createState() => _UpdateDialogState();
}

class _UpdateDialogState extends State<UpdateDialog> with TickerProviderStateMixin {
  int _tab = 0;
  String _selectedPlatform = 'windows';
  int _selectedAsset = 0;
  bool _skipNext = false;
  late AnimationController _enterCtrl;
  late AnimationController _pulseCtrl;
  late AnimationController _shimmerCtrl;
  late AnimationController _tabCtrl;
  late Animation<double> _enterAnim;
  late Animation<double> _pulseAnim;

  static const _tabs = <String>['更新内容', '下载资源', '版本信息'];

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 500), vsync: this);
    _pulseCtrl = AnimationController(duration: const Duration(seconds: 4), vsync: this)..repeat();
    _shimmerCtrl = AnimationController(duration: const Duration(seconds: 3), vsync: this)..repeat();
    _tabCtrl = AnimationController(duration: const Duration(milliseconds: 400), vsync: this);
    _enterAnim = CurvedAnimation(parent: _enterCtrl, curve: XlCurve.springSoft);
    _pulseAnim = CurvedAnimation(parent: _pulseCtrl, curve: XlCurve.standard);
    _enterCtrl.forward();
    _tabCtrl.forward();
    _initPlatform();
  }

  @override
  void dispose() {
    _enterCtrl.dispose();
    _pulseCtrl.dispose();
    _shimmerCtrl.dispose();
    _tabCtrl.dispose();
    super.dispose();
  }

  void _initPlatform() {
    if (widget.info.assets.isEmpty) return;
    final guess = _guessPlatform();
    for (var i = 0; i < widget.info.assets.length; i++) {
      if (widget.info.assets[i].platform == guess) {
        _selectedPlatform = guess;
        _selectedAsset = i;
        return;
      }
    }
    _selectedPlatform = widget.info.assets.first.platform;
    _selectedAsset = 0;
  }

  String _guessPlatform() {
    final assets = widget.info.assets;
    if (assets.any((a) => a.platform == 'windows')) return 'windows';
    if (assets.any((a) => a.platform == 'macos')) return 'macos';
    if (assets.any((a) => a.platform == 'linux')) return 'linux';
    return assets.first.platform;
  }

  Color _platformColor(XlPalette p, String platform) {
    switch (platform) {
      case 'windows': return p.blue;
      case 'macos': return p.violet;
      case 'linux': return p.gold;
      case 'android': return p.green;
      case 'ios': return p.pink;
      default: return p.pink;
    }
  }

  IconData _platformIcon(String platform) {
    switch (platform) {
      case 'windows': return Icons.window_rounded;
      case 'macos': return Icons.laptop_mac_rounded;
      case 'linux': return Icons.terminal_rounded;
      case 'android': return Icons.android_rounded;
      case 'ios': return Icons.phone_iphone_rounded;
      case 'zip': return Icons.folder_zip_rounded;
      case 'tarball': return Icons.archive_outlined;
      default: return Icons.insert_drive_file_outlined;
    }
  }

  String _platformLabel(String platform) {
    switch (platform) {
      case 'windows': return 'Windows';
      case 'macos': return 'macOS';
      case 'linux': return 'Linux';
      case 'android': return 'Android';
      case 'ios': return 'iOS';
      case 'zip': return '压缩包';
      case 'tarball': return 'Tarball';
      default: return '其他';
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return AnimatedBuilder(
      animation: _enterAnim,
      builder: (_, child) => Opacity(
        opacity: _enterAnim.value,
        child: Transform.scale(
          scale: 0.94 + _enterAnim.value * 0.06,
          child: child,
        ),
      ),
      child: Dialog(
        backgroundColor: Colors.transparent,
        elevation: 0,
        insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
        child: Container(
          width: 560,
          constraints: BoxConstraints(
            maxHeight: MediaQuery.of(context).size.height - 80,
          ),
          decoration: AppTheme.neuLg(context, r: XlRadius.xxxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _hero(p),
              AppTheme.divider(context),
              _tabsRow(p),
              AppTheme.divider(context),
              Flexible(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(24, 20, 24, 8),
                  child: _tabContent(p),
                ),
              ),
              AppTheme.divider(context),
              _actions(p),
            ],
          ),
        ),
      ),
    );
  }

  Widget _hero(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              AnimatedBuilder(
                animation: _pulseAnim,
                builder: (_, __) {
                  final t = _pulseAnim.value;
                  return Stack(
                    alignment: Alignment.center,
                    children: [
                      Container(
                        width: 62 + t * 14,
                        height: 62 + t * 14,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: p.pink.withOpacity((1 - t) * 0.20),
                        ),
                      ),
                      Container(
                        width: 62,
                        height: 62,
                        decoration: BoxDecoration(
                          gradient: p.gradBrand,
                          borderRadius: BorderRadius.circular(XlRadius.xl),
                          border: Border.all(
                            color: Colors.white.withOpacity(p.isDark ? 0.35 : 0.5),
                            width: 2,
                          ),
                          boxShadow: [
                            ...p.raisedSm,
                            BoxShadow(
                              color: p.pink.withOpacity(0.42),
                              blurRadius: 24,
                              spreadRadius: -4,
                            ),
                          ],
                        ),
                        child: Icon(
                          Icons.rocket_launch_rounded,
                          size: 26,
                          color: p.btnInk,
                        ),
                      ),
                    ],
                  );
                },
              ),
              const SizedBox(width: 18),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text('发现新版本',
                            style: TextStyle(
                              fontSize: XlFont.h4,
                              fontWeight: FontWeight.w800,
                              color: p.text1,
                              letterSpacing: XlLetterSpacing.normal,
                            )),
                        const SizedBox(width: 10),
                        _pulseChip(p),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        _versionTag(p, 'v${widget.info.current}', p.text3, false),
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 8),
                          child: Icon(
                            Icons.arrow_forward_rounded,
                            size: 14,
                            color: p.decor,
                          ),
                        ),
                        _versionTag(p, 'v${widget.info.latest}', p.green, true),
                      ],
                    ),
                  ],
                ),
              ),
              _closeBtn(p),
            ],
          ),
          if (widget.info.name.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: AppTheme.neuXs(context, r: XlRadius.md),
              child: Row(
                children: [
                  Icon(Icons.label_outline_rounded, size: 14, color: p.gold),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(widget.info.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: XlFont.captionSm,
                          fontWeight: FontWeight.w700,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.wide,
                        )),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 14),
          Row(
            children: [
              _metaPill(p, Icons.tag_rounded, widget.info.tag),
              const SizedBox(width: 8),
              _metaPill(
                p,
                Icons.schedule_rounded,
                Updater.formatDate(widget.info.publishedAt),
              ),
              const SizedBox(width: 8),
              _metaPill(p, Icons.storage_rounded, Updater.formatSize(widget.info.sizeMb)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _pulseChip(XlPalette p) {
    return AnimatedBuilder(
      animation: _pulseAnim,
      builder: (_, __) {
        final t = _pulseAnim.value;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            gradient: p.gradBrand,
            borderRadius: BorderRadius.circular(XlRadius.pill),
            boxShadow: [
              ...p.raisedXxs,
              BoxShadow(
                color: p.pink.withOpacity(0.28 + t * 0.24),
                blurRadius: 14 + t * 6,
                spreadRadius: -3,
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: p.btnInk,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: p.btnInk.withOpacity(0.6),
                      blurRadius: 6,
                      spreadRadius: -1,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 5),
              Text('NEW',
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w800,
                    color: p.btnInk,
                    letterSpacing: XlLetterSpacing.ultra,
                  )),
            ],
          ),
        );
      },
    );
  }

  Widget _versionTag(XlPalette p, String text, Color color, bool highlight) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: highlight
            ? color.withOpacity(p.isDark ? 0.16 : 0.10)
            : p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(
          color: highlight ? color.withOpacity(0.32) : p.edgeSoft,
          width: 1,
        ),
        boxShadow: highlight ? p.raisedXxs : null,
      ),
      child: Text(text,
          style: TextStyle(
            fontSize: XlFont.label,
            fontWeight: FontWeight.w800,
            color: highlight ? color : p.text3,
            letterSpacing: XlLetterSpacing.wider,
            fontFeatures: const [FontFeature.tabularFigures()],
          )),
    );
  }

  Widget _metaPill(XlPalette p, IconData icon, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: p.edgeSoft, width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: p.decor),
          const SizedBox(width: 5),
          Text(text,
              style: TextStyle(
                fontSize: XlFont.micro,
                fontWeight: FontWeight.w700,
                color: p.text2,
                letterSpacing: XlLetterSpacing.wider,
              )),
        ],
      ),
    );
  }

  Widget _closeBtn(XlPalette p) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => Navigator.pop(context, _skipNext ? 'skip' : 'close'),
        borderRadius: BorderRadius.circular(XlRadius.md),
        child: Container(
          width: 40,
          height: 40,
          decoration: AppTheme.neuXs(context, r: XlRadius.md),
          child: Icon(Icons.close_rounded, size: 17, color: p.text2),
        ),
      ),
    );
  }

  Widget _tabsRow(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: List.generate(_tabs.length, (i) {
          final selected = _tab == i;
          return Expanded(
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: () => setState(() => _tab = i),
                borderRadius: BorderRadius.circular(XlRadius.md),
                child: AnimatedContainer(
                  duration: XlDuration.fast,
                  curve: XlCurve.standard,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  decoration: selected
                      ? BoxDecoration(
                          color: p.surfaceLo,
                          borderRadius: BorderRadius.circular(XlRadius.md),
                          border: Border.all(
                            color: p.pink.withOpacity(0.28),
                            width: 1.2,
                          ),
                          boxShadow: p.sunkenSm,
                        )
                      : null,
                  child: Column(
                    children: [
                      Text(_tabs[i],
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: XlFont.captionSm,
                            fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                            color: selected ? p.pink : p.text2,
                            letterSpacing: XlLetterSpacing.wider,
                          )),
                      const SizedBox(height: 4),
                      AnimatedContainer(
                        duration: XlDuration.fast,
                        width: selected ? 20 : 0,
                        height: 2,
                        decoration: BoxDecoration(
                          gradient: p.gradBrand,
                          borderRadius: BorderRadius.circular(99),
                          boxShadow: selected
                              ? [
                                  BoxShadow(
                                    color: p.pink.withOpacity(0.5),
                                    blurRadius: 8,
                                    spreadRadius: -1,
                                  ),
                                ]
                              : null,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _tabContent(XlPalette p) {
    switch (_tab) {
      case 0: return _changelogTab(p);
      case 1: return _assetsTab(p);
      case 2: return _metaTab(p);
      default: return _changelogTab(p);
    }
  }

  Widget _changelogTab(XlPalette p) {
    final lines = Updater.changelogLines(widget.info.body);
    if (lines.isEmpty) return _emptyTab(p, '暂无更新日志');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: AppTheme.neuXs(context, r: XlRadius.md),
          child: Row(
            children: [
              Icon(Icons.auto_awesome_rounded, size: 15, color: p.pink),
              const SizedBox(width: 10),
              Expanded(
                child: Text('这次更新带来了 ${lines.length} 项改动',
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w700,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        ...List.generate(lines.length, (i) => _logLine(p, lines[i], i)),
      ],
    );
  }

  Widget _logLine(XlPalette p, String text, int i) {
    final isHeader = _isHeader(text);
    if (isHeader) {
      return Padding(
        padding: EdgeInsets.only(top: i == 0 ? 0 : 16, bottom: 10),
        child: Row(
          children: [
            Container(
              width: 4,
              height: 16,
              decoration: BoxDecoration(
                gradient: p.gradBrand,
                borderRadius: BorderRadius.circular(99),
                boxShadow: [
                  BoxShadow(
                    color: p.pink.withOpacity(0.4),
                    blurRadius: 8,
                    spreadRadius: -1,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            Text(text,
                style: TextStyle(
                  fontSize: XlFont.caption,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      );
    }
    final color = _lineColor(p, text);
    final icon = _lineIcon(text);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: AppTheme.neuXs(context, r: XlRadius.sm),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 24,
              height: 24,
              decoration: BoxDecoration(
                color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                borderRadius: BorderRadius.circular(XlRadius.xs),
                border: Border.all(color: color.withOpacity(0.28), width: 1),
              ),
              child: Icon(icon, size: 12, color: color),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(text,
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w500,
                    color: p.text1,
                    height: XlLineHeight.relaxed,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
            ),
          ],
        ),
      ),
    );
  }

  bool _isHeader(String s) {
    final lower = s.toLowerCase();
    return lower.startsWith('feature') ||
        lower.startsWith('added') ||
        lower.startsWith('fixed') ||
        lower.startsWith('changed') ||
        lower.startsWith('improved') ||
        lower.startsWith('优化') ||
        lower.startsWith('新增') ||
        lower.startsWith('修复') ||
        lower.startsWith('变更');
  }

  Color _lineColor(XlPalette p, String s) {
    final lower = s.toLowerCase();
    if (lower.contains('fix') || lower.contains('bug') || s.contains('修复')) return p.green;
    if (lower.contains('new') || lower.contains('add') || s.contains('新增')) return p.pink;
    if (lower.contains('remove') || lower.contains('break') || s.contains('移除') || s.contains('破坏')) return p.red;
    if (lower.contains('perf') || lower.contains('improve') || s.contains('优化')) return p.gold;
    return p.violet;
  }

  IconData _lineIcon(String s) {
    final lower = s.toLowerCase();
    if (lower.contains('fix') || lower.contains('bug') || s.contains('修复')) return Icons.bug_report_outlined;
    if (lower.contains('new') || lower.contains('add') || s.contains('新增')) return Icons.add_circle_outline_rounded;
    if (lower.contains('remove') || s.contains('移除')) return Icons.remove_circle_outline_rounded;
    if (lower.contains('perf') || lower.contains('improve') || s.contains('优化')) return Icons.trending_up_rounded;
    return Icons.star_outline_rounded;
  }

  Widget _assetsTab(XlPalette p) {
    final assets = widget.info.assets;
    if (assets.isEmpty) return _emptyTab(p, '暂无可下载资源');
    final grouped = <String, List<int>>{};
    for (var i = 0; i < assets.length; i++) {
      final key = assets[i].platform;
      grouped.putIfAbsent(key, () => []).add(i);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: AppTheme.neuXs(context, r: XlRadius.md),
          child: Row(
            children: [
              Icon(Icons.info_outline_rounded, size: 15, color: p.gold),
              const SizedBox(width: 10),
              Expanded(
                child: Text('选择对应平台的安装包下载，推荐项已高亮',
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w600,
                      color: p.text2,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        ...grouped.entries.map((e) => _platformGroup(p, e.key, e.value)),
      ],
    );
  }

  Widget _platformGroup(XlPalette p, String platform, List<int> indices) {
    final color = _platformColor(p, platform);
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 26,
                height: 26,
                decoration: BoxDecoration(
                  color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                  borderRadius: BorderRadius.circular(XlRadius.xs),
                  border: Border.all(color: color.withOpacity(0.28), width: 1),
                ),
                child: Icon(_platformIcon(platform), size: 13, color: color),
              ),
              const SizedBox(width: 10),
              Text(_platformLabel(platform),
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: p.surfaceLo,
                  borderRadius: BorderRadius.circular(XlRadius.xs),
                ),
                child: Text('${indices.length}',
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      fontWeight: FontWeight.w800,
                      color: p.text3,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ...indices.map((i) => _assetRow(p, i, color)),
        ],
      ),
    );
  }

  Widget _assetRow(XlPalette p, int index, Color color) {
    final a = widget.info.assets[index];
    final selected = _selectedAsset == index;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => setState(() {
            _selectedAsset = index;
            _selectedPlatform = a.platform;
          }),
          borderRadius: BorderRadius.circular(XlRadius.md),
          child: AnimatedContainer(
            duration: XlDuration.fast,
            curve: XlCurve.standard,
            padding: const EdgeInsets.all(12),
            decoration: selected
                ? BoxDecoration(
                    color: p.surfaceLo,
                    borderRadius: BorderRadius.circular(XlRadius.md),
                    border: Border.all(color: color.withOpacity(0.42), width: 1.4),
                    boxShadow: p.sunkenSm,
                  )
                : AppTheme.neuXs(context, r: XlRadius.md),
            child: Row(
              children: [
                AnimatedContainer(
                  duration: XlDuration.fast,
                  width: 20,
                  height: 20,
                  decoration: BoxDecoration(
                    color: selected ? color : Colors.transparent,
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: selected
                          ? color
                          : p.shDark.withOpacity(p.isDark ? 0.32 : 0.14),
                      width: 1.5,
                    ),
                  ),
                  child: selected
                      ? Icon(
                          Icons.check_rounded,
                          size: 13,
                          color: p.isDark ? p.btnInk : Colors.white,
                        )
                      : null,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(a.name,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: XlFont.captionSm,
                                  fontWeight: FontWeight.w700,
                                  color: p.text1,
                                  letterSpacing: XlLetterSpacing.wide,
                                )),
                          ),
                          if (a.recommended) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                              decoration: BoxDecoration(
                                color: p.gold.withOpacity(p.isDark ? 0.18 : 0.12),
                                borderRadius: BorderRadius.circular(XlRadius.xs),
                                border: Border.all(
                                  color: p.gold.withOpacity(0.32),
                                  width: 1,
                                ),
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
                        ],
                      ),
                      const SizedBox(height: 3),
                      Row(
                        children: [
                          Text(Updater.formatSize(a.sizeMb),
                              style: TextStyle(
                                fontSize: XlFont.label,
                                fontWeight: FontWeight.w700,
                                color: p.text3,
                                letterSpacing: XlLetterSpacing.wider,
                                fontFeatures: const [FontFeature.tabularFigures()],
                              )),
                          const SizedBox(width: 10),
                          Container(
                            width: 3,
                            height: 3,
                            decoration: BoxDecoration(
                              color: p.decor,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Text(a.platform.toUpperCase(),
                              style: TextStyle(
                                fontSize: XlFont.label,
                                fontWeight: FontWeight.w800,
                                color: color,
                                letterSpacing: XlLetterSpacing.ultra,
                              )),
                        ],
                      ),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right_rounded, size: 16, color: p.decor),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _metaTab(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _metaSection(p, '版本'),
        _metaRow(p, '当前版本', 'v${widget.info.current}', p.text2),
        const SizedBox(height: 8),
        _metaRow(p, '最新版本', 'v${widget.info.latest}', p.green),
        const SizedBox(height: 8),
        _metaRow(p, '标签', widget.info.tag, p.pink),
        const SizedBox(height: 8),
        _metaRow(p, '发布时间', Updater.formatDate(widget.info.publishedAt), p.gold),
        const SizedBox(height: 16),
        _metaSection(p, '来源'),
        _metaRow(p, '仓库', Updater.repo, p.violet),
        const SizedBox(height: 8),
        _metaRow(p, '镜像源', widget.info.source, p.blue),
        const SizedBox(height: 8),
        _metaRow(p, '预发布', widget.info.prerelease ? '是' : '否', widget.info.prerelease ? p.gold : p.text3),
        const SizedBox(height: 16),
        _metaSection(p, '资源'),
        _metaRow(p, '资源数量', '${widget.info.assets.length} 个', p.pink),
        const SizedBox(height: 8),
        _metaRow(p, '总体积', Updater.formatSize(widget.info.sizeMb), p.green),
        const SizedBox(height: 8),
        _metaRow(p, '直链地址', widget.info.htmlUrl.isEmpty ? '—' : '已获取', p.blue),
      ],
    );
  }

  Widget _metaSection(XlPalette p, String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10, left: 2),
      child: Row(
        children: [
          Container(
            width: 3,
            height: 12,
            decoration: BoxDecoration(
              gradient: p.gradBrand,
              borderRadius: BorderRadius.circular(99),
            ),
          ),
          const SizedBox(width: 8),
          Text(title.toUpperCase(),
              style: TextStyle(
                fontSize: XlFont.label,
                fontWeight: FontWeight.w800,
                color: p.gold,
                letterSpacing: XlLetterSpacing.ultra,
              )),
        ],
      ),
    );
  }

  Widget _metaRow(XlPalette p, String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
      decoration: AppTheme.neuXs(context, r: XlRadius.sm),
      child: Row(
        children: [
          Text(label,
              style: TextStyle(
                fontSize: XlFont.captionSm,
                fontWeight: FontWeight.w600,
                color: p.text3,
                letterSpacing: XlLetterSpacing.wide,
              )),
          const Spacer(),
          Flexible(
            child: Text(value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.right,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  color: color,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          ),
        ],
      ),
    );
  }

  Widget _emptyTab(XlPalette p, String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 40),
      child: Center(
        child: Column(
          children: [
            Container(
              width: 62,
              height: 62,
              decoration: AppTheme.neuXs(context, r: XlRadius.xxl),
              child: Icon(Icons.inbox_outlined, size: 26, color: p.decor),
            ),
            const SizedBox(height: 16),
            Text(text,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w600,
                  color: p.text2,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
        ),
      ),
    );
  }

  Widget _actions(XlPalette p) {
    final asset = widget.info.assets.isEmpty ? null : widget.info.assets[_selectedAsset];
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          Row(
            children: [
              GestureDetector(
                onTap: () => setState(() => _skipNext = !_skipNext),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: _skipNext
                        ? p.gold.withOpacity(p.isDark ? 0.14 : 0.10)
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(XlRadius.sm),
                    border: Border.all(
                      color: _skipNext
                          ? p.gold.withOpacity(0.35)
                          : p.edgeSoft,
                      width: 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      AnimatedContainer(
                        duration: XlDuration.fast,
                        width: 16,
                        height: 16,
                        decoration: BoxDecoration(
                          color: _skipNext ? p.gold : Colors.transparent,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(
                            color: _skipNext
                                ? p.gold
                                : p.shDark.withOpacity(p.isDark ? 0.32 : 0.14),
                            width: 1.4,
                          ),
                        ),
                        child: _skipNext
                            ? Icon(Icons.check_rounded,
                                size: 11,
                                color: p.isDark ? p.btnInk : Colors.white)
                            : null,
                      ),
                      const SizedBox(width: 8),
                      Text('跳过此版本',
                          style: TextStyle(
                            fontSize: XlFont.label,
                            fontWeight: FontWeight.w700,
                            color: _skipNext ? p.gold : p.text3,
                            letterSpacing: XlLetterSpacing.wider,
                          )),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _secondaryBtn(
                  p,
                  Icons.schedule_rounded,
                  '稍后提醒',
                  () => Navigator.pop(context, _skipNext ? 'skip' : 'later'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                flex: 2,
                child: _primaryBtn(
                  p,
                  asset == null ? '查看发布页' : '立即下载',
                  asset == null ? Icons.open_in_new_rounded : Icons.download_rounded,
                  () => _download(asset),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _secondaryBtn(XlPalette p, IconData icon, String label, VoidCallback onTap) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(XlRadius.pill),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: AppTheme.ghost(context, r: XlRadius.pill),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 15, color: p.text2),
              const SizedBox(width: 8),
              Text(label,
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
        ),
      ),
    );
  }

  Widget _primaryBtn(XlPalette p, String label, IconData icon, VoidCallback onTap) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(XlRadius.pill),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: AppTheme.btn(context, r: XlRadius.pill),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 15, color: p.btnInk),
              const SizedBox(width: 8),
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
      ),
    );
  }

  void _download(UpdateAsset? asset) {
    if (asset == null) {
      Navigator.pop(context, _skipNext ? 'skip' : 'open');
      return;
    }
    Clipboard.setData(ClipboardData(text: asset.url));
    HapticFeedback.mediumImpact();
    ScaffoldMessenger.of(context).clearSnackBars();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      behavior: SnackBarBehavior.floating,
      backgroundColor: XlPalette.of(context).surface,
      elevation: 0,
      duration: const Duration(milliseconds: 1800),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(XlRadius.md),
      ),
      content: Row(
        children: [
          Icon(Icons.download_rounded,
              size: 16, color: XlPalette.of(context).pink),
          const SizedBox(width: 10),
          Expanded(
            child: Text('已复制下载链接到剪贴板',
                style: TextStyle(
                  color: XlPalette.of(context).text1,
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w700,
                )),
          ),
        ],
      ),
    ));
    Navigator.pop(context, _skipNext ? 'skip' : 'download');
  }
}

Future<String?> showUpdateDialog(BuildContext context, UpdateInfo info) {
  return showDialog<String>(
    context: context,
    barrierColor: XlPalette.of(context).scrim,
    barrierDismissible: true,
    builder: (_) => UpdateDialog(info: info),
  );
}