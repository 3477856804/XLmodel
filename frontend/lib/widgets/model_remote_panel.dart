import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../theme/theme.dart';

/// 魔搭（ModelScope）远端模型搜索面板。
///
/// 为什么要有这个文件：模型商店原先只把后端内置的 11 个 MODEL_PRESETS
/// 列出来，搜索框在前端做本地字符串过滤 —— 界面看着像商店，其实是一张
/// 固定清单，既搜不到魔搭上的其它模型，也没有按本机硬件给建议。
/// 这里接的是后端的真实指令（全部走 ExecuteCommand JSON，不动 proto）：
///   model:search <词> [页]        真实远端搜索
///   model:recommend              按本机硬件算出的适配/推荐
///   model:files <repo>           列远端仓库的 .gguf 文件
///   model:downloadremote <repo> [量化档]  后台下载，返回 task_id + poll
///   sandbox:status               下载进度真源（后端 TASKS 表）
///   agent:task cancel <id>       取消后台下载
///
/// 降级铁律：后端返回 ok=false 时如实显示错误并保留重试入口，绝不把
/// 「搜不到」画成「没有模型」，也绝不伪造下载进度。
class ModelRemotePanel extends StatefulWidget {
  const ModelRemotePanel({super.key, this.onDownloaded});

  /// 下载成功后通知父页面刷新本地模型清单
  final VoidCallback? onDownloaded;

  @override
  State<ModelRemotePanel> createState() => _ModelRemotePanelState();
}

class _RemoteModel {
  final String repo;
  final String name;
  final String displayName;
  final String description;
  final int downloads;
  final int likes;
  final String license;
  final int sizeMb;
  final String params;
  final List<String> tags;
  final bool private;
  final bool gated;
  final String updated;

  _RemoteModel.fromMap(Map m)
      : repo = (m['repo'] ?? '').toString(),
        name = (m['name'] ?? '').toString(),
        displayName = (m['display_name'] ?? '').toString(),
        description = (m['description'] ?? '').toString(),
        downloads = _asInt(m['downloads']),
        likes = _asInt(m['likes']),
        license = (m['license'] ?? '').toString(),
        sizeMb = _asInt(m['size_mb']),
        params = (m['params'] ?? '').toString(),
        tags = (m['tags'] as List?)?.map((e) => e.toString()).toList() ??
            const <String>[],
        private = m['private'] == true,
        gated = m['gated'] == true,
        updated = (m['updated'] ?? '').toString();

  String get title => displayName.isNotEmpty ? displayName : name;

  /// 量化档候选：魔搭 GGUF 仓库常见命名，列不出来时仍可手填
  static const quantChoices = <String>[
    'Q4_K_M',
    'Q5_K_M',
    'Q3_K_M',
    'Q2_K',
    'Q8_0',
    'FP16',
  ];
}

int _asInt(dynamic v) {
  if (v is int) return v;
  if (v is double) return v.round();
  if (v is String) return int.tryParse(v) ?? 0;
  return 0;
}

double _asDouble(dynamic v) {
  if (v is double) return v;
  if (v is int) return v.toDouble();
  if (v is String) return double.tryParse(v) ?? 0;
  return 0;
}

class _ModelRemotePanelState extends State<ModelRemotePanel> {
  final _ctrl = TextEditingController();

  // ---- 远端搜索 ----
  List<_RemoteModel> _results = [];
  int _page = 1;
  int _total = 0;
  bool _searching = false;
  String? _searchError;
  String _lastQuery = '';

  // ---- 硬件推荐 ----
  Map<String, dynamic>? _recommend;
  bool _recLoading = false;
  String? _recError;

  // ---- 下载进度（按 repo 记） ----
  final Map<String, _RemoteDl> _dl = {};
  Timer? _poll;
  // 连续轮询失败计数。此前 _refreshProgress 的 catch 完全静默：后端一旦永久
  // 不可用，UI 会停在「最后一次已知状态」假装还在下载。现在累计到阈值就在进度
  // 行如实标「同步中断」，不再骗用户。
  int _syncFails = 0;
  static const int _syncFailThreshold = 3;

  // ---- 展开详情的 repo（同时只开一个，移动端省空间） ----
  String? _expanded;

  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _loadRecommend();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _poll?.cancel();
    _ctrl.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------- 推荐

