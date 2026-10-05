import 'package:grpc/grpc.dart';
import '../rpc/xiaoling.pbgrpc.dart';

/// 自动重连的 gRPC 客户端 —— 解决后端启动慢导致首屏连接失败
class XlClient {
  static ClientChannel? _chan;
  static XiaoLingClient? _stub;

  static XiaoLingClient get stub {
    _chan ??= ClientChannel('localhost',
        port: 50051,
        options: const ChannelOptions(
          connectTimeout: Duration(seconds: 5),
          idleTimeout: Duration(minutes: 5),
        ));
    _stub ??= XiaoLingClient(_chan!);
    return _stub!;
  }

  /// 带重试的调用 —— 后端没起来时自动等 1 秒重试，最多 5 次
  static Future<T> withRetry<T>(
    Future<T> Function(XiaoLingClient stub) call, {
    int maxRetries = 5,
  }) async {
    for (int i = 0; i < maxRetries; i++) {
      try {
        return await call(stub);
      } on GrpcError catch (e) {
        if (e.code == StatusCode.unavailable && i < maxRetries - 1) {
          await Future.delayed(Duration(seconds: i + 1));
          continue;
        }
        rethrow;
      }
    }
    throw GrpcError.unavailable('后端连接失败');
  }
}
