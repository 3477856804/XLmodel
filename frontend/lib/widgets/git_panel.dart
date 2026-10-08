import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import '../theme/theme.dart';

class GitPanel extends StatefulWidget {
  final String repoPath;
  const GitPanel({super.key, this.repoPath = '.'});

  @override
  State<GitPanel> createState() => _GitPanelState();
}

class _GitFile {
  final String path;
  final String status;
  final String type;
  bool selected = true;
  _GitFile({required this.path, required this.status, required this.type});
}

class _CommitEntry {
  final String hash;
  final String short;
  final String author;
  final String date;
  final String message;
  _CommitEntry({required this.hash, required this.short, required this.author, required this.date, required this.message});
}

class _BranchEntry {
  final String name;
  final bool current;
  _BranchEntry({required this.name, required this.current});
}

class _GitPanelState extends State<GitPanel> with SingleTickerProviderStateMixin {
  late final TabController _tabCtrl;
  final TextEditingController _commitMsgCtrl = TextEditingController();
  final Set<String> _expanded = {};
  final Map<String, String> _diffCache = {};

  List<_GitFile> _files = [];
  List<_CommitEntry> _commits = [];
  List<_BranchEntry> _branches = [];
  String _currentBranch = '';
  String _repoRoot = '';
  bool _loading = true;
  bool _committing = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
    _refresh();
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    _commitMsgCtrl.dispose();
    super.dispose();
  }

  Future<ProcessResult> _git(List<String> args) async {
    return Process.run('git', args, workingDirectory: widget.repoPath);
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final rootRes = await _git(['rev-parse', '--show-toplevel']);
      final root = rootRes.exitCode == 0 ? (rootRes.stdout as String).trim() : widget.repoPath;

      final statusRes = await _git(['status', '--porcelain']);
      final files = <_GitFile>[];
      if (statusRes.exitCode == 0) {
        for (final line in (statusRes.stdout as String).trim().split('\n')) {
          if (line.isEmpty) continue;
          final code = line.substring(0, 2);
          final name = line.length > 3 ? line.substring(3) : line;
          files.add(_GitFile(path: name, status: code, type: _typeOf(code)));
        }
      }

      final logRes = await _git(['log', '-30', '--pretty=format:%H|%h|%an|%ad|%s', '--date=short']);
      final commits = <_CommitEntry>[];
      if (logRes.exitCode == 0) {
        for (final line in (logRes.stdout as String).trim().split('\n')) {
          final parts = line.split('|');
          if (parts.length == 5) {
            commits.add(_CommitEntry(
              hash: parts[0],
              short: parts[1],
              author: parts[2],
              date: parts[3],
              message: parts[4],
            ));
          }
        }
      }

      final branchRes = await _git(['branch', '-a']);
      final branches = <_BranchEntry>[];
      String current = '';
      if (branchRes.exitCode == 0) {
        for (final line in (branchRes.stdout as String).trim().split('\n')) {
          if (line.isEmpty) continue;
          if (line.startsWith('*')) {
            final n = line.substring(2).trim();
            current = n;
            branches.add(_BranchEntry(name: n, current: true));
          } else {
            branches.add(_BranchEntry(name: line.trim(), current: false));
          }
        }
      }

      if (!mounted) return;
      setState(() {
        _repoRoot = root;
        _files = files;
        _commits = commits;
        _branches = branches;
        _currentBranch = current;
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

  String _typeOf(String code) {
    if (code.startsWith('??')) return 'untracked';
    if (code.startsWith('M')) return 'modified';
    if (code.startsWith('A')) return 'added';
    if (code.startsWith('D')) return 'deleted';
    if (code.startsWith('R')) return 'renamed';
    return 'other';
  }

  Color _statusColor(XlPalette p, String type) {
    switch (type) {
      case 'added':
      case 'untracked':
        return p.green;
      case 'deleted':
        return p.red;
      case 'modified':
        return p.gold;
      case 'renamed':
        return p.blue;
      default:
        return p.text3;
    }
  }

  IconData _statusIcon(String type) {
    switch (type) {
      case 'added':
      case 'untracked':
        return Icons.add_circle_outline_rounded;
      case 'deleted':
        return Icons.remove_circle_outline_rounded;
      case 'modified':
        return Icons.edit_outlined;
      case 'renamed':
        return Icons.drive_file_rename_outline_rounded;
      default:
        return Icons.help_outline_rounded;
    }
  }

  String _statusLabel(String type) {
    switch (type) {
      case 'added':
        return '新增';
      case 'untracked':
        return '未跟踪';
      case 'deleted':
        return '已删除';
      case 'modified':
        return '已修改';
      case 'renamed':
        return '已重命名';
      default:
        return '其他';
    }
  }

  Future<void> _toggleDiff(_GitFile f) async {
    if (_expanded.contains(f.path)) {
      setState(() => _expanded.remove(f.path));
      return;
    }
    setState(() => _expanded.add(f.path));
    if (_diffCache.containsKey(f.path)) return;
    final res = await _git(['diff', f.path]);
    if (!mounted) return;
    setState(() {
      _diffCache[f.path] = res.exitCode == 0 ? (res.stdout as String) : (res.stderr as String);
    });
  }

  bool get _allSelected => _files.isNotEmpty && _files.every((f) => f.selected);

  void _toggleSelectAll() {
    final v = !_allSelected;
    setState(() {
      for (final f in _files) {
        f.selected = v;
      }
    });
  }

  Future<void> _commit() async {
    final msg = _commitMsgCtrl.text.trim();
    if (msg.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请输入提交信息')));
      return;
    }
    setState(() => _committing = true);
    try {
      final selected = _files.where((f) => f.selected).map((f) => f.path).toList();
      if (selected.isNotEmpty) {
        await _git(['add', ...selected]);
      } else {
        await _git(['add', '-A']);
      }
      final res = await _git(['commit', '-m', msg]);
      if (!mounted) return;
      final ok = res.exitCode == 0;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(ok ? '提交成功' : '提交失败: ${(res.stderr as String).trim()}'),
      ));
      if (ok) {
        _commitMsgCtrl.clear();
        _diffCache.clear();
        await _refresh();
      }
    } finally {
      if (mounted) setState(() => _committing = false);
    }
  }

  Future<void> _checkout(_BranchEntry b) async {
    if (b.current) return;
    final res = await _git(['checkout', b.name]);
    if (!mounted) return;
    final ok = res.exitCode == 0;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(ok ? '已切换到 ${b.name}' : '切换失败: ${(res.stderr as String).trim()}'),
    ));
    if (ok) await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Column(
      children: [
        _header(p),
        if (_error != null) ...[
          const SizedBox(height: 12),
          _errorBanner(p),
        ],
        const SizedBox(height: 14),
        _tabBar(p),
        const SizedBox(height: 14),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator(strokeWidth: 2))
              : TabBarView(
                  controller: _tabCtrl,
                  children: [
                    _changesTab(p),
                    _historyTab(p),
                    _branchesTab(p),
                  ],
                ),
        ),
      ],
    );
  }

  Widget _errorBanner(XlPalette p) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: p.red.withOpacity(p.isDark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.md),
        border: Border.all(color: p.red.withOpacity(0.35), width: 1),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline_rounded, size: 15, color: p.red),
          const SizedBox(width: 10),
          Expanded(
            child: Text('无法访问 Git 仓库: ${_error!}',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text1,
                  fontWeight: FontWeight.w600,
                )),
          ),
        ],
      ),
    );
  }

  Widget _header(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neu(context, r: XlRadius.xl),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: AppTheme.brandOrb(context, size: 36),
            child: Icon(Icons.commit_rounded, size: 18, color: p.btnInk),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(_repoRoot.isEmpty ? '未检测到仓库' : _repoRoot,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w700,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                const SizedBox(height: 2),
                Text('版本控制 · Git',
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.text3,
                      fontWeight: FontWeight.w600,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ],
            ),
          ),
          const SizedBox(width: 10),
          if (_currentBranch.isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: AppTheme.gold(context, r: XlRadius.pill),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.fork_right_rounded, size: 12, color: p.gold),
                  const SizedBox(width: 5),
                  Text(_currentBranch,
                      style: TextStyle(
                        fontSize: XlFont.captionSm,
                        fontWeight: FontWeight.w800,
                        color: p.gold,
                        letterSpacing: XlLetterSpacing.wider,
                      )),
                ],
              ),
            ),
          const SizedBox(width: 10),
          _RefreshBtn(onTap: _refresh),
        ],
      ),
    );
  }

  Widget _tabBar(XlPalette p) {
    return Container(
      decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
      padding: const EdgeInsets.all(4),
      child: TabBar(
        controller: _tabCtrl,
        indicator: BoxDecoration(
          gradient: p.btnFace,
          borderRadius: BorderRadius.circular(XlRadius.pill),
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        dividerColor: Colors.transparent,
        labelColor: p.isDark ? p.btnInk : Colors.white,
        unselectedLabelColor: p.text2,
        labelStyle: const TextStyle(
          fontSize: XlFont.captionSm,
          fontWeight: FontWeight.w800,
          letterSpacing: XlLetterSpacing.wider,
        ),
        unselectedLabelStyle: const TextStyle(
          fontSize: XlFont.captionSm,
          fontWeight: FontWeight.w600,
          letterSpacing: XlLetterSpacing.wider,
        ),
        tabs: const [
          Tab(text: '变更', height: 36),
          Tab(text: '历史', height: 36),
          Tab(text: '分支', height: 36),
        ],
      ),
    );
  }

  Widget _changesTab(XlPalette p) {
    if (_files.isEmpty) {
      return _emptyState(p, '暂无变更', '工作区干净，没有待提交的修改');
    }
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: AppTheme.sunkenHair(context, r: XlRadius.pill),
          child: Row(
            children: [
              SizedBox(
                width: 22,
                height: 22,
                child: Checkbox(
                  value: _allSelected,
                  onChanged: (_) => _toggleSelectAll(),
                  activeColor: p.pink,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ),
              const SizedBox(width: 8),
              Text('全选',
                  style: TextStyle(
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w700,
                    color: p.text2,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
              const Spacer(),
              Text('${_files.where((f) => f.selected).length}/${_files.length} 个文件',
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w700,
                    color: p.text3,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
        ),
        const SizedBox(height: 10),
        Expanded(
          child: ListView.separated(
            itemCount: _files.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (_, i) => _fileTile(p, _files[i]),
          ),
        ),
        const SizedBox(height: 10),
        _commitBar(p),
      ],
    );
  }

  Widget _fileTile(XlPalette p, _GitFile f) {
    final color = _statusColor(p, f.type);
    final expanded = _expanded.contains(f.path);
    return Container(
      decoration: AppTheme.neuXs(context, r: XlRadius.md),
      child: Column(
        children: [
          InkWell(
            onTap: () => _toggleDiff(f),
            borderRadius: BorderRadius.circular(XlRadius.md),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              child: Row(
                children: [
                  SizedBox(
                    width: 22,
                    height: 22,
                    child: Checkbox(
                      value: f.selected,
                      onChanged: (v) => setState(() => f.selected = v ?? false),
                      activeColor: p.pink,
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Icon(_statusIcon(f.type), size: 15, color: color),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(f.path,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: XlFont.captionSm,
                          fontWeight: FontWeight.w600,
                          color: p.text1,
                        )),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: color.withOpacity(p.isDark ? 0.16 : 0.12),
                      borderRadius: BorderRadius.circular(XlRadius.pill),
                      border: Border.all(color: color.withOpacity(0.32), width: 1),
                    ),
                    child: Text(_statusLabel(f.type),
                        style: TextStyle(
                          fontSize: XlFont.micro,
                          fontWeight: FontWeight.w800,
                          color: color,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                  ),
                  Icon(expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                      size: 16, color: p.decor),
                ],
              ),
            ),
          ),
          if (expanded) _diffView(p, f.path),
        ],
      ),
    );
  }

  Widget _diffView(XlPalette p, String path) {
    final diff = _diffCache[path];
    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(maxHeight: 280),
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      padding: const EdgeInsets.all(10),
      decoration: AppTheme.screen(context, r: XlRadius.sm),
      child: diff == null
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(12),
                child: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
              ),
            )
          : diff.trim().isEmpty
              ? Text('无差异内容',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: XlFont.captionSm,
                    color: p.text3,
                  ))
              : SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: diff
                          .split('\n')
                          .where((l) => l.isNotEmpty)
                          .map((l) => _diffLine(p, l))
                          .toList(),
                    ),
                  ),
                ),
    );
  }

  Widget _diffLine(XlPalette p, String line) {
    Color bg;
    Color fg;
    if (line.startsWith('+')) {
      bg = p.green.withOpacity(p.isDark ? 0.18 : 0.12);
      fg = p.green;
    } else if (line.startsWith('-')) {
      bg = p.red.withOpacity(p.isDark ? 0.18 : 0.12);
      fg = p.red;
    } else if (line.startsWith('@')) {
      bg = p.gold.withOpacity(p.isDark ? 0.18 : 0.12);
      fg = p.gold;
    } else {
      bg = Colors.transparent;
      fg = p.text2;
    }
    return Container(
      color: bg,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
      child: Text(line,
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: XlFont.captionSm,
            color: fg,
            height: 1.35,
          )),
    );
  }

  Widget _commitBar(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: AppTheme.neu(context, r: XlRadius.lg),
      child: Row(
        children: [
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
              decoration: AppTheme.sunken(context, r: XlRadius.md),
              child: TextField(
                controller: _commitMsgCtrl,
                style: TextStyle(
                  fontSize: XlFont.bodySm,
                  color: p.text1,
                  fontWeight: FontWeight.w600,
                ),
                decoration: InputDecoration(
                  border: InputBorder.none,
                  hintText: '输入提交信息…',
                  hintStyle: TextStyle(
                    color: p.text3,
                    fontSize: XlFont.bodySm,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                onSubmitted: (_) => _committing ? null : _commit(),
              ),
            ),
          ),
          const SizedBox(width: 12),
          _CommitBtn(
            onTap: _committing ? null : _commit,
            busy: _committing,
          ),
        ],
      ),
    );
  }

  Widget _historyTab(XlPalette p) {
    if (_commits.isEmpty) {
      return _emptyState(p, '暂无提交记录', '初始化仓库并完成第一次提交后将显示历史');
    }
    return ListView.separated(
      itemCount: _commits.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (_, i) => _commitTile(p, _commits[i]),
    );
  }

  Widget _commitTile(XlPalette p, _CommitEntry c) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neuXs(context, r: XlRadius.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: AppTheme.gold(context, r: XlRadius.pill),
            child: Text(c.short,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  color: p.gold,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(c.message,
                    style: TextStyle(
                      fontSize: XlFont.bodySm,
                      fontWeight: FontWeight.w700,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Icon(Icons.person_outline_rounded, size: 12, color: p.decor),
                    const SizedBox(width: 4),
                    Text(c.author,
                        style: TextStyle(
                          fontSize: XlFont.micro,
                          color: p.text3,
                          fontWeight: FontWeight.w600,
                          letterSpacing: XlLetterSpacing.wider,
                        )),
                    const SizedBox(width: 12),
                    Icon(Icons.calendar_today_rounded, size: 11, color: p.decor),
                    const SizedBox(width: 4),
                    Text(c.date,
                        style: TextStyle(
                          fontSize: XlFont.micro,
                          color: p.text3,
                          fontWeight: FontWeight.w600,
                          letterSpacing: XlLetterSpacing.wider,
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

  Widget _branchesTab(XlPalette p) {
    if (_branches.isEmpty) {
      return _emptyState(p, '暂无分支', '当前仓库还没有分支');
    }
    return ListView.separated(
      itemCount: _branches.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (_, i) => _branchTile(p, _branches[i]),
    );
  }

  Widget _branchTile(XlPalette p, _BranchEntry b) {
    return GestureDetector(
      onTap: () => _checkout(b),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: b.current ? AppTheme.accent(context, r: XlRadius.md) : AppTheme.neuXs(context, r: XlRadius.md),
        child: Row(
          children: [
            Icon(
              b.current ? Icons.fork_right_rounded : Icons.fork_right_outlined,
              size: 16,
              color: b.current ? p.pink : p.decor,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(b.name,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: XlFont.captionSm,
                    fontWeight: b.current ? FontWeight.w800 : FontWeight.w600,
                    color: b.current ? p.pink : p.text1,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
            ),
            if (b.current)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: p.pink.withOpacity(p.isDark ? 0.18 : 0.14),
                  borderRadius: BorderRadius.circular(XlRadius.pill),
                  border: Border.all(color: p.pink.withOpacity(0.4), width: 1),
                ),
                child: Text('当前',
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      fontWeight: FontWeight.w800,
                      color: p.pink,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ),
          ],
        ),
      ),
    );
  }

  Widget _emptyState(XlPalette p, String title, String sub) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: AppTheme.brandOrbLg(context, size: 72),
            child: Icon(Icons.commit_rounded, size: 30, color: p.btnInk),
          ),
          const SizedBox(height: 18),
          Text(title,
              style: TextStyle(
                fontSize: XlFont.caption,
                color: p.text2,
                fontWeight: FontWeight.w700,
                letterSpacing: XlLetterSpacing.wide,
              )),
          const SizedBox(height: 6),
          Text(sub,
              style: TextStyle(
                fontSize: XlFont.micro,
                color: p.text3,
                fontWeight: FontWeight.w500,
                letterSpacing: XlLetterSpacing.wider,
              )),
        ],
      ),
    );
  }
}

