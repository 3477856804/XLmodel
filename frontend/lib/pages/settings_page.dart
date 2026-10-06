import 'package:flutter/material.dart';
import '../theme/theme.dart';
import '../rpc/client.dart';
import '../rpc/xiaoling_client_ext.dart';
import '../rpc/xiaoling_ext.dart';
import '../rpc/xiaoling.pb.dart' as pb;

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});
  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> with TickerProviderStateMixin {
  pb.SettingsReply? _remote;
  pb.VoiceList? _voices;
  pb.HardwareInfo? _hardware;
  bool _loading = true;
  bool _synced = false;
  String _activeSection = 'model';
  final _searchCtrl = TextEditingController();
  final _searchFocus = FocusNode();
  String _query = '';
  late AnimationController _enterCtrl;
  late AnimationController _pulseCtrl;
  late Animation<double> _enterAnim;

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

  String _model = '小凌';
  String _voice = '晓晓';
  String _render = '软件光栅';
  String _threads = '4 线程';
  String _theme = '跟随系统';
  String _language = '简体中文';
  String _cacheSize = '计算中…';

  static const _sections = <_Section>[
    _Section('model', '模型设置', Icons.memory_rounded, 'pink'),
    _Section('render', '渲染设置', Icons.blur_on_rounded, 'gold'),
    _Section('voice', '语音设置', Icons.record_voice_over_rounded, 'violet'),
    _Section('interface', '界面设置', Icons.dashboard_customize_rounded, 'green'),
    _Section('advanced', '高级设置', Icons.tune_rounded, 'blue'),
    _Section('about', '关于小凌', Icons.info_outline_rounded, 'pink'),
  ];

  static const _models = <String>['小凌', 'Vivi', 'QuQu', 'Imeris', 'Yuki'];
  static const _voices = <String>['晓晓', '晓伊', '云希', '云扬', '晓辰', '晓涵'];
  static const _renders = <String>['软件光栅', 'OpenGL', 'Vulkan', 'Metal'];
  static const _threadsList = <String>['2 线程', '4 线程', '6 线程', '8 线程', '自动'];
  static const _themes = <String>['跟随系统', '始终深色', '始终浅色'];
  static const _languages = <String>['简体中文', '繁體中文', 'English', '日本語'];

  @override
  void initState() {
    super.initState();
    _enterCtrl = AnimationController(duration: const Duration(milliseconds: 900), vsync: this);
    _pulseCtrl = AnimationController(duration: const Duration(seconds: 4), vsync: this)..repeat();
    _enterAnim = CurvedAnimation(parent: _enterCtrl, curve: XlCurve.easeOut);
    _enterCtrl.forward();
    _loadSettings();
    _calcCache();
  }

  @override
  void dispose() {
    _enterCtrl.dispose();
    _pulseCtrl.dispose();
    _searchCtrl.dispose();
    _searchFocus.dispose();
    super.dispose();
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
      _voices = prefs.voices;
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
    await Future.delayed(const Duration(milliseconds: 800));
    if (mounted) setState(() => _cacheSize = '128.4 MB');
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
    return Padding(
      padding: const EdgeInsets.fromLTRB(26, 6, 26, 30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _heroRow(p),
          const SizedBox(height: 20),
          Expanded(
            child: LayoutBuilder(
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
            ),
          ),
        ],
      ),
    );
  }

  Widget _heroRow(XlPalette p) {
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
            color: color.withOpacity(p.dark ? 0.14 : 0.10),
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
      width: 280,
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
            GestureDetector(
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
          ? BoxDecoration(
              color: p.surfaceLo,
              borderRadius: BorderRadius.circular(XlRadius.md),
              border: Border.all(color: color.withOpacity(0.35), width: 1.2),
              boxShadow: p.sunkenSm,
            )
          : const BoxDecoration(),
      child: Row(
        mainAxisSize: horizontal ? MainAxisSize.min : MainAxisSize.max,
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              color: selected ? color.withOpacity(p.dark ? 0.18 : 0.12) : p.surfaceLo,
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
              decoration: BoxDecoration(
                color: color,
                shape: BoxShape.circle,
                boxShadow: [BoxShadow(color: color.withOpacity(0.6), blurRadius: 8, spreadRadius: -1)],
              ),
            ),
        ],
      ),
    );
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => setState(() => _activeSection = s.key),
        borderRadius: BorderRadius.circular(XlRadius.md),
        child: chip,
      ),
    );
  }

  Widget _contentPane(XlPalette p) {
    return Container(
      decoration: AppTheme.neu(context, r: XlRadius.xxl),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: _loading ? _loadingPane(p) : _sectionContent(p),
      ),
    );
  }

  Widget _loadingPane(XlPalette p) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 60),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 40,
              height: 40,
              child: CircularProgressIndicator(strokeWidth: 3, color: p.pink),
            ),
            const SizedBox(height: 18),
            Text('正在读取设置…',
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  color: p.text2,
                  fontWeight: FontWeight.w600,
                  letterSpacing: XlLetterSpacing.wider,
                )),
          ],
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
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withOpacity(p.dark ? 0.14 : 0.10),
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
        _selectRow(p, '角色模型', '当前对话使用的角色形象与性格', Icons.face_6_rounded, _models, _model, p.pink, (v) async {
          setState(() => _model = v);
          await XlClient.stub.safe(() => XlClient.stub.setModelName(v));
        }),
        const SizedBox(height: 12),
        _selectRow(p, '推理后端', '影响响应速度与资源占用', Icons.memory_rounded, _renders, _render, p.gold, (v) => setState(() => _render = v)),
        const SizedBox(height: 12),
        _selectRow(p, '推理线程数', '更多线程更快但更耗电', Icons.speed_rounded, _threadsList, _threads, p.violet, (v) => setState(() => _threads = v)),
        const SizedBox(height: 12),
        _switchRow(p, '硬件加速', '使用 GPU / NPU 加速推理', Icons.bolt_rounded, 'hardwareAccel', p.green),
        if (hw != null) ...[
          const SizedBox(height: 18),
          _hwInfoPanel(p, hw),
        ],
        const SizedBox(height: 18),
        _infoPanel(p, '当前模型占用约 $_cacheSize，切换模型会自动重新加载。'),
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
              color: p.pink.withOpacity(p.dark ? 0.06 : 0.05),
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
        _selectRow(p, '渲染模式', '默认使用软件光栅，兼容性最好', Icons.blur_on_rounded, _renders, _render, p.gold, (v) => setState(() => _render = v)),
        const SizedBox(height: 12),
        _switchRow(p, '窗口置顶', '让小凌始终显示在最前面', Icons.push_pin_rounded, 'alwaysOnTop', p.pink),
        const SizedBox(height: 12),
        _switchRow(p, '开机自启', '登录系统后自动启动小凌', Icons.power_settings_new_rounded, 'autoStart', p.violet),
        const SizedBox(height: 12),
        _switchRow(p, '启用动画', '关闭后所有过渡效果立即完成', Icons.animation_rounded, 'animations', p.green),
        const SizedBox(height: 12),
        _sliderRow(p, '窗口透明度', Icons.opacity_rounded, p.gold, 0.92),
        const SizedBox(height: 12),
        _sliderRow(p, '3D 渲染质量', Icons.high_quality_rounded, p.pink, 0.78),
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
        _selectRow(p, '合成音色', '不同角色默认绑定不同音色', Icons.graphic_eq_rounded, _voices, _voice, p.violet, (v) async {
          setState(() => _voice = v);
          await XlClient.stub.safe(() => XlClient.stub.setVoiceName(v));
        }),
        const SizedBox(height: 12),
        _switchRow(p, '语音识别', '允许小凌听到你的声音', Icons.record_voice_over_rounded, 'asr', p.pink),
        const SizedBox(height: 12),
        _switchRow(p, '语音朗读', '聊天后自动朗读回复', Icons.volume_up_rounded, 'tts', p.gold),
        const SizedBox(height: 12),
        _switchRow(p, '阅读模式', '朗读长文本时自动分句', Icons.menu_book_rounded, 'readAloud', p.green),
        const SizedBox(height: 12),
        _switchRow(p, '系统音效', '操作时播放轻提示音', Icons.music_note_rounded, 'sound', p.blue),
        const SizedBox(height: 12),
        _sliderRow(p, '语速', Icons.speed_rounded, p.violet, 0.55),
        const SizedBox(height: 12),
        _sliderRow(p, '音量', Icons.volume_down_rounded, p.pink, 0.80),
        if (_voices != null && _voices!.voices.isNotEmpty) ...[
          const SizedBox(height: 18),
          _voiceListPanel(p, _voices!),
        ],
      ],
    );
  }

  Widget _voiceListPanel(XlPalette p, pb.VoiceList list) {
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
              _tinyChip(p, '${list.voices.length} 个', p.violet),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: list.voices.map((v) => _voiceChip(p, v)).toList(),
          ),
        ],
      ),
    );
  }

  Widget _voiceChip(XlPalette p, pb.VoiceInfo v) {
    final color = v.isFemale ? p.pink : (v.isMale ? p.blue : p.gold);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(p.dark ? 0.12 : 0.08),
        borderRadius: BorderRadius.circular(XlRadius.pill),
        border: Border.all(color: color.withOpacity(0.28), width: 1),
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
              boxShadow: [BoxShadow(color: color.withOpacity(0.6), blurRadius: 6, spreadRadius: -1)],
            ),
          ),
          const SizedBox(width: 8),
          Text(v.displayName,
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
        ],
      ),
    );
  }

  Widget _interfaceSection(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '界面设置', '主题、语言与启动行为', p.green),
        _selectRow(p, '主题模式', '深色为默认，浅色更明亮', Icons.brightness_6_rounded, _themes, _theme, p.green, (v) => setState(() => _theme = v)),
        const SizedBox(height: 12),
        _selectRow(p, '界面语言', '目前仅简体中文为完整支持', Icons.language_rounded, _languages, _language, p.gold, (v) => setState(() => _language = v)),
        const SizedBox(height: 12),
        _switchRow(p, '启动动画', '启动时显示小凌的欢迎画面', Icons.movie_filter_rounded, 'splash', p.violet),
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
              Expanded(child: _swatch(p, 'Deep', p.bg, p.pink, true)),
              const SizedBox(width: 10),
              Expanded(child: _swatch(p, 'Light', XlPalette.light.bg, XlPalette.light.pink, false)),
              const SizedBox(width: 10),
              Expanded(child: _swatch(p, 'Auto', p.surface, p.gold, false)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _swatch(XlPalette p, String label, Color bg, Color accent, bool active) {
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

  Widget _advancedSection(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '高级设置', '数据、更新与诊断', p.blue),
        _switchRow(p, '自动更新', '启动时检查是否有新版本', Icons.system_update_alt_rounded, 'autoUpdate', p.green),
        const SizedBox(height: 12),
        _switchRow(p, '崩溃上报', '发送匿名崩溃日志帮助我们修复问题', Icons.bug_report_outlined, 'crash', p.gold),
        const SizedBox(height: 12),
        _switchRow(p, '使用统计', '发送匿名功能使用数据', Icons.analytics_outlined, 'telemetry', p.red),
        const SizedBox(height: 18),
        _actionRow(p, '清理缓存', '当前占用 $_cacheSize', Icons.cleaning_services_outlined, p.pink, () {
          setState(() => _cacheSize = '0 B');
        }),
        const SizedBox(height: 10),
        _actionRow(p, '导出数据', '导出对话、记忆和配置', Icons.upload_file_rounded, p.violet, () {}),
        const SizedBox(height: 10),
        _actionRow(p, '导入数据', '从备份文件恢复', Icons.download_rounded, p.blue, () {}),
        const SizedBox(height: 10),
        _actionRow(p, '重置所有设置', '恢复出厂默认，不可撤销', Icons.restart_alt_rounded, p.red, () {}),
      ],
    );
  }

  Widget _aboutSection(XlPalette p) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(p, '关于小凌', '版本、协议与开源信息', p.pink),
        _aboutHero(p),
        const SizedBox(height: 18),
        _aboutRow(p, '版本', 'v0.0.1', Icons.tag_rounded),
        const SizedBox(height: 10),
        _aboutRow(p, '构建', 'flutter-v0.0.1 · debug', Icons.build_rounded),
        const SizedBox(height: 10),
        _aboutRow(p, '架构', 'Flutter + Python + gRPC', Icons.architecture_rounded),
        const SizedBox(height: 10),
        _aboutRow(p, '开源协议', 'MIT License', Icons.gavel_rounded),
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

  Widget _aboutHero(XlPalette p) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: p.gradBrand,
        borderRadius: BorderRadius.circular(XlRadius.xxl),
        border: Border.all(color: Colors.white.withOpacity(p.dark ? 0.28 : 0.42), width: 1.4),
        boxShadow: [...p.raisedSm, BoxShadow(color: p.pink.withOpacity(0.35), blurRadius: 26, spreadRadius: -6)],
      ),
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
                      color: Colors.white.withOpacity(p.dark ? 0.22 : 0.32),
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
                        color: Colors.black.withOpacity(p.dark ? 0.24 : 0.18),
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
                        color: Colors.black.withOpacity(p.dark ? 0.24 : 0.18),
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

  Widget _aboutRow(XlPalette p, String label, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: AppTheme.neuXs(context, r: XlRadius.md),
      child: Row(
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              color: p.pink.withOpacity(p.dark ? 0.14 : 0.10),
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
                color: p.text1,
                fontWeight: FontWeight.w800,
                letterSpacing: XlLetterSpacing.wide,
                fontFeatures: const [FontFeature.tabularFigures()],
              )),
        ],
      ),
    );
  }

  Widget _aboutLink(XlPalette p, String label, IconData icon, Color color) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () {},
        borderRadius: BorderRadius.circular(XlRadius.md),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: AppTheme.neuXs(context, r: XlRadius.md),
          child: Column(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: color.withOpacity(p.dark ? 0.14 : 0.10),
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
      ),
    );
  }

  Widget _selectRow(XlPalette p, String title, String sub, IconData icon, List<String> options, String current, Color color, ValueChanged<String> onChanged) {
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
              color: color.withOpacity(p.dark ? 0.14 : 0.10),
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

  Widget _dropdown(XlPalette p, List<String> options, String current, Color color, ValueChanged<String> onChanged) {
    final safe = options.contains(current) ? current : options.first;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      decoration: BoxDecoration(
        color: p.surfaceLo,
        borderRadius: BorderRadius.circular(XlRadius.md),
        border: Border.all(color: p.shDark.withOpacity(p.dark ? 0.28 : 0.12), width: 1),
        boxShadow: p.sunkenXxs,
      ),
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
            value: o,
            child: Text(o,
                style: TextStyle(
                  fontSize: XlFont.captionSm,
                  fontWeight: FontWeight.w700,
                  color: o == safe ? color : p.text1,
                  letterSpacing: XlLetterSpacing.wide,
                )),
          )).toList(),
          onChanged: (v) {
            if (v != null) onChanged(v);
          },
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
              color: on ? color.withOpacity(p.dark ? 0.18 : 0.12) : p.surfaceLo,
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
          _toggle(p, on, color, () => setState(() => _toggles[key] = !on)),
        ],
      ),
    );
  }

  Widget _toggle(XlPalette p, bool on, Color color, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
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
                ? Colors.white.withOpacity(p.dark ? 0.34 : 0.22)
                : p.shDark.withOpacity(p.dark ? 0.32 : 0.14),
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
          child: Container(
            margin: const EdgeInsets.all(3),
            width: 20,
            height: 20,
            decoration: BoxDecoration(
              color: p.surfaceHi,
              shape: BoxShape.circle,
              boxShadow: p.raisedXxs,
            ),
          ),
        ),
      ),
    );
  }

  Widget _sliderRow(XlPalette p, String label, IconData icon, Color color, double value) {
    if (!_matches(label, '')) return const SizedBox.shrink();
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
                  color: color.withOpacity(p.dark ? 0.14 : 0.10),
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
          _sliderTrack(p, value, color),
        ],
      ),
    );
  }

  Widget _sliderTrack(XlPalette p, double value, Color color) {
    return LayoutBuilder(
      builder: (context, c) {
        return Stack(
          children: [
            Container(
              height: 8,
              decoration: BoxDecoration(
                color: p.surfaceLo,
                borderRadius: BorderRadius.circular(99),
                boxShadow: p.sunkenXxs,
              ),
            ),
            FractionallySizedBox(
              widthFactor: value.clamp(0.0, 1.0),
              child: Container(
                height: 8,
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: [color.withOpacity(0.7), color]),
                  borderRadius: BorderRadius.circular(99),
                  boxShadow: [BoxShadow(color: color.withOpacity(0.35), blurRadius: 10, spreadRadius: -2)],
                ),
              ),
            ),
            Positioned(
              left: (c.maxWidth - 18) * value.clamp(0.0, 1.0),
              top: -5,
              child: Container(
                width: 18,
                height: 18,
                decoration: BoxDecoration(
                  color: p.surfaceHi,
                  shape: BoxShape.circle,
                  border: Border.all(color: color.withOpacity(0.55), width: 1.5),
                  boxShadow: [...p.raisedXs, BoxShadow(color: color.withOpacity(0.35), blurRadius: 10, spreadRadius: -1)],
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _actionRow(XlPalette p, String title, String sub, IconData icon, Color color, VoidCallback onTap) {
    if (!_matches(title, sub)) return const SizedBox.shrink();
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(XlRadius.lg),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: AppTheme.neuXs(context, r: XlRadius.lg),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: color.withOpacity(p.dark ? 0.14 : 0.10),
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
      ),
    );
  }

  Widget _infoPanel(XlPalette p, String text) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: p.pink.withOpacity(p.dark ? 0.06 : 0.05),
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
        color: color.withOpacity(p.dark ? 0.14 : 0.10),
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