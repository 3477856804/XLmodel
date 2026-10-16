import 'dart:async';
import 'package:grpc/grpc.dart';
import '../rpc/xiaoling.pbgrpc.dart';
import 'package:flutter/foundation.dart';

enum XlConnectionState {
  idle,
  connecting,
  connected,
  reconnecting,
  disconnected,
  failed,
  closed,
}

enum ConnectionStatus {
  connected,
  disconnected,
  connecting,
}

typedef ConnectionChangedCallback = void Function(ConnectionStatus status);

ConnectionStatus _mapStatus(XlConnectionState s) {
  switch (s) {
    case XlConnectionState.connected:
      return ConnectionStatus.connected;
    case XlConnectionState.connecting:
    case XlConnectionState.reconnecting:
      return ConnectionStatus.connecting;
    default:
      return ConnectionStatus.disconnected;
  }
}

class XlConnectionEvent {
  final XlConnectionState state;
  final DateTime at;
  final String? detail;
  final Duration? latency;
  const XlConnectionEvent({
    required this.state,
    required this.at,
    this.detail,
    this.latency,
  });
  @override
  String toString() => '[${at.toIso8601String()}] ${state.name}${detail == null ? '' : ' · $detail'}';
}

class XlMetrics {
  int totalCalls = 0;
  int successCalls = 0;
  int failedCalls = 0;
  int retriedCalls = 0;
  int cancelledCalls = 0;
  int timedOutCalls = 0;
  Duration totalLatency = Duration.zero;
  Duration maxLatency = Duration.zero;
  Duration minLatency = Duration.zero;
  DateTime? lastSuccessAt;
  DateTime? lastFailureAt;
  String? lastError;
  int reconnectCount = 0;
  int unavailableCount = 0;
  int deadlineCount = 0;
  int internalCount = 0;
  int unknownCount = 0;

  Duration get avgLatency {
    if (successCalls == 0) return Duration.zero;
    return Duration(microseconds: totalLatency.inMicroseconds ~/ successCalls);
  }

  double get successRate {
    if (totalCalls == 0) return 0;
    return successCalls / totalCalls;
  }

  void record(Duration latency) {
    totalCalls++;
    successCalls++;
    totalLatency += latency;
    if (maxLatency == Duration.zero || latency > maxLatency) maxLatency = latency;
    if (minLatency == Duration.zero || latency < minLatency) minLatency = latency;
    lastSuccessAt = DateTime.now();
  }

  void fail(Object e) {
    totalCalls++;
    failedCalls++;
    lastError = e.toString();
    lastFailureAt = DateTime.now();
    if (e is GrpcError) {
      switch (e.code) {
        case StatusCode.unavailable:
          unavailableCount++;
          break;
        case StatusCode.deadlineExceeded:
          deadlineCount++;
          break;
        case StatusCode.internal:
          internalCount++;
          break;
        default:
          unknownCount++;
      }
    } else {
      unknownCount++;
    }
  }

  void retry() => retriedCalls++;
  void cancel() => cancelledCalls++;
  void timeout() => timedOutCalls++;
  void reconnect() => reconnectCount++;

  void reset() {
    totalCalls = 0;
    successCalls = 0;
    failedCalls = 0;
    retriedCalls = 0;
    cancelledCalls = 0;
    timedOutCalls = 0;
    totalLatency = Duration.zero;
    maxLatency = Duration.zero;
    minLatency = Duration.zero;
    lastSuccessAt = null;
    lastFailureAt = null;
    lastError = null;
    reconnectCount = 0;
    unavailableCount = 0;
    deadlineCount = 0;
    internalCount = 0;
    unknownCount = 0;
  }

  Map<String, dynamic> toMap() => {
        'total': totalCalls,
        'success': successCalls,
        'failed': failedCalls,
        'retried': retriedCalls,
        'cancelled': cancelledCalls,
        'timedOut': timedOutCalls,
        'avgMs': avgLatency.inMilliseconds,
        'maxMs': maxLatency.inMilliseconds,
        'minMs': minLatency.inMilliseconds,
        'successRate': successRate,
        'reconnects': reconnectCount,
        'unavailable': unavailableCount,
        'deadline': deadlineCount,
        'internal': internalCount,
        'unknown': unknownCount,
      };
}

