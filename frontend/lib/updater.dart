import 'dart:convert';
import 'package:flutter/foundation.dart';
import '../rpc/client.dart';
// safe() / commandOutput() 是 xiaoling_client_ext.dart 里对 XiaoLingClient
// 的扩展方法，不 import 该文件扩展不在作用域 → undefined_method 编译错误
// （曾导致 flutter build windows 失败）。
import '../rpc/xiaoling_client_ext.dart';

class UpdateInfo {
  final bool hasUpdate;
  final String latest;
  final String current;
  final String tag;
  final String name;
  final String body;
  final String htmlUrl;
  final String publishedAt;
  final bool prerelease;
  final bool draft;
  final double sizeMb;
  final List<UpdateAsset> assets;
  final String source;
  final String message;
  const UpdateInfo({
    required this.hasUpdate,
    required this.latest,
    required this.current,
    required this.tag,
    required this.name,
    required this.body,
    required this.htmlUrl,
    required this.publishedAt,
    required this.prerelease,
    required this.draft,
    required this.sizeMb,
    required this.assets,
    required this.source,
    required this.message,
  });
  static const empty = UpdateInfo(
    hasUpdate: false,
    latest: '',
    current: '',
    tag: '',
    name: '',
    body: '',
    htmlUrl: '',
    publishedAt: '',
    prerelease: false,
    draft: false,
    sizeMb: 0,
    assets: [],
    source: '',
    message: '',
  );
  UpdateInfo copyWith({String? source, String? message}) => UpdateInfo(
        hasUpdate: hasUpdate,
        latest: latest,
        current: current,
        tag: tag,
        name: name,
        body: body,
        htmlUrl: htmlUrl,
        publishedAt: publishedAt,
        prerelease: prerelease,
        draft: draft,
        sizeMb: sizeMb,
        assets: assets,
        source: source ?? this.source,
        message: message ?? this.message,
      );

  /// Maps a snake_case backend dict (from `update:check`) to [UpdateInfo].
  factory UpdateInfo.fromBackend(Map m) {
    final rawAssets = m['assets'];
    final assets = <UpdateAsset>[];
    if (rawAssets is List) {
      for (final a in rawAssets) {
        if (a is Map) assets.add(UpdateAsset.fromBackend(a));
      }
    }
    final totalSize = assets.fold<double>(0, (s, a) => s + a.sizeMb);
    return UpdateInfo(
      hasUpdate: m['has_update'] == true,
      latest: (m['latest'] ?? '').toString(),
      current: (m['current'] ?? '').toString(),
      tag: (m['tag'] ?? '').toString(),
      name: (m['name'] ?? '').toString(),
      body: (m['body'] ?? '').toString(),
      htmlUrl: (m['html_url'] ?? '').toString(),
      publishedAt: (m['published_at'] ?? '').toString(),
      prerelease: m['prerelease'] == true,
      draft: m['draft'] == true,
      sizeMb: totalSize,
      assets: assets,
      source: (m['source'] ?? '').toString(),
      message: (m['message'] ?? '').toString(),
    );
  }
}

class UpdateAsset {
  final String name;
  final String url;
  final double sizeMb;
  final String platform;
  final bool recommended;
  const UpdateAsset({
    required this.name,
    required this.url,
    required this.sizeMb,
    required this.platform,
    required this.recommended,
  });

  /// Maps a snake_case backend dict to [UpdateAsset].
  factory UpdateAsset.fromBackend(Map m) {
    final size = (m['size_mb'] is num)
        ? (m['size_mb'] as num).toDouble()
        : 0.0;
    return UpdateAsset(
      name: (m['name'] ?? '').toString(),
      url: (m['url'] ?? '').toString(),
      sizeMb: size,
      platform: (m['platform'] ?? '').toString(),
      recommended: m['recommended'] == true,
    );
  }
}

class Updater {
  // Kept so update_dialog.dart:922 still shows a meaningful repo label.
  static const String repo = '3477856804/XLmodel-release';

  static String? _current;
  static String? _skipped;
  static bool _snapshotLoaded = false;
  static UpdateInfo? _cache;
  static Duration? _cacheAge;
  static bool _hasCached = false;

  static String get current => _current ?? '0.0.1';
  static String? get skipped => _skipped;
  static bool get hasCached => _hasCached;
  static Duration? get cacheAge => _cacheAge;

