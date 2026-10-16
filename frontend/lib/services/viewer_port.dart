import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';

/// 3D 查看器（后端 HTTP 静态服务）的端口发现。
///
/// 为什么不能写死 8765：
///   1. 打包态：前端自己挑一个空闲端口，用 `--web-port` 传给后端 —— 端口是
///      动态的，会被别的软件占掉；
///   2. 开发态：后端常常是**手动** `python main.py` 起的（Debug 构建旁边没有
///      backend.exe），这时没人告诉前端端口，而且后端在端口冲突时会自己顺延。
///
/// 发现顺序（从最可信到兜底）：
///   pin（启动器给的环境变量 / 手动指定）
///     → 问后端 `system:ports`（gRPC 连接已经建立，后端知道自己实际绑到
///        哪个端口，这是唯一不会猜错的来源）
///     → 小范围探测（仅用于连 gRPC 都没连上的极端情况）
///
/// 以前只有「pin + 盲扫 8765~8785」两级。盲扫有两个真问题：后端顺延出窗口
/// 就永远找不到（表现成「3D 角色一直加载不出来」）；更糟的是同号端口可能
/// 属于别的软件，扫过去 WebView 里会渲染出莫名其妙的页面。
class ViewerPort {
  ViewerPort._();

  /// 默认值：后端没被指定端口时用的就是它。
  static const int defaultPort = 8765;

  /// 当前生效端口。
  static int value = defaultPort;

  /// 打包态由前端指定、并已传给后端的端口（优先相信它）。
  static int? _pinned;

  static int? get pinned => _pinned;

  /// 上一次从后端问到的真实端口（问成功就记住，重试时不必再问）。
  static int? _fromBackend;

  /// 后端明确告知「查看器没起来」的原因，用于界面如实提示。
  static String? lastError;

  /// 挑一个可用端口：优先 preferred，被占则向系统要一个空闲端口。
  /// 返回值同时写入 [_pinned] 与 [value]。
  static Future<int> pick([int preferred = defaultPort]) async {
    for (final p in <int>[preferred, 0]) {
      try {
        final s = await ServerSocket.bind(InternetAddress.loopbackIPv4, p);
        final got = s.port;
        await s.close();
        _pinned = got;
        value = got;
        return got;
      } catch (_) {
        continue;
      }
    }
    _pinned = preferred;
    value = preferred;
    return preferred;
  }

  /// 探一个端口上是否真的有我们的查看器（只认 200 的 /viewer.html）。
  static Future<bool> _alive(int port) async {
    HttpClient? c;
    try {
      c = HttpClient()..connectionTimeout = const Duration(milliseconds: 400);
      final req = await c
          .getUrl(Uri.parse('http://127.0.0.1:$port/viewer.html'))
          .timeout(const Duration(milliseconds: 700));
      final resp = await req.close().timeout(const Duration(milliseconds: 900));
      await resp.drain<void>();
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    } finally {
      c?.close(force: true);
    }
  }

  /// 直接问后端：查看器实际绑在哪个端口。
  ///
  /// 返回端口号；问不到（未连接 / 老后端没有这条指令 / JSON 不合法）返回
  /// null，由调用方决定下一步。**后端说 port=0 时返回 0**，那是「服务确实
  /// 没起来」的明确答案，不能和「问不到」混为一谈 —— 否则界面会一直转圈，
  /// 而实际上再等多久都不会起来。
  static Future<int?> queryBackend() async {
    try {
      final raw = await XlClient.stub
          .safe(() => XlClient.stub.commandOutput('system:ports',
              opt: const XlCallOptions(
                  timeout: Duration(seconds: 4), silent: true)))
          .timeout(const Duration(seconds: 6));
      if (raw == null || raw.trim().isEmpty) return null;
      final d = jsonDecode(raw);
      if (d is! Map || d['ok'] != true) return null;
      final p = d['web'];
      if (p is! num) return null;
      final e = d['web_error'];
      lastError = (e is String && e.trim().isNotEmpty) ? e : null;
      final port = p.toInt();
      if (port < 0 || port >= 65536) return null;
      _fromBackend = port;
      return port;
    } catch (e) {
      debugPrint('向后端查询查看器端口失败: $e');
      return null;
    }
  }

  /// 单文件版由 packaging/launcher.py 先挑好端口再拉起后端，
  /// 并通过环境变量 XIAOLING_WEB_PORT 告知。这里直接 pin，
  /// 避免在 8765~8785 里盲探（可能命中别的软件的同号服务）。
  ///
  /// 注意必须用 [Platform.environment] 读运行时环境变量：
  /// `String.fromEnvironment` 是编译期常量，运行期 set 的环境变量读不到。
  static void adoptFromEnv() {
    final p = int.tryParse(Platform.environment['XIAOLING_WEB_PORT'] ?? '');
    if (p != null && p > 0 && p < 65536) {
      _pinned = p;
      value = p;
    }
  }

