import 'package:flutter/material.dart';

import '../services/local_store.dart';

class XlLocaleController extends ChangeNotifier {
  XlLocaleController._();

  static final XlLocaleController instance = XlLocaleController._();

  static const _file = 'ui_prefs.json';

  String _mode = 'system';
  bool _loaded = false;

  String get mode => _mode;

  bool get isSystem => _mode == 'system';
  bool get isZh => _mode == 'zh';
  bool get isEn => _mode == 'en';

  Locale? get locale {
    switch (_mode) {
      case 'zh':
        return const Locale('zh');
      case 'en':
        return const Locale('en');
      default:
        return null;
    }
  }

  static String fromLocale(Locale? l) {
    if (l == null) return 'system';
    return l.languageCode == 'en' ? 'en' : 'zh';
  }

  Future<void> load() async {
    if (_loaded) return;
    _loaded = true;
    try {
      final m = await LocalStore.readJson(_file);
      final v = (m['lang'] ?? '').toString();
      if (v.isNotEmpty) {
        _mode = _normalize(v);
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> set(String value) async {
    _mode = _normalize(value);
    notifyListeners();
    try {
      final m = await LocalStore.readJson(_file);
      m['lang'] = _mode;
      await LocalStore.writeJson(_file, m);
    } catch (_) {}
  }

  String _normalize(String v) {
    switch (v.trim().toLowerCase()) {
      case 'en':
      case 'en-us':
      case 'en_us':
        return 'en';
      case 'zh':
      case 'zh-cn':
      case 'zh_cn':
        return 'zh';
      default:
        return 'system';
    }
  }
}
