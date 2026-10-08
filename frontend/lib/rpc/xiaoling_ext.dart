import 'dart:math' as math;
import '../rpc/xiaoling.pb.dart';

extension XlStatusExt on StatusReply {
  String get displayVersion => version.isEmpty ? 'v0.0.1' : 'v$version';
  String get displayStage => stage.isEmpty ? '待机中' : stage;
  String get displayModel => model.isEmpty ? '未加载模型' : model;
  String get displayBackend => backend.isEmpty ? 'CPU' : backend;
  String get displayMessage => message.isEmpty ? '运行正常' : message;
  double get normalizedProgress => (progress.isFinite ? progress : 0.0).clamp(0.0, 100.0) / 100.0;
  String get progressLabel => '${(normalizedProgress * 100).toStringAsFixed(0)}%';
  bool get ready => ok && !backend.isEmpty;
}

extension XlGrowthExt on GrowthStatusReply {
  String get displayStage => stage.isEmpty ? '初识' : stage;
  String get displayEmotion => emotion.isEmpty ? '平静' : emotion;
  String get displayRank => currentRank.isEmpty ? '初识阶段' : currentRank;
  double get normalizedProgress => (progressPercent.isFinite ? progressPercent : 0.0).clamp(0.0, 100.0);
  double get progressRatio => normalizedProgress / 100.0;
  String get progressLabel => '${normalizedProgress.toStringAsFixed(1)}%';
  String get interactionsLabel => totalInteractions <= 0 ? '还没聊过' : '$totalInteractions 次';
  String get generationLabel => '$currentGeneration / $totalGenerations';
  double get generationRatio {
    if (totalGenerations <= 0) return 0.0;
    return (currentGeneration / totalGenerations).clamp(0.0, 1.0);
  }
  bool get paused => trainingPaused;
  String get trainingLabel => trainingPaused ? '训练已暂停' : '成长中';
  String get shortSummary =>
      '${displayStage} · ${progressLabel} · 第 ${currentGeneration} 代';
}

extension XlTrainingExt on TrainingStatusReply {
  bool get idle => !isTraining;
  double get progressRatio {
    if (totalEpochs <= 0) return 0.0;
    return (currentEpoch / totalEpochs).clamp(0.0, 1.0);
  }
  String get progressLabel => '${(progressRatio * 100).toStringAsFixed(0)}%';
  String get epochLabel => '$currentEpoch / $totalEpochs';
  String get lossLabel => loss <= 0 ? '—' : loss.toStringAsFixed(4);
  String get displayStatus => statusText.isEmpty ? (isTraining ? '训练中' : '待机') : statusText;
  double get lossQuality {
    if (loss <= 0) return 0.0;
    return (1.0 - (loss / 3.0).clamp(0.0, 1.0));
  }
  double get avgDimension {
    if (dimensions.isEmpty) return 0.0;
    return dimensions.map((d) => d.value).reduce((a, b) => a + b) / dimensions.length;
  }
  String get avgDimensionLabel => '${avgDimension.toStringAsFixed(1)}%';
  List<TrainingDimension> get sortedDimensions {
    final list = List<TrainingDimension>.from(dimensions);
    list.sort((a, b) => b.value.compareTo(a.value));
    return list;
  }
  String get strongest {
    if (dimensions.isEmpty) return '—';
    return sortedDimensions.first.name;
  }
  String get weakest {
    if (dimensions.isEmpty) return '—';
    return sortedDimensions.last.name;
  }
}

extension XlDimensionExt on TrainingDimension {
  String get displayName => name.isEmpty ? '未命名' : name;
  String get displayLabel => label.isEmpty ? displayName : label;
  double get normalized => value.clamp(0.0, 100.0);
  double get ratio => normalized / 100.0;
  String get valueLabel => '${normalized.toStringAsFixed(1)}%';
  String get tier {
    if (normalized >= 90) return '卓越';
    if (normalized >= 75) return '优秀';
    if (normalized >= 60) return '良好';
    if (normalized >= 40) return '一般';
    return '待提升';
  }
}

