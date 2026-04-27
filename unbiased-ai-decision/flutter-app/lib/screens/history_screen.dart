import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../services/auth_service.dart';
import '../services/firebase_service.dart';
import 'report_screen.dart';

class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  Color _badgeColor(double score) {
    if (score <= 30) {
      return const Color(0xFF16A34A);
    }
    if (score <= 60) {
      return const Color(0xFFF59E0B);
    }
    return const Color(0xFFDC2626);
  }

  String _formatDate(dynamic value) {
    if (value is DateTime) {
      return DateFormat.yMMMd().add_jm().format(value);
    }
    if (value is String) {
      final parsed = DateTime.tryParse(value);
      if (parsed != null) {
        return DateFormat.yMMMd().add_jm().format(parsed.toLocal());
      }
    }
    return value?.toString() ?? 'Unknown date';
  }

  @override
  Widget build(BuildContext context) {
    final session = AuthService.instance.currentSession;
    if (session == null) {
      return const Scaffold(
        body: Center(child: Text('Sign in to view your audit history.')),
      );
    }

    final stream = session.isGuest
        ? Stream<List<Map<String, dynamic>>>.fromFuture(
            FirebaseService.instance
                .fetchRecentAudits(session.uid, limit: 20)
                .then(
              (audits) async {
                if (audits.isNotEmpty) {
                  return audits;
                }

                final sample =
                    await FirebaseService.instance.fetchSampleAudit();
                return [sample];
              },
            ),
          )
        : FirebaseService.instance.streamAuditHistory(session.uid);

    return Scaffold(
      appBar: AppBar(title: const Text('Audit History')),
      body: StreamBuilder<List<Map<String, dynamic>>>(
        stream: stream,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          final audits = snapshot.data ?? <Map<String, dynamic>>[];
          if (audits.isEmpty) {
            return const Center(
              child: Text(
                  'No audit history yet. Run your first audit to populate this view.'),
            );
          }

          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemBuilder: (context, index) {
              final audit = audits[index];
              final score = (audit['bias_score'] as num?)?.toDouble() ?? 0;
              return ListTile(
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(18)),
                tileColor: Colors.white,
                title: Text('${audit['model_name'] ?? 'Untitled model'}'),
                subtitle: Text(_formatDate(audit['created_at'])),
                trailing: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: _badgeColor(score).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    '${score.toStringAsFixed(0)}/100',
                    style: TextStyle(
                      color: _badgeColor(score),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => ReportScreen(initialAudit: audit),
                    ),
                  );
                },
              );
            },
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemCount: audits.length,
          );
        },
      ),
    );
  }
}