class XlRetryPolicy {
  final int maxRetries;
  final Duration baseDelay;
  final Duration maxDelay;
  final double multiplier;
  final double jitter;
  final bool retryOnUnavailable;
  final bool retryOnDeadline;
  final bool retryOnInternal;
  const XlRetryPolicy({
    this.maxRetries = 5,
    this.baseDelay = const Duration(seconds: 1),
    this.maxDelay = const Duration(seconds: 12),
    this.multiplier = 1.6,
    this.jitter = 0.2,
    this.retryOnUnavailable = true,
    this.retryOnDeadline = false,
    this.retryOnInternal = false,
  });
  static const defaultPolicy = XlRetryPolicy();
  static const aggressive = XlRetryPolicy(
    maxRetries: 8,
    baseDelay: Duration(milliseconds: 400),
    maxDelay: Duration(seconds: 6),
    multiplier: 1.35,
    jitter: 0.3,
    retryOnDeadline: true,
  );
  static const conservative = XlRetryPolicy(
    maxRetries: 2,
    baseDelay: Duration(seconds: 2),
    maxDelay: Duration(seconds: 4),
    multiplier: 2.0,
    jitter: 0.1,
  );
  static const fast = XlRetryPolicy(
    maxRetries: 3,
    baseDelay: Duration(milliseconds: 200),
    maxDelay: Duration(milliseconds: 800),
    multiplier: 1.5,
    jitter: 0.15,
  );
  Duration delayFor(int attempt) {
    final base = baseDelay.inMilliseconds * _pow(multiplier, attempt);
    final capped = base > maxDelay.inMilliseconds ? maxDelay.inMilliseconds.toDouble() : base;
    final jit = capped * jitter * (_rand() * 2 - 1);
    final total = (capped + jit).clamp(0.0, maxDelay.inMilliseconds.toDouble());
    return Duration(milliseconds: total.round());
  }
  double _pow(double base, int exp) {
    var r = 1.0;
    for (var i = 0; i < exp; i++) {
      r *= base;
    }
    return r;
  }
  double _rand() {
    final t = DateTime.now().microsecondsSinceEpoch % 10000;
    return t / 10000.0;
  }
  bool shouldRetry(GrpcError e) {
    switch (e.code) {
      case StatusCode.unavailable:
        return retryOnUnavailable;
      case StatusCode.deadlineExceeded:
        return retryOnDeadline;
      case StatusCode.internal:
        return retryOnInternal;
      default:
        return false;
    }
  }
}

class XlEndpoint {
  final String host;
  final int port;
  final String label;
  final int priority;
  const XlEndpoint(this.host, this.port, this.label, this.priority);
  static const primary = XlEndpoint('localhost', 50051, 'primary', 0);
  static const ipv4 = XlEndpoint('127.0.0.1', 50051, 'ipv4', 1);
  static const ipv6 = XlEndpoint('::1', 50051, 'ipv6', 2);
  String get address => '$host:$port';
  @override
  String toString() => '$label@$address';
}

class XlClient {
  static ClientChannel? _chan;
  static XiaoLingClient? _stub;
  static final XlMetrics metrics = XlMetrics();
  static final List<XlConnectionEvent> _events = [];
  static final StreamController<XlConnectionEvent> _eventCtrl =
      StreamController<XlConnectionEvent>.broadcast();
  static final StreamController<XlMetrics> _metricsCtrl =
      StreamController<XlMetrics>.broadcast();
  static XlConnectionState _state = XlConnectionState.idle;
  static XlEndpoint _endpoint = XlEndpoint.primary;
  static XlRetryPolicy _policy = XlRetryPolicy.defaultPolicy;
  static Timer? _healthTimer;
  static Timer? _metricsTimer;
  static bool _autoReconnect = true;
  static bool _healthProbe = false;
  static Duration _defaultTimeout = const Duration(seconds: 30);
  static int _activeCalls = 0;
  static int _peakConcurrent = 0;
  static final List<_PendingCall> _pending = [];
  static bool _keepAlive = true;
  static ConnectionChangedCallback? _onConnectionChanged;
  static Timer? _reconnectTimer;
  static int _reconnectAttempts = 0;
  static const int maxReconnectAttempts = 5;
  static const List<Duration> _backoffSchedule = [
    Duration(seconds: 1),
    Duration(seconds: 2),
    Duration(seconds: 4),
    Duration(seconds: 8),
    Duration(seconds: 16),
  ];