  Future<void> _loadRecommend() async {
    setState(() {
      _recLoading = true;
      _recError = null;
    });
    try {
      final out = await XlClient.stub
          .safe(() => XlClient.stub.commandOutput('model:recommend',
              opt: const XlCallOptions(
                  timeout: Duration(seconds: 20), silent: true)))
          .timeout(const Duration(seconds: 24));
      final j = out == null ? null : jsonDecode(out);
      if (!mounted) return;
      if (j is Map) {
        setState(() {
          _recommend = Map<String, dynamic>.from(j);
          _recLoading = false;
        });
      } else {
        setState(() {
          _recLoading = false;
          _recError = '后端没有返回推荐数据';
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _recLoading = false;
        _recError = '$e';
      });
    }
  }

  // ---------------------------------------------------------------- 搜索

  void _onChanged(String v) {
    _debounce?.cancel();
    final q = v.trim();
    if (q.isEmpty) {
      setState(() {
        _results = [];
        _searchError = null;
        _total = 0;
        _page = 1;
        _lastQuery = '';
      });
      return;
    }
    // 输入停顿再发请求，避免每敲一个字打一次接口
    _debounce = Timer(const Duration(milliseconds: 550), () => _search(q));
  }

  Future<void> _search(String query, {int page = 1}) async {
    if (query.trim().isEmpty) return;
    setState(() {
      _searching = true;
      _searchError = null;
    });
    try {
      final cmd = page > 1 ? 'model:search $query $page' : 'model:search $query';
      final out = await XlClient.stub
          .safe(() => XlClient.stub.commandOutput(cmd,
              opt: const XlCallOptions(timeout: Duration(seconds: 20))))
          .timeout(const Duration(seconds: 24));
      final j = out == null ? null : jsonDecode(out);
      if (!mounted) return;
      if (j is! Map) {
        setState(() {
          _searching = false;
          _searchError = '搜索返回格式异常，未能解析';
        });
        return;
      }
      if (j['ok'] != true) {
        // 关键：失败就是失败。不清空上一次结果，但明确报错并可重试。
        setState(() {
          _searching = false;
          _searchError = (j['error'] ?? '搜索失败').toString();
          _lastQuery = query;
          _page = page;
        });
        return;
      }
      final list = (j['models'] as List? ?? [])
          .whereType<Map>()
          .map((e) => _RemoteModel.fromMap(e))
          .toList();
      setState(() {
        _searching = false;
        _results = list;
        _total = _asInt(j['total']);
        _page = _asInt(j['page']) == 0 ? page : _asInt(j['page']);
        _lastQuery = query;
        _searchError = list.isEmpty ? '魔搭上没有匹配「$query」的模型' : null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _searching = false;
        _searchError = '搜索失败：$e';
        _lastQuery = query;
      });
    }
  }

  void _turnPage(int delta) {
    final target = _page + delta;
    if (target < 1 || _lastQuery.isEmpty) return;
    final maxPage = (_total / 20).ceil().clamp(1, 9999);
    if (target > maxPage) return;
    _search(_lastQuery, page: target);
  }

  // ---------------------------------------------------------------- 下载

  Future<void> _download(_RemoteModel m, String quant) async {
    if (_dl[m.repo]?.running == true) return;
    _syncFails = 0; // 新下载：清掉之前可能累计的失败计数，否则刚点就被判「同步中断」
    setState(() => _dl[m.repo] = _RemoteDl(status: 'starting'));
    try {
      final out = await XlClient.stub
          .safe(() => XlClient.stub.commandOutput(
              'model:downloadremote ${m.repo} $quant',
              opt: const XlCallOptions(timeout: Duration(seconds: 20))))
          .timeout(const Duration(seconds: 24));
      final j = out == null ? null : jsonDecode(out);
      if (!mounted) return;
      if (j is! Map || j['ok'] != true) {
        setState(() => _dl[m.repo] = _RemoteDl(
            status: 'error',
            error: (j is Map ? (j['error'] ?? '启动失败') : '启动失败').toString()));
        return;
      }
      setState(() => _dl[m.repo] = _RemoteDl(
          status: 'downloading',
          taskId: (j['task_id'] ?? '').toString()));
          // 修正：原处多传 repo: m.repo，但 _RemoteDl 无此字段（map 本以 repo 为键），
          // 编译期即报错，已移除。
      _startPolling();
    } catch (e) {
      if (!mounted) return;
      setState(() => _dl[m.repo] = _RemoteDl(status: 'error', error: '$e'));
    }
  }

  void _startPolling() {
    if (_poll != null) return;
    _poll = Timer.periodic(const Duration(seconds: 2), (_) => _refreshProgress());
  }

  Future<void> _refreshProgress() async {
    try {
      final out = await XlClient.stub
          .safe(() => XlClient.stub.commandOutput('sandbox:status',
              opt: const XlCallOptions(
                  timeout: Duration(seconds: 8), silent: true)))
          .timeout(const Duration(seconds: 10));
      final j = out == null ? null : jsonDecode(out);
      if (!mounted) return;
      final prog = (j is Map ? j['progress'] : null);
      if (prog is! Map) {
        // 请求通了但返回体没有 progress 字段：等同于失败，累计计数。
        _noteSyncFailure();
        return;
      }
      _syncFails = 0; // 成功一轮，恢复。
      var anyRunning = false;
      var done = false;
      prog.forEach((k, v) {
        if (v is! Map) return;
        final status = (v['status'] ?? '').toString();
        if (!_dl.containsKey(k.toString())) return;
        _dl[k.toString()] = _dl[k.toString()]!.copyWith(
          status: status,
          percent: _asDouble(v['percent']),
          doneMb: _asDouble(v['done_mb']),
          totalMb: _asDouble(v['total_mb']),
          error: (v['error'] ?? '').toString(),
        );
        if (status == 'downloading' || status == 'starting' || status == 'cancelling') {
          anyRunning = true;
        }
        if (status == 'done') done = true;
      });
      setState(() {});
      if (done) {
        widget.onDownloaded?.call();
      }
      if (!anyRunning) {
        _poll?.cancel();
        _poll = null;
      }
    } catch (_) {
      _noteSyncFailure();
    }
  }

  /// 一轮同步失败：累计计数；越过阈值后就在进度行显示「同步中断」，
  /// 不再让用户看一个假「还在下载」的进度条。
  void _noteSyncFailure() {
    if (!mounted) return;
    _syncFails++;
    if (_syncFails >= _syncFailThreshold) {
      _poll?.cancel();
      _poll = null;
    }
    setState(() {});
  }

  Future<void> _cancel(String repo) async {
    final id = _dl[repo]?.taskId ?? '';
    if (id.isEmpty) {
      setState(() => _dl[repo] = _RemoteDl(
          status: 'error', error: '没有 task id，无法取消（后端未返回）'));
      return;
    }
    try {
      await XlClient.stub.safe(() => XlClient.stub.commandOutput(
          'agent:task cancel $id',
          opt: const XlCallOptions(timeout: Duration(seconds: 10))));
    } catch (_) {/* 取消是协作式的，尽力而为；状态以 sandbox:status 为准 */}
    if (!mounted) return;
    setState(() => _dl[repo] = (_dl[repo] ?? _RemoteDl(status: '')).copyWith(
        status: 'cancelling'));
  }

  // ---------------------------------------------------------------- UI

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _searchBar(p),
        const SizedBox(height: 12),
        _recommendCard(p),
        const SizedBox(height: 12),
        ..._resultsSection(p),
      ],
    );
  }

  Widget _searchBar(XlPalette p) {
    return Container(
      height: 46,
      decoration: AppTheme.sunkenXs(context, r: XlRadius.lg),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      child: Row(
        children: [
          Icon(Icons.cloud_outlined, size: 16, color: p.decor),
          const SizedBox(width: 10),
          Expanded(
            child: TextField(
              controller: _ctrl,
              onChanged: _onChanged,
              onSubmitted: (v) => _search(v.trim()),
              style: TextStyle(fontSize: XlFont.caption, color: p.text1),
              decoration: InputDecoration(
                hintText: '在魔搭（ModelScope）搜索模型，例如 qwen gguf…',
                hintStyle: TextStyle(fontSize: XlFont.caption, color: p.decor),
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.zero,
              ),
            ),
          ),
          if (_searching)
            SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2, color: p.violet),
            )
          else if (_ctrl.text.trim().isNotEmpty)
            GestureDetector(
              onTap: () {
                _ctrl.clear();
                setState(() {
                  _results = [];
                  _searchError = null;
                  _total = 0;
                  _page = 1;
                  _lastQuery = '';
                });
              },
              child: Icon(Icons.close_rounded, size: 16, color: p.decor),
            ),
          const SizedBox(width: 10),
          if (!_searching && _lastQuery.isNotEmpty)
            GestureDetector(
              onTap: () => _search(_lastQuery, page: _page),
              child: Text('重试',
                  style: TextStyle(
                      fontSize: XlFont.captionSm, color: p.violet2)),
            ),
        ],
      ),
    );
  }

  Widget _recommendCard(XlPalette p) {
    final r = _recommend;
    if (_recLoading && r == null) {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: AppTheme.neuXs(context, r: XlRadius.lg),
        child: Row(children: [
          SizedBox(width: 14, height: 14,
              child: CircularProgressIndicator(strokeWidth: 2, color: p.decor)),
          const SizedBox(width: 10),
          Text('正在按本机硬件计算适配模型…',
              style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
        ]),
      );
    }
    if (_recError != null && r == null) {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: AppTheme.neuXs(context, r: XlRadius.lg),
        child: Row(children: [
          Icon(Icons.error_outline, size: 15, color: p.red),
          const SizedBox(width: 10),
          Expanded(
            child: Text('硬件推荐不可用：$_recError',
                style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
          ),
          GestureDetector(
            onTap: _loadRecommend,
            child: Text('重新探测',
                style: TextStyle(fontSize: XlFont.captionSm, color: p.violet2)),
          ),
        ]),
      );
    }
    if (r == null) {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: AppTheme.neuXs(context, r: XlRadius.lg),
        child: Row(children: [
          Icon(Icons.auto_awesome_outlined, size: 15, color: p.decor),
          const SizedBox(width: 10),
          Expanded(
            child: Text('还没有按本机硬件算过推荐',
                style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
          ),
          GestureDetector(
            onTap: _loadRecommend,
            child: Text('立即推荐',
                style: TextStyle(fontSize: XlFont.captionSm, color: p.violet2)),
          ),
        ]),
      );
    }

    final available = r['available'] == true;
    final why = (r['why'] ?? '').toString();
    final tier = (r['tier'] ?? '未知').toString();
    final models = (r['models'] as List? ?? []).whereType<Map>().toList();
    final picked = models.where((m) => m['recommended'] == true).toList();
    final shown = picked.isNotEmpty ? picked : models.take(3).toList();
    final det = (r['detected'] as Map?) ?? const {};

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.memory_outlined, size: 15,
                  color: available ? p.green : p.orange),
              const SizedBox(width: 8),
              Text(available ? '本机推荐' : '推荐（硬件未探测到）',
                  style: TextStyle(
                      fontSize: XlFont.caption,
                      fontWeight: FontWeight.w800,
                      color: p.text1)),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(XlRadius.pill),
                  color: (available ? p.green : p.orange).withOpacity(0.14),
                ),
                child: Text('档位 $tier',
                    style: TextStyle(
                        fontSize: XlFont.captionSm - 1,
                        color: available ? p.green : p.orange)),
              ),
              const Spacer(),
              GestureDetector(
                onTap: _loadRecommend,
                child: Text('刷新',
                    style: TextStyle(
                        fontSize: XlFont.captionSm, color: p.violet2)),
              ),
            ],
          ),
          if (why.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(why,
                style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
          ],
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final m in shown)
                _recChip(p, Map<String, dynamic>.from(m)),
              if (shown.isEmpty)
                Text(
                    models.isEmpty
                        ? '没有可评估的内置模型'
                        : '按当前硬件没有判定为可跑的模型',
                    style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
            ],
          ),
          if (det.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(_hwLine(det),
                style: TextStyle(
                    fontSize: XlFont.captionSm - 1, color: p.text4)),
          ],
        ],
      ),
    );
  }

  String _hwLine(Map det) {
    String n(dynamic v, {String unit = ''}) {
      final d = _asDouble(v);
      if (d <= 0) return '未探测';
      return '${d.toStringAsFixed(1)}$unit';
    }
    final parts = <String>[
      'RAM ${n(det['ram_total_gb'], unit: 'GB')}',
      '可用 ${n(det['ram_available_gb'], unit: 'GB')}',
      '磁盘 ${n(det['disk_free_gb'], unit: 'GB')}',
    ];
    final vram = _asDouble(det['vram_gb']);
    if (vram > 0) parts.add('VRAM ${vram.toStringAsFixed(1)}GB');
    final gpu = (det['gpu_name'] ?? '').toString();
    if (gpu.isNotEmpty) parts.add(gpu);
    final cores = _asInt(det['cpu_cores']);
    if (cores > 0) parts.add('$cores 核');
    return parts.join(' · ');
  }

  Widget _recChip(XlPalette p, Map m) {
    final name = (m['name'] ?? '').toString();
    final canRun = m['can_run'] == true;
    final quant = (m['quant'] ?? '').toString();
    final params = (m['params'] ?? '').toString();
    final color = canRun ? p.green : p.text3;
    return GestureDetector(
      // 点推荐项 → 直接把名字填进搜索框发起搜索，走同一条真实下载链路
      onTap: () {
        final q = params.isEmpty ? name : '$name $params';
        _ctrl.text = q;
        _search(q);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(XlRadius.md),
          border: Border.all(color: color.withOpacity(0.35)),
          color: color.withOpacity(0.07),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(name,
                style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w700,
                    color: p.text1)),
            Text(
                '${params.isEmpty ? '' : '$params · '}${quant.isEmpty ? '量化未知' : quant}'
                ' · ${canRun ? '本机可跑' : '本机吃力'}',
                style:
                    TextStyle(fontSize: XlFont.captionSm - 1, color: color)),
          ],
        ),
      ),
    );
  }

  List<Widget> _resultsSection(XlPalette p) {
    if (_searchError != null && _results.isEmpty) {
      return [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: AppTheme.neuXs(context, r: XlRadius.lg),
          child: Row(children: [
            Icon(Icons.cloud_off_outlined, size: 15, color: p.orange),
            const SizedBox(width: 10),
            Expanded(
              child: Text(_searchError!,
                  style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
            ),
          ]),
        ),
      ];
    }
    if (_results.isEmpty) return const [];
    return [
      Row(
        children: [
          Text('魔搭结果',
              style: TextStyle(
                  fontSize: XlFont.caption,
                  fontWeight: FontWeight.w800,
                  color: p.text1)),
          const SizedBox(width: 8),
          Text(_total > 0 ? '共 $_total 个，第 $_page 页' : '',
              style: TextStyle(fontSize: XlFont.captionSm, color: p.text3)),
          const Spacer(),
          if (_page > 1)
            GestureDetector(
              onTap: _searching ? null : () => _turnPage(-1),
              child: Icon(Icons.chevron_left_rounded, size: 18, color: p.text2),
            ),
          const SizedBox(width: 4),
          if (_page * 20 < _total)
            GestureDetector(
              onTap: _searching ? null : () => _turnPage(1),
              child:
                  Icon(Icons.chevron_right_rounded, size: 18, color: p.text2),
            ),
        ],
      ),
      const SizedBox(height: 10),
      for (final m in _results) _resultCard(p, m),
    ];
  }

  Widget _resultCard(XlPalette p, _RemoteModel m) {
    final dl = _dl[m.repo];
    final expanded = _expanded == m.repo;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: () => setState(() => _expanded = expanded ? null : m.repo),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(m.title,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                    fontSize: XlFont.caption,
                                    fontWeight: FontWeight.w700,
                                    color: p.text1)),
                          ),
                          if (m.gated) ...[
                            const SizedBox(width: 6),
                            _tag(p, '受限', p.orange),
                          ],
                          if (m.private) ...[
                            const SizedBox(width: 6),
                            _tag(p, '私有', p.red),
                          ],
                        ],
                      ),
                      const SizedBox(height: 3),
                      Text(
                        '${m.repo} · ${m.params.isEmpty ? "参数量未知" : m.params}'
                        ' · ${m.sizeMb > 0 ? "${m.sizeMb} MB" : "体积未知"}'
                        ' · 下载 ${m.downloads} · 赞 ${m.likes}',
                        style:
                            TextStyle(fontSize: XlFont.captionSm - 1, color: p.text3),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Icon(expanded ? Icons.expand_less : Icons.expand_more,
                    size: 18, color: p.decor),
              ],
            ),
          ),
          if (dl != null) ...[
            const SizedBox(height: 10),
            _dlRow(p, m, dl),
          ],
          if (expanded) ...[
            const SizedBox(height: 10),
            if (m.description.isNotEmpty) ...[
              Text(m.description,
                  style:
                      TextStyle(fontSize: XlFont.captionSm, color: p.text2)),
              const SizedBox(height: 8),
            ],
            if (m.license.isNotEmpty || m.updated.isNotEmpty) ...[
              Text([
                if (m.license.isNotEmpty) '许可证 ${m.license}',
                if (m.updated.isNotEmpty) '更新 ${m.updated}',
              ].join(' · '),
                  style:
                      TextStyle(fontSize: XlFont.captionSm - 1, color: p.text4)),
              const SizedBox(height: 8),
            ],
            if (m.tags.isNotEmpty) ...[
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final t in m.tags.take(6)) _tag(p, t, p.violet2),
                ],
              ),
              const SizedBox(height: 8),
            ],
            _filesBox(p, m),
          ],
        ],
      ),
    );
  }

  Widget _dlRow(XlPalette p, _RemoteModel m, _RemoteDl dl) {
    final Color color;
    final String label;
    // 连续多轮 sandbox:status 拉不到 → 之前那个「还在下载」的进度条其实是最后
    // 一次已知状态，属于假活。这里显式改成「同步中断」。轮询在 _noteSyncFailure
    // 里已经停掉了；恢复只需用户重点「下载」触发 _startPolling。
    final stale = _syncFails >= _syncFailThreshold &&
        (dl.status == 'downloading' ||
            dl.status == 'starting' ||
            dl.status == 'cancelling');
    if (stale) {
      color = p.orange;
      label = '同步中断（后端已无响应，进度停留在最后一次已知状态）';
    } else {
      switch (dl.status) {
      case 'done':
        color = p.green;
        label = '下载完成';
        break;
      case 'error':
        color = p.red;
        label = '失败：${dl.error.isEmpty ? "未知错误" : dl.error}';
        break;
      case 'cancelled':
        color = p.orange;
        label = '已取消（.part 保留，可续传）';
        break;
      case 'cancelling':
        color = p.orange;
        label = '正在取消…';
        break;
      case 'starting':
        color = p.violet;
        label = '准备中…';
        break;
      default:
        color = p.violet;
        label = '${dl.percent.toStringAsFixed(1)}%'
            '${dl.totalMb > 0 ? " · ${dl.doneMb.toStringAsFixed(1)}/${dl.totalMb.toStringAsFixed(1)} MB" : ""}';
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(XlRadius.pill),
          child: LinearProgressIndicator(
            value: dl.status == 'done' ? 1.0 : (dl.percent / 100).clamp(0.0, 1.0),
            minHeight: 5,
            backgroundColor: p.decorSoft.withOpacity(0.25),
            valueColor: AlwaysStoppedAnimation(color),
          ),
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            Expanded(
              child: Text(label,
                  style: TextStyle(fontSize: XlFont.captionSm - 1, color: color)),
            ),
            if (dl.status == 'downloading' || dl.status == 'starting')
              GestureDetector(
                onTap: () => _cancel(m.repo),
                child: Text('取消',
                    style:
                        TextStyle(fontSize: XlFont.captionSm - 1, color: p.red)),
              ),
          ],
        ),
      ],
    );
  }

  Widget _filesBox(XlPalette p, _RemoteModel m) {
    return FutureBuilder<Map<String, dynamic>?>(
      future: _fetchFiles(m.repo),
      builder: (ctx, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return Text('正在读取仓库文件…',
              style: TextStyle(fontSize: XlFont.captionSm - 1, color: p.text4));
        }
        final j = snap.data;
        if (j == null || j['ok'] != true) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('无法读取仓库文件列表：${(j?['error'] ?? '接口失败')}',
                  style: TextStyle(fontSize: XlFont.captionSm - 1, color: p.orange)),
              const SizedBox(height: 8),
              _quantRow(p, m, const []),
            ],
          );
        }
        final gguf = (j['gguf'] as List? ?? []).map((e) => e.toString()).toList();
        if (gguf.isEmpty) {
          return Text('这个仓库里没有 .gguf 文件（可能不是量化仓库，无法直接下载）',
              style: TextStyle(fontSize: XlFont.captionSm - 1, color: p.text4));
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('可下载的量化档：${gguf.length} 个',
                style: TextStyle(fontSize: XlFont.captionSm - 1, color: p.text4)),
            const SizedBox(height: 6),
            for (final g in gguf.take(6))
              Padding(
                padding: const EdgeInsets.only(bottom: 2),
                child: Text('· $g',
                    style:
                        TextStyle(fontSize: XlFont.captionSm - 1, color: p.text3)),
              ),
            const SizedBox(height: 8),
            _quantRow(p, m, gguf),
          ],
        );
      },
    );
  }

  Widget _quantRow(XlPalette p, _RemoteModel m, List<String> gguf) {
    // 量化档：优先用仓库里真实存在的文件名推出来的档位，再补常见档位。
    // 去重是因为多个文件可能推出同一个档名。
    final choices = <String>{
      ...gguf.map(_guessQuant),
      ..._RemoteModel.quantChoices,
    }.toList();
    final saved = _quantSel[m.repo];
    // DropdownButton 的 value 必须是 items 之一，否则渲染期断言失败 ——
    // 所以这里先落到合法值，而不是把可能非法的 saved 直接传进去。
    final sel = (saved != null && choices.contains(saved))
        ? saved
        : (choices.isEmpty ? 'Q4_K_M' : choices.first);
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        DropdownButtonHideUnderline(
          child: DropdownButton<String>(
            value: sel,
            isDense: true,
            dropdownColor: p.surface,
            style: TextStyle(fontSize: XlFont.captionSm, color: p.text1),
            items: [
              for (final c in choices)
                DropdownMenuItem(value: c, child: Text(c)),
            ],
            onChanged: (v) {
              if (v != null) setState(() => _quantSel[m.repo] = v);
            },
          ),
        ),
        GestureDetector(
          onTap: () => _download(m, sel),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
            decoration: AppTheme.brand(context, r: XlRadius.pill),
            child: Text('下载',
                style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: p.btnInk)),
          ),
        ),
      ],
    );
  }

  Widget _tag(XlPalette p, String t, Color c) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(XlRadius.micro),
          color: c.withOpacity(0.15),
        ),
        child: Text(t,
            style: TextStyle(fontSize: XlFont.captionSm - 2, color: c)),
      );

  // ---- 文件列表缓存：展开时只请求一次 ----
  final Map<String, Future<Map<String, dynamic>?>> _filesCache = {};
  final Map<String, String> _quantSel = {};

  Future<Map<String, dynamic>?> _fetchFiles(String repo) {
    return _filesCache.putIfAbsent(repo, () async {
      try {
        final out = await XlClient.stub
            .safe(() => XlClient.stub.commandOutput('model:files $repo',
                opt: const XlCallOptions(timeout: Duration(seconds: 20))))
            .timeout(const Duration(seconds: 24));
        final j = out == null ? null : jsonDecode(out);
        return j is Map ? Map<String, dynamic>.from(j) : null;
      } catch (_) {
        return {'ok': false, 'error': '请求失败'};
      }
    });
  }

  /// 从 gguf 文件名里猜量化档：`qwen2.5-7b-instruct-q4_k_m.gguf` → `Q4_K_M`
  static String _guessQuant(String path) {
    final lower = path.toLowerCase();
    for (final q in _RemoteModel.quantChoices) {
      if (lower.contains(q.toLowerCase())) return q;
    }
    final m = RegExp(r'(q\d+[_a-z0-9]*)').firstMatch(lower);
    if (m != null) return m.group(1)!.toUpperCase();
    return path.split('/').last;
  }
}

class _RemoteDl {
  final String status;
  final double percent;
  final double doneMb;
  final double totalMb;
  final String error;
  final String taskId;

  const _RemoteDl({
    required this.status,
    this.percent = 0,
    this.doneMb = 0,
    this.totalMb = 0,
    this.error = '',
    this.taskId = '',
  });

  bool get running =>
      status == 'downloading' || status == 'starting' || status == 'cancelling';

  _RemoteDl copyWith({
    String? status,
    double? percent,
    double? doneMb,
    double? totalMb,
    String? error,
  }) =>
      _RemoteDl(
        status: status ?? this.status,
        percent: percent ?? this.percent,
        doneMb: doneMb ?? this.doneMb,
        totalMb: totalMb ?? this.totalMb,
        error: error ?? this.error,
        taskId: taskId,
      );
}
