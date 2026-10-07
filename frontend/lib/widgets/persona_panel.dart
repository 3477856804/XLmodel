import 'dart:math' as math;

import 'package:flutter/material.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling.pb.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../theme/theme.dart';

/// 人格 / Agent 面板：情绪画像 + 六维雷达 + 亲密度 + 人格切换。
///
/// 此前头像按钮只是个装饰性 `Container`，连 `InkWell` 都没有。这里补齐：
/// - 上半区：**实时画像**（情绪 / 强度 / 亲密度等级 / 六维情绪雷达）
/// - 下半区：**人格选择**（5 个内置 + 任意自定义，可新增/ 删除）
class PersonaPanel extends StatefulWidget {
  const PersonaPanel({super.key, required this.onClose});

  final VoidCallback onClose;

  @override
  State<PersonaPanel> createState() => _PersonaPanelState();
}

class _PersonaPanelState extends State<PersonaPanel> {
  PersonaReply? _persona;
  List<PersonaPreset> _presets = const [];
  bool _loading = true;
  bool _busy = false;
  String? _err;

  // 自定义人格弹窗
  bool _showAdd = false;
  final _nameCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  final _hintCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    _hintCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _err = null;
    });
    try {
      final p = await XlClient.stub.safe(() => XlClient.stub.fetchPersona());
      final l = await XlClient.stub.safe(() => XlClient.stub.fetchPersonas());
      if (!mounted) return;
      setState(() {
        _persona = p;
        _presets = l?.presets ?? const [];
      });
    } catch (e) {
      if (mounted) setState(() => _err = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), duration: XlDuration.fast),
    );
  }

  Future<void> _switchTo(PersonaPreset preset) async {
    if (preset.active) return;
    setState(() => _busy = true);
    final r = await XlClient.stub.safe(
      () => XlClient.stub.switchPersona(preset.name),
    );
    if (!mounted) return;
    setState(() => _busy = false);
    _toast(r?.message.isNotEmpty == true ? r!.message : '切换失败');
    await _load();
  }

  Future<void> _submitCustom() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      _toast('请填写人格名');
      return;
    }
    setState(() => _busy = true);
    final r = await XlClient.stub.safe(() => XlClient.stub.createPersona(
          name,
          description: _descCtrl.text.trim(),
          promptHint: _hintCtrl.text.trim(),
        ));
    if (!mounted) return;
    setState(() => _busy = false);
    _toast(r?.message.isNotEmpty == true ? r!.message : '添加失败');
    if (r?.ok ?? false) {
      _nameCtrl.clear();
      _descCtrl.clear();
      _hintCtrl.clear();
      setState(() => _showAdd = false);
      await _load();
    }
  }

  Future<void> _remove(PersonaPreset preset) async {
    setState(() => _busy = true);
    final r = await XlClient.stub.safe(
      () => XlClient.stub.removePersona(preset.name),
    );
    if (!mounted) return;
    setState(() => _busy = false);
    _toast(r?.message.isNotEmpty == true ? r!.message : '删除失败');
    await _load();
  }

  Future<void> _resetAll() async {
    setState(() => _busy = true);
    final r = await XlClient.stub.safe(() => XlClient.stub.resetPersonaState());
    if (!mounted) return;
    setState(() => _busy = false);
    _toast(r?.message.isNotEmpty == true ? r!.message : '重置失败');
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Stack(
      children: [
        Positioned.fill(
          child: GestureDetector(
            onTap: widget.onClose,
            child: Container(color: p.scrim),
          ),
        ),
        Positioned.fill(
          child: GestureDetector(
            onTap: () {},
            child: Center(
              child: Container(
                width: 560,
                constraints: const BoxConstraints(maxHeight: 680),
                margin: const EdgeInsets.all(24),
                decoration: AppTheme.neuLg(context, r: XlRadius.xxl),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _header(p),
                    AppTheme.divider(context),
                    Flexible(child: _body(p)),
                    AppTheme.divider(context),
                    _footer(p),
                  ],
                ),
              ),
            ),
          ),
        ),
        if (_showAdd) _addDialog(p),
      ],
    );
  }

  Widget _header(XlPalette p) {
    final persona = _persona;
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 16, 14, 14),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              gradient: p.gradBrand,
              borderRadius: BorderRadius.circular(XlRadius.md),
            ),
            child: Center(
              child: Text('凌',
                  style: TextStyle(
                      fontSize: XlFont.h6,
                      fontWeight: FontWeight.w800,
                      color: p.btnInk)),
            ),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('人格与 Agent',
                  style: TextStyle(
                      fontSize: XlFont.h6,
                      fontWeight: FontWeight.w800,
                      color: p.text1)),
              Text(
                  '当前：${persona?.persona.isNotEmpty == true ? persona!.persona : '活泼'} · 情绪 ${persona?.emotion ?? '—'}',
                  style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
            ],
          ),
          const Spacer(),
          GestureDetector(
            onTap: widget.onClose,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: p.surfaceLo,
                borderRadius: BorderRadius.circular(XlRadius.xs),
                border: Border.all(color: p.edge, width: 1),
              ),
              child: Text('关闭',
                  style: TextStyle(
                      fontSize: XlFont.micro,
                      color: p.text3,
                      fontWeight: FontWeight.w700)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _body(XlPalette p) {
    if (_loading) {
      return const Padding(
        padding: EdgeInsets.all(40),
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    final persona = _persona;
    return ListView(
      shrinkWrap: true,
      padding: const EdgeInsets.all(16),
      children: [
        _profileCard(p, persona),
        const SizedBox(height: 16),
        _presetCard(p),
        if (_err != null) ...[
          const SizedBox(height: 10),
          Text(_err!,
              style: TextStyle(fontSize: XlFont.captionSm, color: p.red)),
        ],
      ],
    );
  }

  // ---------------- 画像区----------------
  Widget _profileCard(XlPalette p, PersonaReply? persona) {
    if (persona == null) {
      return _card(
        p,
        child: Center(
          child: Text('暂无画像数据',
              style: TextStyle(fontSize: XlFont.caption, color: p.text3)),
        ),
      );
    }
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 190,
          height: 190,
          child: CustomPaint(
            painter: _RadarPainter(
              axes: persona.axes
          .map((a) => (a.label, a.value.clamp(0.0, 100.0).toDouble()))
          .toList(),
              color: p.pink,
              gridColor: p.edge,
              labelColor: p.text3,
              fillColor: p.pink.withOpacity(0.18),
            ),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _statRow(p, '情绪', persona.emotion, p.pink),
              const SizedBox(height: 8),
              _statRow(p, '亲密度', persona.relationship, p.violet),
              const SizedBox(height: 8),
              _statRow(p, '称呼你', persona.userName.isEmpty ? '你' : persona.userName, p.gold),
              const SizedBox(height: 12),
              Text('情绪强度',
                  style: TextStyle(fontSize: XlFont.micro, color: p.text3)),
              const SizedBox(height: 5),
              _bar(p, persona.emotionIntensity * 100, p.pink),
              const SizedBox(height: 12),
              Text('亲密度进度（距下一级）',
                  style: TextStyle(fontSize: XlFont.micro, color: p.text3)),
              const SizedBox(height: 5),
              _bar(p, persona.relationshipProgress * 100, p.violet),
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(Icons.favorite_rounded, size: 13, color: p.pink),
                  const SizedBox(width: 4),
                  Text('累计互动 ${persona.relationshipScore.toStringAsFixed(1)}',
                      style: TextStyle(fontSize: XlFont.micro, color: p.text2)),
                  const Spacer(),
                  Icon(Icons.alarm_on_rounded, size: 13, color: p.gold),
                  const SizedBox(width: 4),
                  Text('${persona.remindersPending} 条提醒',
                      style: TextStyle(fontSize: XlFont.micro, color: p.text2)),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _statRow(XlPalette p, String label, String value, Color dot) {
    return Row(
      children: [
        Container(
          width: 7,
          height: 7,
          margin: const EdgeInsets.only(right: 8),
          decoration: BoxDecoration(color: dot, shape: BoxShape.circle),
        ),
        Text(label,
            style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
        const Spacer(),
        Flexible(
          child: Text(value,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  fontSize: XlFont.bodySm,
                  color: p.text1,
                  fontWeight: FontWeight.w700)),
        ),
      ],
    );
  }

  // ---------------- 人格选择区 ----------------
  Widget _presetCard(XlPalette p) {
    final builtin = _presets.where((e) => e.builtin).toList();
    final custom = _presets.where((e) => !e.builtin).toList();
    return _card(
      p,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.psychology_alt_rounded, size: 17, color: p.violet),
              const SizedBox(width: 8),
              Text('人格预设',
                  style: TextStyle(
                      fontSize: XlFont.bodySm,
                      fontWeight: FontWeight.w800,
                      color: p.text1)),
              const Spacer(),
              GestureDetector(
                onTap: _busy ? null : () => setState(() => _showAdd = true),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    gradient: p.gradBrand,
                    borderRadius: BorderRadius.circular(XlRadius.xs),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.add_rounded, size: 13, color: p.btnInk),
                      const SizedBox(width: 3),
                      Text('自定义',
                          style: TextStyle(
                              fontSize: XlFont.micro,
                              color: p.btnInk,
                              fontWeight: FontWeight.w800)),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: builtin.map((e) => _presetChip(p, e)).toList(),
          ),
          if (custom.isNotEmpty) ...[
            const SizedBox(height: 14),
            Row(
              children: [
                Text('自定义人格',
                    style: TextStyle(fontSize: XlFont.micro, color: p.text3)),
                const SizedBox(width: 8),
                Container(height: 1, color: p.edgeSoft),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: custom.map((e) => _presetChip(p, e, deletable: true)).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _presetChip(XlPalette p, PersonaPreset preset, {bool deletable = false}) {
    final active = preset.active;
    return GestureDetector(
      onTap: _busy ? null : () => _switchTo(preset),
      onLongPress: deletable && !active ? () => _remove(preset) : null,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          gradient: active ? p.gradBrand : null,
          color: active ? null : p.surfaceLo,
          borderRadius: BorderRadius.circular(XlRadius.md),
          border: Border.all(
            color: active ? Colors.transparent : p.edge,
            width: 1,
          ),
          boxShadow: active
              ? [BoxShadow(color: p.pink.withOpacity(0.3), blurRadius: 10, spreadRadius: -2)]
              : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (active) ...[
              Icon(Icons.check_rounded, size: 13, color: p.btnInk),
              const SizedBox(width: 4),
            ],
            Text(preset.name,
                style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w700,
                    color: active ? p.btnInk : p.text1)),
            if (deletable && !active) ...[
              const SizedBox(width: 5),
              GestureDetector(
                onTap: _busy ? null : () => _remove(preset),
                child: Icon(Icons.close_rounded,
                    size: 13, color: p.text3.withOpacity(0.7)),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _footer(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 14, 12),
      child: Row(
        children: [
          Text('切换后立即对下一轮对话生效',
              style: TextStyle(fontSize: XlFont.micro, color: p.text3)),
          const Spacer(),
          GestureDetector(
            onTap: _busy ? null : _resetAll,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
              decoration: BoxDecoration(
                color: p.surfaceLo,
                borderRadius: BorderRadius.circular(XlRadius.xs),
                border: Border.all(color: p.red.withOpacity(0.5), width: 1),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.restart_alt_rounded, size: 14, color: p.red),
                  const SizedBox(width: 5),
                  Text('重置画像',
                      style: TextStyle(
                          fontSize: XlFont.captionSm,
                          color: p.red,
                          fontWeight: FontWeight.w700)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------- 自定义人格弹窗 ----------------
  Widget _addDialog(XlPalette p) {
    return Positioned.fill(
      child: GestureDetector(
        onTap: _busy ? null : () => setState(() => _showAdd = false),
        child: Container(
          color: p.scrim,
          child: Center(
            child: GestureDetector(
              onTap: () {},
              child: Container(
                width: 420,
                margin: const EdgeInsets.all(24),
                padding: const EdgeInsets.all(20),
                decoration: AppTheme.neuLg(context, r: XlRadius.xxl),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('新增自定义人格',
                        style: TextStyle(
                            fontSize: XlFont.h6,
                            fontWeight: FontWeight.w800,
                            color: p.text1)),
                    const SizedBox(height: 4),
                    Text('自定义人格会写入 .star_core/persona_custom.json',
                        style: TextStyle(fontSize: XlFont.micro, color: p.text3)),
                    const SizedBox(height: 16),
                    _field(p, _nameCtrl, '人格名（必填，最多 12 字）', autofocus: true),
                    const SizedBox(height: 10),
                    _field(p, _descCtrl, '一句话描述（选填）'),
                    const SizedBox(height: 10),
                    _field(p, _hintCtrl, '语气引导（选填，会注入系统提示词）',
                        maxLines: 3),
                    const SizedBox(height: 18),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        GestureDetector(
                          onTap: _busy ? null : () => setState(() => _showAdd = false),
                          child: Padding(
                            padding: const EdgeInsets.all(10),
                            child: Text('取消',
                                style: TextStyle(
                                    fontSize: XlFont.bodySm, color: p.text3)),
                          ),
                        ),
                        const SizedBox(width: 8),
                        GestureDetector(
                          onTap: _busy ? null : _submitCustom,
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 20, vertical: 10),
                            decoration: BoxDecoration(
                              gradient: p.gradBrand,
                              borderRadius: BorderRadius.circular(XlRadius.md),
                            ),
                            child: Text('创建',
                                style: TextStyle(
                                    fontSize: XlFont.bodySm,
                                    color: p.btnInk,
                                    fontWeight: FontWeight.w800)),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _field(XlPalette p, TextEditingController ctrl, String hint,
      {int maxLines = 1, bool autofocus = false}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.md),
        border: Border.all(color: p.edge, width: 1),
      ),
      child: TextField(
        controller: ctrl,
        maxLines: maxLines,
        autofocus: autofocus,
        style: TextStyle(fontSize: XlFont.bodySm, color: p.text1),
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: TextStyle(fontSize: XlFont.captionSm, color: p.decor),
          border: InputBorder.none,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(vertical: 11),
        ),
      ),
    );
  }

  Widget _card(XlPalette p, {required Widget child}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.lg),
        border: Border.all(color: p.edgeSoft, width: 1),
      ),
      child: child,
    );
  }

  Widget _bar(XlPalette p, double pct, Color color) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(XlRadius.sm),
      child: Container(
        height: 6,
        color: p.surfaceHi,
        child: FractionallySizedBox(
          widthFactor: (pct / 100).clamp(0.0, 1.0),
          child: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                  colors: [color.withOpacity(0.7), color]),
            ),
          ),
        ),
      ),
    );
  }
}

/// 六维情绪雷达图（纯 Canvas 绘制，无外部依赖）。
class _RadarPainter extends CustomPainter {
  _RadarPainter({
    required this.axes,
    required this.color,
    required this.gridColor,
    required this.labelColor,
    required this.fillColor,
  });

  final List<(String, double)> axes;
  final Color color;
  final Color gridColor;
  final Color labelColor;
  final Color fillColor;

  @override
  void paint(Canvas canvas, Size size) {
    if (axes.length < 3) return;
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 22;

    // 网格：3 圈同心六边形
    final grid = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = gridColor;
    for (final f in [0.33, 0.66, 1.0]) {
      final path = _poly(center, radius * f);
      canvas.drawPath(path, grid);
    }
    // 轴线
    for (var i = 0; i < axes.length; i++) {
      final a = _angle(i);
      canvas.drawLine(
          center, center + Offset(math.cos(a), math.sin(a)) * radius, grid);
    }

    // 数据多边形
    final data = Path();
    for (var i = 0; i < axes.length; i++) {
      final a = _angle(i);
      final v = (axes[i].$2 / 100).clamp(0.0, 1.0);
      final pt = center + Offset(math.cos(a), math.sin(a)) * radius * v;
      i == 0 ? data.moveTo(pt.dx, pt.dy) : data.lineTo(pt.dx, pt.dy);
    }
    data.close();
    canvas.drawPath(data, Paint()..color = fillColor);
    canvas.drawPath(
      data,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..color = color,
    );

    // 顶点+ 标签
    for (var i = 0; i < axes.length; i++) {
      final a = _angle(i);
      final v = (axes[i].$2 / 100).clamp(0.0, 1.0);
      final pt = center + Offset(math.cos(a), math.sin(a)) * radius * v;
      canvas.drawCircle(pt, 3, Paint()..color = color);

      final lp = center + Offset(math.cos(a), math.sin(a)) * (radius + 13);
      final tp = TextPainter(
        text: TextSpan(
          text: axes[i].$1,
          style: TextStyle(
              fontSize: 9, color: labelColor, fontWeight: FontWeight.w700),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, lp - Offset(tp.width / 2, tp.height / 2));
    }
  }

  Path _poly(Offset c, double r) {
    final path = Path();
    for (var i = 0; i < axes.length; i++) {
      final a = _angle(i);
      final pt = c + Offset(math.cos(a), math.sin(a)) * r;
      i == 0 ? path.moveTo(pt.dx, pt.dy) : path.lineTo(pt.dx, pt.dy);
    }
    return path..close();
  }

  /// 从正上方 (-90°) 开始，顺时针均分。
  double _angle(int i) => -math.pi / 2 + (2 * math.pi * i / axes.length);

  @override
  bool shouldRepaint(_RadarPainter old) =>
      old.axes != axes || old.color != color;
}