  static XlConnectionState get state => _state;
  static XlEndpoint get endpoint => _endpoint;
  static XlRetryPolicy get policy => _policy;
  static bool get isConnected => _state == XlConnectionState.connected;
  static bool get isBusy => _activeCalls > 0;
  static int get activeCalls => _activeCalls;
  static int get peakConcurrent => _peakConcurrent;
  static List<XlConnectionEvent> get events => List.unmodifiable(_events);
  static Stream<XlConnectionEvent> get onEvent => _eventCtrl.stream;
  static Stream<XlMetrics> get onMetrics => _metricsCtrl.stream;
  static Duration get defaultTimeout => _defaultTimeout;
  static ConnectionChangedCallback? get onConnectionChanged => _onConnectionChanged;
  static set onConnectionChanged(ConnectionChangedCallback? cb) {
    _onConnectionChanged = cb;
    if (cb != null) cb(_mapStatus(_state));
  }

  static XiaoLingClient get stub {
    _ensureChannel();
    return _stub!;
  }

  static ClientChannel get channel {
    _ensureChannel();
    return _chan!;
  }

  static void _ensureChannel() {
    if (_chan != null && _stub != null) return;
    _setState(XlConnectionState.connecting, detail: _endpoint.address);
    try {
      _chan = ClientChannel(
        _endpoint.host,
        port: _endpoint.port,
        options: ChannelOptions(
          credentials: ChannelCredentials.insecure(),
          connectTimeout: Duration(seconds: 5),
          idleTimeout: Duration(minutes: 10),
          keepAlive: ClientKeepAliveOptions(
            pingInterval: Duration(seconds: _keepAlive ? 30 : 86400),
            timeout: Duration(seconds: 10),
            permitWithoutCalls: true,
          ),
        ),
      );
      _stub = XiaoLingClient(_chan!);
      _startMetricsTimer();
    } catch (e) {
      _setState(XlConnectionState.failed, detail: 'channel init failed: $e');
      rethrow;
    }
  }

  static void _setState(XlConnectionState s, {String? detail, Duration? latency}) {
    if (_state == s && detail == null) return;
    final prev = _state;
    _state = s;
    final ev = XlConnectionEvent(state: s, at: DateTime.now(), detail: detail, latency: latency);
    _events.add(ev);
    if (_events.length > 200) _events.removeAt(0);
    if (!_eventCtrl.isClosed) _eventCtrl.add(ev);
    if (_onConnectionChanged != null && _mapStatus(prev) != _mapStatus(s)) {
      _onConnectionChanged!(_mapStatus(s));
    }
  }

  static void scheduleAutoReconnect() {
    _reconnectTimer?.cancel();
    if (_reconnectAttempts >= maxReconnectAttempts) return;
    final delay = _backoffSchedule[
        _reconnectAttempts.clamp(0, _backoffSchedule.length - 1)];
    _reconnectAttempts++;
    _reconnectTimer = Timer(delay, () async {
      metrics.reconnect();
      final ok = await ping();
      if (ok) {
        _reconnectAttempts = 0;
        await reconnect(force: true);
      } else {
        scheduleAutoReconnect();
      }
    });
  }

