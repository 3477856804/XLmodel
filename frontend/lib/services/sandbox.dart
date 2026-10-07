import 'dart:convert';
import 'dart:io';
import 'package:flutter/services.dart';

class SandboxService {
  static const MethodChannel _channel = MethodChannel('xiaoling/sandbox');

  static bool get isSupported => Platform.isAndroid;

  static Future<bool> start() async {
    if (!isSupported) return false;
    try {
      final r = await _channel.invokeMethod('startSandbox');
      return r is Map && r['ok'] == true;
    } catch (_) {
      return false;
    }
  }

  static Future<void> stop() async {
    if (!isSupported) return;
    try {
      await _channel.invokeMethod('stopSandbox');
    } catch (_) {}
  }

  static Future<Map<String, dynamic>> status() async {
    if (!isSupported) return {'started': false, 'supported': false};
    try {
      final r = await _channel.invokeMethod('getSandboxStatus');
      if (r is Map) {
        final out = <String, dynamic>{'supported': true};
        final s = r['status'];
        if (s is String && s.isNotEmpty) {
          try {
            out.addAll(jsonDecode(s) as Map<String, dynamic>);
          } catch (_) {}
        }
        final snap = r['snapshot'];
        if (snap is String && snap.isNotEmpty) {
          try {
            out['snapshot'] = jsonDecode(snap);
          } catch (_) {}
        }
        return out;
      }
    } catch (_) {}
    return {'started': false, 'supported': true};
  }

  static Future<Map<String, dynamic>> downloadModel(String name,
      {String quant = 'q4_k_m'}) async {
    if (!isSupported) return {'ok': false, 'error': 'unsupported'};
    try {
      final r = await _channel.invokeMethod('downloadModel', {
        'name': name,
        'quant': quant,
      });
      if (r is Map) {
        final res = r['result'];
        if (res is String && res.isNotEmpty) {
          try {
            return jsonDecode(res) as Map<String, dynamic>;
          } catch (_) {}
        }
        return {'ok': r['ok'] == true};
      }
    } catch (e) {
      return {'ok': false, 'error': e.toString()};
    }
    return {'ok': false};
  }
}
