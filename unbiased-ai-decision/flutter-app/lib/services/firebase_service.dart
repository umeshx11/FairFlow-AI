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

  CollectionReference<Map<String, dynamic>> get audits =>
      _firestore!.collection('audits');

  bool get usesFirestore => _firestore != null;

  String createAuditId() {
    if (_firestore != null) {
      return audits.doc().id;
    }
    return 'local-${DateTime.now().microsecondsSinceEpoch}';
  }

  Future<Map<String, dynamic>> fetchSampleAudit() async {
    if (_firestore == null) {
      return ApiService.instance.fetchAudit(sampleAuditId);
    }

    final snapshot = await audits.doc(sampleAuditId).get();
    if (snapshot.exists) {
      return _withId(snapshot.data() ?? <String, dynamic>{}, snapshot.id);
    }

    try {
      return await ApiService.instance.fetchAudit(sampleAuditId);
    } catch (_) {
      throw Exception('Sample audit is not seeded yet.');
    }
  }

  Future<Map<String, dynamic>?> fetchAuditById(String auditId) async {
    if (_firestore == null) {
      return ApiService.instance.fetchAudit(auditId);
    }

    final snapshot = await audits.doc(auditId).get();
    if (!snapshot.exists) {
      return ApiService.instance.fetchAudit(auditId);
    }
    return _withId(snapshot.data() ?? <String, dynamic>{}, snapshot.id);
  }

  Future<List<Map<String, dynamic>>> fetchRecentAudits(
    String userId, {
    int limit = 5,
  }) async {
    if (_firestore == null) {
      final history = await ApiService.instance.fetchAuditHistory(userId);
      return history.take(limit).toList(growable: false);
    }

    final query = await audits
        .where('user_id', isEqualTo: userId)
        .orderBy('created_at', descending: true)
        .limit(limit)
        .get();
    return query.docs.map((doc) => _withId(doc.data(), doc.id)).toList();
  }

  Stream<Map<String, dynamic>?> streamAudit(String auditId) {
    if (_firestore == null) {
      return _pollAudit(auditId);
    }

    return audits.doc(auditId).snapshots().map((snapshot) {
      if (!snapshot.exists) {
        return null;
      }
      return _withId(snapshot.data() ?? <String, dynamic>{}, snapshot.id);
    });
  }

  Stream<List<Map<String, dynamic>>> streamAuditHistory(
    String userId, {
    int limit = 20,
  }) {
    if (_firestore == null) {
      return _pollAuditHistory(userId, limit: limit);
    }

    return audits
        .where('user_id', isEqualTo: userId)
        .orderBy('created_at', descending: true)
        .limit(limit)
        .snapshots()
        .map(
          (snapshot) => snapshot.docs
              .map((doc) => _withId(doc.data(), doc.id))
              .toList(growable: false),
        );
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