  static Future<void> _ensureSnapshot() async {
    if (_snapshotLoaded) return;
    _snapshotLoaded = true;
    try {
      final out = await XlClient.stub.safe(
        () => XlClient.stub.commandOutput('update:snapshot'),
      );
      if (out == null) return;
      final m = jsonDecode(out);
      if (m is! Map) return;
      final cur = (m['current'] ?? '').toString();
      if (cur.isNotEmpty) _current = cur;
      final sk = (m['skipped'] ?? '').toString();
      if (sk.isNotEmpty) _skipped = sk;
      final cached = m['cached'];
      if (cached is Map) {
        _cache = UpdateInfo.fromBackend(cached);
        _hasCached = true;
        final age = m['cache_age'];
        if (age is num) {
          _cacheAge = Duration(seconds: age.toInt());
        }
      }
    } catch (e) {
      debugPrint('操作失败: $e');
    }
  }

  static Future<(bool, String, String)> check() async {
    final info = await checkDetailed();
    return (info.hasUpdate, info.latest, info.message);
  }

  static Future<UpdateInfo> checkDetailed({
    bool force = false,
    bool allowPrerelease = false,
    bool useCache = true,
  }) async {
    await _ensureSnapshot();
    try {
      final cmd = force ? 'update:check force' : 'update:check';
      final out = await XlClient.stub.safe(
        () => XlClient.stub.commandOutput(cmd),
      );
      if (out == null) {
        return UpdateInfo.empty.copyWith(
          message: '后端未连接或检查失败',
        );
      }
      final raw = jsonDecode(out);
      if (raw is! Map) {
        return UpdateInfo.empty.copyWith(
          message: '后端返回数据格式异常',
        );
      }
      final info = UpdateInfo.fromBackend(raw);
      _cache = info;
      _hasCached = true;
      _cacheAge = Duration.zero;
      return info;
    } catch (e) {
      return UpdateInfo.empty.copyWith(
        message: '后端未连接或检查失败: $e',
      );
    }
  }

  static Future<void> skipVersion(String version) async {
    try {
      await XlClient.stub.safe(
        () => XlClient.stub.commandOutput('update:skip $version'),
      );
      _skipped = version;
    } catch (e) {
      debugPrint('操作失败: $e');
    }
  }

  static Future<void> clearSkip() async {
    try {
      await XlClient.stub.safe(
        () => XlClient.stub.commandOutput('update:clear-skip'),
      );
      _skipped = null;
    } catch (e) {
      debugPrint('操作失败: $e');
    }
  }

  static Future<void> invalidate() async {
    try {
      await XlClient.stub.safe(
        () => XlClient.stub.commandOutput('update:check force'),
      );
    } catch (e) {
      debugPrint('操作失败: $e');
    }
    _cache = null;
    _hasCached = false;
    _cacheAge = null;
  }

  static UpdateAsset? pickForPlatform(UpdateInfo info, String platform) {
    for (final a in info.assets) {
      if (a.platform == platform) return a;
    }
    return null;
  }

  static UpdateAsset? pickRecommended(UpdateInfo info) {
    for (final a in info.assets) {
      if (a.recommended) return a;
    }
    return info.assets.isEmpty ? null : info.assets.first;
  }

  static String formatSize(double mb) {
    if (mb <= 0) return '—';
    if (mb < 1) return '${(mb * 1024).toStringAsFixed(0)} KB';
    if (mb < 1024) return '${mb.toStringAsFixed(1)} MB';
    return '${(mb / 1024).toStringAsFixed(2)} GB';
  }

  static String formatDate(String iso) {
    if (iso.isEmpty) return '—';
    try {
      final d = DateTime.parse(iso).toLocal();
      final y = d.year.toString();
      final m = d.month.toString().padLeft(2, '0');
      final day = d.day.toString().padLeft(2, '0');
      final hh = d.hour.toString().padLeft(2, '0');
      final mm = d.minute.toString().padLeft(2, '0');
      return '$y-$m-$day $hh:$mm';
    } catch (_) {
      return iso;
    }
  }

  static List<String> changelogLines(String body) {
    if (body.isEmpty) return const [];
    return body
        .split('\n')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .map((s) => s.replaceFirst(RegExp(r'^[-*+]\s*'), ''))
        .map((s) => s.replaceFirst(RegExp(r'^#+\s*'), ''))
        .toList();
  }
}
