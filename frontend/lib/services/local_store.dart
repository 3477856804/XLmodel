import 'dart:convert';
import 'dart:io';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:flutter/foundation.dart';

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