  static void cancelAutoReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _reconnectAttempts = 0;
  }

  static void _startMetricsTimer() {
    _metricsTimer?.cancel();
    _metricsTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (!_metricsCtrl.isClosed) _metricsCtrl.add(metrics);
    });
  }

  static Future<T> withRetry<T>(
    Future<T> Function(XiaoLingClient stub) call, {
    int maxRetries = 5,
    XlRetryPolicy? policy,
    Duration? timeout,
    String? label,
    bool silent = false,
  }) async {
    final pol = policy ?? _policy;
    final limit = maxRetries == 5 ? pol.maxRetries : maxRetries;
    final t = timeout ?? _defaultTimeout;
    final tag = label ?? 'call';
    final callId = _nextCallId();
    final pending = _PendingCall(callId, tag, DateTime.now());
    _pending.add(pending);
    _activeCalls++;
    if (_activeCalls > _peakConcurrent) _peakConcurrent = _activeCalls;

    Object? lastError;
    StackTrace? lastStack;
    for (var i = 0; i < limit; i++) {
      if (pending.cancelled) {
        metrics.cancel();
        _activeCalls--;
        _pending.remove(pending);
        throw GrpcError.cancelled('已取消 · $tag');
      }
      final sw = Stopwatch()..start();
      try {
        final result = await call(stub).timeout(t);
        sw.stop();
        metrics.record(sw.elapsed);
        _setState(XlConnectionState.connected, latency: sw.elapsed);
        _activeCalls--;
        _pending.remove(pending);
        if (!silent) _emitMetrics();
        return result;
      } on GrpcError catch (e) {
        sw.stop();
        lastError = e;
        lastStack = StackTrace.current;
        metrics.fail(e);
        if (e.code == StatusCode.unavailable) {
          _setState(XlConnectionState.reconnecting, detail: '$tag · ${'${e.code}'}');
        }
        if (!pol.shouldRetry(e) || i >= limit - 1) {
          _activeCalls--;
          _pending.remove(pending);
          _emitMetrics();
          Error.throwWithStackTrace(e, lastStack);
        }
        metrics.retry();
        final d = pol.delayFor(i);
        if (!silent) {
          _setState(XlConnectionState.reconnecting, detail: 'retry ${i + 1}/$limit in ${d.inMilliseconds}ms');
        }
        await Future.delayed(d);
      } on TimeoutException catch (e) {
        sw.stop();
        lastError = e;
        lastStack = StackTrace.current;
        metrics.timeout();
        _setState(XlConnectionState.reconnecting, detail: '$tag · timeout');
        if (i >= limit - 1) {
          _activeCalls--;
          _pending.remove(pending);
          _emitMetrics();
          throw GrpcError.deadlineExceeded('请求超时 · $tag');
        }
        metrics.retry();
        await Future.delayed(pol.delayFor(i));
      } catch (e) {
        sw.stop();
        lastError = e;
        lastStack = StackTrace.current;
        metrics.fail(e);
        _activeCalls--;
        _pending.remove(pending);
        _emitMetrics();
        rethrow;
      }
    }
    _activeCalls--;
    _pending.remove(pending);
    _emitMetrics();
    if (lastError is GrpcError) {
      Error.throwWithStackTrace(lastError, lastStack ?? StackTrace.current);
    }
    throw GrpcError.unavailable('后端连接失败 · $tag · $lastError');
  }

  static Future<T> call<T>(
    Future<T> Function(XiaoLingClient stub) call, {
    XlRetryPolicy? policy,
    Duration? timeout,
    String? label,
    bool silent = false,
  }) =>
      withRetry(call, policy: policy, timeout: timeout, label: label, silent: silent);

  static Future<T?> safeCall<T>(
    Future<T> Function(XiaoLingClient stub) call, {
    XlRetryPolicy? policy,
    Duration? timeout,
    String? label,
  }) async {
    try {
      return await withRetry(call, policy: policy, timeout: timeout, label: label, silent: true);
    } catch (_) {
      return null;
    }
  }

  static Future<T> fastCall<T>(
    Future<T> Function(XiaoLingClient stub) call, {
    String? label,
  }) =>
      withRetry(call, policy: XlRetryPolicy.fast, timeout: const Duration(seconds: 8), label: label);

  static Future<T> slowCall<T>(
    Future<T> Function(XiaoLingClient stub) call, {
    String? label,
  }) =>
      withRetry(call, policy: XlRetryPolicy.conservative, timeout: const Duration(minutes: 3), label: label);

  static Future<T> backgroundCall<T>(
    Future<T> Function(XiaoLingClient stub) call, {
    String? label,
  }) =>
      withRetry(call, timeout: const Duration(minutes: 10), label: label, silent: true);

  static Future<bool> ping() async {
    try {
      await withRetry(
        (s) => s.getStatus(StatusRequest()),
        policy: XlRetryPolicy.fast,
        timeout: const Duration(seconds: 4),
        label: 'ping',
        silent: true,
      );
      _setState(XlConnectionState.connected);
      return true;
    } catch (_) {
      _setState(XlConnectionState.disconnected);
      return false;
    }
  }

  static String _nextCallId() =>
      '${DateTime.now().microsecondsSinceEpoch.toRadixString(36)}-${(_pending.length + 1).toRadixString(36)}';

  static void _emitMetrics() {
    if (!_metricsCtrl.isClosed) _metricsCtrl.add(metrics);
  }

  static void cancelAll() {
    for (final p in _pending) {
      p.cancel();
    }
    metrics.cancelledCalls += _activeCalls;
    _activeCalls = 0;
    _pending.clear();
  }

  static bool cancel(String callId) {
    for (final p in _pending) {
      if (p.id == callId) {
        p.cancel();
        return true;
      }
    }
    return false;
  }

  static Future<void> reconnect({bool force = false}) async {
    if (!_autoReconnect && !force) return;
    metrics.reconnect();
    _setState(XlConnectionState.reconnecting, detail: 'manual reconnect');
    await _shutdownChannel();
    _endpoint = XlEndpoint.primary;
    _ensureChannel();
    final ok = await ping();
    if (ok) {
      _setState(XlConnectionState.connected, detail: 'reconnected');
    } else {
      await _fallbackEndpoint();
    }
  }

  static Future<void> _fallbackEndpoint() async {
    final candidates = [XlEndpoint.primary, XlEndpoint.ipv4, XlEndpoint.ipv6];
    for (final ep in candidates) {
      if (ep.address == _endpoint.address) continue;
      _setState(XlConnectionState.reconnecting, detail: 'try ${ep.address}');
      await _shutdownChannel();
      _endpoint = ep;
      _ensureChannel();
      final ok = await ping();
      if (ok) {
        _setState(XlConnectionState.connected, detail: 'fallback to ${ep.label}');
        return;
      }
    }
    _setState(XlConnectionState.failed, detail: 'all endpoints failed');
  }

  static Future<void> _shutdownChannel() async {
    try {
      await _chan?.shutdown();
    } catch (e) { debugPrint('操作失败: $e'); }
    _chan = null;
    _stub = null;
  }

  static void startHealthProbe({Duration interval = const Duration(seconds: 20)}) {
    stopHealthProbe();
    _healthProbe = true;
    _healthTimer = Timer.periodic(interval, (_) async {
      if (!_healthProbe) return;
      if (_state == XlConnectionState.reconnecting || _state == XlConnectionState.connecting) return;
      final ok = await ping();
      if (!ok && _autoReconnect) {
        await reconnect(force: true);
      }
    });
  }

  static void stopHealthProbe() {
    _healthProbe = false;
    _healthTimer?.cancel();
    _healthTimer = null;
  }

  static bool get healthProbeActive => _healthProbe;

  static void setAutoReconnect(bool enabled) {
    _autoReconnect = enabled;
    if (!enabled) {
      stopHealthProbe();
    } else if (!_healthProbe) {
      startHealthProbe();
    }
  }

  static bool get autoReconnect => _autoReconnect;

  static void setDefaultTimeout(Duration d) {
    _defaultTimeout = d;
  }

  static void setPolicy(XlRetryPolicy p) {
    _policy = p;
  }

  static void setKeepAlive(bool enabled) {
    if (_keepAlive == enabled) return;
    _keepAlive = enabled;
    // keepAlive 参数在建channel 时固化，需重建才生效
    if (_chan != null) {
      unawaited(_rebuild());
    }
  }

  static Future<void> _rebuild() async {
    await _shutdownChannel();
    _ensureChannel();
  }

  static Future<void> setEndpoint(XlEndpoint ep) async {
    if (ep.address == _endpoint.address) return;
    await _shutdownChannel();
    _endpoint = ep;
    _ensureChannel();
  }

  static Future<void> dispose() async {
    stopHealthProbe();
    _metricsTimer?.cancel();
    _metricsTimer = null;
    cancelAll();
    await _shutdownChannel();
    _setState(XlConnectionState.closed);
    _events.clear();
    metrics.reset();
    if (!_eventCtrl.isClosed) await _eventCtrl.close();
    if (!_metricsCtrl.isClosed) await _metricsCtrl.close();
  }

  static String describe() {
    final buf = StringBuffer();
    buf.writeln('endpoint: ${_endpoint.address} (${_endpoint.label})');
    buf.writeln('state: ${_state.name}');
    buf.writeln('active: $_activeCalls  peak: $_peakConcurrent');
    buf.writeln('calls: ${metrics.totalCalls}  success: ${metrics.successCalls}  failed: ${metrics.failedCalls}');
    buf.writeln('rate: ${(metrics.successRate * 100).toStringAsFixed(1)}%');
    buf.writeln('avg: ${metrics.avgLatency.inMilliseconds}ms  max: ${metrics.maxLatency.inMilliseconds}ms');
    buf.writeln('retries: ${metrics.retriedCalls}  reconnects: ${metrics.reconnectCount}');
    buf.writeln('healthProbe: $_healthProbe  autoReconnect: $_autoReconnect');
    return buf.toString();
  }

  static List<XlConnectionEvent> recentEvents({int limit = 10}) {
    final start = _events.length - limit;
    if (start <= 0) return List.unmodifiable(_events);
    return List.unmodifiable(_events.sublist(start));
  }
}

class _PendingCall {
  final String id;
  final String label;
  final DateTime startedAt;
  bool cancelled = false;
  _PendingCall(this.id, this.label, this.startedAt);
  void cancel() => cancelled = true;
  Duration get age => DateTime.now().difference(startedAt);
}