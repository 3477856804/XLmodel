import 'dart:async';
import 'dart:typed_data';
import 'package:grpc/grpc.dart';
import 'xiaoling.pb.dart';
import 'xiaoling.pbgrpc.dart';
import 'client.dart';
import 'package:flutter/foundation.dart';

class XlCallOptions {
  final Duration? timeout;
  final String? label;
  final bool silent;
  final XlRetryPolicy? policy;
  const XlCallOptions({this.timeout, this.label, this.silent = false, this.policy});
  static const none = XlCallOptions();
  static const fast = XlCallOptions(timeout: Duration(seconds: 8), silent: false);
  static const slow = XlCallOptions(timeout: Duration(minutes: 3));
  static const bg = XlCallOptions(timeout: Duration(minutes: 10), silent: true);
}

class XlChatSession {
  final String text;
  final StringBuffer buffer = StringBuffer();
  final List<String> deltas = [];
  int chunkCount = 0;
  int byteCount = 0;
  DateTime startedAt = DateTime.now();
  DateTime? finishedAt;
  bool done = false;
  bool cancelled = false;
  String? error;
  ResponseStream<ChatChunk>? _stream;
  void Function(String delta)? onDelta;
  void Function(int count, int bytes)? onProgress;
  XlChatSession(this.text);
  Duration get elapsed => (finishedAt ?? DateTime.now()).difference(startedAt);
  String get result => buffer.toString();
  bool get isComplete => done && error == null && !cancelled;
  bool get hasError => error != null;
  void attach(ResponseStream<ChatChunk> st) => _stream = st;
  void detach() => _stream = null;
  void cancel() {
    cancelled = true;
    _stream?.cancel();
    _stream = null;
  }
  double get estimatedSpeed {
    final ms = elapsed.inMilliseconds;
    if (ms <= 0) return 0;
    return byteCount / ms * 1000;
  }
  void reset() {
    buffer.clear();
    deltas.clear();
    chunkCount = 0;
    byteCount = 0;
    startedAt = DateTime.now();
    finishedAt = null;
    done = false;
    cancelled = false;
    error = null;
  }
}

class XlAudioResult {
  final Uint8List bytes;
  final int chunkCount;
  final Duration elapsed;
  final bool success;
  final String? error;
  const XlAudioResult({
    required this.bytes,
    required this.chunkCount,
    required this.elapsed,
    required this.success,
    this.error,
  });
  int get byteCount => bytes.length;
  double get sizeKb => bytes.length / 1024;
  String get sizeLabel {
    if (bytes.isEmpty) return '0 B';
    if (bytes.length < 1024) return '${bytes.length} B';
    if (bytes.length < 1024 * 1024) return '${(bytes.length / 1024).toStringAsFixed(1)} KB';
    return '${(bytes.length / 1024 / 1024).toStringAsFixed(2)} MB';
  }
  static final empty = XlAudioResult(
    bytes: Uint8List(0),
    chunkCount: 0,
    elapsed: Duration.zero,
    success: false,
  );
}

class XlAudioStreamProgress {
  final int chunks;
  final int bytes;
  final Duration elapsed;
  final bool done;
  const XlAudioStreamProgress({
    required this.chunks,
    required this.bytes,
    required this.elapsed,
    required this.done,
  });
  double get sizeKb => bytes / 1024;
  String get sizeLabel {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / 1024 / 1024).toStringAsFixed(2)} MB';
  }
  String get rateLabel {
    final ms = elapsed.inMilliseconds;
    if (ms <= 0) return '—';
    return '${(bytes / ms * 1000 / 1024).toStringAsFixed(1)} KB/s';
  }
}

class XlBootstrapResult {
  final StatusReply status;
  final GrowthStatusReply growth;
  final TrainingStatusReply training;
  final ModelList models;
  final PluginList plugins;
  final HardwareInfo? hardware;
  final Duration elapsed;
  final int successCount;
  final int failureCount;
  final List<String> errors;
  const XlBootstrapResult({
    required this.status,
    required this.growth,
    required this.training,
    required this.models,
    required this.plugins,
    this.hardware,
    required this.elapsed,
    required this.successCount,
    required this.failureCount,
    required this.errors,
  });
  bool get allOk => failureCount == 0;
  bool get anyOk => successCount > 0;
}

