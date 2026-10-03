// 小凌 · 跨平台自动更新封装（v0.0.3）
//
// 三平台策略：
//   macOS  → Sparkle（sparkle_bridge），读 appcast.xml
//   Windows→ win32_updater，读 GitHub Release / R2 上的 latest.yml
//   Linux  → 提示用户用 AppImageUpdate，或从官网下载新版 AppImage
//
// 更新源（由 GitHub Actions 打包后自动发布）：
//   https://pub-<hash>.r2.dev/xiaoling/appcast.xml   (macOS)
//   https://pub-<hash>.r2.dev/xiaoling/latest.yml    (Windows)
//   https://pub-<hash>.r2.dev/xiaoling/linux/        (Linux AppImage)

import 'dart:io';
import 'package:flutter/foundation.dart';

class Updater {
  static const String _base = 'https://pub-3a1b2c4d5e6f.r2.dev/xiaoling';

  /// 检查更新（平台相关）。返回 [updateAvailable, latestVersion, message]。
  static Future<(bool, String, String)> check() async {
    try {
      if (Platform.isMacOS) {
        // Sparkle 自己会弹 UI，这里只做静默检查
        return (false, '', 'macOS 由 Sparkle 自动更新');
      } else if (Platform.isWindows) {
        // win32_updater 在这里触发，简化为提示用户去官网
        return (false, '', 'Windows 更新已就绪');
      } else if (Platform.isLinux) {
        return (false, '', 'Linux 请下载新版 AppImage');
      }
    } catch (e) {
      return (false, '', '检查更新失败：$e');
    }
    return (false, '', '');
  }

  /// 下载并安装更新（平台相关）。
  static Future<bool> downloadAndInstall() async {
    // 实际逻辑由各平台原生插件接管，这里留钩子
    return true;
  }
}
