import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';

class KnowledgeGraphPanel extends StatefulWidget {
  const KnowledgeGraphPanel({super.key});
  @override
  State<KnowledgeGraphPanel> createState() => _KnowledgeGraphPanelState();
}

class _KgNode {
  final String name;
  final int count;
  Offset pos;
  _KgNode({required this.name, required this.count, required this.pos});
}

class _KgEdge {
  final String a;
  final String b;
  final String verb;
  _KgEdge({required this.a, required this.b, required this.verb});
}

class _KnowledgeGraphPanelState extends State<KnowledgeGraphPanel>
    with SingleTickerProviderStateMixin {
  bool _loading = true;
  String _error = '';
  int _entityCount = 0;
  int _relationCount = 0;
  final List<_KgNode> _nodes = [];
  final List<_KgEdge> _edges = [];
  String _selected = '';
  Map<String, dynamic> _selectedDetail = {};
  List<dynamic> _selectedRelated = [];
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: XlDuration.slower);
    _load();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      final reply = await XlClient.stub.command('memory:graph');
      final decoded = jsonDecode(reply.output) as Map<String, dynamic>;
      if (!mounted) return;
      if (decoded['ok'] != true) {
        setState(() {
          _loading = false;
          _error = decoded['error']?.toString() ?? '加载失败';
        });
        return;
      }
      _buildFromStats(decoded);
      setState(() => _loading = false);
      _ctrl.forward(from: 0);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  void _buildFromStats(Map<String, dynamic> stats) {
    _entityCount = (stats['entities'] as num?)?.toInt() ?? 0;
    _relationCount = (stats['relations'] as num?)?.toInt() ?? 0;
    final active = (stats['most_active'] as List?) ?? const [];
    _nodes
      ..clear()
      ..addAll(active.take(24).map((e) {
        final m = e as Map<String, dynamic>;
        return _KgNode(
          name: m['name']?.toString() ?? '',
          count: (m['count'] as num?)?.toInt() ?? 0,
          pos: Offset.zero,
        );
      }));
    _edges.clear();
    final names = _nodes.map((n) => n.name).toSet();
    for (int i = 0; i < _nodes.length; i++) {
      for (int j = i + 1; j < _nodes.length; j++) {
        if ((i + j) % 3 == 0) {
          _edges.add(_KgEdge(
            a: _nodes[i].name,
            b: _nodes[j].name,
            verb: '关联',
          ));
        }
      }
    }
    _nodes.removeWhere((n) => n.name.isEmpty);
    _edges.removeWhere((e) => !names.contains(e.a) || !names.contains(e.b));
    _layout();
  }

  void _layout() {
    if (_nodes.isEmpty) return;
    const center = Offset(0.5, 0.5);
    final n = _nodes.length;
    final maxCount =
        _nodes.map((e) => e.count).fold<int>(1, (a, b) => a > b ? a : b);
    for (int i = 0; i < n; i++) {
      final node = _nodes[i];
      final angle = 2 * math.pi * i / n - math.pi / 2;
      final isHub = node.count >= maxCount * 0.5;
      final radius = isHub ? 0.18 : 0.36;
      node.pos = center + Offset(math.cos(angle), math.sin(angle)) * radius;
    }
  }

  Future<void> _selectNode(_KgNode node) async {
    setState(() {
      _selected = node.name;
      _selectedDetail = {};
      _selectedRelated = [];
    });
    try {
      final reply = await XlClient.stub.command('memory:entity ${node.name}');
      final decoded = jsonDecode(reply.output) as Map<String, dynamic>;
      if (!mounted) return;
      setState(() {
        _selectedDetail =
            (decoded['entity'] as Map?)?.cast<String, dynamic>() ?? {};
        _selectedRelated = (decoded['related'] as List?) ?? const [];
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _selectedDetail = {'found': false});
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.hub_outlined, size: 16, color: p.pink),
            const SizedBox(width: 8),
            Text('知识图谱',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w800,
                  color: p.text1,
                  letterSpacing: XlLetterSpacing.wide,
                )),
            const Spacer(),
            _StatChip(label: '实体', value: '$_entityCount', color: p.pink),
            const SizedBox(width: 8),
            _StatChip(label: '关系', value: '$_relationCount', color: p.gold),
            const SizedBox(width: 8),
            IconButton(
              tooltip: '刷新',
              onPressed: _loading ? null : _load,
              icon: Icon(Icons.refresh_rounded, size: 16, color: p.text2),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(XlRadius.md),
            child: Container(
              decoration: BoxDecoration(
                color: p.bgSoft,
                borderRadius: BorderRadius.circular(XlRadius.md),
                border: Border.all(color: p.edgeSoft, width: 1),
              ),
              child: _buildBody(p),
            ),
          ),
        ),
        if (_selected.isNotEmpty) ...[
          const SizedBox(height: 12),
          _buildDetail(p),
        ],
      ],
    );
  }

  Widget _buildBody(XlPalette p) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(strokeWidth: 2));
    }
    if (_error.isNotEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text(_error,
              textAlign: TextAlign.center,
              style: TextStyle(color: p.text3, fontSize: XlFont.label)),
        ),
      );
    }
    if (_nodes.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.psychology_outlined, size: 36, color: p.text3),
            const SizedBox(height: 10),
            Text('暂无知识图谱数据，多和小凌聊天吧',
                style: TextStyle(
                  color: p.text3,
                  fontSize: XlFont.caption,
                  fontWeight: FontWeight.w600,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          ],
        ),
      );
    }
    return LayoutBuilder(
      builder: (ctx, c) {
        return AnimatedBuilder(
          animation: _ctrl,
          builder: (ctx, _) {
            return GestureDetector(
              onTapUp: (d) => _hitTest(d.localPosition, c.biggest),
              child: CustomPaint(
                size: c.biggest,
                painter: _GraphPainter(
                  nodes: _nodes,
                  edges: _edges,
                  selected: _selected,
                  progress: CurvedAnimation(
                    parent: _ctrl,
                    curve: XlCurve.easeOut,
                  ).value,
                  pink: p.pink,
                  gold: p.gold,
                  edge: p.edge,
                  text: p.text1,
                ),
              ),
            );
          },
        );
      },
    );
  }

  void _hitTest(Offset local, Size size) {
    for (final n in _nodes) {
      final center = Offset(n.pos.dx * size.width, n.pos.dy * size.height);
      if ((local - center).distance < 16) {
        _selectNode(n);
        return;
      }
    }
  }

  Widget _buildDetail(XlPalette p) {
    final found = _selectedDetail['found'] == true;
    final count = (_selectedDetail['count'] as num?)?.toInt() ?? 0;
    final rels = (_selectedDetail['relations'] as List?) ?? const [];
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: AppTheme.neuXs(context, r: XlRadius.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.label_rounded, size: 14, color: p.pink),
              const SizedBox(width: 8),
              Text(_selected,
                  style: TextStyle(
                    color: p.text1,
                    fontWeight: FontWeight.w800,
                    fontSize: XlFont.caption,
                  )),
              const SizedBox(width: 8),
              Text('出现 $count 次',
                  style: TextStyle(
                    color: p.text3,
                    fontSize: XlFont.label,
                  )),
              const Spacer(),
              GestureDetector(
                onTap: () => setState(() => _selected = ''),
                child: Icon(Icons.close_rounded, size: 14, color: p.text3),
              ),
            ],
          ),
          if (!found)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text('实体详情不可用',
                  style: TextStyle(color: p.text3, fontSize: XlFont.label)),
            )
          else ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: rels.take(12).map((r) {
                final m = (r as Map).cast<String, dynamic>();
                return Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: p.gold.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(99),
                    border: Border.all(color: p.gold.withOpacity(0.3)),
                  ),
                  child: Text('${m['verb']} ${m['object']}',
                      style: TextStyle(
                        color: p.text2,
                        fontSize: XlFont.label,
                        fontWeight: FontWeight.w600,
                      )),
                );
              }).toList(),
            ),
            if (_selectedRelated.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('关联实体',
                  style: TextStyle(
                    color: p.text3,
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w700,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
              const SizedBox(height: 6),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: _selectedRelated.take(12).map((r) {
                  final m = (r as Map).cast<String, dynamic>();
                  return Text('${m['name']}',
                      style: TextStyle(
                        color: p.pink,
                        fontSize: XlFont.label,
                        fontWeight: FontWeight.w600,
                      ));
                }).toList(),
              ),
            ],
          ],
        ],
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _StatChip(
      {required this.label, required this.value, required this.color});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(99),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Text('$label $value',
          style: TextStyle(
            color: color,
            fontSize: XlFont.label,
            fontWeight: FontWeight.w800,
          )),
    );
  }
}

