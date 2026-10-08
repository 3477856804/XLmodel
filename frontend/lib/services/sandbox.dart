import 'dart:convert';
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart';

import '../rpc/client.dart';
// safe() 与 commandOutput() 都是挂在 XiaoLingClient 上的扩展方法，
// 不显式 import 这个文件时它们"看起来不存在"（报 undefined_method）。
import '../rpc/xiaoling_client_ext.dart';

/// 小凌的自有沙箱环境。
///
/// 两套实现：
///   · Android  → Termux 侧原生实现，走 MethodChannel
///   · 桌面端   → 后端 sandbox 模块，走 gRPC 的 `sandbox:*` 指令
///
/// 关键在于**两端返回结构保持一致**（`snapshot.progress.<模型名>`），
/// 模型商店页那段下载轮询是 Android 时代写好的，桌面端沿用同一结构即可，
/// 不必再写一份,也不会出现"桌面没进度条"的割裂感。
class SandboxService {
  static const MethodChannel _channel = MethodChannel('xiaoling/sandbox');

  /// Android 走原生，其余桌面平台（Windows / Linux / macOS）走后端沙箱。
  static bool get isSupported => Platform.isAndroid || !kIsWeb;

  static Future<bool> start() async {
    if (Platform.isAndroid) {
      try {
        final r = await _channel.invokeMethod('startSandbox');
        return r is Map && r['ok'] == true;
      } catch (_) {
        return false;
      }
    }
    // 桌面端：后端一收到 sandbox:status 就会 ensure() 出完整目录结构，
    // 所以这里不需要单独的 start 语义，成功拿到状态即视为沙箱就位。
    try {
      final raw = await XlClient.stub
          .safe(() => XlClient.stub.commandOutput('sandbox:status')) ?? '';
      final d = jsonDecode(raw);
      return d is Map && d['started'] == true;
    } catch (e) {
      debugPrint('沙箱初始化失败: $e');
      return false;
    }
  }

  static Future<void> stop() async {
    if (!Platform.isAndroid) return;
    try {
      await _channel.invokeMethod('stopSandbox');
    } catch (e) {
      debugPrint('操作失败: $e');
    }
  }

  static Future<Map<String, dynamic>> status() async {
    if (Platform.isAndroid) {
      try {
        final r = await _channel.invokeMethod('getSandboxStatus');
        if (r is Map) {
          final out = <String, dynamic>{'supported': true};
          final s = r['status'];
          if (s is String && s.isNotEmpty) {
            try {
              out.addAll(jsonDecode(s) as Map<String, dynamic>);
            } catch (e) {
              debugPrint('操作失败: $e');
            }
          }
          final snap = r['snapshot'];
          if (snap is String && snap.isNotEmpty) {
            try {
              out['snapshot'] = jsonDecode(snap);
            } catch (e) {
              debugPrint('操作失败: $e');
            }
          }
          return out;
        }
      } catch (e) {
        debugPrint('操作失败: $e');
      }
      return {'started': false, 'supported': true};
    }

    // ---- 桌面端：包成与 Android 同构的形状 ----
    try {
      final raw = await XlClient.stub
          .safe(() => XlClient.stub.commandOutput('sandbox:status')) ?? '';
      final d = jsonDecode(raw);
      if (d is! Map) return {'started': false, 'supported': false};
      final paths = d['paths'] is Map ? d['paths'] as Map : const {};
      final usage = d['usage'] is Map ? d['usage'] as Map : const {};
      final progress = d['progress'] is Map ? d['progress'] as Map : const {};
      return {
        'supported': true,
        'started': d['started'] == true,
        'snapshot': {
          'paths': Map<String, dynamic>.from(paths),
          'usage': Map<String, dynamic>.from(usage),
          'progress': Map<String, dynamic>.from(progress),
        },
        // 顶层也放一份，方便新写的代码直接取
        'paths': Map<String, dynamic>.from(paths),
        'usage': Map<String, dynamic>.from(usage),
        'progress': Map<String, dynamic>.from(progress),
      };
    } catch (e) {
      debugPrint('获取沙箱状态失败: $e');
      return {'started': false, 'supported': false};
    }
  }

  /// 沙箱内的受限执行（cwd 固定在 sandbox/workspace，路径逃逸会被拒绝）。
  static Future<Map<String, dynamic>> execScript(String command) async {
    if (Platform.isAndroid) return {'ok': false, 'error': 'unsupported'};
    try {
      final raw = await XlClient.stub
              .safe(() => XlClient.stub.commandOutput('sandbox:exec $command')) ??
          '';
      final d = jsonDecode(raw);
      return d is Map ? Map<String, dynamic>.from(d) : {'ok': false, 'raw': raw};
    } catch (e) {
      return {'ok': false, 'error': e.toString()};
    }
  }

  static Future<Map<String, dynamic>> downloadModel(String name,
      {String quant = 'q4_k_m'}) async {
    if (Platform.isAndroid) {
      try {
        final r = await _channel.invokeMethod('downloadModel', {
          'name': name,
          'quant': quant,
        });
        if (r is Map) {
          final res = r['result'];
          if (res is String && res.isNotEmpty) {
            try {
              return jsonDecode(res) as Map<String, dynamic>;
            } catch (e) {
              debugPrint('操作失败: $e');
            }
          }
          return {'ok': r['ok'] == true};
        }
      } catch (e) {
        return {'ok': false, 'error': e.toString()};
      }
      return {'ok': false};
    }

    // 桌面端主下载通道其实是 XlClient.stub.download（流式，进度更细）；
    // 这条是经沙箱的备用路径，内部同样落到 sandbox 的 models 目录。
    try {
      final raw = await XlClient.stub
              .safe(() => XlClient.stub.commandOutput('sandbox:download $name')) ??
          '';
      final d = jsonDecode(raw);
      return d is Map ? Map<String, dynamic>.from(d) : {'ok': false, 'raw': raw};
    } catch (e) {
      return {'ok': false, 'error': e.toString()};
    }
  }
}