class _RefreshBtn extends StatefulWidget {
  final VoidCallback onTap;
  const _RefreshBtn({required this.onTap});
  @override
  State<_RefreshBtn> createState() => _RefreshBtnState();
}

class _RefreshBtnState extends State<_RefreshBtn> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  );
  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return GestureDetector(
      onTap: () {
        _ctrl.repeat();
        widget.onTap();
        Future.delayed(const Duration(milliseconds: 900), () {
          if (mounted) {
            _ctrl.stop();
            _ctrl.value = 0;
          }
        });
      },
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: AppTheme.ghost(context, r: XlRadius.md),
        child: RotationTransition(
          turns: _ctrl,
          child: Icon(Icons.refresh_rounded, size: 16, color: p.text1),
        ),
      ),
    );
  }
}

class _CommitBtn extends StatefulWidget {
  final VoidCallback? onTap;
  final bool busy;
  const _CommitBtn({required this.onTap, required this.busy});
  @override
  State<_CommitBtn> createState() => _CommitBtnState();
}

class _CommitBtnState extends State<_CommitBtn> {
  bool _down = false;
  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return GestureDetector(
      onTapDown: widget.onTap == null ? null : (_) => setState(() => _down = true),
      onTapUp: widget.onTap == null ? null : (_) => setState(() => _down = false),
      onTapCancel: () => setState(() => _down = false),
      onTap: widget.onTap,
      child: AnimatedScale(
        scale: _down ? 0.96 : 1.0,
        duration: XlDuration.micro,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          decoration: widget.onTap == null
              ? AppTheme.ghostPressed(context, r: XlRadius.pill)
              : AppTheme.btn(context, r: XlRadius.pill),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (widget.busy)
                SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2, color: p.btnInk),
                )
              else
                Icon(Icons.check_rounded, size: 15, color: p.btnInk),
              const SizedBox(width: 8),
              Text('提交',
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
}
