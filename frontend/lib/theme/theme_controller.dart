import 'package:flutter/material.dart';

import '../services/local_store.dart';

/// 全局主题控制器。
///
/// 之前主题模式是个「死」的：
/// - 侧边栏那个「深色主题」按钮直接改 `_XiaoLingAppState._mode`，
///   而「设置 → 界面设置 → 主题模式」下拉框改了 `_SettingsPageState._theme`，
///   两个 state 各管各的，永不互通；
/// - 而且两边都**不落盘**，重启就回到深色。
/// 现在收敛到一个全局控制器：设置页、侧边栏按钮、启动页都读写它，
/// 并持久化到本地，下次启动直接恢复。
class XlThemeController extends ChangeNotifier {
  XlThemeController._();

  static final XlThemeController instance = XlThemeController._();

  static const _file = 'ui_prefs.json';

  ThemeMode _mode = ThemeMode.dark;
  bool _loaded = false;
  bool _backendSynced = false;

  /// 对比度档位：auto 跟随系统，on/off 是应用内强制档位。
  ///
  /// 这里以前是三个从没被读过、也从没落盘的字段
  /// （_reduceMotion / _reduceTransparency / _increasedContrast）——
  /// 典型的「写了个开关就以为做了无障碍」。HIG《Color》要求自定义色
  /// 必须同时提供 light / dark / increased contrast 三套，
  /// 所以这一档现在真的接到 XlPalette.darkHc / lightHc 上，
  /// 并且和主题模式一样落盘，重启后保持。
  ///
  /// 为什么要应用内开关而不只看系统：Flutter 只在
  /// iOS / macOS / Android 上报 highContrast，Windows 与 Linux 桌面
  /// 没有对应信号，若只依赖系统，这两端永远拿不到高对比配色。
  String _contrast = 'auto';

  ThemeMode get mode => _mode;
  bool get isDark => _mode == ThemeMode.dark;
  bool get isLight => _mode == ThemeMode.light;
  bool get loaded => _loaded;

  String get contrast => _contrast;
  set contrast(String v) => _contrast = _valid(v);

  static String _valid(String v) {
    switch (v) {
      case 'on':
      case 'off':
      case 'auto':
        return v;
      default:
        return 'auto';
    }
  }

  /// 是否应该使用提高对比度的调色板（系统开关 + 应用内档位一起决定）。
  bool resolveHighContrast(bool systemHighContrast) {
    switch (_contrast) {
      case 'on':
        return true;
      case 'off':
        return false;
      default:
        return systemHighContrast;
    }
  }

  /// 后端配置里用的取值：system / dark / light
  String get value {
    switch (_mode) {
      case ThemeMode.light:
        return 'light';
      case ThemeMode.system:
        return 'system';
      case ThemeMode.dark:
        return 'dark';
    }
  }

  static ThemeMode fromValue(String? v) {
    switch ((v ?? '').trim().toLowerCase()) {
      case 'light':
        return ThemeMode.light;
      case 'system':
        return ThemeMode.system;
      case 'dark':
        return ThemeMode.dark;
      default:
        return ThemeMode.dark;
    }
  }

  /// 启动时调用一次：读本地偏好，立即生效（不等后端）。
  Future<void> load() async {
    if (_loaded) return;
    _loaded = true;
    try {
      final m = await LocalStore.readJson(_file);
      var changed = false;
      final v = (m['theme'] ?? '').toString();
      if (v.isNotEmpty) {
        _mode = fromValue(v);
        changed = true;
      }
      final c = (m['contrast'] ?? '').toString();
      if (c.isNotEmpty) {
        _contrast = _valid(c);
        changed = true;
      }
      if (changed) notifyListeners();
    } catch (_) {
      // 读不到就用默认深色，不阻塞启动
    }
  }

  /// 切换主题并落盘。
  ///
  /// [pushToBackend] 用于让后端配置(`ui.theme`)保持一致——由调用方传入
  /// 写入函数，避免这里直接依赖 gRPC 客户端（启动早期后端可能还没起来）。
  Future<void> set(String value, {Future<void> Function(String)? pushToBackend}) async {
    final next = fromValue(value);
    _mode = next;
    notifyListeners();
    try {
      await _mergeWrite();
    } catch (_) {}
    if (pushToBackend != null) {
      try {
        await pushToBackend(value);
      } catch (_) {}
    }
  }

  Future<void> toggle() => set(isDark ? 'light' : 'dark');

  /// 切换对比度档位并落盘。
  Future<void> setContrast(String value) async {
    final next = _valid(value);
    if (next == _contrast) return;
    _contrast = next;
    notifyListeners();
    try {
      await _mergeWrite();
    } catch (_) {}
  }

  /// 增量写回本控制器拥有的两个键。
  ///
  /// `ui_prefs.json` 是和 [XlLocaleController] 共用的文件，而
  /// `LocalStore.writeJson` 是**整档覆盖**：原先这里只写 `theme`
  /// （补 contrast 时也只是把这两个键写全），于是切一次主题就把用户存的
  /// `lang` 抹掉，下次启动语言回落成系统默认 —— 一个静默的数据丢失 bug。
  /// 现在先读后合并，只覆盖自己的键，别人的键原样保留。
  Future<void> _mergeWrite() async {
    final m = await LocalStore.readJson(_file);
    m['theme'] = value;
    m['contrast'] = _contrast;
    await LocalStore.writeJson(_file, m);
  }

  /// 标记已经和后端对齐过，避免重复写。
  bool get backendSynced => _backendSynced;
  set backendSynced(bool v) => _backendSynced = v;
}