extension XlModelInfoExt on ModelInfo {
  String get displayName => name.isEmpty ? '未命名模型' : name;
  double get sizeGb => sizeMb / 1024.0;
  String get sizeLabel {
    if (sizeMb <= 0) return '未知';
    if (sizeMb < 1024) return '${sizeMb.toStringAsFixed(0)} MB';
    return '${sizeGb.toStringAsFixed(2)} GB';
  }
  String get shortPath {
    if (path.isEmpty) return '—';
    final parts = path.split(RegExp(r'[/\\]'));
    return parts.length > 2 ? parts.sublist(parts.length - 2).join('/') : path;
  }
  String get fileName {
    if (path.isEmpty) return displayName;
    final parts = path.split(RegExp(r'[/\\]'));
    return parts.isEmpty ? displayName : parts.last;
  }
  bool get looksQuantized {
    final n = name.toLowerCase();
    return n.contains('q4') || n.contains('q5') || n.contains('q8') || n.contains('int4') || n.contains('int8');
  }
  bool get looksInstruct {
    final n = name.toLowerCase();
    return n.contains('instruct') || n.contains('chat') || n.contains('it');
  }
}

extension XlRecommendedExt on RecommendedModel {
  String get displayName => name.isEmpty ? '未命名' : name;
  String get displayParams => params.isEmpty ? '未知' : params;
  String get displayQuant => quant.isEmpty ? 'Q4' : quant;
  String get displayContext => context.isEmpty ? '8K' : context;
  double get sizeGb => sizeMb / 1024.0;
  String get sizeLabel {
    if (sizeMb <= 0) return '未知';
    if (sizeMb < 1024) return '${sizeMb.toStringAsFixed(0)} MB';
    return '${sizeGb.toStringAsFixed(2)} GB';
  }
  String get ramLabel => '${ramGb.toStringAsFixed(1)} GB';
  String get vramLabel => vramGb <= 0 ? '共享' : '${vramGb.toStringAsFixed(1)} GB';
  String get qualityLabel => quality <= 0 ? '—' : '$quality';
  double get qualityRatio => (quality / 100).clamp(0.0, 1.0);
  double get ramRatio => (ramGb / 32).clamp(0.0, 1.0);
  double get sizeRatio => (sizeMb / 8000).clamp(0.0, 1.0);
  String get tier {
    if (params.contains('0.5') || params.contains('1B') || params.contains('1.5')) return '轻量';
    if (params.contains('3B') || params.contains('2B') || params.contains('4B')) return '均衡';
    if (params.contains('7B') || params.contains('9B') || params.contains('8B')) return '高质';
    if (params.contains('14B') || params.contains('13B') || params.contains('32B')) return '旗舰';
    return '其他';
  }
  String get recommendation {
    if (recommended) return '推荐';
    if (canRun) return '可运行';
    return '硬件不足';
  }
  String get summary => '$displayParams · $displayQuant · $displayContext';
}

