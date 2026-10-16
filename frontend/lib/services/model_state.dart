import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';

/// 「当前使用的模型」的前端唯一真源。
///
/// 后端把这件事收敛到了 `core.model.active_model()`（以磁盘事实为准），
/// 通过 `model:active` 指令返回 JSON。本类只负责：
///   1. 拉取 + 解析成 [XlModelState]；
///   2. **短 TTL 内存缓存** —— 聊天页、状态栏、模型商店会同时问「用的哪个模型」，
///      没有缓存就是三次 gRPC 往返；有了缓存绝大多数时候零往返。
///      后端本身也有 3s 缓存，两级缓存叠加后重复查询几乎不花时间。
///   3. 广播变化，让 UI 不必各自轮询。
///
/// 为什么不读 GetStatus：StatusReply.model 是给「状态栏一行字」用的，
/// 塞了"（已加载）"之类后缀且不含 params/quant/size，无法直接驱动 UI。
class ModelStateService {
  ModelStateService._();
  static final ModelStateService instance = ModelStateService._();

  /// 缓存有效期。取 2 秒：既能让"刚下载完模型立刻看到"，
  /// 又不会让切模型后的显示明显滞后。
  static const Duration _ttl = Duration(seconds: 2);

  XlModelState? _cached;
  DateTime? _cachedAt;
  Future<XlModelState>? _inflight;

  final StreamController<XlModelState> _ctrl =
      StreamController<XlModelState>.broadcast();

  /// 模型状态变化流。UI 订阅后即可自动刷新，无需手动轮询。
  Stream<XlModelState> get changes => _ctrl.stream;

  XlModelState? get cached => _cached;

  /// 拉取当前模型状态。命中缓存则直接返回，不产生网络往返。
  Future<XlModelState> fetch({bool force = false}) async {
    final now = DateTime.now();
    if (!force &&
        _cached != null &&
        _cachedAt != null &&
        now.difference(_cachedAt!) < _ttl) {
      return _cached!;
    }
    // 合并并发的重复请求：多个页面同时初始化时只打一次后端
    if (_inflight != null) return _inflight!;
    final fut = _fetchRaw();
    _inflight = fut;
    try {
      final s = await fut;
      final changed = _cached?.signature != s.signature;
      _cached = s;
      _cachedAt = DateTime.now();
      if (changed && !_ctrl.isClosed) _ctrl.add(s);
      return s;
    } finally {
      _inflight = null;
    }
  }

  Future<XlModelState> _fetchRaw() async {
    try {
      final raw = await XlClient.stub
          .commandOutput('model:active')
          .timeout(const Duration(seconds: 6));
      final map = jsonDecode(raw);
      if (map is Map<String, dynamic>) return XlModelState.fromJson(map);
    } catch (e) {
      debugPrint('读取当前模型失败：$e');
    }
    return const XlModelState.unavailable(reason: '后端未响应，无法确认模型状态');
  }

  /// 切换模型（严格匹配，不会静默换成别的模型）。
  Future<XlModelState> use(String name) async {
    try {
      final raw = await XlClient.stub
          .commandOutput('model:use $name')
          .timeout(const Duration(seconds: 10));
      final map = jsonDecode(raw);
      if (map is Map<String, dynamic> && map['ok'] == true) {
        final s = XlModelState.fromJson(map);
        _cached = s;
        _cachedAt = DateTime.now();
        if (!_ctrl.isClosed) _ctrl.add(s);
        return s;
      }
      _cached = XlModelState.unavailable(
          reason: (map is Map && map['error'] is String)
              ? map['error'] as String
              : '切换失败');
      return _cached!;
    } catch (e) {
      _cached = XlModelState.unavailable(reason: '切换失败：$e');
      return _cached!;
    }
  }

  /// 本地失效缓存。模型下载完成后调用，让 UI 立刻重新识别。
  void invalidate() {
    _cached = null;
    _cachedAt = null;
  }

  void dispose() {
    if (!_ctrl.isClosed) _ctrl.close();
  }
}

/// 当前模型的结构化状态。
class XlModelState {
  const XlModelState({
    required this.available,
    required this.name,
    required this.path,
    required this.params,
    required this.quant,
    required this.size,
    required this.backend,
    required this.loaded,
    required this.reason,
    required this.guidance,
    required this.action,
    required this.text,
  });

  /// 没有模型（或后端没响应）时的状态。
  const XlModelState.unavailable({this.reason = '尚未安装模型'})
      : available = false,
        name = '',
        path = '',
        params = '',
        quant = '',
        size = '',
        backend = '',
        loaded = false,
        guidance = '',
        action = 'open:model_store',
        text = '';

  /// 本机磁盘上确实存在并会被使用的模型。
  final bool available;

  /// 模型名（如 Qwen3.5-9B-DeepSeek-V4-Flash-Q4_K_M）。
  final String name;
  final String path;

  /// 参数量（如 9B）。
  final String params;

  /// 量化档位（如 Q4_K_M）。
  final String quant;

  /// 人类可读体积（如 5.24 GB）。
  final String size;

  /// gguf / transformers。
  final String backend;

  /// 是否已经加载进内存（正在出字）。
  final bool loaded;

  /// 为什么是这个模型 / 为什么没有模型。
  final String reason;

  /// 没有模型时的引导文案。
  final String guidance;

  /// 需要前端执行的动作（无模型时是 open:model_store）。
  final String action;

  /// 后端给好的、可直接显示的一句话说明。
  final String text;

  /// 变化检测用：只有这些字段变了才算「状态变了」，才广播。
  String get signature => '$available|$name|$loaded|$backend';

  factory XlModelState.fromJson(Map<String, dynamic> j) {
    return XlModelState(
      available: j['available'] == true,
      name: (j['name'] ?? '').toString(),
      path: (j['path'] ?? '').toString(),
      params: (j['params'] ?? '').toString(),
      quant: (j['quant'] ?? '').toString(),
      size: (j['size'] ?? '').toString(),
      backend: (j['backend'] ?? '').toString(),
      loaded: j['loaded'] == true,
      reason: (j['reason'] ?? '').toString(),
      guidance: (j['guidance'] ?? '').toString(),
      action: (j['action'] ?? '').toString(),
      text: (j['text'] ?? '').toString(),
    );
  }

  /// 聊天页头部的一行摘要。
  String get subtitle {
    if (!available) return '未安装模型 · 点这里去模型商店下载';
    final meta = <String>[];
    if (params.isNotEmpty) meta.add(params);
    if (quant.isNotEmpty) meta.add(quant);
    if (size.isNotEmpty) meta.add(size);
    final tag = loaded ? '已加载' : '待加载';
    return meta.isEmpty
        ? '$name（$tag）'
        : '$name · ${meta.join(' · ')}（$tag）';
  }

  /// 头部显示用的模型名。
  String get displayName => available && name.isNotEmpty ? name : '未安装模型';
}
