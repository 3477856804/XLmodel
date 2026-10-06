import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

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
}

class Updater {
  static const String _repo = '3477856804/XLmodel-release';
  static const String _current = '0.0.1';
  static const Duration _timeout = Duration(seconds: 6);
  static const Duration _cacheTtl = Duration(minutes: 30);

  static final List<String> _mirrors = [
    'https://api.github.com/repos/$_repo/releases/latest',
    'https://ghfast.top/https://api.github.com/repos/$_repo/releases/latest',
    'https://ghproxy.net/https://api.github.com/repos/$_repo/releases/latest',
  ];

  static UpdateInfo? _cache;
  static DateTime? _cacheAt;
  static String? _skippedVersion;

  static String get current => _current;
  static String get repo => _repo;
  static String? get skipped => _skippedVersion;

  static Future<(bool, String, String)> check() async {
    final info = await checkDetailed();
    return (info.hasUpdate, info.latest, info.message);
  }

  static Future<UpdateInfo> checkDetailed({
    bool force = false,
    bool allowPrerelease = false,
    bool useCache = true,
  }) async {
    if (!force && useCache && _cache != null && _cacheAt != null) {
      final age = DateTime.now().difference(_cacheAt!);
      if (age < _cacheTtl) return _cache!;
    }

    Object? lastError;
    for (final url in _mirrors) {
      try {
        final resp = await http
            .get(Uri.parse(url), headers: {
              'Accept': 'application/vnd.github+json',
              'User-Agent': 'XiaoLing-Updater/0.0.1',
            })
            .timeout(_timeout);
        if (resp.statusCode != 200) {
          lastError = 'HTTP ${resp.statusCode}';
          continue;
        }
        final raw = json.decode(resp.body);
        if (raw is! Map) {
          lastError = 'invalid payload';
          continue;
        }
        final info = _parse(raw, url, allowPrerelease);
        if (info == null) {
          lastError = 'parse failed';
          continue;
        }
        _cache = info;
        _cacheAt = DateTime.now();
        return info;
      } catch (e) {
        lastError = e;
      }
    }

    final fallback = UpdateInfo.empty.copyWith(
      message: 'check failed: $lastError',
    );
    return fallback;
  }

  static UpdateInfo? _parse(Map raw, String source, bool allowPrerelease) {
    final tag = (raw['tag_name'] ?? '').toString();
    final latest = _normalize(tag);
    if (latest.isEmpty) return null;

    final prerelease = raw['prerelease'] == true;
    final draft = raw['draft'] == true;
    if (draft) return null;
    if (prerelease && !allowPrerelease) return null;

    final skipped = _skippedVersion;
    final hasUpdate = _isNewer(latest, _current) && latest != skipped;

    final assets = <UpdateAsset>[];
    final rawAssets = raw['assets'];
    if (rawAssets is List) {
      for (final a in rawAssets) {
        if (a is! Map) continue;
        final name = (a['name'] ?? '').toString();
        final url = (a['browser_download_url'] ?? '').toString();
        if (name.isEmpty || url.isEmpty) continue;
        final size = (a['size'] is num) ? (a['size'] as num).toDouble() / 1024 / 1024 : 0.0;
        final plat = _platformOf(name);
        assets.add(UpdateAsset(
          name: name,
          url: url,
          sizeMb: size,
          platform: plat,
          recommended: _isRecommended(name),
        ));
      }
    }

    assets.sort((a, b) {
      if (a.recommended != b.recommended) return a.recommended ? -1 : 1;
      return a.sizeMb.compareTo(b.sizeMb);
    });

    final totalSize = assets.fold<double>(0, (s, a) => s + a.sizeMb);

    return UpdateInfo(
      hasUpdate: hasUpdate,
      latest: latest,
      current: _current,
      tag: tag.isEmpty ? 'v$latest' : tag,
      name: (raw['name'] ?? '').toString(),
      body: (raw['body'] ?? '').toString(),
      htmlUrl: (raw['html_url'] ?? '').toString(),
      publishedAt: (raw['published_at'] ?? '').toString(),
      prerelease: prerelease,
      draft: draft,
      sizeMb: totalSize,
      assets: assets,
      source: _sourceLabel(source),
      message: hasUpdate
          ? (latest == skipped ? '已跳过 v$latest' : '发现新版本 v$latest')
          : '已是最新版本',
    );
  }

  static String _sourceLabel(String url) {
    if (url.contains('ghfast.top')) return 'ghfast';
    if (url.contains('ghproxy.net')) return 'ghproxy';
    if (url.contains('api.github.com')) return 'github';
    return 'mirror';
  }

  static String _platformOf(String name) {
    final n = name.toLowerCase();
    if (n.endsWith('.exe') || n.contains('setup') || n.contains('windows')) return 'windows';
    if (n.endsWith('.dmg') || n.contains('macos') || n.contains('mac')) return 'macos';
    if (n.endsWith('.appimage') || n.endsWith('.deb') || n.contains('linux')) return 'linux';
    if (n.endsWith('.apk') || n.contains('android')) return 'android';
    if (n.endsWith('.ipa') || n.contains('ios')) return 'ios';
    if (n.endsWith('.zip')) return 'zip';
    if (n.endsWith('.tar.gz')) return 'tarball';
    return 'other';
  }

  static bool _isRecommended(String name) {
    final n = name.toLowerCase();
    if (n.contains('setup') || n.contains('installer')) return true;
    if (n.endsWith('.exe')) return true;
    if (n.endsWith('.dmg')) return true;
    if (n.endsWith('.appimage')) return true;
    return false;
  }

  static String _normalize(String tag) {
    var v = tag.trim();
    if (v.startsWith('v') || v.startsWith('V')) v = v.substring(1);
    return v;
  }

  static bool _isNewer(String latest, String current) {
    try {
      final a = latest.split('.').map((s) => int.tryParse(s) ?? 0).toList();
      final b = current.split('.').map((s) => int.tryParse(s) ?? 0).toList();
      final n = a.length > b.length ? a.length : b.length;
      for (var i = 0; i < n; i++) {
        final x = i < a.length ? a[i] : 0;
        final y = i < b.length ? b[i] : 0;
        if (x > y) return true;
        if (x < y) return false;
      }
    } catch (_) {}
    return false;
  }

  static void skipVersion(String version) {
    _skippedVersion = _normalize(version);
    _cache = null;
    _cacheAt = null;
  }

  static void clearSkip() {
    _skippedVersion = null;
    _cache = null;
    _cacheAt = null;
  }

  static void invalidate() {
    _cache = null;
    _cacheAt = null;
  }

  static bool get hasCached => _cache != null && _cacheAt != null;

  static Duration? get cacheAge {
    if (_cacheAt == null) return null;
    return DateTime.now().difference(_cacheAt!);
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