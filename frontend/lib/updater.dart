// 小凌 · 跨平台自动更新（v0.0.1 真实现）
// 启动时拉 GitHub Release API，比对版本号，有新版就提示。
import 'package:http/http.dart' as http;
import 'dart:convert';

class Updater {
  static const String _repo = '3477856804/XLmodel-release';
  static const String _current = '0.0.1';

  static Future<(bool, String, String)> check() async {
    try {
      final uri = Uri.parse('https://api.github.com/repos/$_repo/releases/latest');
      final resp = await http.get(uri, headers: {'Accept': 'application/vnd.github+json'})
          .timeout(const Duration(seconds: 5));
      if (resp.statusCode != 200) return (false, '', 'check failed: HTTP ${resp.statusCode}');
      final j = json.decode(resp.body);
      final latest = (j['tag_name'] ?? '').toString().replaceFirst('v', '');
      if (latest.isEmpty) return (false, '', '');
      final hasUpdate = _isNewer(latest, _current);
      return (hasUpdate, latest,
          hasUpdate ? 'Found v$latest' : 'Up to date');
    } catch (e) {
      return (false, '', 'check failed: $e');
    }
  }

  static bool _isNewer(String latest, String current) {
    try {
      final a = latest.split('.').map(int.parse).toList();
      final b = current.split('.').map(int.parse).toList();
      for (var i = 0; i < 3; i++) {
        final x = i < a.length ? a[i] : 0;
        final y = i < b.length ? b[i] : 0;
        if (x > y) return true;
        if (x < y) return false;
      }
    } catch (_) {}
    return false;
  }
}
