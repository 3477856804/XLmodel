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

  ThemeMode get mode => _mode;
  bool get isDark => _mode == ThemeMode.dark;
  bool get isLight => _mode == ThemeMode.light;
  bool get loaded => _loaded;

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
      final v = (m['theme'] ?? '').toString();
      if (v.isNotEmpty) {
        _mode = fromValue(v);
        notifyListeners();
      }
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
      await LocalStore.writeJson(_file, {'theme': value});
    } catch (_) {}
    if (pushToBackend != null) {
      try {
        await pushToBackend(value);
      } catch (_) {}
    }
  }

  Future<void> toggle() => set(isDark ? 'light' : 'dark');

  /// 标记已经和后端对齐过，避免重复写。
  bool get backendSynced => _backendSynced;
  set backendSynced(bool v) => _backendSynced = v;
}
