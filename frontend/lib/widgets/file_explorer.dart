import 'package:flutter/material.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling.pb.dart' as pb;
import '../rpc/xiaoling_ext.dart';
import '../theme/theme.dart';

class FileExplorer extends StatefulWidget {
  final void Function(pb.FileItem item)? onFileTap;
  final String initialPath;
  const FileExplorer({super.key, this.onFileTap, this.initialPath = '/'});
  @override
  State<FileExplorer> createState() => _FileExplorerState();
}

class _FileExplorerState extends State<FileExplorer> {
  String _currentPath = '/';
  String _parentPath = '';
  List<pb.FileItem> _items = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _currentPath = widget.initialPath;
    _load(_currentPath);
  }

  Future<void> _load(String path) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final reply = await XlClient.fastCall(
        (s) => s.fileList(pb.FileListRequest(path: path)),
        label: 'fileList',
      );
      if (!mounted) return;
      setState(() {
        _currentPath = reply.currentPath.isEmpty ? path : reply.currentPath;
        _parentPath = reply.parentPath;
        _items = List.of(reply.items);
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  IconData _iconFor(pb.FileItem item) {
    if (item.isDir) return Icons.folder_rounded;
    final ext = item.extension_6.toLowerCase();
    switch (ext) {
      case 'py':
        return Icons.code_rounded;
      case 'dart':
        return Icons.code_rounded;
      case 'md':
        return Icons.description_rounded;
      case 'json':
        return Icons.data_object_rounded;
      case 'yaml':
      case 'yml':
        return Icons.settings_rounded;
      case 'txt':
        return Icons.notes_rounded;
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'webp':
        return Icons.image_rounded;
      default:
        return Icons.insert_drive_file_rounded;
    }
  }

  Color _iconColor(XlPalette p, pb.FileItem item) {
    if (item.isDir) return p.gold;
    final ext = item.extension_6.toLowerCase();
    if (ext == 'py' || ext == 'dart') return p.pink;
    if (ext == 'json' || ext == 'yaml' || ext == 'yml') return p.violet;
    if (ext == 'md') return p.blue;
    return p.text3;
  }

  List<String> _pathSegments(String path) {
    if (path.isEmpty || path == '/') return ['/'];
    final parts = path.split('/').where((s) => s.isNotEmpty).toList();
    return ['/', ...parts];
  }

  String _joinSegments(List<String> segs, int upto) {
    if (upto == 0) return '/';
    final picked = segs.sublist(1, upto + 1);
    return '/${picked.join('/')}';
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Container(
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _pathBar(p),
          const SizedBox(height: 12),
          Expanded(child: _listArea(p)),
        ],
      ),
    );
  }

  Widget _pathBar(XlPalette p) {
    final segs = _pathSegments(_currentPath);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
      child: Row(
        children: [
          _barIconBtn(p, Icons.arrow_upward_rounded, '上级',
              _parentPath.isEmpty ? null : () => _load(_parentPath)),
          const SizedBox(width: 6),
          _barIconBtn(p, Icons.refresh_rounded, '刷新',
              _loading ? null : () => _load(_currentPath)),
          const SizedBox(width: 8),
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (int i = 0; i < segs.length; i++) ...[
                    if (i > 0)
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 4),
                        child: Text('/',
                            style: TextStyle(
                              fontSize: XlFont.captionSm,
                              color: p.text4,
                            )),
                      ),
                    _Pressable(
                      onTap: () => _load(_joinSegments(segs, i)),
                      scale: 0.95,
                      child: Text(
                        segs[i] == '/' ? 'root' : segs[i],
                        style: TextStyle(
                          fontSize: XlFont.captionSm,
                          fontWeight: i == segs.length - 1 ? w700 : w600,
                          color: i == segs.length - 1 ? p.gold : p.text2,
                          letterSpacing: XlLetterSpacing.wide,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  static const w700 = FontWeight.w700;
  static const w600 = FontWeight.w600;

  Widget _barIconBtn(XlPalette p, IconData icon, String tip, VoidCallback? onTap) {
    return Tooltip(
      message: tip,
      child: _Pressable(
        onTap: onTap,
        scale: 0.9,
        child: Container(
          width: 28,
          height: 28,
          alignment: Alignment.center,
          decoration: AppTheme.neuXxs(context, r: XlRadius.xs),
          child: Icon(icon, size: 14, color: onTap == null ? p.text4 : p.pink),
        ),
      ),
    );
  }

  Widget _listArea(XlPalette p) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded, size: 28, color: p.red),
            const SizedBox(height: 10),
            Text('加载失败',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w700,
                  color: p.text1,
                )),
            const SizedBox(height: 6),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Text(_error!,
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: XlFont.micro, color: p.text3)),
            ),
          ],
        ),
      );
    }
    if (_items.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.folder_open_rounded, size: 36, color: p.decor),
            const SizedBox(height: 10),
            Text('空目录',
                style: TextStyle(
                  fontSize: XlFont.caption,
                  fontWeight: FontWeight.w700,
                  color: p.text2,
                )),
          ],
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.symmetric(vertical: 4),
      itemCount: _items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 4),
      itemBuilder: (_, i) => _row(p, _items[i]),
    );
  }

  Widget _row(XlPalette p, pb.FileItem item) {
    return _Pressable(
      onTap: () {
        if (item.isDir) {
          _load(item.path);
        } else {
          widget.onFileTap?.call(item);
        }
      },
      scale: 0.98,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: AppTheme.neuXs(context, r: XlRadius.sm),
        child: Row(
          children: [
            Icon(_iconFor(item), size: 16, color: _iconColor(p, item)),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                item.name,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w600,
                  color: item.isDir ? p.text1 : p.text2,
                  letterSpacing: XlLetterSpacing.wide,
                ),
              ),
            ),
            if (!item.isDir)
              Text(
                formatBytes(item.size.toInt()),
                style: TextStyle(
                  fontSize: XlFont.micro,
                  color: p.text4,
                  fontWeight: FontWeight.w600,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
          ],
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
  bool _hover = false;
  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTapDown: widget.onTap == null ? null : (_) => setState(() => _down = true),
        onTapUp: widget.onTap == null ? null : (_) => setState(() => _down = false),
        onTapCancel: () {
          if (mounted) setState(() => _down = false);
        },
        onTap: widget.onTap,
        child: AnimatedScale(
          scale: _down ? widget.scale : 1.0,
          duration: XlDuration.micro,
          curve: XlCurve.standard,
          child: AnimatedContainer(
            duration: XlDuration.fast,
            curve: XlCurve.standard,
            decoration: _hover && widget.onTap != null
                ? BoxDecoration(
                    borderRadius: BorderRadius.circular(XlRadius.sm),
                    color: p.pink.withOpacity(p.isDark ? 0.10 : 0.06),
                  )
                : null,
            child: widget.child,
          ),
        ),
      ),
    );
  }
}
