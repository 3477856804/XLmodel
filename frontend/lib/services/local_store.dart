import 'dart:convert';
import 'dart:io';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/animation.dart' show AnimationController;

class LocalStore {
  LocalStore._();

  static Directory? _dir;

  static Future<Directory> _storageDir() async {
    if (_dir != null) return _dir!;
    final base = await getApplicationDocumentsDirectory();
    final dir = Directory(p.join(base.path, 'xiaoling'));
    if (!await dir.exists()) {
      await dir.create(recursive: true);
    }
    _dir = dir;
    return dir;
  }

  static Future<Map<String, dynamic>> readJson(String name) async {
    try {
      final dir = await _storageDir();
      final file = File(p.join(dir.path, name));
      if (!await file.exists()) return {};
      final raw = await file.readAsString();
      if (raw.trim().isEmpty) return {};
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) return decoded;
      return {};
    } catch (_) {
      return {};
    }
  }

  static Future<void> writeJson(String name, Map<String, dynamic> data) async {
    try {
      final dir = await _storageDir();
      final file = File(p.join(dir.path, name));
      await file.writeAsString(const JsonEncoder.withIndent('  ').convert(data));
    } catch (e) { debugPrint('操作失败: $e'); }
  }

  static Future<List<String>> readStringList(String name) async {
    final map = await readJson(name);
    final list = map['items'];
    if (list is List) return list.map((e) => e.toString()).toList();
    return [];
  }

  static Future<void> writeStringList(String name, List<String> items) async {
    await writeJson(name, {'items': items});
  }
}

/// 全局「动态效果」开关（总闸 + 细分档位）。
///
/// 持久化复用设置页同一套本地存储（[LocalStore] 的 `channels.json` 里的
/// `toggles.*` 字段），不另立文件、不发明新存储。
///
/// ## 为什么默认关闭（2026-10 调整）
/// 老板的机器是集显/入门 GPU，桌宠页面同时有 VRM 渲染 + 多路 `repeat()` 动画。
/// 常驻的呼吸缩放、光晕脉冲、光带扫过在后台常驻时**持续占用 GPU 与电量**，
/// 却几乎不携带信息 —— 属于典型的「非必要动效」。因此改为**默认全关**：
///   * 关闭后各页面的 AnimationController 不再 repeat（省电、省 GPU）；
///   * 但**必要反馈**（加载、按下、进度）仍然保留，否则界面会显得"卡住"。
///
/// ## 三档而不是一个开关
/// 一刀切会导致"关掉动效后连按压反馈都没了"，显得界面死板。故提供三档：
///   * [XlEffectLevel.off]  全部关闭：只保留必要的进度/加载指示；
///   * [XlEffectLevel.lite]（默认）只开"有用"的那部分：按压反馈 + 状态过渡；
///   * [XlEffectLevel.full] 全开：呼吸、光晕、扫光、逐字动画全部恢复。
///
/// 各页面在 AnimatedBuilder 里读 [ambient]（环境动效，非必要装饰）：
/// 关闭时直接渲染静态外观（scale=1.0、动画值冻结），文字不再缩放抖动。
class XlEffects {
  XlEffects._();

  // --- 持久化 key ---
  static const String _levelKey = 'effects_level';   // 'off' | 'lite' | 'full'
  static const String _legacyKey = 'effects_enabled'; // 老版本布尔开关

  /// 动效档位。
  static XlEffectLevel _level = XlEffectLevel.lite;

  /// 当前动效档位。
  static XlEffectLevel get level => _level;

  /// 直接设置档位（设置页从持久化数据恢复时用）。
  static set level(XlEffectLevel v) => _level = v;

  /// **总开关**，保持向后兼容（老代码读的是这个）。
  /// true 等价于 [XlEffectLevel.full]，false 等价于 [XlEffectLevel.off]。
  static bool get enabled => _level == XlEffectLevel.full;

  static set enabled(bool v) {
    _level = v ? XlEffectLevel.full : XlEffectLevel.off;
  }

  /// 非必要装饰动效（呼吸 / 光晕 / 扫光 / 逐字缩放）。
  ///
  /// 默认档位 lite 下为 false —— 这正是"默认关闭非必要动效"的落点。
  static bool get ambient => _level == XlEffectLevel.full;

