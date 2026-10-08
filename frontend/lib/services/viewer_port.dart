import 'dart:io';

/// 3D 查看器（后端 HTTP 静态服务）的端口发现。
///
/// 为什么不能写死 8765：
///   1. 打包态：前端自己挑一个空闲端口，用 `--web-port` 传给后端 —— 端口是
///      动态的，会被别的软件占掉；
///   2. 开发态：后端常常是**手动** `python main.py` 起的（Debug 构建旁边没有
///      backend.exe），这时没人告诉前端端口，而且后端在端口冲突时会自己顺延。
///
/// 所以这里做两级发现：先用已知端口（pin / 默认），再回退到小范围探测。
class ViewerPort {
  ViewerPort._();

  /// 默认值：后端没被指定端口时用的就是它。
  static const int defaultPort = 8765;

  /// 当前生效端口。
  static int value = defaultPort;

  /// 打包态由前端指定、并已传给后端的端口（优先相信它）。
  static int? _pinned;

  static int? get pinned => _pinned;

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

  /// 解析出真实端口；找不到就退回 [value]（随后 UI 会显示"服务未响应"）。
  static Future<int> resolve() async {
    final order = <int>[
      if (_pinned != null) _pinned!,
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

  static Uri viewerUri({String model = '小凌.vrm', int? port}) => Uri.parse(
        'http://127.0.0.1:${port ?? value}/viewer.html'
        '?model=${Uri.encodeComponent(model)}',
      );
}
