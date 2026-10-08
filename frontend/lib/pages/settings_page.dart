import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import '../theme/theme.dart';
import '../theme/theme_controller.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;
import '../widgets/mcp_panel.dart';
import '../widgets/security_panel.dart';
import '../widgets/knowledge_graph_panel.dart';
import '../services/local_store.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});
  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> with TickerProviderStateMixin {
  pb.SettingsReply? _remote;
  pb.HardwareInfo? _hardware;
  bool _loading = true;
  bool _synced = false;
  bool _clearingCache = false;
  String _activeSection = 'model';
  final _searchCtrl = TextEditingController();
  final _searchFocus = FocusNode();
  String _query = '';
  late AnimationController _enterCtrl;
  late AnimationController _pulseCtrl;
  late Animation<double> _enterAnim;
  final List<_SettingChange> _history = [];
  bool _aboutExpanded = false;
  final List<_ChangeRecord> _changeLog = [];
  bool _diagExpanded = false;
  Map<String, dynamic> _memStats = const {};
  bool _memLoading = false;
  bool _forgettingOld = false;

  final Map<String, bool> _toggles = {
    'alwaysOnTop': false,
    'autoStart': false,
    'asr': true,
    'tts': true,
    'readAloud': false,
    'splash': true,
    'sound': true,
    'crash': true,
    'telemetry': false,
    'animations': true,
    'hardwareAccel': true,
    'autoUpdate': true,
  };

  String _model = '活泼';
  String _voice = '晓晓';
  String _render = 'auto';
  String _inferBackend = 'auto';
  String _threads = 'auto';
  String _theme = 'dark';
  String _language = 'zh-CN';
  String _cacheSize = '计算中…';

  final Map<String, bool> _channels = {
    'Webhook': false,
    'Telegram': false,
    'Discord': false,
    '飞书': false,
    'WhatsApp': false,
    'Slack': false,
    'Signal': false,
    '邮件': false,
  };

  final Map<String, double> _sliders = {
    'speed': 0.55,
    'volume': 0.80,
    'opacity': 0.92,
    'renderQuality': 0.78,
  };
  int _sliderSaveSeq = 0;

  static const _sections = <_Section>[
    _Section('model', '模型设置', Icons.memory_rounded, 'pink'),
    _Section('render', '渲染设置', Icons.blur_on_rounded, 'gold'),
    _Section('voice', '语音设置', Icons.record_voice_over_rounded, 'violet'),
    _Section('interface', '界面设置', Icons.dashboard_customize_rounded, 'green'),
    _Section('channels', '多平台通道', Icons.hub_rounded, 'gold'),
    _Section('memory', '记忆与知识', Icons.psychology_outlined, 'pink'),
    _Section('advanced', '高级设置', Icons.tune_rounded, 'blue'),
    _Section('about', '关于小凌', Icons.info_outline_rounded, 'pink'),
  ];

  List<_Opt> _optPersonas = const [];
  List<_Opt> _optInferBackends = const [];
  List<_Opt> _optThreads = const [];
  List<_Opt> _optRenderModes = const [];
  List<_Opt> _optThemes = const [];
  List<_Opt> _optLangs = const [];
  List<_VoiceOpt> _optVoices = const [];
  Map<String, dynamic> _voiceEngines = const {};
  Map<String, dynamic> _optSliders = const {};
  bool _optsLoaded = false;

  String _voiceId = '';
  final AudioPlayer _voicePlayer = AudioPlayer();
  bool _previewing = false;

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 900), vsync: this);
    _pulseCtrl = AnimationController(duration: const Duration(seconds: 4), vsync: this)..repeat();
    _enterAnim = CurvedAnimation(parent: _enterCtrl, curve: XlCurve.easeOut);
    _enterCtrl.forward();
    _restoreLocal();
    _loadSettings();
    _loadOptions();
    _calcCache();
    _loadMemStats();
  }

  Future<void> _loadOptions() async {
    final raw = await XlClient.stub.safe(() =>
        XlClient.stub.commandOutput('settings:options'));
    if (!mounted) return;
    Map<String, dynamic> data = const {};
    if (raw != null && raw.trim().isNotEmpty) {
      try {
        final decoded = jsonDecode(raw);
        if (decoded is Map<String, dynamic>) data = decoded;
      } catch (_) {}
    }
    setState(() {
      _optsLoaded = true;
      final ui = (data['ui'] as Map?) ?? const {};
      final mdl = (data['model'] as Map?) ?? const {};
      final rnd = (data['render'] as Map?) ?? const {};
      final vc = (data['voice'] as Map?) ?? const {};
      _optThemes = _nonEmpty(_Opt.fromJson(ui['themes']), _fallbackThemes);
      _optLangs = _nonEmpty(_Opt.fromJson(ui['languages']), _fallbackLangs);
      _optPersonas = _nonEmpty(_Opt.fromJson(mdl['personas']), _fallbackPersonas);
      _optInferBackends =
          _nonEmpty(_Opt.fromJson(mdl['inference_backends']), _fallbackInfer);
      _optThreads = _nonEmpty(_Opt.fromJson(mdl['threads']), _fallbackThreads);
      _optRenderModes =
          _nonEmpty(_Opt.fromJson(rnd['modes']), _fallbackRenderModes);
      _optVoices = _VoiceOpt.fromJson(vc['voices']);
      _voiceEngines = (vc['engines'] as Map?)?.cast<String, dynamic>() ?? const {};
      _optSliders = (data['sliders'] as Map?)?.cast<String, dynamic>() ?? const {};
      final curVoice = (vc['current'] ?? '').toString();
      if (curVoice.isNotEmpty) _voiceId = curVoice;
      final curInfer = (mdl['inference_backend'] ?? '').toString();
      if (curInfer.isNotEmpty) _inferBackend = curInfer;
      final curThreads = (mdl['threads_current'] ?? '').toString();
      if (curThreads.isNotEmpty) _threads = curThreads;
      final curRender = (rnd['mode'] ?? '').toString();
      if (curRender.isNotEmpty) _render = curRender;
      final curPersona = (mdl['persona'] ?? '').toString();
      if (curPersona.isNotEmpty) _model = curPersona;
      final curTheme = (ui['theme'] ?? '').toString();
      if (curTheme.isNotEmpty) _theme = curTheme;
      final curLang = (ui['language'] ?? '').toString();
      if (curLang.isNotEmpty) _language = curLang;
    });
  }

  static const _fallbackThemes = <_Opt>[
    _Opt('system', '跟随系统'), _Opt('dark', '始终深色'), _Opt('light', '始终浅色'),
  ];
  static const _fallbackLangs = <_Opt>[
    _Opt('zh-CN', '简体中文'), _Opt('zh-TW', '繁體中文', enabled: false),
    _Opt('en-US', 'English', enabled: false), _Opt('ja-JP', '日本語', enabled: false),
  ];
  static const _fallbackPersonas = <_Opt>[
    _Opt('活泼', '活泼'), _Opt('温柔', '温柔'), _Opt('高冷', '高冷'),
    _Opt('元气', '元气'), _Opt('沉稳', '沉稳'),
  ];
  static const _fallbackInfer = <_Opt>[
    _Opt('auto', '自动（推荐）'), _Opt('cpu', 'CPU'), _Opt('cuda', 'CUDA / GPU'),
  ];
  static const _fallbackThreads = <_Opt>[
    _Opt('auto', '自动'), _Opt('4', '4 线程'), _Opt('8', '8 线程'),
  ];
  static const _fallbackRenderModes = <_Opt>[
    _Opt('auto', '自动'), _Opt('software', '软件光栅'), _Opt('gpu', 'GPU 加速'),
  ];

  static List<_Opt> _nonEmpty(List<_Opt> got, List<_Opt> fallback) =>
      got.isEmpty ? fallback : got;

  Future<bool> _setOption(String path, String value, {bool quiet = false}) async {
    final raw = await XlClient.stub.safe(
        () => XlClient.stub.commandOutput('settings:set $path $value'));
    var ok = raw != null;
    var msg = '';
    if (raw != null && raw.trim().isNotEmpty) {
      try {
        final d = jsonDecode(raw);
        if (d is Map) {
          ok = d['ok'] == true;
          msg = (d['error'] ?? '').toString();
        }
      } catch (_) {}
    }
    if (!quiet) {
      _showSnack(ok ? '已保存' : '保存失败${msg.isEmpty ? '' : '：$msg'}');
    }
    return ok;
  }

  @override
  void dispose() {
    _enterCtrl.dispose();
    _pulseCtrl.dispose();
    _searchCtrl.dispose();
    _searchFocus.dispose();
    _voicePlayer.dispose();
    super.dispose();
  }

  Future<void> _applyVoice(String voiceId, String label) async {
    setState(() {
      _voiceId = voiceId;
      _voice = label;
    });
    final r = await XlClient.stub.safe(
        () => XlClient.stub.setVoice(pb.VoiceRequest(voiceId: voiceId)));
    if (!mounted) return;
    if (r?.ok != true) {
      _showSnack('切换音色失败');
      return;
    }
    _showSnack('已切换为「$label」，正在试听');
    setState(() => _previewing = true);
    try {
      final local = await LocalStore.readJson('channels.json');
      var speed = 0.55;
      final sl = local['sliders'];
      if (sl is Map && sl['speed'] is num) {
        speed = (sl['speed'] as num).toDouble().clamp(0.0, 1.0);
      }
      final pct = ((speed - 0.5) * 100).round().clamp(-40, 50);
      final rate = pct == 0 ? '+0%' : (pct > 0 ? '+$pct%' : '$pct%');
      final audio = await XlClient.stub.readAloudBytes(
          '你好，我是小凌，这是我的声音。',
          rate: rate);
      if (!mounted || !audio.success || audio.bytes.isEmpty) return;
      final dir = await getTemporaryDirectory();
      final f = File('${dir.path}/xl_voice_preview.mp3');
      await f.writeAsBytes(audio.bytes);
      await _voicePlayer.stop();
      await _voicePlayer.play(DeviceFileSource(f.path));
    } catch (_) {
    } finally {
      if (mounted) setState(() => _previewing = false);
    }
  }

  Future<void> _loadSettings() async {
    setState(() {
      _loading = true;
      _synced = false;
    });
    final prefs = await XlClient.stub.refreshPreferences();
    final hw = await XlClient.stub.safe(() => XlClient.stub.hardware());
    if (!mounted) return;
    setState(() {
      _remote = prefs.settings;
      _hardware = hw;
      if (prefs.settings != null) {
        final s = prefs.settings!;
        _model = s.displayModel;
        _voice = s.displayVoice;
        _render = s.displayRender;
        _toggles['alwaysOnTop'] = s.alwaysOnTop;
        _toggles['autoStart'] = s.autoStart;
        _toggles['asr'] = s.asrEnabled;
        _toggles['tts'] = s.ttsEnabled;
        _toggles['readAloud'] = s.readAloudMode;
        _synced = true;
      }
      _loading = false;
    });
  }

  Future<void> _calcCache() async {
    try {
      final tmp = await getTemporaryDirectory();
      final size = await _dirSize(tmp);
      if (!mounted) return;
      setState(() => _cacheSize = _fmtSize(size));
    } catch (_) {
      if (mounted) setState(() => _cacheSize = '未知');
    }
  }

  Future<int> _dirSize(Directory d) async {
    var total = 0;
    try {
      await for (final e in d.list(recursive: true, followLinks: false)) {
        if (e is File) total += await e.length();
      }
    } catch (e) { debugPrint('操作失败: $e'); }
    return total;
  }

  String _fmtSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / 1024 / 1024).toStringAsFixed(1)} MB';
  }

  String _two(int n) => n.toString().padLeft(2, '0');

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(milliseconds: 1800),
        content: Text(msg, style: const TextStyle(fontWeight: FontWeight.w600)),
      ));
  }

  Future<void> _clearCache() async {
    if (_clearingCache) return;
    setState(() => _clearingCache = true);
    try {
      final tmp = await getTemporaryDirectory();
      final size = await _dirSize(tmp);
      try {
        await for (final e in tmp.list()) {
          e.delete(recursive: true);
        }
      } catch (e) { debugPrint('操作失败: $e'); }
      await Future.delayed(const Duration(milliseconds: 700));
      if (!mounted) return;
      setState(() {
        _cacheSize = '0 B';
        _clearingCache = false;
      });
      _showSnack('已清理 ${(size / 1024 / 1024).toStringAsFixed(1)} MB 缓存');
    } catch (_) {
      if (!mounted) return;
      setState(() => _clearingCache = false);
      _showSnack('缓存清理完成');
    }
  }

  Future<void> _exportData() async {
    try {
      final blob = await XlClient.stub.exportData(pb.Empty());
      final docs = await getApplicationDocumentsDirectory();
      final now = DateTime.now();
      final stamp = '${now.year}${_two(now.month)}${_two(now.day)}';
      final name = 'xiaoling_export_$stamp.json';
      final file = File(p.join(docs.path, name));
      await file.writeAsString(blob.json);
      if (!mounted) return;
      _showSnack('数据已导出到：$name');
    } catch (e) {
      if (!mounted) return;
      _showSnack('导出失败：$e');
    }
  }

  Future<void> _importData() async {
    final ctrl = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: XlPalette.of(context).surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: const Text('导入数据'),
        content: TextField(
          controller: ctrl,
          maxLines: 8,
          autofocus: true,
          decoration: const InputDecoration(hintText: '粘贴备份 JSON 内容…'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('导入')),
        ],
      ),
    );
    if (confirmed != true) return;
    final content = ctrl.text.trim();
    if (content.isEmpty) {
      _showSnack('内容为空，未导入');
      return;
    }
    try {
      final r = await XlClient.stub.importData(pb.DataBlob(json: content));
      if (!mounted) return;
      _showSnack(r.ok ? '数据导入成功' : '导入失败：${r.message}');
    } catch (e) {
      if (!mounted) return;
      _showSnack('导入失败：$e');
    }
  }

  Future<void> _resetSettings() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: XlPalette.of(context).surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: const Text('确认重置'),
        content: const Text('将恢复所有设置为默认值，确定继续？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('确定')),
        ],
      ),
    );
    if (confirmed != true) return;
    await XlClient.stub.safe(() => XlClient.stub.updateSettings(pb.SettingsRequest()));
    if (!mounted) return;
    await _loadSettings();
    await _loadOptions();
    _showSnack('设置已重置');
  }

  void _logChange(String key, bool value) {
    _changeLog.insert(0, _ChangeRecord(key, value, DateTime.now()));
    if (_changeLog.length > 12) _changeLog.removeLast();
  }

  String _labelForKey(String key) {
    switch (key) {
      case 'alwaysOnTop': return '窗口置顶';
      case 'autoStart': return '开机自启';
      case 'asr': return '语音识别';
      case 'tts': return '语音朗读';
      case 'readAloud': return '阅读模式';
      case 'splash': return '启动动画';
      case 'sound': return '系统音效';
      case 'crash': return '崩溃上报';
      case 'telemetry': return '使用统计';
      case 'animations': return '启用动画';
      case 'hardwareAccel': return '硬件加速';
      case 'autoUpdate': return '自动更新';
      default: return key;
    }
  }

  String _fmtClock(DateTime t) {
    return '${_two(t.hour)}:${_two(t.minute)}:${_two(t.second)}';
  }

  Future<void> _exportConfigSnapshot() async {
    try {
      final docs = await getApplicationDocumentsDirectory();
      final now = DateTime.now();
      final stamp = '${now.year}${_two(now.month)}${_two(now.day)}_${_two(now.hour)}${_two(now.minute)}';
      final payload = <String, dynamic>{
        'version': '0.0.1',
        'exportedAt': now.toIso8601String(),
        'toggles': Map<String, bool>.from(_toggles),
        'channels': Map<String, bool>.from(_channels),
        'model': _model,
        'voice': _voice,
        'render': _render,
        'threads': _threads,
        'theme': _theme,
        'language': _language,
        'changeLog': _changeLog.map((e) => {
              'key': e.key,
              'label': _labelForKey(e.key),
              'value': e.value,
              'time': e.time.toIso8601String(),
            }).toList(),
      };
      final file = File(p.join(docs.path, 'xiaoling_config_$stamp.json'));
      await file.writeAsString(const JsonEncoder.withIndent('  ').convert(payload));
      if (!mounted) return;
      _showSnack('配置快照已导出：${p.basename(file.path)}');
    } catch (e) {
      if (!mounted) return;
      _showSnack('导出失败：$e');
    }
  }

  void _openMcpPanel() {
    final p = XlPalette.of(context);
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: p.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.xl)),
        insetPadding: const EdgeInsets.all(24),
        child: Container(
          width: 520,
          constraints: const BoxConstraints(maxHeight: 600),
          padding: const EdgeInsets.all(20),
          child: const McpPanel(),
        ),
      ),
    );
  }

  void _openSecurityPanel() {
    final p = XlPalette.of(context);
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: p.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.xl)),
        insetPadding: const EdgeInsets.all(24),
        child: Container(
          width: 520,
          constraints: const BoxConstraints(maxHeight: 640),
          padding: const EdgeInsets.all(20),
          child: const SecurityPanel(),
        ),
      ),
    );
  }

  Future<void> _persistChannels() async {
    await LocalStore.writeJson('channels.json', {
      'channels': Map<String, bool>.from(_channels),
      'toggles': Map<String, bool>.from(_toggles),
      'theme': _theme,
      'sliders': Map<String, double>.from(_sliders),
    });
  }

  void _setSlider(String key, double v) {
    setState(() => _sliders[key] = v.clamp(0.0, 1.0));
    final seq = ++_sliderSaveSeq;
    Future.delayed(const Duration(milliseconds: 400), () {
      if (!mounted || seq != _sliderSaveSeq) return;
      _persistChannels();
    });
  }

  Future<void> _restoreLocal() async {
    final data = await LocalStore.readJson('channels.json');
    if (!mounted) return;
    setState(() {
      final ch = data['channels'];
      if (ch is Map) ch.forEach((k, v) {
        if (v is bool) _channels[k.toString()] = v;
      });
      final tg = data['toggles'];
      if (tg is Map) tg.forEach((k, v) {
        if (v is bool) _toggles[k.toString()] = v;
      });
      final th = data['theme'];
      if (th is String && th.isNotEmpty) _theme = th;
      final sl = data['sliders'];
      if (sl is Map) sl.forEach((k, v) {
        if (v is num) _sliders[k.toString()] = v.toDouble().clamp(0.0, 1.0);
      });
    });
  }

  Color _colorOf(XlPalette p, String key) {
    switch (key) {
      case 'pink': return p.pink;
      case 'gold': return p.gold;
      case 'violet': return p.violet;
      case 'green': return p.green;
      case 'blue': return p.blue;
      case 'red': return p.red;
      default: return p.pink;
    }
  }

  bool _matches(String label, String sub) {
    if (_query.isEmpty) return true;
    final q = _query.toLowerCase();
    return label.toLowerCase().contains(q) || sub.toLowerCase().contains(q);
  }

  @override
  Widget build(BuildContext context) {
    final p = XlPalette.of(context);
    return Stack(
      children: [
        Positioned.fill(child: AppTheme.aurora(context, child: const SizedBox.shrink())),
        AnimatedBuilder(
          animation: _enterAnim,
          builder: (_, __) => Opacity(
            opacity: _enterAnim.value,
            child: Transform.translate(
              offset: Offset(0, (1 - _enterAnim.value) * 16),
              child: _body(p),
            ),
          ),
        ),
      ],
    );
  }

  Widget _body(XlPalette p) {
    final isMobile = MediaQuery.of(context).size.width < 600;
    final hPad = isMobile ? 16.0 : 26.0;
    return Padding(
      padding: EdgeInsets.fromLTRB(hPad, 6, hPad, 30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _stagger(0, _heroRow(p)),
          const SizedBox(height: 20),
          Expanded(
            child: _stagger(1, LayoutBuilder(
              builder: (context, c) {
                final stacked = c.maxWidth < 900;
                if (stacked) {
                  return Column(
                    children: [
                      _sectionRail(p, horizontal: true),
                      const SizedBox(height: 14),
                      Expanded(child: _contentPane(p)),
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(width: 240, child: _sectionRail(p, horizontal: false)),
                    const SizedBox(width: 20),
                    Expanded(child: _contentPane(p)),
                  ],
                );
              },
            )),
          ),
        ],
      ),
    );
  }

  Widget _stagger(int index, Widget child) {
    final start = (index * 0.15).clamp(0.0, 0.6);
    final end = (start + 0.6).clamp(0.0, 1.0);
    return AnimatedBuilder(
      animation: _enterAnim,
      builder: (_, __) {
        final t = Interval(start, end, curve: Curves.easeOut).transform(_enterAnim.value);
        return Opacity(
          opacity: t,
          child: Transform.translate(offset: Offset(0, (1 - t) * 16), child: child),
        );
      },
    );
  }

  Widget _heroRow(XlPalette p) {
    return LayoutBuilder(
      builder: (context, c) {
        final narrow = c.maxWidth < 500;
        if (narrow) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text('设置',
                      style: TextStyle(
                        fontSize: XlFont.h2,
                        fontWeight: FontWeight.w800,
                        color: p.text1,
                        letterSpacing: XlLetterSpacing.normal,
                      )),
                  const SizedBox(width: 12),
                  _statusChip(p),
                ],
              ),
              const SizedBox(height: 6),
              Text('调整小凌的行为、声音与外观',
                  style: TextStyle(
                    fontSize: XlFont.caption,
                    color: p.text2,
                    fontWeight: FontWeight.w500,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
              const SizedBox(height: 14),
              _searchBox(p),
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text('设置',
                          style: TextStyle(
                            fontSize: XlFont.h2,
                            fontWeight: FontWeight.w800,
                            color: p.text1,
                            letterSpacing: XlLetterSpacing.normal,
                          )),
                      const SizedBox(width: 12),
                      _statusChip(p),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text('调整小凌的行为、声音与外观',
                      style: TextStyle(
                        fontSize: XlFont.caption,
                        color: p.text2,
                        fontWeight: FontWeight.w500,
                        letterSpacing: XlLetterSpacing.wide,
                      )),
                ],
              ),
            ),
            const SizedBox(width: 16),
            _searchBox(p),
          ],
        );
      },
    );
  }

  Widget _statusChip(XlPalette p) {
    final color = _synced ? p.green : p.gold;
    return AnimatedBuilder(
      animation: _pulseCtrl,
      builder: (_, __) {
        final t = _pulseCtrl.value;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: color.withOpacity(p.isDark ? 0.14 : 0.10),
            borderRadius: BorderRadius.circular(XlRadius.pill),
            border: Border.all(color: color.withOpacity(0.32), width: 1),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                  boxShadow: [BoxShadow(color: color.withOpacity(0.5 + t * 0.4), blurRadius: 6, spreadRadius: -1)],
                ),
              ),
              const SizedBox(width: 6),
              Text(_synced ? 'SYNCED' : 'LOCAL',
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w800,
                    color: color,
                    letterSpacing: XlLetterSpacing.ultra,
                  )),
            ],
          ),
        );
      },
    );
  }

  Widget _searchBox(XlPalette p) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 280),
      height: 42,
      decoration: AppTheme.sunkenXs(context, r: XlRadius.lg),
      padding: const EdgeInsets.symmetric(horizontal: 14),
      child: Row(
        children: [
          Icon(Icons.search_rounded, size: 15, color: p.decor),
          const SizedBox(width: 10),
          Expanded(
            child: TextField(
              controller: _searchCtrl,
              focusNode: _searchFocus,
              onChanged: (v) => setState(() => _query = v.trim().toLowerCase()),
              style: TextStyle(fontSize: XlFont.captionSm, color: p.text1),
              decoration: InputDecoration(
                hintText: '搜索设置项…',
                hintStyle: TextStyle(fontSize: XlFont.captionSm, color: p.decor),
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.zero,
              ),
            ),
          ),
          if (_query.isNotEmpty)
            _Pressable(
              onTap: () {
                _searchCtrl.clear();
                setState(() => _query = '');
              },
              child: Icon(Icons.close_rounded, size: 15, color: p.decor),
            ),
        ],
      ),
    );
  }

  Widget _sectionRail(XlPalette p, {required bool horizontal}) {
    if (horizontal) {
      return SizedBox(
        height: 48,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemCount: _sections.length,
          separatorBuilder: (_, __) => const SizedBox(width: 8),
          itemBuilder: (_, i) => _railChip(p, _sections[i], horizontal: true),
        ),
      );
    }
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: Column(
        children: [
          for (int i = 0; i < _sections.length; i++) ...[
            _railChip(p, _sections[i], horizontal: false),
            if (i != _sections.length - 1) const SizedBox(height: 4),
          ],
        ],
      ),
    );
  }

  Widget _railChip(XlPalette p, _Section s, {required bool horizontal}) {
    final selected = _activeSection == s.key;
    final color = _colorOf(p, s.color);
    final chip = AnimatedContainer(
      duration: XlDuration.fast,
      curve: XlCurve.standard,
      padding: horizontal
          ? const EdgeInsets.symmetric(horizontal: 16, vertical: 10)
          : const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: selected
          ? AppTheme.sunkenSm(context, r: XlRadius.md)
          : const BoxDecoration(),
      child: Row(
        mainAxisSize: horizontal ? MainAxisSize.min : MainAxisSize.max,
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              color: selected ? color.withOpacity(p.isDark ? 0.18 : 0.12) : p.surfaceLo,
              borderRadius: BorderRadius.circular(XlRadius.sm),
              border: Border.all(
                color: selected ? color.withOpacity(0.30) : p.edgeSoft,
                width: 1,
              ),
            ),
            child: Icon(s.icon, size: 14, color: selected ? color : p.text3),
          ),
          const SizedBox(width: 12),
          if (!horizontal)
            Expanded(
              child: Text(s.label,
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                    color: selected ? color : p.text2,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
            )
          else
            Text(s.label,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                  color: selected ? color : p.text2,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          if (!horizontal && selected)
            Container(
              width: 6,
              height: 6,
              decoration: AppTheme.glowDot(color, size: 6),
            ),
        ],
      ),
    );
    return _Pressable(
      onTap: () => setState(() => _activeSection = s.key),
      child: chip,
    );
  }

  Widget _contentPane(XlPalette p) {
    final isMobile = MediaQuery.of(context).size.width < 600;
    return Container(
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: SingleChildScrollView(
        padding: EdgeInsets.all(isMobile ? 16 : 24),
        child: _loading
            ? _loadingPane(p)
            : AnimatedSwitcher(
                duration: XlDuration.medium,
                transitionBuilder: (child, anim) => FadeTransition(
                  opacity: anim,
                  child: SlideTransition(
                    position: Tween(begin: const Offset(0, 0.04), end: Offset.zero).animate(anim),
                    child: child,
                  ),
                ),
                child: KeyedSubtree(
                  key: ValueKey(_activeSection),
                  child: _sectionContent(p),
                ),
              ),
      ),
    );
  }

  Widget _loadingPane(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [_skeleton(p, width: 44, height: 44, radius: 12), const SizedBox(width: 14), Column(crossAxisAlignment: CrossAxisAlignment.start, children: [_skeleton(p, width: 140, height: 16, radius: 6), const SizedBox(height: 8), _skeleton(p, width: 200, height: 11, radius: 6)])]),
        const SizedBox(height: 24),
        for (int i = 0; i < 4; i++) ...[
          _skeleton(p, width: double.infinity, height: 64, radius: 16),
          const SizedBox(height: 12),
        ],
      ],
    );
  }

  Widget _skeleton(XlPalette p, {required double width, required double height, double radius = 12}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: p.surfaceLo,
          borderRadius: BorderRadius.circular(radius),
          boxShadow: p.sunkenXs,
        ),
        child: AnimatedBuilder(
          animation: _pulseCtrl,
          builder: (_, __) {
            return LayoutBuilder(builder: (ctx, c) {
              final w = c.maxWidth;
              final dx = (_pulseCtrl.value * 2.2 - 0.6) * w;
              return Stack(children: [
                Positioned(
                  left: dx.clamp(-w * 0.6, w),
                  top: 0, bottom: 0,
                  width: w * 0.4,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(colors: [
                        Colors.white.withOpacity(0.0),
                        Colors.white.withOpacity(p.isDark ? 0.06 : 0.16),
                        Colors.white.withOpacity(0.0),
                      ]),
                    ),
                  ),
                ),
              ]);
            });
          },
        ),
      ),
    );
  }

  Widget _sectionContent(XlPalette p) {
    switch (_activeSection) {
      case 'model': return _modelSection(p);
      case 'render': return _renderSection(p);
      case 'voice': return _voiceSection(p);
      case 'interface': return _interfaceSection(p);
      case 'channels': return _channelsSection(p);
      case 'memory': return _memorySection(p);
      case 'advanced': return _advancedSection(p);
      case 'about': return _aboutSection(p);
      default: return _modelSection(p);
    }
  }

  Widget _sectionHeader(XlPalette p, String title, String sub, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 38,
            decoration: BoxDecoration(
              gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [color, color.withOpacity(0.4)]),
              borderRadius: BorderRadius.circular(99),
              boxShadow: [BoxShadow(color: color.withOpacity(0.4), blurRadius: 10, spreadRadius: -2)],
            ),
          ),
          const SizedBox(width: 14),
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withOpacity(p.isDark ? 0.14 : 0.10),
              borderRadius: BorderRadius.circular(XlRadius.md),
              border: Border.all(color: color.withOpacity(0.28), width: 1),
              boxShadow: [BoxShadow(color: color.withOpacity(0.20), blurRadius: 16, spreadRadius: -4)],
            ),
            child: Icon(_sectionIcon(), size: 19, color: color),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: TextStyle(
                      fontSize: XlFont.h5,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.normal,
                    )),
                const SizedBox(height: 3),
                Text(sub,
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text3,
                      fontWeight: FontWeight.w500,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
              ],
            ),
          ),
        ],
      ),
    );
  }

  IconData _sectionIcon() {
    final s = _sections.firstWhere((it) => it.key == _activeSection, orElse: () => _sections.first);
    return s.icon;
  }

  Widget _modelSection(XlPalette p) {
    final hw = _hardware;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '模型设置', '选择角色、推理后端与线程配置', p.pink),
        _selectRow(p, '角色人格', '小凌的性格与说话风格（人格预设）', Icons.face_6_rounded,
            _optPersonas, _model, p.pink, (v) async {
          setState(() => _model = v);
          final r = await XlClient.stub.safe(() => XlClient.stub.switchPersona(v));
          if (!mounted) return;
          _showSnack(r?.ok == true ? '人格已切换为「$v」' : '切换人格失败');
        }),
        const SizedBox(height: 12),
        _selectRow(p, '推理后端', '影响响应速度与资源占用', Icons.memory_rounded,
            _optInferBackends, _inferBackend, p.gold, (v) async {
          setState(() => _inferBackend = v);
          await _setOption('model.inference_backend', v);
        }),
        const SizedBox(height: 12),
        _selectRow(p, '推理线程数', '更多线程更快但更耗电', Icons.speed_rounded,
            _optThreads, _threads, p.violet, (v) async {
          setState(() => _threads = v);
          await _setOption('model.threads', v);
        }),
        const SizedBox(height: 12),
        if (hw != null) ...[
          const SizedBox(height: 18),
          _hwInfoPanel(p, hw),
        ],
        const SizedBox(height: 18),
        _infoPanel(p, '推理后端与线程数由上方选项控制；切换模型后会自动重新加载。'),
      ],
    );
  }

  Widget _hwInfoPanel(XlPalette p, pb.HardwareInfo hw) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.memory_rounded, size: 15, color: p.pink),
              const SizedBox(width: 10),
              Text('硬件概览',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
              const Spacer(),
              _tinyChip(p, hw.tier, hw.hasGpu ? p.green : p.blue),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _hwStat(p, '内存', hw.ramLabel, p.pink, hw.ramRatio)),
              const SizedBox(width: 12),
              Expanded(child: _hwStat(p, '显存', hw.vramLabel, p.gold, hw.vramRatio)),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _hwStat(p, 'CPU', hw.cpuLabel, p.violet, hw.cpuRatio)),
              const SizedBox(width: 12),
              Expanded(child: _hwStat(p, '磁盘', hw.diskLabel, p.green, hw.diskRatio)),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: p.pink.withOpacity(p.isDark ? 0.06 : 0.05),
              borderRadius: BorderRadius.circular(XlRadius.sm),
              border: Border.all(color: p.pink.withOpacity(0.18), width: 1),
            ),
            child: Row(
              children: [
                Icon(Icons.lightbulb_outline_rounded, size: 14, color: p.pink),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(hw.recommendedSize,
                      style: TextStyle(
                        fontSize: XlFont.label,
                        color: p.text2,
                        fontWeight: FontWeight.w600,
                        letterSpacing: XlLetterSpacing.wide,
                      )),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _hwStat(XlPalette p, String label, String value, Color color, double progress) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(label,
                style: TextStyle(
                  fontSize: XlFont.micro,
                  color: p.text3,
                  fontWeight: FontWeight.w700,
                  letterSpacing: XlLetterSpacing.wider,
                )),
            const Spacer(),
            Flexible(
              child: Text(value,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: XlFont.label,
                    color: color,
                    fontWeight: FontWeight.w800,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  )),
            ),
          ],
        ),
        const SizedBox(height: 5),
        ClipRRect(
          borderRadius: BorderRadius.circular(2),
          child: LinearProgressIndicator(
            value: progress.clamp(0.0, 1.0),
            minHeight: 3,
            backgroundColor: p.surfaceLo,
            valueColor: AlwaysStoppedAnimation(color),
          ),
        ),
      ],
    );
  }

  Widget _renderSection(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '渲染设置', '调整窗口、动画与 3D 渲染参数', p.gold),
        _selectRow(p, '渲染模式', '默认使用软件光栅，兼容性最好', Icons.blur_on_rounded,
            _optRenderModes, _render, p.gold, (v) async {
          setState(() => _render = v);
          await _setOption('render.backend', v);
        }),
        const SizedBox(height: 12),
        _switchRow(p, '窗口置顶', '让小凌始终显示在最前面', Icons.push_pin_rounded, 'alwaysOnTop', p.pink),
        const SizedBox(height: 12),
        _switchRow(p, '开机自启', '登录系统后自动启动小凌', Icons.power_settings_new_rounded, 'autoStart', p.violet),
        const SizedBox(height: 12),
        _switchRow(p, '启用动画', '关闭后所有过渡效果立即完成（仅本地）', Icons.animation_rounded, 'animations', p.green),
        const SizedBox(height: 12),
        _sliderRow(p, 'opacity', '窗口透明度', Icons.opacity_rounded, p.gold, 0.92),
        const SizedBox(height: 12),
        _sliderRow(p, 'renderQuality', '3D 渲染质量', Icons.high_quality_rounded, p.pink, 0.78),
        const SizedBox(height: 18),
        _infoPanel(p, '降低渲染质量可以显著减少 GPU 占用，适合老机器。'),
      ],
    );
  }

  Widget _voiceSection(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '语音设置', '语音识别与语音合成', p.violet),
        _selectRow(p, '合成音色', _voiceSubtitle(), Icons.graphic_eq_rounded,
            _voiceOpts(), _voiceId, p.violet, (v) async {
          await _applyVoice(v, _voiceName(v));
        }),
        const SizedBox(height: 12),
        _switchRow(p, '语音识别', '允许小凌听到你的声音', Icons.record_voice_over_rounded, 'asr', p.pink),
        const SizedBox(height: 12),
        _switchRow(p, '语音朗读', '聊天后自动朗读回复', Icons.volume_up_rounded, 'tts', p.gold),
        const SizedBox(height: 12),
        _switchRow(p, '阅读模式', '朗读长文本时自动分句', Icons.menu_book_rounded, 'readAloud', p.green),
        const SizedBox(height: 12),
        _switchRow(p, '系统音效', '操作时播放轻提示音（仅本地）', Icons.music_note_rounded, 'sound', p.blue),
        const SizedBox(height: 12),
        _sliderRow(p, 'speed', '语速', Icons.speed_rounded, p.violet, 0.55),
        const SizedBox(height: 12),
        _sliderRow(p, 'volume', '音量', Icons.volume_down_rounded, p.pink, 0.80),
        if (_optVoices.isNotEmpty) ...[
          const SizedBox(height: 18),
          _voiceListPanel(p),
        ],
      ],
    );
  }

  String _voiceSubtitle() {
    if (!_optsLoaded) return '正在读取本机可用音色…';
    final e = _voiceEngines;
    final note = (e['note'] ?? '').toString();
    if (_hostPlatform() == 'android' && note.isNotEmpty) return note;
    if (e['edge_tts'] != true) {
      return '未检测到 edge-tts${note.isNotEmpty ? '，$note' : ''}';
    }
    return '共 ${_optVoices.length} 个 edge-tts 音色，点击下方标签即可切换';
  }

  Widget _voiceListPanel(XlPalette p) {
    final voices = _optVoices;
    if (voices.isEmpty) return const SizedBox.shrink();
    final usable = voices.where((v) => v.available).length;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.graphic_eq_rounded, size: 15, color: p.violet),
              const SizedBox(width: 10),
              Text('可用音色',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
              const Spacer(),
              _tinyChip(p, '$usable / ${voices.length} 可用', p.violet),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: voices.map((v) => _voiceChip(p, v)).toList(),
          ),
        ],
      ),
    );
  }

  String _hostPlatform() {
    if (Platform.isAndroid) return 'android';
    if (Platform.isWindows) return 'windows';
    if (Platform.isMacOS) return 'macos';
    if (Platform.isLinux) return 'linux';
    return 'unknown';
  }

  String _voiceName(String id) {
    for (final v in _optVoices) {
      if (v.id == id) return v.name;
    }
    return id;
  }

  List<_Opt> _voiceOpts() => _optVoices
      .map((v) => _Opt(v.id, v.name, note: v.style, enabled: v.available))
      .toList();

  Widget _voiceChip(XlPalette p, _VoiceOpt v) {
    final color = _genderColor(p, v.gender);
    final active = v.id == _voiceId;
    return Opacity(
      opacity: v.available ? 1.0 : 0.4,
      child: GestureDetector(
        onTap: v.available
            ? () async {
                await _applyVoice(v.id, v.name);
              }
            : null,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: color.withOpacity(p.isDark ? (active ? 0.20 : 0.12) : (active ? 0.14 : 0.08)),
            borderRadius: BorderRadius.circular(XlRadius.pill),
            border: Border.all(
                color: color.withOpacity(active ? 0.6 : 0.28),
                width: active ? 1.6 : 1),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _previewing && active
                  ? SizedBox(
                      width: 11,
                      height: 11,
                      child: CircularProgressIndicator(strokeWidth: 1.6, color: color),
                    )
                  : Container(
                      width: 6,
                      height: 6,
                      decoration: AppTheme.glowDot(color, size: 6),
                    ),
              const SizedBox(width: 8),
              Text(v.name,
                  style: TextStyle(
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w700,
                    color: p.text1,
                    letterSpacing: XlLetterSpacing.wide,
                  )),
              const SizedBox(width: 6),
              Text(v.genderLabel,
                  style: TextStyle(
                    fontSize: XlFont.micro,
                    fontWeight: FontWeight.w700,
                    color: color,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
              if (v.style.isNotEmpty && v.style != 'null') ...[
                const SizedBox(width: 6),
                Text('· ${v.style}',
                    style: TextStyle(
                      fontSize: XlFont.micro,
                      fontWeight: FontWeight.w600,
                      color: p.text3,
                    )),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Color _genderColor(XlPalette p, String gender) {
    final g = gender.toLowerCase();
    if (g.startsWith('f')) return p.pink;
    if (g.startsWith('m')) return p.blue;
    return p.gold;
  }

  Widget _interfaceSection(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '界面设置', '主题、语言与启动行为', p.green),
        _selectRow(p, '主题模式', '深色为默认，浅色更明亮', Icons.brightness_6_rounded,
            _optThemes, _theme, p.green, (v) async {
          setState(() => _theme = v);
          await XlThemeController.instance.set(v,
              pushToBackend: (val) async => await _setOption('ui.theme', val, quiet: true));
          if (!mounted) return;
          _showSnack('主题已切换');
        }),
        const SizedBox(height: 12),
        _selectRow(p, '界面语言', '目前仅简体中文为完整支持', Icons.language_rounded,
            _optLangs, _language, p.gold, (v) async {
          final opt = _optLangs.firstWhere((o) => o.value == v,
              orElse: () => _Opt(v, v));
          if (!opt.enabled) {
            _showSnack('「${opt.label}」尚未完成翻译，当前仍是简体中文');
            return;
          }
          setState(() => _language = v);
          await _setOption('ui.language', v);
        }),
        const SizedBox(height: 12),
        _switchRow(p, '启动动画', '启动时显示小凌的欢迎画面（仅本地）', Icons.movie_filter_rounded, 'splash', p.violet),
        const SizedBox(height: 18),
        _themePreview(p),
      ],
    );
  }

  Widget _themePreview(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('主题预览',
              style: TextStyle(
                fontSize: XlFont.label,
                fontWeight: FontWeight.w800,
                color: p.text3,
                letterSpacing: XlLetterSpacing.ultra,
              )),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                  child: _swatch(p, 'Deep', p.bg, p.pink, _theme == 'dark',
                      () => _pickTheme('dark'))),
              const SizedBox(width: 10),
              Expanded(
                  child: _swatch(p, 'Light', XlPalette.light.bg, XlPalette.light.pink,
                      _theme == 'light', () => _pickTheme('light'))),
              const SizedBox(width: 10),
              Expanded(
                  child: _swatch(p, 'Auto', p.surface, p.gold, _theme == 'system',
                      () => _pickTheme('system'))),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _pickTheme(String v) async {
    setState(() => _theme = v);
    await XlThemeController.instance.set(v,
        pushToBackend: (val) async => await _setOption('ui.theme', val, quiet: true));
    if (!mounted) return;
    final label = _optThemes
        .firstWhere((o) => o.value == v, orElse: () => _Opt(v, v))
        .label;
    _showSnack('主题已切换为「$label」');
  }

  Widget _swatch(XlPalette p, String label, Color bg, Color accent, bool active,
      VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: _swatchBody(p, label, bg, accent, active),
    );
  }

  Widget _swatchBody(XlPalette p, String label, Color bg, Color accent, bool active) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(XlRadius.md),
        border: Border.all(
          color: active ? accent.withOpacity(0.55) : p.edge,
          width: active ? 1.6 : 1,
        ),
        boxShadow: active ? [BoxShadow(color: accent.withOpacity(0.35), blurRadius: 18, spreadRadius: -4)] : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 28,
            height: 5,
            decoration: BoxDecoration(color: accent, borderRadius: BorderRadius.circular(99)),
          ),
          const SizedBox(height: 6),
          Container(
            width: 42,
            height: 3,
            decoration: BoxDecoration(color: accent.withOpacity(0.5), borderRadius: BorderRadius.circular(99)),
          ),
          const SizedBox(height: 10),
          Text(label,
              style: TextStyle(
                fontSize: XlFont.micro,
                fontWeight: FontWeight.w800,
                color: accent,
                letterSpacing: XlLetterSpacing.wider,
              )),
        ],
      ),
    );
  }

  Widget _channelsSection(XlPalette p) {
    const meta = <Map<String, Object>>[
      {'name': 'Webhook', 'desc': '接收外部系统推送', 'icon': Icons.webhook_rounded},
      {'name': 'Telegram', 'desc': '通过 Bot 收发消息', 'icon': Icons.send_rounded},
      {'name': 'Discord', 'desc': '接入 Discord 服务器', 'icon': Icons.discord_rounded},
      {'name': '飞书', 'desc': '飞书机器人', 'icon': Icons.business_center_rounded},
      {'name': 'WhatsApp', 'desc': 'Business API 推送消息', 'icon': Icons.chat_rounded},
      {'name': 'Slack', 'desc': 'Webhook / Bot 推送到频道', 'icon': Icons.tag_rounded},
      {'name': 'Signal', 'desc': 'signal-cli REST 发送', 'icon': Icons.enhanced_encryption_rounded},
      {'name': '邮件', 'desc': 'SMTP 收发邮件', 'icon': Icons.email_rounded},
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '多平台通道', '把消息推送到你的常用平台（本地开关）', p.gold),
        ...meta.map((e) {
          final name = e['name'] as String;
          final on = _channels[name] ?? false;
          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: AppTheme.neuXs(context, r: XlRadius.lg),
            child: Row(children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: on ? p.gold.withOpacity(p.isDark ? 0.18 : 0.12) : p.surfaceLo,
                  borderRadius: BorderRadius.circular(XlRadius.md),
                  border: Border.all(color: on ? p.gold.withOpacity(0.30) : p.edgeSoft, width: 1),
                ),
                child: Icon(e['icon'] as IconData, color: on ? p.gold : p.text3, size: 18),
              ),
              const SizedBox(width: 14),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(name, style: TextStyle(fontSize: XlFont.caption, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.wide)),
                const SizedBox(height: 3),
                Text(e['desc'] as String, style: TextStyle(fontSize: XlFont.label, color: p.text3, fontWeight: FontWeight.w500, letterSpacing: XlLetterSpacing.wide)),
                const SizedBox(height: 4),
                Text('未配置 · 通道接入待后端支持',
                    style: TextStyle(
                        fontSize: XlFont.micro,
                        color: p.decor,
                        fontWeight: FontWeight.w800,
                        letterSpacing: XlLetterSpacing.wider)),
              ])),
              _toggle(p, false, p.gold, null),
            ]),
            ),
          );
        }).toList(),
      ],
    );
  }

  Future<void> _loadMemStats() async {
    if (_memLoading) return;
    setState(() => _memLoading = true);
    try {
      final raw = await XlClient.stub.safe(() =>
          XlClient.stub.commandOutput('memory:stats'));
      if (!mounted) return;
      Map<String, dynamic> data = const {};
      if (raw != null && raw.trim().isNotEmpty) {
        try {
          final decoded = jsonDecode(raw);
          if (decoded is Map<String, dynamic>) data = decoded;
        } catch (_) {}
      }
      setState(() {
        _memStats = data;
        _memLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _memLoading = false);
    }
  }

  Future<void> _forgetOld() async {
    if (_forgettingOld) return;
    setState(() => _forgettingOld = true);
    try {
      final raw = await XlClient.stub.safe(() =>
          XlClient.stub.commandOutput('memory:forget 30'));
      if (!mounted) return;
      int removed = 0;
      if (raw != null && raw.trim().isNotEmpty) {
        try {
          final decoded = jsonDecode(raw);
          if (decoded is Map) removed = (decoded['removed'] as num?)?.toInt() ?? 0;
        } catch (_) {}
      }
      _showSnack('已清理 $removed 条旧记忆');
      await _loadMemStats();
    } finally {
      if (mounted) setState(() => _forgettingOld = false);
    }
  }

  void _openGraphPanel() {
    final p = XlPalette.of(context);
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: p.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(XlRadius.xl)),
        insetPadding: const EdgeInsets.all(24),
        child: Container(
          width: 640,
          height: 560,
          padding: const EdgeInsets.all(20),
          child: const KnowledgeGraphPanel(),
        ),
      ),
    );
  }

  Widget _memorySection(XlPalette p) {
    final mem = (_memStats['memory'] as Map?)?.cast<String, dynamic>() ?? const {};
    final graph = (_memStats['graph'] as Map?)?.cast<String, dynamic>() ?? const {};
    final total = (mem['total'] as num?)?.toInt() ?? 0;
    final entities = (graph['entities'] as num?)?.toInt() ?? 0;
    final relations = (graph['relations'] as num?)?.toInt() ?? 0;
    final tagDist = (mem['tag_distribution'] as Map?) ?? const {};
    final recent = (mem['recent'] as List?) ?? const [];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '记忆与知识', '小凌的长期记忆与知识图谱', p.pink),
        Row(
          children: [
            Expanded(child: _memStatCard(p, '长期记忆', '$total', Icons.history_rounded, p.pink)),
            const SizedBox(width: 10),
            Expanded(child: _memStatCard(p, '实体', '$entities', Icons.category_rounded, p.gold)),
            const SizedBox(width: 10),
            Expanded(child: _memStatCard(p, '关系', '$relations', Icons.link_rounded, p.violet)),
          ],
        ),
        const SizedBox(height: 14),
        if (tagDist.isNotEmpty) ...[
          Container(
            padding: const EdgeInsets.all(14),
            decoration: AppTheme.neuXs(context, r: XlRadius.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('标签分布',
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text3,
                      fontWeight: FontWeight.w700,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: tagDist.entries.take(10).map((e) => Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: p.pink.withOpacity(0.12),
                          borderRadius: BorderRadius.circular(99),
                          border: Border.all(color: p.pink.withOpacity(0.3)),
                        ),
                        child: Text('${e.key} × ${e.value}',
                            style: TextStyle(
                              color: p.text2,
                              fontSize: XlFont.label,
                              fontWeight: FontWeight.w600,
                            )),
                      )).toList(),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ],
        if (recent.isNotEmpty) ...[
          Container(
            padding: const EdgeInsets.all(14),
            decoration: AppTheme.neuXs(context, r: XlRadius.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('最近记忆',
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text3,
                      fontWeight: FontWeight.w700,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                const SizedBox(height: 10),
                ...recent.take(5).map((r) {
                  final m = (r as Map).cast<String, dynamic>();
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.circle, size: 6, color: p.gold),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            (m['content']?.toString() ?? '').isEmpty
                                ? '（空）'
                                : m['content'].toString(),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: p.text2,
                              fontSize: XlFont.label,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                  );
                }),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ],
        _actionRow(p, '知识图谱可视化', '查看实体节点与关系连线', Icons.hub_outlined, p.pink, () => _openGraphPanel()),
        const SizedBox(height: 10),
        _actionRow(p, '清理旧记忆', _forgettingOld ? '正在清理…' : '删除 30 天前且重要度低的记忆',
            Icons.cleaning_services_outlined, p.gold, () => _forgetOld()),
        const SizedBox(height: 10),
        _actionRow(p, '刷新统计', '重新拉取记忆与图谱数据', Icons.refresh_rounded, p.blue, () => _loadMemStats()),
      ],
    );
  }

  Widget _memStatCard(XlPalette p, String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neuXs(context, r: XlRadius.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(height: 8),
          Text(value,
              style: TextStyle(
                fontSize: XlFont.h4,
                fontWeight: FontWeight.w800,
                color: p.text1,
              )),
          const SizedBox(height: 2),
          Text(label,
              style: TextStyle(
                fontSize: XlFont.label,
                color: p.text3,
                fontWeight: FontWeight.w600,
                letterSpacing: XlLetterSpacing.wide,
              )),
        ],
      ),
    );
  }

  Widget _advancedSection(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '高级设置', '数据、更新与诊断', p.blue),
        _switchRow(p, '自动更新', '启动时检查是否有新版本（仅本地）', Icons.system_update_alt_rounded, 'autoUpdate', p.green),
        const SizedBox(height: 12),
        _switchRow(p, '崩溃上报', '发送匿名崩溃日志帮助我们修复问题（仅本地）', Icons.bug_report_outlined, 'crash', p.gold),
        const SizedBox(height: 12),
        _switchRow(p, '使用统计', '发送匿名功能使用数据（仅本地）', Icons.analytics_outlined, 'telemetry', p.red),
        const SizedBox(height: 18),
        Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _actionRow(p, '清理缓存', _clearingCache ? '正在清理…' : '当前占用 $_cacheSize', Icons.cleaning_services_outlined, p.pink, () => _clearCache()),
            AnimatedSize(
              duration: XlDuration.normal,
              curve: XlCurve.standard,
              child: _clearingCache
                  ? Padding(
                      padding: const EdgeInsets.only(top: 8, left: 4, right: 4),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(99),
                        child: LinearProgressIndicator(minHeight: 3, color: p.pink, backgroundColor: p.surfaceLo),
                      ),
                    )
                  : const SizedBox(width: double.infinity),
            ),
            const SizedBox(height: 8),
            _cacheBreakdown(p),
          ],
        ),
        const SizedBox(height: 10),
        _actionRow(p, '导出数据', '导出对话、记忆和配置', Icons.upload_file_rounded, p.violet, () => _exportData()),
        const SizedBox(height: 10),
        _actionRow(p, '导入数据', '从备份文件恢复', Icons.download_rounded, p.blue, () => _importData()),
        const SizedBox(height: 10),
        _actionRow(p, '导出配置快照', '把当前本地设置打包成 JSON 备份', Icons.backup_table_rounded, p.green, () => _exportConfigSnapshot()),
        const SizedBox(height: 10),
        _actionRow(p, 'MCP 工具连接', '连接外部 MCP 服务器扩展 AI 能力', Icons.hub_rounded, p.pink, () => _openMcpPanel()),
        const SizedBox(height: 10),
        _actionRow(p, '安全中心', '权限管理、目录保护与操作审计', Icons.shield_outlined, p.gold, () => _openSecurityPanel()),
        const SizedBox(height: 10),
        _actionRow(p, '重置所有设置', '恢复出厂默认，不可撤销', Icons.restart_alt_rounded, p.red, () => _resetSettings()),
        const SizedBox(height: 14),
        _diagGroup(p),
      ],
    );
  }

  Widget _aboutSection(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '关于小凌', '版本、协议与开源信息', p.pink),
        _aboutHero(p),
        const SizedBox(height: 14),
        _aboutExpandCard(p),
        const SizedBox(height: 18),
        _aboutRow(p, '版本', 'v0.0.1', Icons.tag_rounded, valueColor: p.gold),
        const SizedBox(height: 10),
        _aboutRow(p, '构建', 'flutter-v0.0.1 · debug', Icons.build_rounded, valueColor: p.gold),
        const SizedBox(height: 10),
        _aboutRow(p, '架构', 'Flutter + Python + gRPC', Icons.architecture_rounded),
        const SizedBox(height: 10),
        _aboutRow(p, '开源协议', 'MIT License', Icons.gavel_rounded),
        const SizedBox(height: 18),
        _systemInfoPanel(p),
        const SizedBox(height: 18),
        Row(
          children: [
            Expanded(child: _aboutLink(p, 'GitHub', Icons.code_rounded, p.pink)),
            const SizedBox(width: 10),
            Expanded(child: _aboutLink(p, '文档', Icons.menu_book_rounded, p.gold)),
            const SizedBox(width: 10),
            Expanded(child: _aboutLink(p, '反馈', Icons.bug_report_outlined, p.violet)),
          ],
        ),
      ],
    );
  }

  Widget _aboutExpandCard(XlPalette p) {
    return _Pressable(
      onTap: () => setState(() => _aboutExpanded = !_aboutExpanded),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: AppTheme.neuXs(context, r: XlRadius.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.expand_more_rounded, size: 16, color: p.pink),
                const SizedBox(width: 8),
                Text('开源协议与依赖详情',
                    style: TextStyle(fontSize: XlFont.captionSm, fontWeight: FontWeight.w800, color: p.text1, letterSpacing: XlLetterSpacing.wide)),
                const Spacer(),
                Text(_aboutExpanded ? '收起' : '展开',
                    style: TextStyle(fontSize: XlFont.label, fontWeight: FontWeight.w700, color: p.pink, letterSpacing: XlLetterSpacing.wider)),
              ],
            ),
            AnimatedCrossFade(
              duration: XlDuration.normal,
              crossFadeState: _aboutExpanded ? CrossFadeState.showSecond : CrossFadeState.showFirst,
              firstChild: const SizedBox(height: 0, width: double.infinity),
              secondChild: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SizedBox(height: 14),
                  _aboutRow(p, 'Flutter SDK', '3.x · stable', Icons.flutter_dash_rounded),
                  const SizedBox(height: 8),
                  _aboutRow(p, 'gRPC', 'grpc-dart 4.x', Icons.hub_rounded),
                  const SizedBox(height: 8),
                  _aboutRow(p, '路径管理', 'path_provider', Icons.folder_rounded),
                  const SizedBox(height: 8),
                  _aboutRow(p, '项目地址', 'github.com/xiaoling/xl', Icons.link_rounded, valueColor: p.blue),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _aboutHero(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: AppTheme.brand(context, r: XlRadius.xxl),
      child: Row(
        children: [
          AnimatedBuilder(
            animation: _pulseCtrl,
            builder: (_, __) {
              final t = _pulseCtrl.value;
              return Stack(
                alignment: Alignment.center,
                children: [
                  Container(
                    width: 72 + t * 14,
                    height: 72 + t * 14,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: Colors.white.withOpacity((1 - t) * 0.22),
                    ),
                  ),
                  Container(
                    width: 72,
                    height: 72,
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(p.isDark ? 0.22 : 0.32),
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white.withOpacity(0.5), width: 2),
                    ),
                    child: Icon(Icons.auto_awesome_rounded, size: 30, color: p.btnInk),
                  ),
                ],
              );
            },
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('小凌 XIAOLING',
                    style: TextStyle(
                      fontSize: XlFont.h4,
                      fontWeight: FontWeight.w800,
                      color: p.btnInk,
                      letterSpacing: XlLetterSpacing.normal,
                    )),
                const SizedBox(height: 4),
                Text('会成长的数字生命',
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      color: p.btnInk.withOpacity(0.75),
                      fontWeight: FontWeight.w600,
                      letterSpacing: XlLetterSpacing.wider,
                    )),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(p.isDark ? 0.24 : 0.18),
                        borderRadius: BorderRadius.circular(XlRadius.pill),
                      ),
                      child: Text('v0.0.1',
                          style: TextStyle(
                            fontSize: XlFont.micro,
                            fontWeight: FontWeight.w800,
                            color: p.btnInk,
                            letterSpacing: XlLetterSpacing.ultra,
                          )),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(p.isDark ? 0.24 : 0.18),
                        borderRadius: BorderRadius.circular(XlRadius.pill),
                      ),
                      child: Text('MIT',
                          style: TextStyle(
                            fontSize: XlFont.micro,
                            fontWeight: FontWeight.w800,
                            color: p.btnInk,
                            letterSpacing: XlLetterSpacing.ultra,
                          )),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _aboutRow(XlPalette p, String label, String value, IconData icon, {Color? valueColor}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: AppTheme.neuXs(context, r: XlRadius.md),
      child: Row(
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              color: p.pink.withOpacity(p.isDark ? 0.14 : 0.10),
              borderRadius: BorderRadius.circular(XlRadius.sm),
              border: Border.all(color: p.pink.withOpacity(0.28), width: 1),
            ),
            child: Icon(icon, size: 14, color: p.pink),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(label,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text2,
                  fontWeight: FontWeight.w600,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          ),
          Text(value,
              style: TextStyle(
                fontSize: XlFont.captionSm,
                color: valueColor ?? p.text1,
                fontWeight: FontWeight.w800,
                letterSpacing: XlLetterSpacing.wide,
                fontFeatures: const [FontFeature.tabularFigures()],
              )),
        ],
      ),
    );
  }

  Widget _aboutLink(XlPalette p, String label, IconData icon, Color color) {
    return _Pressable(
      onTap: () => _showSnack('$label 功能开发中'),
      child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: AppTheme.neuXs(context, r: XlRadius.md),
          child: Column(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                  borderRadius: BorderRadius.circular(XlRadius.sm),
                  border: Border.all(color: color.withOpacity(0.28), width: 1),
                ),
                child: Icon(icon, size: 15, color: color),
              ),
              const SizedBox(height: 8),
              Text(label,
                  style: TextStyle(
                    fontSize: XlFont.label,
                    fontWeight: FontWeight.w800,
                    color: p.text2,
                    letterSpacing: XlLetterSpacing.wider,
                  )),
            ],
          ),
        ),
      );
  }

  Widget _selectRow(XlPalette p, String title, String sub, IconData icon, List<_Opt> options, String current, Color color, ValueChanged<String> onChanged) {
    if (!_matches(title, sub)) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: color.withOpacity(p.isDark ? 0.14 : 0.10),
              borderRadius: BorderRadius.circular(XlRadius.md),
              border: Border.all(color: color.withOpacity(0.28), width: 1),
            ),
            child: Icon(icon, size: 17, color: color),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: TextStyle(
                      fontSize: XlFont.caption,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                const SizedBox(height: 3),
                Text(sub,
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text3,
                      fontWeight: FontWeight.w500,
                      letterSpacing: XlLetterSpacing.wide,
                      height: XlLineHeight.relaxed,
                    )),
              ],
            ),
          ),
          const SizedBox(width: 14),
          _dropdown(p, options, current, color, onChanged),
        ],
      ),
    );
  }

  Widget _dropdown(XlPalette p, List<_Opt> options, String current, Color color, ValueChanged<String> onChanged) {
    if (options.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: Text('加载中…',
            style: TextStyle(
              fontSize: XlFont.label,
              color: p.text3,
              fontWeight: FontWeight.w600,
            )),
      );
    }
    final enabled = options.where((o) => o.enabled).toList();
    var safe = current;
    if (!options.any((o) => o.value == safe)) {
      safe = (enabled.isNotEmpty ? enabled.first : options.first).value;
    }
    final safeOpt = options.firstWhere((o) => o.value == safe,
        orElse: () => options.first);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      decoration: AppTheme.sunkenXs(context, r: XlRadius.md),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: safe,
          isDense: true,
          icon: Icon(Icons.expand_more_rounded, size: 16, color: color),
          dropdownColor: p.surfaceHi,
          borderRadius: BorderRadius.circular(XlRadius.md),
          style: TextStyle(
            fontSize: XlFont.captionSm,
            fontWeight: FontWeight.w700,
            color: p.text1,
            letterSpacing: XlLetterSpacing.wide,
          ),
          items: options.map((o) => DropdownMenuItem<String>(
            value: o.value,
            enabled: o.enabled,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(o.label,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w700,
                      color: !o.enabled
                          ? p.text3
                          : (o.value == safe ? color : p.text1),
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                if (!o.enabled) ...[
                  const SizedBox(width: 6),
                  Text('不可用',
                      style: TextStyle(
                        fontSize: XlFont.micro,
                        fontWeight: FontWeight.w700,
                        color: p.text3,
                      )),
                ],
              ],
            ),
          )).toList(),
          onChanged: safeOpt.enabled
              ? (v) {
                  if (v != null) onChanged(v);
                }
              : null,
        ),
      ),
    );
  }

  Widget _switchRow(XlPalette p, String title, String sub, IconData icon, String key, Color color) {
    if (!_matches(title, sub)) return const SizedBox.shrink();
    final on = _toggles[key] ?? false;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: on ? color.withOpacity(p.isDark ? 0.18 : 0.12) : p.surfaceLo,
              borderRadius: BorderRadius.circular(XlRadius.md),
              border: Border.all(
                color: on ? color.withOpacity(0.30) : p.edgeSoft,
                width: 1,
              ),
            ),
            child: Icon(icon, size: 17, color: on ? color : p.text3),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: TextStyle(
                      fontSize: XlFont.caption,
                      fontWeight: FontWeight.w800,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
                const SizedBox(height: 3),
                Text(sub,
                    style: TextStyle(
                      fontSize: XlFont.label,
                      color: p.text3,
                      fontWeight: FontWeight.w500,
                      letterSpacing: XlLetterSpacing.wide,
                      height: XlLineHeight.relaxed,
                    )),
              ],
            ),
          ),
          const SizedBox(width: 14),
          _toggle(p, on, color, () => _onToggleChanged(key, on)),
        ],
      ),
    );
  }

  void _onToggleChanged(String key, bool oldValue) {
    final newValue = !oldValue;
    setState(() => _toggles[key] = newValue);
    _history.add(_SettingChange(key, oldValue));
    _logChange(key, newValue);
    if (_history.length > 10) _history.removeAt(0);
    _pushToggleToBackend(key, newValue);
    _persistChannels();
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(milliseconds: 2200),
        content: const Text('设置已保存', style: TextStyle(fontWeight: FontWeight.w600)),
        action: SnackBarAction(
          label: '撤销',
          textColor: XlPalette.of(context).pink,
          onPressed: () {
            if (_history.isEmpty) return;
            final last = _history.removeLast();
            setState(() => _toggles[last.key] = last.oldValue);
          },
        ),
      ));
  }

  Future<void> _pushToggleToBackend(String key, bool value) async {
    final req = pb.SettingsRequest();
    switch (key) {
      case 'alwaysOnTop':
        req.alwaysOnTop = value;
        break;
      case 'autoStart':
        req.autoStart = value;
        break;
      case 'asr':
        req.asrEnabled = value;
        break;
      case 'tts':
        req.ttsEnabled = value;
        break;
      case 'readAloud':
        req.readAloudMode = value;
        break;
      default:
        return;
    }
    await XlClient.stub.safe(() => XlClient.stub.updateSettings(req));
    await XlClient.stub.safe(() => XlClient.stub.settings());
  }

  Widget _toggle(XlPalette p, bool on, Color color, VoidCallback? onTap) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedOpacity(
        opacity: onTap == null ? 0.45 : 1.0,
        duration: XlDuration.fast,
        child: AnimatedContainer(
        duration: XlDuration.normal,
        curve: XlCurve.springSoft,
        width: 50,
        height: 28,
        decoration: BoxDecoration(
          gradient: on ? LinearGradient(colors: [color, color.withOpacity(0.8)]) : null,
          color: on ? null : p.surfaceLo,
          borderRadius: BorderRadius.circular(XlRadius.pill),
          border: Border.all(
            color: on
                ? Colors.white.withOpacity(p.isDark ? 0.34 : 0.22)
                : p.shDark.withOpacity(p.isDark ? 0.32 : 0.14),
            width: 1,
          ),
          boxShadow: on
              ? [...p.raisedXxs, BoxShadow(color: color.withOpacity(0.35), blurRadius: 12, spreadRadius: -2)]
              : p.sunkenXs,
        ),
        child: AnimatedAlign(
          duration: XlDuration.normal,
          curve: XlCurve.springSoft,
          alignment: on ? Alignment.centerRight : Alignment.centerLeft,
          child: AnimatedContainer(
            duration: XlDuration.normal,
            curve: XlCurve.standard,
            margin: const EdgeInsets.all(3),
            width: 20,
            height: 20,
            decoration: BoxDecoration(
              color: on ? Colors.white : p.surfaceHi,
              shape: BoxShape.circle,
              border: Border.all(color: on ? color.withOpacity(0.55) : Colors.transparent, width: 1.5),
              boxShadow: on
                  ? [...p.raisedXxs, BoxShadow(color: color.withOpacity(0.5), blurRadius: 8, spreadRadius: -1)]
                  : p.raisedXxs,
            ),
          ),
        ),
        ),
      ),
    );
  }

  Widget _sliderRow(XlPalette p, String key, String label, IconData icon,
      Color color, double fallback) {
    if (!_matches(label, '')) return const SizedBox.shrink();
    final spec = _optSliders[key];
    if (spec is Map) {
      final plats = spec['platforms'];
      if (plats is List && plats.isNotEmpty) {
        final me = _hostPlatform();
        if (!plats.map((e) => e.toString()).contains(me)) {
          return const SizedBox.shrink();
        }
      }
    }
    var minV = 0.0;
    var fb = fallback;
    if (spec is Map) {
      final mn = spec['min'];
      final df = spec['default'];
      if (mn is num) minV = mn.toDouble().clamp(0.0, 1.0);
      if (df is num) fb = df.toDouble().clamp(0.0, 1.0);
    }
    final value = (_sliders[key] ?? fb).clamp(minV, 1.0);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                  borderRadius: BorderRadius.circular(XlRadius.sm),
                  border: Border.all(color: color.withOpacity(0.28), width: 1),
                ),
                child: Icon(icon, size: 14, color: color),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(label,
                    style: TextStyle(
                      fontSize: XlFont.captionSm,
                      fontWeight: FontWeight.w700,
                      color: p.text1,
                      letterSpacing: XlLetterSpacing.wide,
                    )),
              ),
              Text('${(value * 100).toInt()}%',
                  style: TextStyle(
                    fontSize: XlFont.captionSm,
                    fontWeight: FontWeight.w800,
                    color: color,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  )),
            ],
          ),
          const SizedBox(height: 10),
          _sliderTrack(p, value, color, minV, (v) => _setSlider(key, v)),
        ],
      ),
    );
  }

  Widget _sliderTrack(XlPalette p, double value, Color color, double minV,
      ValueChanged<double> onChanged) {
    const knob = 18.0;
    const trackH = 8.0;
    const rowH = knob + 6;
    final lo = minV.clamp(0.0, 0.95);
    final span = 1.0 - lo;
    return LayoutBuilder(
      builder: (context, c) {
        final w = c.maxWidth;
        final v = span <= 0 ? 1.0 : ((value - lo) / span).clamp(0.0, 1.0);
        void handle(Offset local) {
          if (w <= 0) return;
          final ratio = (local.dx / w).clamp(0.0, 1.0);
          onChanged((lo + ratio * span).clamp(0.0, 1.0));
        }

        return MouseRegion(
          cursor: SystemMouseCursors.click,
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTapDown: (d) => handle(d.localPosition),
            onHorizontalDragStart: (d) => handle(d.localPosition),
            onHorizontalDragUpdate: (d) => handle(d.localPosition),
            child: SizedBox(
              height: rowH,
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Positioned(
                    left: 0,
                    right: 0,
                    top: (rowH - trackH) / 2,
                    child: Container(
                      height: trackH,
                      decoration: BoxDecoration(
                        color: p.surfaceLo,
                        borderRadius: BorderRadius.circular(99),
                        boxShadow: p.sunkenXxs,
                      ),
                    ),
                  ),
                  Positioned(
                    left: 0,
                    top: (rowH - trackH) / 2,
                    width: w * v,
                    height: trackH,
                    child: Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                            colors: [color.withOpacity(0.7), color]),
                        borderRadius: BorderRadius.circular(99),
                        boxShadow: [
                          BoxShadow(
                              color: color.withOpacity(0.35),
                              blurRadius: 10,
                              spreadRadius: -2)
                        ],
                      ),
                    ),
                  ),
                  Positioned(
                    left: (w - knob) * v,
                    top: (rowH - knob) / 2,
                    child: Container(
                      width: knob,
                      height: knob,
                      decoration: BoxDecoration(
                        color: p.surfaceHi,
                        shape: BoxShape.circle,
                        border:
                            Border.all(color: color.withOpacity(0.55), width: 1.5),
                        boxShadow: [
                          ...p.raisedXs,
                          BoxShadow(
                              color: color.withOpacity(0.35),
                              blurRadius: 10,
                              spreadRadius: -1)
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _actionRow(XlPalette p, String title, String sub, IconData icon, Color color, VoidCallback onTap) {
    if (!_matches(title, sub)) return const SizedBox.shrink();
    return _Pressable(
      onTap: onTap,
      tint: p.pink.withOpacity(0.06),
      child: Container(
          padding: const EdgeInsets.all(16),
          decoration: AppTheme.neuXs(context, r: XlRadius.lg),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: color.withOpacity(p.isDark ? 0.14 : 0.10),
                  borderRadius: BorderRadius.circular(XlRadius.md),
                  border: Border.all(color: color.withOpacity(0.28), width: 1),
                ),
                child: Icon(icon, size: 17, color: color),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: TextStyle(
                          fontSize: XlFont.caption,
                          fontWeight: FontWeight.w800,
                          color: p.text1,
                          letterSpacing: XlLetterSpacing.wide,
                        )),
                    const SizedBox(height: 3),
                    Text(sub,
                        style: TextStyle(
                          fontSize: XlFont.label,
                          color: p.text3,
                          fontWeight: FontWeight.w500,
                          letterSpacing: XlLetterSpacing.wide,
                        )),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, size: 16, color: p.decor),
            ],
          ),
        ),
      );
  }

  Widget _cacheBreakdown(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppTheme.neuXs(context, r: XlRadius.md),
      child: Column(
        children: [
          _cacheRow(p, '临时缓存目录', _cacheSize, Icons.folder_special_rounded, p.pink),
          const SizedBox(height: 8),
          _cacheRow(p, '对话历史', '未知', Icons.chat_bubble_outline_rounded, p.violet),
          const SizedBox(height: 8),
          _cacheRow(p, '模型文件缓存', '未知', Icons.memory_rounded, p.gold),
        ],
      ),
    );
  }

  Widget _cacheRow(XlPalette p, String label, String value, IconData icon, Color color) {
    return Row(
      children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 10),
        Text(label,
            style: TextStyle(fontSize: XlFont.label, color: p.text2, fontWeight: FontWeight.w600, letterSpacing: XlLetterSpacing.wide)),
        const Spacer(),
        Text(value,
            style: TextStyle(fontSize: XlFont.label, color: color, fontWeight: FontWeight.w800, fontFeatures: const [FontFeature.tabularFigures()])),
      ],
    );
  }

  Widget _diagGroup(XlPalette p) {
    return Container(
      decoration: AppTheme.neuXs(context, r: XlRadius.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _Pressable(
            onTap: () => setState(() => _diagExpanded = !_diagExpanded),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: p.blue.withOpacity(p.isDark ? 0.14 : 0.10),
                      borderRadius: BorderRadius.circular(XlRadius.md),
                      border: Border.all(color: p.blue.withOpacity(0.28), width: 1),
                    ),
                    child: Icon(Icons.history_rounded, size: 17, color: p.blue),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('诊断与变更日志',
                            style: TextStyle(
                                fontSize: XlFont.caption,
                                fontWeight: FontWeight.w800,
                                color: p.text1,
                                letterSpacing: XlLetterSpacing.wide)),
                        const SizedBox(height: 3),
                        Text('最近的开关改动与运行时信息',
                            style: TextStyle(
                                fontSize: XlFont.label,
                                color: p.text3,
                                fontWeight: FontWeight.w500,
                                letterSpacing: XlLetterSpacing.wide)),
                      ],
                    ),
                  ),
                  AnimatedRotation(
                    turns: _diagExpanded ? 0.5 : 0.0,
                    duration: XlDuration.normal,
                    child: Icon(Icons.expand_more_rounded, size: 18, color: p.decor),
                  ),
                ],
              ),
            ),
          ),
          AnimatedCrossFade(
            duration: XlDuration.normal,
            crossFadeState: _diagExpanded ? CrossFadeState.showSecond : CrossFadeState.showFirst,
            firstChild: const SizedBox(width: double.infinity),
            secondChild: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _changeLogPanel(p),
                  const SizedBox(height: 12),
                  _systemInfoPanel(p),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _changeLogPanel(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.md),
        boxShadow: p.sunkenXs,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.recent_actors_rounded, size: 14, color: p.gold),
              const SizedBox(width: 8),
              Text('最近变更',
                  style: TextStyle(
                      fontSize: XlFont.label,
                      fontWeight: FontWeight.w800,
                      color: p.text2,
                      letterSpacing: XlLetterSpacing.wide)),
              const Spacer(),
              Text('${_changeLog.length} 条',
                  style: TextStyle(
                      fontSize: XlFont.micro,
                      fontWeight: FontWeight.w700,
                      color: p.decor,
                      letterSpacing: XlLetterSpacing.wider)),
            ],
          ),
          const SizedBox(height: 10),
          if (_changeLog.isEmpty)
            Text('暂无变更记录，修改任意开关后会记录在这里',
                style: TextStyle(
                    fontSize: XlFont.label,
                    color: p.decor,
                    fontWeight: FontWeight.w500,
                    letterSpacing: XlLetterSpacing.wide))
          else
            for (final e in _changeLog.take(6))
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _changeRow(p, e),
              ),
        ],
      ),
    );
  }

  Widget _changeRow(XlPalette p, _ChangeRecord e) {
    final color = e.value ? p.green : p.decor;
    return Row(
      children: [
        Icon(e.value ? Icons.toggle_on_rounded : Icons.toggle_off_rounded, size: 14, color: color),
        const SizedBox(width: 8),
        Expanded(
          child: Text(_labelForKey(e.key),
              style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.text2,
                  fontWeight: FontWeight.w600,
                  letterSpacing: XlLetterSpacing.wide)),
        ),
        Text(e.value ? '开启' : '关闭',
            style: TextStyle(
                fontSize: XlFont.label,
                color: color,
                fontWeight: FontWeight.w800,
                letterSpacing: XlLetterSpacing.wide)),
        const SizedBox(width: 10),
        Text(_fmtClock(e.time),
            style: TextStyle(
                fontSize: XlFont.micro,
                color: p.decor,
                fontWeight: FontWeight.w700,
                fontFeatures: const [FontFeature.tabularFigures()],
                letterSpacing: XlLetterSpacing.wider)),
      ],
    );
  }

  Widget _systemInfoPanel(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.md),
        boxShadow: p.sunkenXs,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.memory_rounded, size: 14, color: p.violet),
              const SizedBox(width: 8),
              Text('运行时信息',
                  style: TextStyle(
                      fontSize: XlFont.label,
                      fontWeight: FontWeight.w800,
                      color: p.text2,
                      letterSpacing: XlLetterSpacing.wide)),
            ],
          ),
          const SizedBox(height: 10),
          _sysRow(p, '操作系统', Platform.operatingSystem, Icons.desktop_windows_rounded),
          const SizedBox(height: 6),
          _sysRow(p, '系统版本', Platform.operatingSystemVersion.split(' ').take(2).join(' '), Icons.badge_rounded),
          const SizedBox(height: 6),
          _sysRow(p, 'CPU 核心', '${Platform.numberOfProcessors} 核', Icons.developer_board_rounded),
          const SizedBox(height: 6),
          _sysRow(p, '分隔符', Platform.pathSeparator, Icons.folder_rounded),
        ],
      ),
    );
  }

  Widget _sysRow(XlPalette p, String label, String value, IconData icon) {
    return Row(
      children: [
        Icon(icon, size: 13, color: p.text3),
        const SizedBox(width: 10),
        Text(label,
            style: TextStyle(
                fontSize: XlFont.label,
                color: p.text2,
                fontWeight: FontWeight.w600,
                letterSpacing: XlLetterSpacing.wide)),
        const Spacer(),
        Flexible(
          child: Text(value,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.text1,
                  fontWeight: FontWeight.w800,
                  letterSpacing: XlLetterSpacing.wide)),
        ),
      ],
    );
  }

  Widget _infoPanel(XlPalette p, String text) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: p.pink.withOpacity(p.isDark ? 0.06 : 0.05),
        borderRadius: BorderRadius.circular(XlRadius.md),
        border: Border.all(color: p.pink.withOpacity(0.18), width: 1),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline_rounded, size: 15, color: p.pink.withOpacity(0.8)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(text,
                style: TextStyle(
                  fontSize: XlFont.label,
                  color: p.text2,
                  fontWeight: FontWeight.w500,
                  height: XlLineHeight.relaxed,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          ),
        ],
      ),
    );
  }

  Widget _tinyChip(XlPalette p, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(p.isDark ? 0.14 : 0.10),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: color.withOpacity(0.28), width: 1),
      ),
      child: Text(text,
          style: TextStyle(
            fontSize: XlFont.micro,
            fontWeight: FontWeight.w800,
            color: color,
            letterSpacing: XlLetterSpacing.ultra,
          )),
    );
  }
}