extension XlHardwareExt on HardwareInfo {
  bool get hasGpu => hasCuda || hasMetal;
  bool get isAppleSilicon => hasMetal && !hasCuda;
  bool get isNvidia => hasCuda;
  bool get cpuOnly => !hasCuda && !hasMetal;
  String get accelLabel {
    if (hasCuda) return 'CUDA';
    if (hasMetal) return 'METAL';
    return 'CPU';
  }
  String get accelFullLabel {
    if (hasCuda) return 'CUDA 加速可用';
    if (hasMetal) return 'Metal 加速可用';
    return '仅 CPU 推理';
  }
  String get displayGpu => gpuName.isEmpty ? 'Integrated Graphics' : gpuName;
  String get displayPlatform => platform.isEmpty ? 'Unknown' : platform;
  String get ramLabel => '${ramGb.toStringAsFixed(1)} GB';
  String get vramLabel => vramGb <= 0 ? '共享内存' : '${vramGb.toStringAsFixed(1)} GB';
  String get cpuLabel => '$cpuCores 核';
  String get diskLabel => '${diskFreeGb.toStringAsFixed(0)} GB';
  double get ramRatio => (ramGb / 32).clamp(0.0, 1.0);
  double get vramRatio => vramGb <= 0 ? 0.0 : (vramGb / 16).clamp(0.0, 1.0);
  double get cpuRatio => (cpuCores / 16).clamp(0.0, 1.0);
  double get diskRatio => (diskFreeGb / 500).clamp(0.0, 1.0);
  String get tier {
    if (ramGb >= 32 && vramGb >= 12) return '旗舰';
    if (ramGb >= 16 && vramGb >= 6) return '标准';
    if (ramGb >= 8) return '入门';
    return '低配';
  }
  int get maxModelParams {
    if (vramGb >= 16 || ramGb >= 32) return 14;
    if (vramGb >= 10 || ramGb >= 24) return 9;
    if (vramGb >= 6 || ramGb >= 16) return 7;
    if (ramGb >= 12) return 3;
    if (ramGb >= 8) return 1;
    return 0;
  }
  String get recommendedSize {
    final p = maxModelParams;
    if (p <= 0) return '建议先升级内存';
    if (p <= 1) return '推荐 0.5B ~ 1.5B';
    if (p <= 3) return '推荐 1.5B ~ 3B';
    if (p <= 7) return '推荐 3B ~ 7B';
    if (p <= 9) return '推荐 7B ~ 9B';
    return '推荐 7B ~ 14B';
  }
}

extension XlPluginExt on PluginInfo {
  String get displayName => name.isEmpty ? '未命名插件' : name;
  String get displayDesc => description.isEmpty ? '暂无描述' : description;
  String get displayVersion => version.isEmpty ? 'v1.0.0' : 'v$version';
  String get displayCategory {
    switch (category) {
      case 'core': return '核心';
      case 'ai': return '智能';
      case 'tool': return '工具';
      case 'fun': return '娱乐';
      case 'system': return '系统';
      default: return category.isEmpty ? '其他' : category;
    }
  }
  String get stateLabel => enabled ? '已启用' : '已禁用';
  double get stateRatio => enabled ? 1.0 : 0.0;
}

extension XlVoiceExt on VoiceInfo {
  String get displayName => name.isEmpty ? '未命名音色' : name;
  String get displayLang => lang.isEmpty ? 'zh-CN' : lang;
  String get shortId {
    var s = id.replaceFirst(RegExp(r'^zh-CN-'), '');
    s = s.replaceFirst(RegExp(r'Neural$'), '');
    return s.isEmpty ? 'edge-tts' : s;
  }
  bool get isChinese => lang.startsWith('zh') || id.startsWith('zh');
  bool get isFemale {
    final n = (name + id).toLowerCase();
    return n.contains('xiao') || n.contains('female') || n.contains('女');
  }
  bool get isMale {
    final n = (name + id).toLowerCase();
    return n.contains('yun') || n.contains('male') || n.contains('男');
  }
  String get genderLabel {
    if (isFemale) return '女声';
    if (isMale) return '男声';
    return '中性';
  }
}

extension XlActionExt on ActionInfo {
  String get displayName => name.isEmpty ? '未命名动作' : name;
  String get typeLabel {
    if (dance) return '舞蹈';
    if (idle) return '待机';
    return '动作';
  }
  String get shortPath {
    if (path.isEmpty) return '—';
    final parts = path.split(RegExp(r'[/\\]'));
    return parts.length > 2 ? parts.sublist(parts.length - 2).join('/') : path;
  }
}