  /// 手动指定端口（开发态 / 测试用）。
  static void pin(int port) {
    if (port <= 0 || port >= 65536) return;
    _pinned = port;
    value = port;
  }

  /// 解析出真实端口；找不到就退回 [value]（随后 UI 会显示"服务未响应"）。
  ///
  /// 启动器是「先拉后端、再拉前端」的，两者是并行启动的：前端探端口时
  /// 后端可能还没 listen 上。所以对 pin 端口做几轮短重试，
  /// 否则会误判成「3D 服务不存在」。
  static Future<int> resolve() async {
    final pinnedPort = _pinned;
    if (pinnedPort != null) {
      for (var i = 0; i < 6; i++) {
        if (await _alive(pinnedPort)) {
          value = pinnedPort;
          return pinnedPort;
        }
        await Future<void>.delayed(Duration(milliseconds: 350 + i * 250));
      }
      // pin 的端口不通时**先问后端**，别直接摆烂：后端可能因为端口被占
      // 顺延到了别处，此时 pin 值已经过期，而真值只有后端知道。
      final asked = await queryBackend();
      if (asked != null && asked > 0) {
        // 后端报了非零端口但 _alive 首次不通：给几轮短重试再决定。此前
        // 首试失败就回退到过期 pin，WebView 会拼出「错误端口 URL」→ 空白
        // 页或别人的同号服务。
        for (var i = 0; i < 3; i++) {
          if (await _alive(asked)) {
            value = asked;
            return asked;
          }
          await Future<void>.delayed(
              Duration(milliseconds: 300 + i * 300));
        }
      } else if (asked == 0) {
        // 后端明确说查看器没起来，返回 0 让上层显示「服务未响应」而不是
        // 摆一个过期 pin 出去。
        value = 0;
        return 0;
      }
      // 问不到（gRPC 也未就绪，多半是后端还在并行启动）：返回 0 让上层
      // 显示「服务未启动」并走自动重试。此前的做法是把过期 pin 当结果
      // 返回，WebView 拼出连不上的 URL → onLoadError 直接落错误态，
      // 且没有任何自动恢复路径，冷启动慢的机器上必现「3D 加载不出来」。
      value = 0;
      return 0;
    }

    // 没有 pin —— 优先问后端要真值（开发态手动起后端就走这条）。
    for (var i = 0; i < 4; i++) {
      final asked = await queryBackend();
      if (asked != null) {
        if (asked == 0) {
          // 后端明确说「查看器没起来」：返回 0 让上层走 error UI，
          // 别再回退到 defaultPort —— 那会让 WebView 去连一个不属于我们的
          // 端口，展示一个空白/错位页面。
          value = 0;
          return 0;
        }
        if (await _alive(asked)) {
          value = asked;
          return asked;
        }
      }
      await Future<void>.delayed(Duration(milliseconds: 400 + i * 400));
    }
    if (_fromBackend == 0) {
      value = 0;
      return 0;
    }

    // 最后才盲扫，并且只扫默认窗口（这条路径意味着 gRPC 也没连上，
    // 属于「后端整个没起来」的兜底提示场景）。
    final order = <int>[
      value,
      defaultPort,
      for (var i = defaultPort + 1; i <= defaultPort + 20; i++) i,
    ];
    final tried = <int>{};
    for (final p in order) {
      if (p <= 0 || !tried.add(p)) continue;
      if (await _alive(p)) {
        value = p;
        return p;
      }
    }
    return value;
  }

  static Uri viewerUri({String model = '小凌.vrm', int? port, double? renderQuality}) {
    final uri = Uri.parse(
      'http://127.0.0.1:${port ?? value}/viewer.html'
      '?model=${Uri.encodeComponent(model)}',
    );
    if (renderQuality == null) return uri;
    return uri.replace(queryParameters: {
      ...uri.queryParameters,
      'rq': renderQuality.clamp(0.0, 1.0).toStringAsFixed(3),
    });
  }
}


/// 全局 3D 渲染质量控制。
///
/// [quality] 来自设置页的 renderQuality 滑块（0..1，默认 0.78）。
///
/// model_showcase 在 WebView 就绪后把 [quality] 注入 three.js 页面：
///   1) 通过 [ViewerPort.viewerUri] 的 `rq` 查询参数在页面加载时读取；
///   2) 通过 `window.__xl.setRenderQuality(x)` 在滑块拖动时实时推送
///      （见 resources/web/viewer.html 的实现：调整 renderer.setPixelRatio）。
///
/// [apply] 由 model_showcase 注册：质量变化发生时实时推给渲染器。
class XlRender {
  XlRender._();

  /// 当前渲染质量 0..1。
  static double quality = 0.78;

  /// model_showcase 注册：当质量变化时实时推给渲染器。
  static void Function(double)? apply;
}
