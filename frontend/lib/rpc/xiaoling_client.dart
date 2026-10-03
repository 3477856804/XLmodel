import 'package:grpc/grpc.dart';
import 'xiaoling.pb.dart';
import 'xiaoling.pbgrpc.dart';

/// 小凌 gRPC 客户端 - 连接 Python 后端
class XiaoLingClient {
  late ClientChannel _channel;
  late XiaoLingClientStub _stub;

  bool _connected = false;

  bool get isConnected => _connected;

  /// 连接后端
  Future<bool> connect({String host = 'localhost', int port = 50051}) async {
    try {
      _channel = ClientChannel(
        host,
        port: port,
        options: const ChannelOptions(
          connectTimeout: Duration(seconds: 3),
        ),
      );
      _stub = XiaoLingClientStub(_channel);

      // 测试连接
      await getStatus();
      _connected = true;
      return true;
    } catch (e) {
      _connected = false;
      return false;
    }
  }

  /// 断开连接
  Future<void> disconnect() async {
    await _channel.shutdown();
    _connected = false;
  }

  /// 获取状态
  Future<StatusReply> getStatus() async {
    return await _stub.getStatus(StatusRequest());
  }

  /// 聊天（流式）
  Stream<ChatChunk> chat(String text) {
    return _stub.chat(ChatRequest(text: text));
  }

  /// 列出模型
  Future<ModelList> listModels() async {
    return await _stub.listModels(ListRequest());
  }

  /// 切换模型
  Future<StatusReply> switchModel(String path) async {
    return await _stub.switchModel(SwitchModelRequest(path: path));
  }

  /// 硬件检测
  Future<HardwareInfo> detectHardware() async {
    return await _stub.detectHardware(Empty());
  }

  /// 推荐模型
  Future<RecommendedModelList> listRecommendedModels() async {
    return await _stub.listRecommendedModels(HardwareRequest());
  }

  /// 列出音色
  Future<VoiceList> listVoices() async {
    return await _stub.listVoices(Empty());
  }

  /// 获取设置
  Future<SettingsReply> getSettings() async {
    return await _stub.getSettings(Empty());
  }

  /// 更新设置
  Future<StatusReply> updateSettings(SettingsRequest request) async {
    return await _stub.updateSettings(request);
  }

  /// 关闭后端
  Future<StatusReply> shutdown() async {
    return await _stub.shutdown(ShutdownRequest());
  }
}
