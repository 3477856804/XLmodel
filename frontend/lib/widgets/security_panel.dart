import 'dart:convert';
import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';

class SecurityPanel extends StatefulWidget {
  const SecurityPanel({super.key});
  @override
  State<SecurityPanel> createState() => _SecurityPanelState();
}

class _ToolPerm {
  final String name;
  final String desc;
  bool allowed;
  bool needApproval;
  _ToolPerm({
    required this.name,
    required this.desc,
    required this.allowed,
    this.needApproval = false,
  });
}

class _AuditEntry {
  final String time;
  final String action;
  final String detail;
  final String risk;
  _AuditEntry({
    required this.time,
    required this.action,
    required this.detail,
    required this.risk,
  });
}

class _SecurityPanelState extends State<SecurityPanel> {
  bool _loading = true;

  late final List<_ToolPerm> _tools = [
    _ToolPerm(name: 'file_read', desc: '读取本地文件内容', allowed: false),
    _ToolPerm(name: 'file_write', desc: '修改或创建本地文件', allowed: false),
    _ToolPerm(name: 'terminal', desc: '在终端执行 Shell 命令', allowed: false),
    _ToolPerm(name: 'network', desc: '发起外部网络请求', allowed: false),
    _ToolPerm(name: 'browser', desc: '自动操作浏览器页面', allowed: false),
    _ToolPerm(name: 'git', desc: '提交、推送与拉取代码', allowed: false),
    _ToolPerm(name: 'mcp', desc: '调用外部 MCP 服务器工具', allowed: false),
  ];

  final List<String> _protectedDirs = [];
  final _dirCtrl = TextEditingController();
  final List<String> _requireApproval = [];

  final List<_AuditEntry> _audit = [];

  Color _riskColor(XlPalette p, String risk) {
    switch (risk) {
      case 'high':
        return p.red;
      case 'medium':
        return p.gold;
      default:
        return p.green;
    }
  }