class XlServerCapabilities {
  final bool hasChat;
  final bool hasGrowth;
  final bool hasTraining;
  final bool hasPlugins;
  final bool hasModels;
  final bool hasHardware;
  final bool hasVoice;
  final bool hasSettings;
  final bool hasActions;
  final bool hasUpdater;
  final bool hasShutdown;
  final bool hasCommand;
  final int reachableCount;
  final int totalCount;
  const XlServerCapabilities({
    required this.hasChat,
    required this.hasGrowth,
    required this.hasTraining,
    required this.hasPlugins,
    required this.hasModels,
    required this.hasHardware,
    required this.hasVoice,
    required this.hasSettings,
    required this.hasActions,
    required this.hasUpdater,
    required this.hasShutdown,
    required this.hasCommand,
    required this.reachableCount,
    required this.totalCount,
  });
  double get ratio => totalCount == 0 ? 0 : reachableCount / totalCount;
  String get label {
    if (ratio >= 0.95) return '全部可用';
    if (ratio >= 0.7) return '大部分可用';
    if (ratio >= 0.4) return '部分可用';
    if (ratio > 0) return '有限可用';
    return '全部离线';
  }
}

extension XlApiChat on XiaoLingClient {
  Stream<ChatChunk> chatRaw(ChatRequest req, {XlCallOptions opt = XlCallOptions.none}) {
    return chat(req, options: opt.timeout == null ? null : CallOptions(timeout: opt.timeout!));
  }

  Stream<String> chatDeltas(String text, {XlCallOptions opt = XlCallOptions.none}) async* {
    final req = ChatRequest(text: text);
    await for (final chunk in chat(req, options: opt.timeout == null ? null : CallOptions(timeout: opt.timeout!))) {
      if (chunk.error.isNotEmpty) throw StateError(chunk.error);
      if (chunk.delta.isNotEmpty) yield chunk.delta;
      if (chunk.done) break;
    }
  }

  Future<String> chatText(String text, {XlCallOptions opt = XlCallOptions.none}) async {
    final buf = StringBuffer();
    await for (final d in chatDeltas(text, opt: opt)) {
      buf.write(d);
    }
    return buf.toString();
  }

  Future<XlChatSession> chatSession(
    String text, {
    XlCallOptions opt = XlCallOptions.none,
    void Function(String delta)? onDelta,
    void Function(int count, int bytes)? onProgress,
    void Function(XlChatSession session)? onAttached,
  }) async {
    final session = XlChatSession(text);
    session.onDelta = onDelta;
    session.onProgress = onProgress;
    onAttached?.call(session);
    final completer = Completer<void>();
    void complete() {
      if (!completer.isCompleted) completer.complete();
    }
    try {
      final req = ChatRequest(text: text);
      final stream = chat(req, options: opt.timeout == null ? null : CallOptions(timeout: opt.timeout!));
      session.attach(stream);
      stream.listen(
        (chunk) {
          if (session.cancelled) return;
          session.chunkCount++;
          session.byteCount += chunk.delta.length;
          if (chunk.error.isNotEmpty) {
            session.error = chunk.error;
            complete();
            return;
          }
          if (chunk.delta.isNotEmpty) {
            session.deltas.add(chunk.delta);
            session.buffer.write(chunk.delta);
            onDelta?.call(chunk.delta);
          }
          onProgress?.call(session.chunkCount, session.byteCount);
          if (chunk.done) {
            session.done = true;
            complete();
          }
        },
        onError: (Object e) {
          if (!session.cancelled) session.error = e.toString();
          complete();
        },
        onDone: () {
          session.done = true;
          complete();
        },
      );
      await completer.future;
    } catch (e) {
      if (!session.cancelled) session.error = e.toString();
    } finally {
      session.finishedAt = DateTime.now();
      session.detach();
    }
    return session;
  }

  Future<XlChatSession> chatSessionWithHistory(
    List<({String role, String text})> history, {
    XlCallOptions opt = XlCallOptions.none,
    void Function(String delta)? onDelta,
  }) async {
    final merged = history.map((m) => '${m.role}: ${m.text}').join('\n');
    return chatSession(merged, opt: opt, onDelta: onDelta);
  }
}