extension XlSettingsExt on SettingsReply {
  String get displayModel => model.isEmpty ? '小凌' : model;
  String get displayVoice => voice.isEmpty ? '晓晓' : voice;
  String get displayRender => renderBackend.isEmpty ? '软件光栅' : renderBackend;
  String get modeLabel => alwaysOnTop ? '窗口置顶' : '普通窗口';
  String get startupLabel => autoStart ? '开机自启' : '手动启动';
  String get asrLabel => asrEnabled ? '语音识别开' : '语音识别关';
  String get ttsLabel => ttsEnabled ? '语音朗读开' : '语音朗读关';
  String get readAloudLabel => readAloudMode ? '阅读模式开' : '阅读模式关';
  int get enabledCount {
    var c = 0;
    if (asrEnabled) c++;
    if (ttsEnabled) c++;
    if (readAloudMode) c++;
    if (alwaysOnTop) c++;
    if (autoStart) c++;
    return c;
  }
  String get summary => '$displayModel · $displayVoice · $displayRender';
}

extension XlChatChunkExt on ChatChunk {
  bool get hasDelta => delta.isNotEmpty;
  bool get hasError => error.isNotEmpty;
  bool get finished => done || hasError;
  String get safeDelta => hasError ? '出错了：$error' : delta;
  String get statusLabel {
    if (hasError) return '出错';
    if (done) return '完成';
    return '生成中';
  }
}

extension XlDownloadProgressExt on DownloadProgress {
  double get ratio => (percent.isFinite ? percent : 0.0).clamp(0.0, 100.0) / 100.0;
  String get percentLabel => '${(ratio * 100).toStringAsFixed(0)}%';
  String get sizeLabel {
    if (totalMb <= 0) return '未知大小';
    if (totalMb < 1024) return '${downloadedMb.toStringAsFixed(0)} / ${totalMb.toStringAsFixed(0)} MB';
    return '${(downloadedMb / 1024).toStringAsFixed(2)} / ${(totalMb / 1024).toStringAsFixed(2)} GB';
  }
  String get displayStatus {
    if (status.isEmpty) return ratio >= 1.0 ? '已完成' : '下载中';
    return status;
  }
  bool get finished => ratio >= 1.0;
}

extension XlDownloadRequestExt on DownloadRequest {
  String get displayName => modelName.isEmpty ? '未命名模型' : modelName;
  String get displayQuant => quant.isEmpty ? 'Q4_K_M' : quant;
  String get summary => '$displayName · $displayQuant';
}

extension XlCommandReplyExt on CommandReply {
  bool get success => output.isNotEmpty && !output.toLowerCase().contains('error');
  String get displayOutput => output.isEmpty ? '（无输出）' : output;
  int get outputLines => output.isEmpty ? 0 : output.split('\n').where((s) => s.trim().isNotEmpty).length;
}

extension XlModelListExt on ModelList {
  List<ModelInfo> get sortedBySize {
    final list = List<ModelInfo>.from(models);
    list.sort((a, b) => b.sizeMb.compareTo(a.sizeMb));
    return list;
  }
  List<ModelInfo> get sortedByName {
    final list = List<ModelInfo>.from(models);
    list.sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    return list;
  }
  double get totalSizeMb => models.fold<double>(0, (a, b) => a + b.sizeMb);
  String get totalSizeLabel {
    final mb = totalSizeMb;
    if (mb <= 0) return '0 MB';
    if (mb < 1024) return '${mb.toStringAsFixed(0)} MB';
    return '${(mb / 1024).toStringAsFixed(2)} GB';
  }
  bool get isEmpty => models.isEmpty;
  ModelInfo? byName(String name) {
    for (final m in models) {
      if (m.name == name) return m;
    }
    return null;
  }
}