  String _riskLabel(String risk) {
    switch (risk) {
      case 'high':
        return '高';
      case 'medium':
        return '中';
      default:
        return '低';
    }
  }

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    try {
      final reply = await XlClient.stub.command('security:config');
      final decoded = jsonDecode(reply.output);
      if (!mounted) return;
      setState(() {
        final perms = decoded['permissions'];
        if (perms is Map) {
          for (final t in _tools) {
            if (perms.containsKey(t.name)) t.allowed = perms[t.name] == true;
          }
        }
        final approval = decoded['require_approval'];
        if (approval is List) {
          _requireApproval
            ..clear()
            ..addAll(approval.map((e) => e.toString()));
          for (final t in _tools) {
            t.needApproval = _requireApproval.contains(t.name);
          }
        }
        final dirs = decoded['protected_dirs'];
        if (dirs is List) {
          _protectedDirs
            ..clear()
            ..addAll(dirs.map((e) => e.toString()));
        }
        final audit = decoded['audit_log'];
        if (audit is List) {
          _audit
            ..clear()
            ..addAll(audit.map((a) {
              final m = (a is Map) ? a : <String, dynamic>{};
              final rawTime = m['time'];
              String timeLabel = '—';
              if (rawTime is num) {
                final dt = DateTime.fromMillisecondsSinceEpoch(
                    (rawTime * 1000).round());
                timeLabel =
                    '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}:${dt.second.toString().padLeft(2, '0')}';
              } else if (rawTime != null) {
                timeLabel = rawTime.toString();
              }
              return _AuditEntry(
                time: timeLabel,
                action: (m['action'] ?? '').toString(),
                detail: (m['detail'] ?? '').toString(),
                risk: (m['risk'] ?? 'low').toString(),
              );
            }));
        }
        _loading = false;
      });
    } catch (e) {
      debugPrint('操作失败: $e');
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _dirCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return DefaultTabController(
      length: 3,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: p.pink.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(XlRadius.md),
                  border: Border.all(color: p.pink.withOpacity(0.30), width: 1),
                ),
                child: Icon(Icons.shield_outlined, size: 18, color: p.pink),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text('安全中心',
                    style: TextStyle(
                      fontSize: XlFont.h6,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
              ),
              IconButton(
                onPressed: () => Navigator.of(context).pop(),
                icon: Icon(Icons.close_rounded, size: 18, color: p.text3),
                splashRadius: 16,
              ),
            ],
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(4),
            decoration: AppTheme.sunkenXs(context, r: XlRadius.pill),
            child: TabBar(
              labelColor: p.pink,
              unselectedLabelColor: p.text3,
              labelStyle: const TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, letterSpacing: XlLetterSpacing.wide),
              unselectedLabelStyle: const TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w600, letterSpacing: XlLetterSpacing.wide),
              indicator: BoxDecoration(
                color: p.pink.withOpacity(0.12),
                borderRadius: BorderRadius.circular(XlRadius.pill),
              ),
              indicatorPadding: const EdgeInsets.all(3),
              indicatorSize: TabBarIndicatorSize.tab,
              dividerColor: Colors.transparent,
              tabs: const [
                Tab(text: '权限'),
                Tab(text: '保护'),
                Tab(text: '审计'),
              ],
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            height: 380,
            child: _loading
                ? Center(child: CircularProgressIndicator(strokeWidth: 2, color: p.pink))
                : TabBarView(
                    children: [
                      _permissionsTab(p),
                      _protectTab(p),
                      _auditTab(p),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _permissionsTab(XlPalette p) {
    return ListView(
      padding: const EdgeInsets.only(bottom: 8),
      children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: AppTheme.neuXs(context, r: XlRadius.lg),
          child: Row(
            children: [
              Icon(Icons.gpp_good_outlined, size: 18, color: p.gold),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('执行前需审批的工具',
                        style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.wide)),
                    const SizedBox(height: 6),
                    _requireApproval.isEmpty
                        ? Text('当前无需审批的工具',
                            style: TextStyle(fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w500, letterSpacing: XlLetterSpacing.wide))
                        : Wrap(
                            spacing: 6,
                            runSpacing: 6,
                            children: _requireApproval
                                .map((t) => Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: p.gold.withOpacity(0.14),
                                        borderRadius: BorderRadius.circular(XlRadius.pill),
                                        border: Border.all(color: p.gold.withOpacity(0.35), width: 1),
                                      ),
                                      child: Text(t,
                                          style: TextStyle(fontSize: XlFont.micro, fontWeight: FontWeight.w800, color: p.gold, letterSpacing: XlLetterSpacing.wider)),
                                    ))
                                .toList(),
                          ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        ..._tools.map((t) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: AppTheme.neuXs(context, r: XlRadius.lg),
                child: Row(
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: t.allowed ? p.pink.withOpacity(0.12) : p.surfaceLo,
                        borderRadius: BorderRadius.circular(XlRadius.md),
                        border: Border.all(color: t.allowed ? p.pink.withOpacity(0.30) : p.edgeSoft, width: 1),
                      ),
                      child: Icon(_toolIcon(t.name), size: 17, color: t.allowed ? p.pink : p.text3),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(t.name,
                                  style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.wide)),
                              if (t.needApproval) ...[
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: p.gold.withOpacity(0.16),
                                    borderRadius: BorderRadius.circular(XlRadius.pill),
                                    border: Border.all(color: p.gold.withOpacity(0.40), width: 1),
                                  ),
                                  child: Text('需审批',
                                      style: TextStyle(fontSize: XlFont.micro, fontWeight: FontWeight.w800, color: p.gold, letterSpacing: XlLetterSpacing.wider)),
                                ),
                              ],
                            ],
                          ),
                          const SizedBox(height: 3),
                          Text(t.desc,
                              style: TextStyle(fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w500, letterSpacing: XlLetterSpacing.wide)),
                        ],
                      ),
                    ),
                    _miniSwitch(p, t.allowed, t.needApproval ? p.gold : p.pink,
                        () async {
                      final next = !t.allowed;
                      setState(() => t.allowed = next);
                      await XlClient.stub.safe(() =>
                          XlClient.stub.command('security:set ${t.name} $next'));
                    }),
                  ],
                ),
              ),
            )),
      ],
    );
  }

  IconData _toolIcon(String name) {
    switch (name) {
      case 'file_read':
        return Icons.menu_book_outlined;
      case 'file_write':
        return Icons.edit_note_outlined;
      case 'terminal':
        return Icons.terminal_rounded;
      case 'network':
        return Icons.language_rounded;
      case 'browser':
        return Icons.travel_explore_rounded;
      case 'git':
        return Icons.merge_rounded;
      default:
        return Icons.extension_outlined;
    }
  }

  Widget _protectTab(XlPalette p) {
    return ListView(
      padding: const EdgeInsets.only(bottom: 8),
      children: [
        Text('受保护目录',
            style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.text2, letterSpacing: XlLetterSpacing.wide)),
        const SizedBox(height: 10),
        if (_protectedDirs.isEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text('暂无受保护目录',
                style: TextStyle(fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w600, letterSpacing: XlLetterSpacing.wide)),
          ),
        ..._protectedDirs.map((d) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                decoration: AppTheme.neuXs(context, r: XlRadius.md),
                child: Row(
                  children: [
                    Icon(Icons.lock_outline_rounded, size: 15, color: p.gold),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(d,
                          style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w600, color: p.text1, letterSpacing: XlLetterSpacing.normal)),
                    ),
                    GestureDetector(
                      onTap: () async {
                        setState(() => _protectedDirs.remove(d));
                        await XlClient.stub.safe(() =>
                            XlClient.stub.command('security:remove_dir $d'));
                      },
                      child: Icon(Icons.remove_circle_outline_rounded, size: 16, color: p.red),
                    ),
                  ],
                ),
              ),
            )),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
                child: TextField(
                  controller: _dirCtrl,
                  style: TextStyle(fontSize: XlFont.captionSm, color: p.text1, fontWeight: FontWeight.w600),
                  decoration: InputDecoration(
                    border: InputBorder.none,
                    isDense: true,
                    hintText: '添加保护目录路径',
                    hintStyle: TextStyle(fontSize: XlFont.captionSm, color: p.text3, fontWeight: FontWeight.w500),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 10),
            GestureDetector(
              onTap: () async {
                final v = _dirCtrl.text.trim();
                if (v.isEmpty) return;
                setState(() {
                  if (!_protectedDirs.contains(v)) _protectedDirs.add(v);
                  _dirCtrl.clear();
                });
                await XlClient.stub.safe(() =>
                    XlClient.stub.command('security:add_dir $v'));
              },
              child: Container(
                width: 42,
                height: 42,
                decoration: AppTheme.neuXs(context, r: XlRadius.md),
                child: Icon(Icons.add_rounded, size: 18, color: p.pink),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _auditTab(XlPalette p) {
    return Column(
      children: [
        Row(
          children: [
            Text('最近操作',
                style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.text2, letterSpacing: XlLetterSpacing.wide)),
            const Spacer(),
            Text('${_audit.length} 条',
                style: TextStyle(fontSize: XlFont.label, fontWeight: FontWeight.w700, color: p.decor, letterSpacing: XlLetterSpacing.wider)),
          ],
        ),
        const SizedBox(height: 10),
        Expanded(
          child: _audit.isEmpty
              ? Center(
                  child: Text('暂无审计记录',
                      style: TextStyle(fontSize: XlFont.caption, color: p.text3, fontWeight: FontWeight.w600, letterSpacing: XlLetterSpacing.wide)),
                )
              : ListView(
                  children: _audit
                      .map((e) => Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: Container(
                              padding: const EdgeInsets.all(12),
                              decoration: AppTheme.neuXs(context, r: XlRadius.md),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Container(
                                    margin: const EdgeInsets.only(top: 3),
                                    width: 8,
                                    height: 8,
                                    decoration: BoxDecoration(
                                      color: _riskColor(p, e.risk),
                                      shape: BoxShape.circle,
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            Text(e.action,
                                                style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.wide)),
                                            const SizedBox(width: 8),
                                            Text(_riskLabel(e.risk),
                                                style: TextStyle(fontSize: XlFont.micro, fontWeight: FontWeight.w800, color: _riskColor(p, e.risk), letterSpacing: XlLetterSpacing.wider)),
                                          ],
                                        ),
                                        const SizedBox(height: 3),
                                        Text(e.detail,
                                            style: TextStyle(fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w500, letterSpacing: XlLetterSpacing.normal)),
                                      ],
                                    ),
                                  ),
                                  Text(e.time,
                                      style: TextStyle(fontSize: XlFont.label, color: p.decor, fontWeight: FontWeight.w600, letterSpacing: XlLetterSpacing.normal)),
                                ],
                              ),
                            ),
                          ))
                      .toList(),
                ),
        ),
      ],
    );
  }

  Widget _miniSwitch(XlPalette p, bool on, Color color, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: XlDuration.normal,
        curve: XlCurve.standard,
        width: 44,
        height: 24,
        decoration: BoxDecoration(
          gradient: on ? LinearGradient(colors: [color, color.withOpacity(0.8)]) : null,
          color: on ? null : p.surfaceLo,
          borderRadius: BorderRadius.circular(XlRadius.pill),
          border: Border.all(color: on ? Colors.white.withOpacity(0.25) : p.edgeSoft, width: 1),
          boxShadow: on ? p.raisedXxs : p.sunkenXs,
        ),
        child: AnimatedAlign(
          duration: XlDuration.normal,
          curve: XlCurve.standard,
          alignment: on ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            margin: const EdgeInsets.all(2.5),
            width: 17,
            height: 17,
            decoration: BoxDecoration(
              color: on ? Colors.white : p.surfaceHi,
              shape: BoxShape.circle,
            ),
          ),
        ),
      ),
    );
  }
}
