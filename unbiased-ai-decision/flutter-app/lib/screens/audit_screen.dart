import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'report_screen.dart';

Future<T?> showAuditPreviewSheet<T>(
  BuildContext context, {
  required Map<String, dynamic> audit,
}) {
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => AuditPreviewSheet(audit: audit),
  );
}

class AuditScreen extends StatelessWidget {
  const AuditScreen({
    super.key,
    required this.audit,
  });

  final Map<String, dynamic> audit;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        title: const Text('Audit Preview'),
      ),
      body: SafeArea(
        child: Align(
          alignment: Alignment.bottomCenter,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
            child: AuditPreviewSheet(
              audit: audit,
              embedded: true,
            ),
          ),
        ),
      ),
    );
  }
}

class AuditPreviewSheet extends StatelessWidget {
  const AuditPreviewSheet({
    super.key,
    required this.audit,
    this.embedded = false,
  });

  final Map<String, dynamic> audit;
  final bool embedded;

  String _formatDate(dynamic value) {
    if (value is Timestamp) {
      final date = value.toDate();
      return '${date.day}/${date.month}/${date.year}';
    }
    if (value is DateTime) {
      return '${value.day}/${value.month}/${value.year}';
    }
    return value?.toString() ?? 'Unknown date';
  }

  double _score() => (audit['bias_score'] as num?)?.toDouble() ?? 0;

  Color _severityColor(double score) {
    if (score <= 30) return AppColors.success;
    if (score <= 60) return AppColors.warning;
    return AppColors.danger;
  }

  String _severityLabel(double score) {
    if (score <= 30) return 'Low Risk';
    if (score <= 60) return 'Moderate Risk';
    return 'High Risk';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;
    final score = _score();
    final severityColor = _severityColor(score);
    final severityLabel = _severityLabel(score);
    final modelName = audit['model_name']?.toString() ?? 'Untitled model';
    final datasetName = audit['dataset_name']?.toString() ?? 'Unknown dataset';
    final dateText = _formatDate(audit['created_at']);

    final content = Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isDark
              ? [
                  const Color(0xFF1A2340),
                  const Color(0xFF131B31),
                ]
              : [
                  Colors.white,
                  const Color(0xFFF7F9FF),
                ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(32),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(isDark ? 0.28 : 0.12),
            blurRadius: 24,
            offset: const Offset(0, 16),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(22, 14, 22, 22),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 44,
                height: 5,
                decoration: BoxDecoration(
                  color: theme.colorScheme.onSurfaceVariant.withOpacity(0.25),
                  borderRadius: BorderRadius.circular(999),
                ),
              ),
            ),
            const SizedBox(height: 18),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.accentAmber.withOpacity(0.14),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          'Quick audit preview',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: AppColors.accentAmber,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      const SizedBox(height: 14),
                      Text(
                        modelName,
                        style: theme.textTheme.headlineMedium?.copyWith(
                          color: theme.colorScheme.onSurface,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        datasetName,
                        style: theme.textTheme.bodyLarge?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 10,
                  ),
                  decoration: BoxDecoration(
                    color: severityColor.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Column(
                    children: [
                      Text(
                        '${score.toStringAsFixed(0)}/100',
                        style: theme.textTheme.titleLarge?.copyWith(
                          color: severityColor,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        severityLabel,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: severityColor,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: isDark
                    ? Colors.white.withOpacity(0.05)
                    : const Color(0xFFF8FAFF),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(
                  color: isDark
                      ? Colors.white.withOpacity(0.08)
                      : const Color(0xFFE1E8F5),
                ),
              ),
              child: Column(
                children: [
                  _PreviewMetricRow(
                    label: 'Bias score',
                    value: '${score.toStringAsFixed(0)}/100',
                    valueColor: severityColor,
                  ),
                  const SizedBox(height: 12),
                  _PreviewMetricRow(
                    label: 'SDG targets',
                    value: '10.3, 8.5, 16.b',
                    valueColor: AppColors.unBlue,
                  ),
                  const SizedBox(height: 12),
                  _PreviewMetricRow(
                    label: 'Created',
                    value: dateText,
                    valueColor: theme.colorScheme.onSurface,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            Text(
              'This preview is meant to help a non-technical reviewer decide whether to open the full report now. The full report includes the detailed fairness explanation, feature impact, and downloadable PDF.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                if (!embedded)
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.of(context).maybePop(),
                      child: const Text('Close'),
                    ),
                  ),
                if (!embedded) const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: FilledButton(
                    onPressed: () {
                      if (!embedded) {
                        Navigator.of(context).pop();
                      }
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => ReportScreen(initialAudit: audit),
                        ),
                      );
                    },
                    child: const Text('Open Full Report'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );

    if (embedded) {
      return content;
    }

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 16),
        child: content,
      ),
    );
  }
}

class _PreviewMetricRow extends StatelessWidget {
  const _PreviewMetricRow({
    required this.label,
    required this.value,
    required this.valueColor,
  });

  final String label;
  final String value;
  final Color valueColor;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Row(
      children: [
        Expanded(
          child: Text(
            label,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        Text(
          value,
          style: theme.textTheme.bodyMedium?.copyWith(
            color: valueColor,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    );
  }
}
