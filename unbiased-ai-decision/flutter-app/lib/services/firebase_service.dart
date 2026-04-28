import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';

import 'api_service.dart';
import 'app_runtime.dart';

class FirebaseService {
  FirebaseService._();

  static final FirebaseService instance = FirebaseService._();

  static const String sampleAuditId = 'sample_hiring_audit';

  final FirebaseFirestore? _firestore =
      AppRuntime.firebaseWebConfigured ? FirebaseFirestore.instance : null;
  bool _preferLocalMode = false;

  CollectionReference<Map<String, dynamic>> get audits =>
      _firestore!.collection('audits');

  bool get usesFirestore => !_shouldUseLocalMode;

  bool get _shouldUseLocalMode => _preferLocalMode || _firestore == null;

  void useLocalDemoMode() {
    _preferLocalMode = true;
  }

  void useFirestoreWhenAvailable() {
    _preferLocalMode = false;
  }

  String createAuditId() {
    if (!_shouldUseLocalMode) {
      return audits.doc().id;
    }
    return 'local-${DateTime.now().microsecondsSinceEpoch}';
  }

  Future<Map<String, dynamic>> fetchSampleAudit() async {
    if (_shouldUseLocalMode) {
      return ApiService.instance.fetchAudit(sampleAuditId);
    }

    try {
      final snapshot = await audits.doc(sampleAuditId).get();
      if (snapshot.exists) {
        return _withId(snapshot.data() ?? <String, dynamic>{}, snapshot.id);
      }
    } catch (_) {
      // Fall back to the backend sample audit when Firestore is unavailable.
    }

    try {
      return await ApiService.instance.fetchAudit(sampleAuditId);
    } catch (_) {
      throw Exception('Sample audit is not seeded yet.');
    }
  }

  Future<Map<String, dynamic>?> fetchAuditById(String auditId) async {
    if (_shouldUseLocalMode) {
      return ApiService.instance.fetchAudit(auditId);
    }

    try {
      final snapshot = await audits.doc(auditId).get();
      if (snapshot.exists) {
        return _withId(snapshot.data() ?? <String, dynamic>{}, snapshot.id);
      }
    } catch (_) {
      // Fall back to the backend audit lookup when Firestore is unavailable.
    }

    return ApiService.instance.fetchAudit(auditId);
  }

  Future<List<Map<String, dynamic>>> fetchRecentAudits(
    String userId, {
    int limit = 5,
  }) async {
    if (_shouldUseLocalMode) {
      final history = await ApiService.instance.fetchAuditHistory(userId);
      return history.take(limit).toList(growable: false);
    }

    try {
      final query = await audits
          .where('user_id', isEqualTo: userId)
          .orderBy('created_at', descending: true)
          .limit(limit)
          .get();
      return query.docs.map((doc) => _withId(doc.data(), doc.id)).toList();
    } catch (_) {
      final history = await ApiService.instance.fetchAuditHistory(userId);
      return history.take(limit).toList(growable: false);
    }
  }

  Stream<Map<String, dynamic>?> streamAudit(String auditId) {
    if (_shouldUseLocalMode) {
      return _pollAudit(auditId);
    }

    return (() async* {
      try {
        final snapshot = await audits.doc(auditId).get();
        if (!snapshot.exists) {
          yield* _pollAudit(auditId);
          return;
        }

        await for (final liveSnapshot in audits.doc(auditId).snapshots()) {
          if (!liveSnapshot.exists) {
            yield null;
            continue;
          }
          yield _withId(
            liveSnapshot.data() ?? <String, dynamic>{},
            liveSnapshot.id,
          );
        }
      } catch (_) {
        yield* _pollAudit(auditId);
      }
    })();
  }

  Stream<List<Map<String, dynamic>>> streamAuditHistory(
    String userId, {
    int limit = 20,
  }) {
    if (_shouldUseLocalMode) {
      return _pollAuditHistory(userId, limit: limit);
    }

    return (() async* {
      try {
        final query = audits
            .where('user_id', isEqualTo: userId)
            .orderBy('created_at', descending: true)
            .limit(limit);

        await for (final snapshot in query.snapshots()) {
          yield snapshot.docs
              .map((doc) => _withId(doc.data(), doc.id))
              .toList(growable: false);
        }
      } catch (_) {
        yield* _pollAuditHistory(userId, limit: limit);
      }
    })();
  }

  Stream<Map<String, dynamic>?> _pollAudit(String auditId) async* {
    var misses = 0;
    while (true) {
      try {
        final audit = await fetchAuditById(auditId);
        if (audit != null) {
          misses = 0;
          yield audit;
          final status = audit['status']?.toString() ?? '';
          final stage = audit['stage']?.toString() ?? '';
          if (status == 'completed' ||
              status == 'failed' ||
              stage == 'complete' ||
              stage == 'failed') {
            return;
          }
        }
      } catch (_) {
        misses += 1;
        if (misses >= 10) {
          return;
        }
      }
      await Future.delayed(const Duration(seconds: 1));
    }
  }

  Stream<List<Map<String, dynamic>>> _pollAuditHistory(
    String userId, {
    int limit = 20,
  }) async* {
    while (true) {
      yield await fetchRecentAudits(userId, limit: limit);
      await Future.delayed(const Duration(seconds: 2));
    }
  }

  Future<Map<String, dynamic>> computeDashboardSummary(
    String userId, {
    bool includeSample = false,
  }) async {
    final recentAudits = await fetchRecentAudits(userId, limit: 25);
    final items = <Map<String, dynamic>>[...recentAudits];
    if (includeSample && items.isEmpty) {
      items.add(await fetchSampleAudit());
    }

    final biasScores = items
        .map((audit) => (audit['bias_score'] as num?)?.toDouble() ?? 0)
        .toList(growable: false);
    final avgBias = biasScores.isEmpty
        ? 0.0
        : biasScores.reduce((left, right) => left + right) / biasScores.length;

    return {
      'auditsRun': items.length,
      'avgBiasScore': avgBias,
      'sdgAlignment': 'SDG 10.3, 8.5, 16.b',
      'recentAudits': items.take(5).toList(growable: false),
    };
  }

  Map<String, dynamic> _withId(Map<String, dynamic> data, String id) {
    return {
      'audit_id': id,
      ...data,
    };
  }
}