extension XlApiStatus on XiaoLingClient {
  Future<StatusReply> status({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.getStatus(StatusRequest()),
      timeout: opt.timeout,
      label: opt.label ?? 'getStatus',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

extension XlApiGrowth on XiaoLingClient {
  Future<GrowthStatusReply> growth({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.getGrowthStatus(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'getGrowthStatus',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

extension XlApiTraining on XiaoLingClient {
  Future<TrainingStatusReply> training({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.getTrainingStatus(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'getTrainingStatus',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

extension XlApiPlugins on XiaoLingClient {
  Future<PluginList> plugins({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.listPlugins(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'listPlugins',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

extension XlApiModels on XiaoLingClient {
  Future<ModelList> models({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.listModels(ListRequest()),
      timeout: opt.timeout,
      label: opt.label ?? 'listModels',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<ModelList> installedModels({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.listInstalledModels(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'listInstalledModels',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> switchModel(String path, {XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.switchModel(SwitchModelRequest(path: path)),
      timeout: opt.timeout ?? const Duration(seconds: 20),
      label: opt.label ?? 'switchModel',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> deleteModel(String name, {XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.deleteModel(ModelNameRequest(name: name)),
      timeout: opt.timeout,
      label: opt.label ?? 'deleteModel',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

extension XlApiHardware on XiaoLingClient {
  Future<HardwareInfo> hardware({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.detectHardware(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'detectHardware',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<RecommendedModelList> recommended({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.listRecommendedModels(HardwareRequest()),
      timeout: opt.timeout,
      label: opt.label ?? 'listRecommendedModels',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

extension XlApiDownload on XiaoLingClient {
  Stream<DownloadProgress> downloadRaw(DownloadRequest req, {XlCallOptions opt = XlCallOptions.none}) {
    return downloadModel(req, options: opt.timeout == null ? null : CallOptions(timeout: opt.timeout!));
  }

  Stream<DownloadProgress> download(String modelName, {String quant = 'Q4_K_M', XlCallOptions opt = XlCallOptions.none}) {
    final req = DownloadRequest(modelName: modelName, quant: quant);
    return downloadModel(req, options: opt.timeout == null ? null : CallOptions(timeout: opt.timeout!));
  }

  Future<bool> downloadTo(
    String modelName, {
    String quant = 'Q4_K_M',
    void Function(DownloadProgress progress)? onProgress,
    XlCallOptions opt = XlCallOptions.none,
  }) async {
    final req = DownloadRequest(modelName: modelName, quant: quant);
    try {
      await for (final p in downloadModel(req, options: opt.timeout == null ? null : CallOptions(timeout: opt.timeout!))) {
        onProgress?.call(p);
        if (p.percent >= 100) return true;
      }
      return true;
    } catch (_) {
      return false;
    }
  }
}

extension XlApiVoices on XiaoLingClient {
  Future<VoiceList> voices({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.listVoices(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'listVoices',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> setVoice(String voiceId, {XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.setVoice(VoiceRequest(voiceId: voiceId)),
      timeout: opt.timeout,
      label: opt.label ?? 'setVoice',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

extension XlApiAudio on XiaoLingClient {
  Stream<AudioChunk> readAloudRaw(String text, {XlCallOptions opt = XlCallOptions.none, String rate = ''}) {
    return readAloud(ReadRequest(text: text, rate: rate), options: opt.timeout == null ? null : CallOptions(timeout: opt.timeout!));
  }

  Future<XlAudioResult> readAloudBytes(String text, {XlCallOptions opt = XlCallOptions.none, String rate = ''}) async {
    final sw = Stopwatch()..start();
    final chunks = <int>[];
    var count = 0;
    try {
      final req = ReadRequest(text: text, rate: rate);
      await for (final c in readAloud(req, options: opt.timeout == null ? null : CallOptions(timeout: opt.timeout!))) {
        count++;
        chunks.addAll(c.data);
        if (c.done) break;
      }
      sw.stop();
      return XlAudioResult(
        bytes: Uint8List.fromList(chunks),
        chunkCount: count,
        elapsed: sw.elapsed,
        success: true,
      );
    } catch (e) {
      sw.stop();
      return XlAudioResult(
        bytes: Uint8List.fromList(chunks),
        chunkCount: count,
        elapsed: sw.elapsed,
        success: false,
        error: e.toString(),
      );
    }
  }

  Stream<XlAudioStreamProgress> readAloudProgress(
    String text, {
    XlCallOptions opt = XlCallOptions.none,
    String rate = '',
    void Function(Uint8List chunk)? onChunk,
  }) async* {
    final sw = Stopwatch()..start();
    var chunks = 0;
    var bytes = 0;
    try {
      final req = ReadRequest(text: text, rate: rate);
      await for (final c in readAloud(req, options: opt.timeout == null ? null : CallOptions(timeout: opt.timeout!))) {
        chunks++;
        bytes += c.data.length;
        if (c.data.isNotEmpty && onChunk != null) {
          onChunk(Uint8List.fromList(c.data));
        }
        yield XlAudioStreamProgress(
          chunks: chunks,
          bytes: bytes,
          elapsed: sw.elapsed,
          done: c.done,
        );
        if (c.done) break;
      }
    } finally {
      sw.stop();
    }
  }

  Future<Uint8List> readAloudQuick(String text, {XlCallOptions opt = XlCallOptions.none, String rate = ''}) async {
    final r = await readAloudBytes(text, opt: opt, rate: rate);
    return r.bytes;
  }
}

class XlTranscribeResult {
  final String text;
  final bool ok;
  final String error;
  final bool recorded;
  final int durationMs;
  const XlTranscribeResult({
    required this.text,
    required this.ok,
    required this.error,
    required this.recorded,
    required this.durationMs,
  });
  static const unavailable = XlTranscribeResult(
    text: '', ok: false, error: '语音识别未配置', recorded: false, durationMs: 0);
}

extension XlApiAsr on XiaoLingClient {
  Future<XlTranscribeResult> transcribeAudio(
    Uint8List? audio, {
    int seconds = 5,
    String lang = 'zh',
    XlCallOptions opt = XlCallOptions.fast,
  }) async {
    try {
      final req = TranscribeRequest(lang: lang, seconds: seconds);
      if (audio != null && audio.isNotEmpty) req.audio = audio;
      final r = await transcribe(req, options: opt.timeout == null ? null : CallOptions(timeout: opt.timeout!));
      return XlTranscribeResult(
        text: r.text,
        ok: r.ok,
        error: r.error,
        recorded: r.recorded,
        durationMs: r.durationMs,
      );
    } catch (e) {
      return const XlTranscribeResult(
          text: '', ok: false, error: '语音识别未配置', recorded: false, durationMs: 0);
    }
  }
}

extension XlApiSettings on XiaoLingClient {
  Future<SettingsReply> settings({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.getSettings(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'getSettings',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> updateSettings(SettingsRequest req, {XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.updateSettings(req),
      timeout: opt.timeout,
      label: opt.label ?? 'updateSettings',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> toggleTts(bool enabled, {XlCallOptions opt = XlCallOptions.none}) {
    return updateSettings(SettingsRequest()..ttsEnabled = enabled, opt: opt);
  }

  Future<StatusReply> toggleAsr(bool enabled, {XlCallOptions opt = XlCallOptions.none}) {
    return updateSettings(SettingsRequest()..asrEnabled = enabled, opt: opt);
  }

  Future<StatusReply> toggleAlwaysOnTop(bool enabled, {XlCallOptions opt = XlCallOptions.none}) {
    return updateSettings(SettingsRequest()..alwaysOnTop = enabled, opt: opt);
  }

  Future<StatusReply> toggleAutoStart(bool enabled, {XlCallOptions opt = XlCallOptions.none}) {
    return updateSettings(SettingsRequest()..autoStart = enabled, opt: opt);
  }

  Future<StatusReply> setModelName(String model, {XlCallOptions opt = XlCallOptions.none}) {
    return updateSettings(SettingsRequest()..model = model, opt: opt);
  }

  Future<StatusReply> setVoiceName(String voice, {XlCallOptions opt = XlCallOptions.none}) {
    return updateSettings(SettingsRequest()..voice = voice, opt: opt);
  }
}

extension XlApiActions on XiaoLingClient {
  Future<ActionList> actions({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.listActions(ListRequest()),
      timeout: opt.timeout,
      label: opt.label ?? 'listActions',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> playAction(String path, {XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.playAction(PlayActionRequest(path: path)),
      timeout: opt.timeout,
      label: opt.label ?? 'playAction',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

extension XlApiCommand on XiaoLingClient {
  Future<CommandReply> command(String cmd, {XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.executeCommand(CommandRequest(command: cmd)),
      timeout: opt.timeout,
      label: opt.label ?? 'executeCommand',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<String> commandOutput(String cmd, {XlCallOptions opt = XlCallOptions.none}) async {
    final r = await command(cmd, opt: opt);
    return r.output;
  }
}

extension XlApiShutdown on XiaoLingClient {
  Future<StatusReply> shutdownServer({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.shutdown(ShutdownRequest()),
      timeout: opt.timeout ?? const Duration(seconds: 3),
      label: opt.label ?? 'shutdown',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

extension XlApiBootstrap on XiaoLingClient {
  Future<XlBootstrapResult> bootstrap({XlCallOptions opt = XlCallOptions.none}) async {
    final sw = Stopwatch()..start();
    final errors = <String>[];
    var ok = 0;
    var fail = 0;

    StatusReply status;
    GrowthStatusReply growth;
    TrainingStatusReply training;
    ModelList models;
    PluginList plugins;
    HardwareInfo? hardware;

    try {
      status = await this.status(opt: opt);
      ok++;
    } catch (e) {
      errors.add('status: $e');
      fail++;
      status = StatusReply();
    }

    try {
      growth = await this.growth(opt: opt);
      ok++;
    } catch (e) {
      errors.add('growth: $e');
      fail++;
      growth = GrowthStatusReply();
    }

    try {
      training = await this.training(opt: opt);
      ok++;
    } catch (e) {
      errors.add('training: $e');
      fail++;
      training = TrainingStatusReply();
    }

    try {
      models = await this.models(opt: opt);
      ok++;
    } catch (e) {
      errors.add('models: $e');
      fail++;
      models = ModelList();
    }

    try {
      plugins = await this.plugins(opt: opt);
      ok++;
    } catch (e) {
      errors.add('plugins: $e');
      fail++;
      plugins = PluginList();
    }

    try {
      hardware = await this.hardware(opt: opt);
      ok++;
    } catch (e) {
      errors.add('hardware: $e');
      fail++;
    }

    sw.stop();
    return XlBootstrapResult(
      status: status,
      growth: growth,
      training: training,
      models: models,
      plugins: plugins,
      hardware: hardware,
      elapsed: sw.elapsed,
      successCount: ok,
      failureCount: fail,
      errors: errors,
    );
  }

  Future<XlServerCapabilities> capabilities({XlCallOptions opt = XlCallOptions.none}) async {
    var reachable = 0;
    var total = 0;

    Future<bool> probe(Future Function() f) async {
      total++;
      try {
        await f();
        reachable++;
        return true;
      } catch (_) {
        return false;
      }
    }

    final hasStatus = await probe(() => status(opt: opt));
    final hasGrowth = await probe(() => growth(opt: opt));
    final hasTraining = await probe(() => training(opt: opt));
    final hasPlugins = await probe(() => plugins(opt: opt));
    final hasModels = await probe(() => models(opt: opt));
    final hasHardware = await probe(() => hardware(opt: opt));
    final hasVoice = await probe(() => voices(opt: opt));
    final hasSettings = await probe(() => settings(opt: opt));
    final hasActions = await probe(() => actions(opt: opt));
    final hasCommand = await probe(() => command('ping', opt: opt));
    final hasShutdown = true;
    final hasUpdater = false;
    final hasChat = hasStatus;

    return XlServerCapabilities(
      hasChat: hasChat,
      hasGrowth: hasGrowth,
      hasTraining: hasTraining,
      hasPlugins: hasPlugins,
      hasModels: hasModels,
      hasHardware: hasHardware,
      hasVoice: hasVoice,
      hasSettings: hasSettings,
      hasActions: hasActions,
      hasUpdater: hasUpdater,
      hasShutdown: hasShutdown,
      hasCommand: hasCommand,
      reachableCount: reachable,
      totalCount: total,
    );
  }

  Future<XlServerCapabilities> capabilitiesFast({XlCallOptions opt = XlCallOptions.none}) async {
    var reachable = 0;
    var total = 0;
    Future<bool> probe(Future Function() f) async {
      total++;
      try {
        await f();
        reachable++;
        return true;
      } catch (_) {
        return false;
      }
    }
    final hasStatus = await probe(() => status(opt: opt));
    final hasGrowth = await probe(() => growth(opt: opt));
    final hasTraining = await probe(() => training(opt: opt));
    final hasModels = await probe(() => models(opt: opt));
    return XlServerCapabilities(
      hasChat: hasStatus,
      hasGrowth: hasGrowth,
      hasTraining: hasTraining,
      hasPlugins: false,
      hasModels: hasModels,
      hasHardware: false,
      hasVoice: false,
      hasSettings: false,
      hasActions: false,
      hasUpdater: false,
      hasShutdown: true,
      hasCommand: false,
      reachableCount: reachable,
      totalCount: total,
    );
  }
}

extension XlApiRefresh on XiaoLingClient {
  Future<({GrowthStatusReply? growth, TrainingStatusReply? training})> refreshDynamic({
    XlCallOptions opt = XlCallOptions.none,
  }) async {
    GrowthStatusReply? growth;
    TrainingStatusReply? training;
    try {
      growth = await this.growth(opt: opt);
    } catch (e) { debugPrint('操作失败: $e'); }
    try {
      training = await this.training(opt: opt);
    } catch (e) { debugPrint('操作失败: $e'); }
    return (growth: growth, training: training);
  }

  Future<({HardwareInfo? hw, RecommendedModelList? models})> refreshHardware({
    XlCallOptions opt = XlCallOptions.none,
  }) async {
    HardwareInfo? hw;
    RecommendedModelList? models;
    try {
      hw = await hardware(opt: opt);
    } catch (e) { debugPrint('操作失败: $e'); }
    try {
      models = await recommended(opt: opt);
    } catch (e) { debugPrint('操作失败: $e'); }
    return (hw: hw, models: models);
  }

  Future<({VoiceList? voices, SettingsReply? settings})> refreshPreferences({
    XlCallOptions opt = XlCallOptions.none,
  }) async {
    VoiceList? voices;
    SettingsReply? settings;
    try {
      voices = await this.voices(opt: opt);
    } catch (e) { debugPrint('操作失败: $e'); }
    try {
      settings = await this.settings(opt: opt);
    } catch (e) { debugPrint('操作失败: $e'); }
    return (voices: voices, settings: settings);
  }
}

/// 人格 / Agent 与提醒队列的带重试包装。
///
/// 与既有 XlApi* 扩展保持一致：走 `XlClient.withRetry`，
/// 这样面板里直接 `XlClient.stub.getPersona()` 即可，不必关心超时/重试。
/// 注意：Dart 里**实例方法优先于扩展方法**。pbgrpc 生成的 stub 已经有
/// `getPersona` / `setPersona` 等同名实例方法，所以这里的包装方法**必须换名**
/// （fetchPersona / switchPersona / ...），否则扩展永远不会被解析到。
extension XlApiPersona on XiaoLingClient {
  Future<PersonaReply> fetchPersona({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.getPersona(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'fetchPersona',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<PersonaList> fetchPersonas({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.listPersonas(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'fetchPersonas',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> switchPersona(String id,
      {XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.setPersona(PersonaRequest(id: id)),
      timeout: opt.timeout,
      label: opt.label ?? 'switchPersona',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> createPersona(String name,
      {String description = '', String promptHint = '',
      XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.addPersona(PersonaRequest(
        name: name,
        description: description,
        promptHint: promptHint,
      )),
      timeout: opt.timeout,
      label: opt.label ?? 'createPersona',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> removePersona(String name,
      {XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.deletePersona(ModelNameRequest(name: name)),
      timeout: opt.timeout,
      label: opt.label ?? 'removePersona',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> resetPersonaState({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.resetPersona(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'resetPersonaState',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

/// 提醒队列（铃铛面板用）。
extension XlApiReminder on XiaoLingClient {
  Future<ReminderList> fetchReminders({XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.listReminders(Empty()),
      timeout: opt.timeout,
      label: opt.label ?? 'fetchReminders',
      silent: opt.silent,
      policy: opt.policy,
    );
  }

  Future<StatusReply> finishReminder(double dueAt,
      {XlCallOptions opt = XlCallOptions.none}) {
    return XlClient.withRetry(
      (s) => s.completeReminder(ReminderRequest(dueAt: dueAt)),
      timeout: opt.timeout,
      label: opt.label ?? 'finishReminder',
      silent: opt.silent,
      policy: opt.policy,
    );
  }
}

extension XlApiSafe on XiaoLingClient {
  Future<T?> safe<T>(Future<T> Function() call) async {
    try {
      return await call();
    } catch (_) {
      return null;
    }
  }

  Future<T> safeOr<T>(Future<T> Function() call, T fallback) async {
    try {
      return await call();
    } catch (_) {
      return fallback;
    }
  }

  Future<({T? value, Object? error})> tryCall<T>(Future<T> Function() call) async {
    try {
      return (value: await call(), error: null);
    } catch (e) {
      return (value: null, error: e);
    }
  }
}

extension XlApiBatch on XiaoLingClient {
  Future<List<T>> parallel<T>(List<Future<T> Function()> jobs, {int maxConcurrent = 4}) async {
    final results = <T>[];
    final queue = List<Future<T> Function()>.from(jobs);
    final running = <Future>[];
    while (queue.isNotEmpty || running.isNotEmpty) {
      while (running.length < maxConcurrent && queue.isNotEmpty) {
        final job = queue.removeAt(0);
        running.add(job().then((v) => results.add(v)));
      }
      if (running.isNotEmpty) {
        await Future.any(running);
      }
    }
    return results;
  }

  Future<List<T?>> parallelSafe<T>(List<Future<T> Function()> jobs, {int maxConcurrent = 4}) async {
    final results = <T?>[];
    for (var i = 0; i < jobs.length; i++) {
      results.add(null);
    }
    final indexed = <({int index, Future<T> Function() job})>[];
    for (var i = 0; i < jobs.length; i++) {
      indexed.add((index: i, job: jobs[i]));
    }
    final running = <Future>[];
    while (indexed.isNotEmpty || running.isNotEmpty) {
      while (running.length < maxConcurrent && indexed.isNotEmpty) {
        final item = indexed.removeAt(0);
        running.add(() async {
          try {
            results[item.index] = await item.job();
          } catch (_) {
            results[item.index] = null;
          }
        }());
      }
      if (running.isNotEmpty) await Future.any(running);
    }
    return results;
  }
}

extension XlApiStreamHelpers on Stream<ChatChunk> {
  Stream<String> toDeltas() async* {
    await for (final c in this) {
      if (c.error.isNotEmpty) throw StateError(c.error);
      if (c.delta.isNotEmpty) yield c.delta;
      if (c.done) break;
    }
  }

  Future<String> collectText() async {
    final buf = StringBuffer();
    await for (final d in toDeltas()) {
      buf.write(d);
    }
    return buf.toString();
  }

  Stream<String> toDeltasWithHeartbeat({Duration interval = const Duration(seconds: 2)}) {
    final controller = StreamController<String>();
    Timer? timer;
    final sub = listen(
      (c) {
        if (c.error.isNotEmpty) {
          controller.addError(StateError(c.error));
          controller.close();
          return;
        }
        if (c.delta.isNotEmpty) controller.add(c.delta);
        if (c.done) {
          timer?.cancel();
          controller.close();
        }
      },
      onError: (e, st) {
        timer?.cancel();
        controller.addError(e, st);
        controller.close();
      },
      onDone: () {
        timer?.cancel();
        if (!controller.isClosed) controller.close();
      },
    );
    timer = Timer.periodic(interval, (_) {
      if (!controller.isClosed) controller.add('');
    });
    controller.onCancel = () {
      timer?.cancel();
      sub.cancel();
    };
    return controller.stream;
  }
}

extension XlApiStreamAudioHelpers on Stream<AudioChunk> {
  Future<Uint8List> collectBytes() async {
    final list = <int>[];
    await for (final c in this) {
      list.addAll(c.data);
      if (c.done) break;
    }
    return Uint8List.fromList(list);
  }

  Stream<Uint8List> toChunks() {
    return map((c) => Uint8List.fromList(c.data));
  }

  Future<int> byteCount() async {
    var n = 0;
    await for (final c in this) {
      n += c.data.length;
      if (c.done) break;
    }
    return n;
  }
}

extension XlApiStreamDownloadHelpers on Stream<DownloadProgress> {
  Future<bool> awaitCompletion({void Function(DownloadProgress p)? onProgress}) async {
    try {
      await for (final p in this) {
        onProgress?.call(p);
        if (p.percent >= 100) return true;
      }
      return true;
    } catch (_) {
      return false;
    }
  }

  Stream<double> toRatios() => map((p) => (p.percent / 100).clamp(0.0, 1.0));
}