class _Section {
  final String key;
  final String label;
  final IconData icon;
  final String color;
  const _Section(this.key, this.label, this.icon, this.color);
}

class _VoiceOpt {
  final String id;
  final String name;
  final String lang;
  final String gender;
  final String genderLabel;
  final String style;
  final String engine;
  final bool available;

  const _VoiceOpt({
    required this.id,
    required this.name,
    this.lang = '',
    this.gender = 'neutral',
    this.genderLabel = '中性',
    this.style = '',
    this.engine = '',
    this.available = true,
  });

  static List<_VoiceOpt> fromJson(dynamic raw) {
    if (raw is! List) return const [];
    final out = <_VoiceOpt>[];
    for (final e in raw) {
      if (e is! Map) continue;
      final id = (e['id'] ?? '').toString();
      if (id.isEmpty) continue;
      out.add(_VoiceOpt(
        id: id,
        name: (e['name'] ?? id).toString(),
        lang: (e['lang'] ?? '').toString(),
        gender: (e['gender'] ?? 'neutral').toString(),
        genderLabel: (e['gender_label'] ?? '中性').toString(),
        style: (e['style'] ?? '').toString(),
        engine: (e['engine'] ?? '').toString(),
        available: e['available'] == null ? true : e['available'] == true,
      ));
    }
    return out;
  }
}