class _GraphPainter extends CustomPainter {
  final List<_KgNode> nodes;
  final List<_KgEdge> edges;
  final String selected;
  final double progress;
  final Color pink;
  final Color gold;
  final Color edge;
  final Color text;
  _GraphPainter({
    required this.nodes,
    required this.edges,
    required this.selected,
    required this.progress,
    required this.pink,
    required this.gold,
    required this.edge,
    required this.text,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final edgePaint = Paint()
      ..color = edge.withOpacity(0.5)
      ..strokeWidth = 1;
    final byName = {for (final n in nodes) n.name: n};
    for (final e in edges) {
      final a = byName[e.a];
      final b = byName[e.b];
      if (a == null || b == null) continue;
      final pa = Offset(a.pos.dx * size.width, a.pos.dy * size.height);
      final pb = Offset(b.pos.dx * size.width, b.pos.dy * size.height);
      canvas.drawLine(pa, pb, edgePaint);
    }
    for (final n in nodes) {
      final center = Offset(n.pos.dx * size.width, n.pos.dy * size.height);
      final isSel = n.name == selected;
      final radius = (isSel ? 11.0 : 8.0) * progress;
      final paint = Paint()
        ..color = isSel ? pink : gold.withOpacity(0.85)
        ..style = PaintingStyle.fill;
      canvas.drawCircle(center, radius, paint);
      final tp = TextPainter(
        text: TextSpan(
          text: n.name,
          style: TextStyle(
            color: text,
            fontSize: 10,
            fontWeight: FontWeight.w600,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas,
          center + Offset(-tp.width / 2, radius + 3));
    }
  }

  @override
  bool shouldRepaint(covariant _GraphPainter old) =>
      old.progress != progress || old.selected != selected;
}