  /// 必要的交互反馈（按压、状态切换过渡）。lite 与 full 下都保留。
  static bool get feedback => _level != XlEffectLevel.off;

  /// 应用启动时调用：从 channels.json 读取本地档位，立即生效（不等后端）。
  static Future<void> load() async {
    try {
      final m = await LocalStore.readJson('channels.json');
      final tg = m['toggles'];
      if (tg is! Map) return;
      final lv = tg[_levelKey];
      if (lv is String) {
        _level = XlEffectLevel.parse(lv) ?? _level;
        return;
      }
      // 兼容老版本的布尔开关
      final legacy = tg[_legacyKey];
      if (legacy is bool) enabled = legacy;
    } catch (_) {
      // 读不到就用默认 lite，不阻塞启动
    }
  }

  /// 设置档位并落盘（设置页调用）。
  static Future<void> setLevel(XlEffectLevel v) async {
    _level = v;
    try {
      final m = await LocalStore.readJson('channels.json');
      final tg = (m['toggles'] is Map)
          ? Map<String, dynamic>.from(m['toggles'] as Map)
          : <String, dynamic>{};
      tg[_levelKey] = v.name;
      // 同时写回布尔字段，避免旧版本读到不一致的值
      tg[_legacyKey] = (v == XlEffectLevel.full);
      await LocalStore.writeJson('channels.json', {
        ...m,
        'toggles': tg,
      });
    } catch (_) {
      // 落盘失败不影响本次会话生效
    }
  }

  /// 让一个**循环动画**按当前档位决定要不要真的跑起来。
  ///
  /// 为什么重要：`..repeat()` 的 AnimationController 会**每帧请求重绘**，
  /// 即便界面上看不出来，也在持续吃 GPU 与电池。全应用有 20 多处 repeat()，
  /// 同时跑起来对集显机器是实打实的负担。
  ///
  /// 而仅在 build 里把动画值读成 0（`XlEffects.ambient ? ctrl.value : 0`）
  /// 只能"看起来静止"，帧照样在刷。所以这里在**源头**停掉控制器，
  /// 真正做到 0 开销；用户改档位时由 [restartAmbient] 重新拉起。
  static T bindAmbient<T extends AnimationController>(T c) {
    register(c);
    if (!ambient) {
      if (c.isAnimating) c.stop();
    } else if (!c.isAnimating) {
      c.repeat();
    }
    return c;
  }

  /// 档位从"关"改到"开"后，把先前 [bindAmbient] 停掉的控制器重新拉起。
  ///
  /// 需要持有引用才能重启，因此由各页面在自己被通知时调用；
  /// [bindAmbient] 会把控制器登记到 [_ambientCtrls] 里。
  static final List<AnimationController> _ambientCtrls = [];

  static void register(AnimationController c) {
    if (!_ambientCtrls.contains(c)) _ambientCtrls.add(c);
  }

  /// 重新启动所有被 [bindAmbient] 停掉的循环动画。
  static void restartAmbient() {
    if (!ambient) return;
    for (final c in _ambientCtrls.toList()) {
      if (!c.isAnimating) {
        try {
          c.repeat();
        } catch (_) {
          // 已 dispose 的控制器忽略
        }
      }
    }
  }

  /// 页面销毁时注销，避免控制器泄漏。
  static void unregister(AnimationController c) {
    _ambientCtrls.remove(c);
  }
}

/// 动效档位。
enum XlEffectLevel {
  /// 全部关闭：仅保留加载/进度等必要指示。
  off,

  /// 默认档位：保留必要反馈（按压、状态过渡），关闭装饰性动效。
  lite,

  /// 全开：呼吸、光晕、扫光、逐字动画全部恢复。
  full;

  static XlEffectLevel? parse(String? s) {
    for (final v in XlEffectLevel.values) {
      if (v.name == s) return v;
    }
    return null;
  }

  String get label => switch (this) {
        XlEffectLevel.off => '关闭',
        XlEffectLevel.lite => '精简（推荐）',
        XlEffectLevel.full => '完整',
      };

  String get desc => switch (this) {
        XlEffectLevel.off => '全部静止，只保留加载与进度指示',
        XlEffectLevel.lite => '关闭呼吸/光晕/扫光，保留按压与状态反馈',
        XlEffectLevel.full => '全部动画开启，最耗 GPU 与电量',
      };
}