extension XlRecommendedListExt on RecommendedModelList {
  List<RecommendedModel> get runnable => models.where((m) => m.canRun).toList();
  List<RecommendedModel> get recommendedOnly => models.where((m) => m.recommended).toList();
  List<RecommendedModel> get sortedByQuality {
    final list = List<RecommendedModel>.from(models);
    list.sort((a, b) => b.quality.compareTo(a.quality));
    return list;
  }
  List<RecommendedModel> get sortedBySize {
    final list = List<RecommendedModel>.from(models);
    list.sort((a, b) => a.sizeMb.compareTo(b.sizeMb));
    return list;
  }
  List<RecommendedModel> get sortedByRam {
    final list = List<RecommendedModel>.from(models);
    list.sort((a, b) => a.ramGb.compareTo(b.ramGb));
    return list;
  }
  int get runnableCount => runnable.length;
  int get recommendedCount => recommendedOnly.length;
  int get maxQuality => models.isEmpty ? 0 : models.map((m) => m.quality).reduce(math.max);
  String get topName => sortedByQuality.isEmpty ? '—' : sortedByQuality.first.displayName;
}

extension XlAudioChunkExt on AudioChunk {
  int get byteCount => data.length;
  String get sizeLabel {
    if (data.isEmpty) return '0 B';
    if (data.length < 1024) return '${data.length} B';
    if (data.length < 1024 * 1024) return '${(data.length / 1024).toStringAsFixed(1)} KB';
    return '${(data.length / 1024 / 1024).toStringAsFixed(2)} MB';
  }
  bool get isDone => done;
}

extension XlEmotionExt on GrowthStatusReply {
  String get emotionIcon {
    final e = emotion.isEmpty ? '平静' : emotion;
    if (e.contains('开心') || e.contains('高兴') || e.contains('快乐')) return 'happy';
    if (e.contains('难过') || e.contains('伤心')) return 'sad';
    if (e.contains('生气') || e.contains('愤怒')) return 'angry';
    if (e.contains('累') || e.contains('疲惫')) return 'tired';
    if (e.contains('兴奋') || e.contains('激动')) return 'excited';
    if (e.contains('害羞')) return 'shy';
    return 'calm';
  }
  double get emotionEnergy {
    switch (emotionIcon) {
      case 'happy': return 0.85;
      case 'excited': return 0.95;
      case 'sad': return 0.3;
      case 'angry': return 0.6;
      case 'tired': return 0.25;
      case 'shy': return 0.55;
      default: return 0.5;
    }
  }
}

String formatDuration(Duration d) {
  if (d.inHours > 0) {
    final h = d.inHours;
    final m = d.inMinutes.remainder(60);
    return '${h}h ${m}m';
  }
  if (d.inMinutes > 0) {
    final m = d.inMinutes;
    final s = d.inSeconds.remainder(60);
    return '${m}m ${s}s';
  }
  if (d.inSeconds > 0) return '${d.inSeconds}s';
  return '${d.inMilliseconds}ms';
}

String formatRelative(DateTime t) {
  final now = DateTime.now();
  final diff = now.difference(t);
  if (diff.inSeconds < 30) return '刚刚';
  if (diff.inMinutes < 1) return '${diff.inSeconds} 秒前';
  if (diff.inMinutes < 60) return '${diff.inMinutes} 分钟前';
  if (diff.inHours < 24) return '${diff.inHours} 小时前';
  if (diff.inDays < 30) return '${diff.inDays} 天前';
  return '${t.month}/${t.day}';
}

String formatClock(DateTime t) {
  final hh = t.hour.toString().padLeft(2, '0');
  final mm = t.minute.toString().padLeft(2, '0');
  final ss = t.second.toString().padLeft(2, '0');
  return '$hh:$mm:$ss';
}

String formatBytes(int bytes) {
  if (bytes < 1024) return '$bytes B';
  if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
  if (bytes < 1024 * 1024 * 1024) return '${(bytes / 1024 / 1024).toStringAsFixed(2)} MB';
  return '${(bytes / 1024 / 1024 / 1024).toStringAsFixed(2)} GB';
}

String formatNumber(int n) {
  final s = n.abs().toString();
  final buf = StringBuffer();
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) buf.write(',');
    buf.write(s[i]);
  }
  return n < 0 ? '-$buf' : buf.toString();
}