class _Opt {
  final String value;
  final String label;
  final String note;
  final bool enabled;
  const _Opt(this.value, this.label, {this.note = '', this.enabled = true});

  static List<_Opt> fromJson(dynamic raw) {
    if (raw is! List) return const [];
    final out = <_Opt>[];
    for (final e in raw) {
      if (e is Map) {
        final v = (e['value'] ?? e['id'] ?? '').toString();
        final l = (e['label'] ?? e['name'] ?? v).toString();
        final avail = e['available'] == null ? true : e['available'] == true;
        final sup = e['supported'] == null ? true : e['supported'] == true;
        out.add(_Opt(v, l,
            note: (e['desc'] ?? e['style'] ?? '').toString(),
            enabled: avail && sup));
      } else if (e != null) {
        out.add(_Opt(e.toString(), e.toString()));
      }
    }
    return out;
  }
}

class _SettingChange {
  final String key;
  final bool oldValue;
  const _SettingChange(this.key, this.oldValue);
}

class _ChangeRecord {
  final String key;
  final bool value;
  final DateTime time;
  const _ChangeRecord(this.key, this.value, this.time);
}

class _Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  final Color? tint;
  const _Pressable({super.key, required this.child, this.onTap, this.scale = 0.96, this.tint});
  @override
  State<_Pressable> createState() => _PressableState();
}

class _PressableState extends State<_Pressable> {
  bool _down = false;
  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: (_) => setState(() => _down = true),
      onPointerUp: (_) => setState(() => _down = false),
      onPointerCancel: (_) => setState(() => _down = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedScale(
          scale: _down ? widget.scale : 1.0,
          duration: XlDuration.micro,
          curve: XlCurve.standard,
          child: Stack(
            children: [
              widget.child,
              if (widget.tint != null)
                Positioned.fill(
                  child: IgnorePointer(
                    child: AnimatedOpacity(
                      opacity: _down ? 1.0 : 0.0,
                      duration: XlDuration.micro,
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          color: widget.tint,
                          borderRadius: BorderRadius.circular(XlRadius.lg),
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}