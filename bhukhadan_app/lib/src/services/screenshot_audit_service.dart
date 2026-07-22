import 'dart:async';
import 'dart:convert';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../constants/api_constants.dart';
import '../services/api_service.dart';
import '../utils/globals.dart';
import '../utils/storage.dart';

/// Detects screenshots (where OS allows), shows a brief notice, queues offline,
/// and POSTs to the Odoo audit API.
class ScreenshotAuditService {
  ScreenshotAuditService._();
  static final ScreenshotAuditService instance = ScreenshotAuditService._();

  static const MethodChannel _channel = MethodChannel('bhukhadan/screenshot_audit');
  static const int _maxQueue = 50;
  static const int _maxRetries = 8;

  bool _started = false;
  String _screenName = 'unknown';
  int? _surveyId;
  bool _flushing = false;
  DateTime? _lastNoticeAt;

  Future<void> start() async {
    if (_started) return;
    _started = true;
    _channel.setMethodCallHandler(_onPlatformCall);
    try {
      await _channel.invokeMethod('enableSecure');
    } catch (e) {
      debugPrint('[ScreenshotAudit] enableSecure: $e');
    }
    unawaited(flushQueue());
  }

  void stop() {
    _channel.setMethodCallHandler(null);
    _started = false;
  }

  void setContext({String? screenName, int? surveyId, bool clearSurvey = false}) {
    if (screenName != null && screenName.isNotEmpty) {
      _screenName = screenName;
    }
    if (clearSurvey) {
      _surveyId = null;
    }
    if (surveyId != null) {
      _surveyId = surveyId;
    }
  }

  Future<void> _onPlatformCall(MethodCall call) async {
    if (call.method == 'onScreenshot') {
      await onScreenshotDetected();
    }
  }

  Future<void> onScreenshotDetected() async {
    try {
      _showRecordedNotice();
      final event = {
        'screen_name': _screenName,
        'platform': _platformLabel(),
        if (_surveyId != null) 'survey_id': _surveyId,
        'device_info': _deviceInfo(),
        'queued_at': DateTime.now().toUtc().toIso8601String(),
        'retries': 0,
      };
      await _enqueue(event);
      await flushQueue();
    } catch (e) {
      debugPrint('[ScreenshotAudit] onScreenshotDetected error: $e');
    }
  }

  String _platformLabel() {
    if (kIsWeb) return 'web';
    try {
      if (Platform.isAndroid) return 'android';
      if (Platform.isIOS) return 'ios';
      if (Platform.isLinux) return 'linux';
      if (Platform.isWindows) return 'windows';
      if (Platform.isMacOS) return 'macos';
    } catch (_) {}
    return 'unknown';
  }

  String _deviceInfo() {
    if (kIsWeb) return 'web';
    try {
      return '${Platform.operatingSystem} ${Platform.operatingSystemVersion}';
    } catch (_) {
      return 'unknown';
    }
  }

  void _showRecordedNotice() {
    final now = DateTime.now();
    if (_lastNoticeAt != null && now.difference(_lastNoticeAt!).inSeconds < 2) {
      return;
    }
    _lastNoticeAt = now;
    final ctx = navigatorKey.currentContext;
    if (ctx == null) return;
    final messenger = ScaffoldMessenger.maybeOf(ctx);
    messenger?.hideCurrentSnackBar();
    messenger?.showSnackBar(
      const SnackBar(
        content: Text('Screenshot recorded for audit'),
        duration: Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  Future<List<Map<String, dynamic>>> _loadQueue() async {
    final raw = await getAsyncItem(SCREENSHOT_AUDIT_QUEUE_KEY);
    if (raw == null || raw.isEmpty) return [];
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! List) return [];
      return decoded
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> _saveQueue(List<Map<String, dynamic>> queue) async {
    if (queue.isEmpty) {
      await removeAsyncItem(SCREENSHOT_AUDIT_QUEUE_KEY);
      return;
    }
    await setAsyncItem(SCREENSHOT_AUDIT_QUEUE_KEY, jsonEncode(queue));
  }

  Future<void> _enqueue(Map<String, dynamic> event) async {
    final queue = await _loadQueue();
    queue.add(event);
    while (queue.length > _maxQueue) {
      queue.removeAt(0);
    }
    await _saveQueue(queue);
  }

  Future<void> flushQueue() async {
    if (_flushing) return;
    _flushing = true;
    try {
      final token = await getAsyncItem(AUTH_TOKEN_KEY);
      if (token == null || token.isEmpty) return;

      var queue = await _loadQueue();
      if (queue.isEmpty) return;

      final remaining = <Map<String, dynamic>>[];
      for (final event in queue) {
        final ok = await _postEvent(event);
        if (!ok) {
          final retries = (event['retries'] is int) ? event['retries'] as int : 0;
          if (retries + 1 < _maxRetries) {
            remaining.add({...event, 'retries': retries + 1});
          } else {
            remaining.add({...event, 'retries': retries});
          }
        }
      }
      await _saveQueue(remaining);
    } catch (e) {
      debugPrint('[ScreenshotAudit] flushQueue error: $e');
    } finally {
      _flushing = false;
    }
  }

  Future<bool> _postEvent(Map<String, dynamic> event) async {
    try {
      final body = <String, dynamic>{
        'screen_name': event['screen_name'],
        'platform': event['platform'],
        'device_info': event['device_info'],
      };
      if (event['survey_id'] != null) {
        body['survey_id'] = event['survey_id'];
      }
      final response = await ApiService.post(ApiEndpoints.screenshotAudit, body);
      return response.statusCode == 200 || response.statusCode == 201;
    } catch (e) {
      debugPrint('[ScreenshotAudit] post failed: $e');
      return false;
    }
  }
}
