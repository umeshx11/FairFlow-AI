import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

import '../theme/app_theme.dart';
import '../widgets/bias_gauge.dart';
import '../widgets/causal_graph.dart';
import '../widgets/gemini_card.dart';
import '../widgets/sdg_badge.dart';
import '../widgets/shap_chart.dart';
import 'upload_screen.dart';

class ReportScreen extends StatefulWidget {
  const ReportScreen({
    super.key,
    required this.initialAudit,
  });

  final Map<String, dynamic> initialAudit;

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  bool _summaryExpanded = true;

  String _formatDate(dynamic value) {
    if (value is Timestamp) {
      return DateFormat.yMMMd().add_jm().format(value.toDate());
    }
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

  double _metric(Map<String, dynamic> source, String key) {
    if (source[key] is num) {
      return (source[key] as num).toDouble();
    }
    final nested = source['fairness_metrics'];
    if (nested is Map<String, dynamic> && nested[key] is num) {
      return (nested[key] as num).toDouble();
    }
    return 0;
  }

  List<Map<String, dynamic>> _shapValues() {
    return _listMaps('shap_values');
  }

  List<Map<String, dynamic>> _listMaps(String key) {
    final raw = widget.initialAudit[key];
    if (raw is List) {
      return raw
          .whereType<Map>()
          .map((item) => item.cast<String, dynamic>())
          .toList();
    }
    return <Map<String, dynamic>>[];
  }

  Map<String, dynamic> _mapValue(String key) {
    final raw = widget.initialAudit[key];
    if (raw is Map) {
      return raw.cast<String, dynamic>();
    }
    return <String, dynamic>{};
  }

  double _biasScore() =>
      (widget.initialAudit['bias_score'] as num?)?.toDouble() ?? 0;

  String _severityLabel(double score) {
    if (score <= 30) return 'Low Risk';
    if (score <= 60) return 'Moderate Risk';
    return 'High Risk';
  }

  Color _severityColor(double score) {
    if (score <= 30) return AppColors.success;
    if (score <= 60) return AppColors.warning;
    return AppColors.danger;
  }

  Future<void> _sharePdf() async {
    final pdf = pw.Document();
    final modelName = widget.initialAudit['model_name']?.toString() ??
        'Unbiased AI Decision Report';

    pdf.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        build: (context) => [
          pw.Text(
            modelName,
            style: pw.TextStyle(
              fontSize: 22,
              fontWeight: pw.FontWeight.bold,
            ),
          ),
          pw.SizedBox(height: 12),
          pw.Text('Bias score: ${_biasScore().toStringAsFixed(0)}/100'),
          pw.Text(
            'Risk level: ${_severityLabel(_biasScore())}',
          ),
          pw.Text(
            'Dataset: ${widget.initialAudit['dataset_name'] ?? 'Unknown'}',
          ),
          pw.Text(
            'Domain: ${widget.initialAudit['domain'] ?? 'general'}',
          ),
          pw.Text(
            'Analysis backend: ${widget.initialAudit['analysis_backend'] ?? 'local'}',
          ),
          pw.Text(
            'Created: ${_formatDate(widget.initialAudit['created_at'])}',
          ),
          pw.Text(
            'SDG targets: 10.3, 8.5, 16.b',
          ),
          pw.SizedBox(height: 18),
          pw.Text(
            'AI Fairness Insight',
            style: pw.TextStyle(
              fontSize: 16,
              fontWeight: pw.FontWeight.bold,
            ),
          ),
          pw.SizedBox(height: 8),
          pw.Text(widget.initialAudit['gemini_explanation']?.toString() ?? ''),
          if ((widget.initialAudit['gemini_legal_risk'] ?? '')
              .toString()
              .isNotEmpty) ...[
            pw.SizedBox(height: 12),
            pw.Text(widget.initialAudit['gemini_legal_risk'].toString()),
          ],
          pw.SizedBox(height: 18),
          pw.Text(
            'Fairness Metrics',
            style: pw.TextStyle(
              fontSize: 16,
              fontWeight: pw.FontWeight.bold,
            ),
          ),
          pw.SizedBox(height: 8),
          pw.Bullet(
            text:
                'Demographic Parity Difference: ${_metric(widget.initialAudit, 'demographic_parity').toStringAsFixed(3)}',
          ),
          pw.Bullet(
            text:
                'Equalized Odds Difference: ${_metric(widget.initialAudit, 'equalized_odds').toStringAsFixed(3)}',
          ),
          pw.Bullet(
            text:
                'Individual Fairness Score: ${_metric(widget.initialAudit, 'individual_fairness').toStringAsFixed(3)}',
          ),
          pw.Bullet(
            text:
                'Calibration Error: ${_metric(widget.initialAudit, 'calibration_error').toStringAsFixed(3)}',
          ),
        ],
      ),
    );
    await Printing.sharePdf(
      bytes: await pdf.save(),
      filename: 'unbiased-ai-report.pdf',
    );
  }

  void _startNewAudit() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const UploadScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final shapValues = _shapValues();
    final recommendations = _listMaps('gemini_recommendations');
    final auditQa = _listMaps('gemini_audit_qa');
    final candidateFlags = _listMaps('candidate_flags');
    final sdgMapping = _listMaps('sdg_mapping');
    final causalGraph = _mapValue('causal_graph_json');
    final score = _biasScore();
    final severityColor = _severityColor(score);
    final severityLabel = _severityLabel(score);
    final auditId = widget.initialAudit['audit_id']?.toString() ??
        widget.initialAudit['model_name']?.toString() ??
        'audit-report';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Audit Report'),
        actions: [
          IconButton(
            tooltip: 'Share as PDF',
            onPressed: _sharePdf,
            icon: const Icon(
              Icons.share_rounded,
              semanticLabel: 'Share audit report',
            ),
          ),
        ],
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Container(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
          decoration: BoxDecoration(
            color: theme.scaffoldBackgroundColor.withOpacity(0.96),
            border: Border(
              top: BorderSide(
                color: theme.colorScheme.outline.withOpacity(0.30),
              ),
            ),
          ),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _sharePdf,
                  icon: const Icon(
                    Icons.picture_as_pdf_rounded,
                    semanticLabel: 'Share report as PDF',
                  ),
                  label: const Text('Share Report (PDF)'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.icon(
                  onPressed: _startNewAudit,
                  icon: const Icon(
                    Icons.refresh_rounded,
                    semanticLabel: 'Run new audit',
                  ),
                  label: const Text('Run New Audit'),
                ),
              ),
            ],
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 120),
        children: [
          _SummaryHeaderCard(
            heroTag: 'audit-card-$auditId',
            modelName: widget.initialAudit['model_name']?.toString() ??
                'Untitled model',
            datasetName: widget.initialAudit['dataset_name']?.toString() ??
                'Unknown dataset',
            createdAt: _formatDate(widget.initialAudit['created_at']),
            score: score,
            severityColor: severityColor,
            severityLabel: severityLabel,
            expanded: _summaryExpanded,
            onToggle: () =>
                setState(() => _summaryExpanded = !_summaryExpanded),
          ),
          const SizedBox(height: 20),
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Bias Risk Overview',
                  style: textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'This score shows how strongly the system’s decisions may be disadvantaging some groups.',
                  style: textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 12),
                BiasGauge(score: score),
              ],
            ),
          ),
          const SizedBox(height: 20),
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'What was found?',
                  style: textTheme.headlineMedium,
                ),
                const SizedBox(height: 12),
                GeminiCard(
                  explanation:
                      widget.initialAudit['gemini_explanation']?.toString() ??
                          'No Gemini explanation is available for this audit.',
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          if (recommendations.isNotEmpty)
            _SectionCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Remediation Actions',
                    style: textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 12),
                  for (final item in recommendations)
                    _RecommendationTile(item: item),
                ],
              ),
            ),
          if (recommendations.isNotEmpty) const SizedBox(height: 20),
          if ((widget.initialAudit['gemini_legal_risk'] ?? '')
                  .toString()
                  .isNotEmpty ||
              auditQa.isNotEmpty)
            _SectionCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Legal Risk and Audit Q&A',
                    style: textTheme.headlineMedium,
                  ),
                  if ((widget.initialAudit['gemini_legal_risk'] ?? '')
                      .toString()
                      .isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Text(
                      widget.initialAudit['gemini_legal_risk'].toString(),
                      style: textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                  const SizedBox(height: 14),
                  for (final item in auditQa) _QuestionAnswerTile(item: item),
                ],
              ),
            ),
          if ((widget.initialAudit['gemini_legal_risk'] ?? '')
                  .toString()
                  .isNotEmpty ||
              auditQa.isNotEmpty)
            const SizedBox(height: 20),
          if (candidateFlags.isNotEmpty)
            _SectionCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Flagged Decisions',
                    style: textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 12),
                  for (final item in candidateFlags)
                    _CandidateFlagTile(item: item),
                ],
              ),
            ),
          if (candidateFlags.isNotEmpty) const SizedBox(height: 20),
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Feature Impact (SHAP)',
                  style: textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Higher bars point to the features contributing most to unfair outcomes in this audit.',
                  style: textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 16),
                ShapChart(shapValues: shapValues),
              ],
            ),
          ),
          const SizedBox(height: 20),
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Causal Pathway',
                  style: textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  widget.initialAudit['causal_pathway']?.toString() ??
                      'No strong pathway detected.',
                  style: textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 14),
                CausalGraph(graph: causalGraph),
              ],
            ),
          ),
          const SizedBox(height: 20),
          SdgBadge(mapping: sdgMapping),
          const SizedBox(height: 20),
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Fairness Metrics',
                  style: textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Each metric gives a different view of whether decisions stayed consistent and fair across groups.',
                  style: textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 18),
                GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 14,
                  crossAxisSpacing: 14,
                  childAspectRatio: 1.05,
                  children: [
                    _MetricCard(
                      name: 'Demographic Parity',
                      value: _metric(widget.initialAudit, 'demographic_parity'),
                      status: _parityStatus(
                          _metric(widget.initialAudit, 'demographic_parity')),
                    ),
                    _MetricCard(
                      name: 'Equalized Odds',
                      value: _metric(widget.initialAudit, 'equalized_odds'),
                      status: _parityStatus(
                          _metric(widget.initialAudit, 'equalized_odds')),
                    ),
                    _MetricCard(
                      name: 'Individual Fairness',
                      value:
                          _metric(widget.initialAudit, 'individual_fairness'),
                      status: _fairnessStatus(
                        _metric(widget.initialAudit, 'individual_fairness'),
                      ),
                    ),
                    _MetricCard(
                      name: 'Calibration Error',
                      value: _metric(widget.initialAudit, 'calibration_error'),
                      status: _calibrationStatus(
                        _metric(widget.initialAudit, 'calibration_error'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  _MetricStatus _parityStatus(double value) {
    final magnitude = value.abs();
    if (magnitude <= 0.10) {
      return const _MetricStatus.good();
    }
    if (magnitude <= 0.20) {
      return const _MetricStatus.warning();
    }
    return const _MetricStatus.critical();
  }

  _MetricStatus _fairnessStatus(double value) {
    if (value >= 0.80) return const _MetricStatus.good();
    if (value >= 0.60) return const _MetricStatus.warning();
    return const _MetricStatus.critical();
  }

  _MetricStatus _calibrationStatus(double value) {
    if (value <= 0.10) return const _MetricStatus.good();
    if (value <= 0.20) return const _MetricStatus.warning();
    return const _MetricStatus.critical();
  }
}

class _SummaryHeaderCard extends StatelessWidget {
  const _SummaryHeaderCard({
    required this.heroTag,
    required this.modelName,
    required this.datasetName,
    required this.createdAt,
    required this.score,
    required this.severityColor,
    required this.severityLabel,
    required this.expanded,
    required this.onToggle,
  });

  final String heroTag;
  final String modelName;
  final String datasetName;
  final String createdAt;
  final double score;
  final Color severityColor;
  final String severityLabel;
  final bool expanded;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isDark
              ? [
                  const Color(0xFF1B2440),
                  const Color(0xFF121A31),
                ]
              : [
                  Colors.white,
                  const Color(0xFFF7F9FF),
                  const Color(0xFFFFFBEB),
                ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(isDark ? 0.24 : 0.07),
            blurRadius: 20,
            offset: const Offset(0, 14),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
                        color: AppColors.accentAmber.withOpacity(0.16),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        'Audit Summary',
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: AppColors.accentAmber,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Hero(
                      tag: heroTag,
                      child: Material(
                        color: Colors.transparent,
                        child: Text(
                          modelName,
                          style: theme.textTheme.headlineMedium?.copyWith(
                            color: theme.colorScheme.onSurface,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      datasetName,
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      createdAt,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 14),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
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
                  const SizedBox(height: 12),
                  IconButton(
                    onPressed: onToggle,
                    tooltip: expanded ? 'Collapse summary' : 'Expand summary',
                    icon: AnimatedRotation(
                      turns: expanded ? 0.5 : 0,
                      duration: const Duration(milliseconds: 220),
                      child: const Icon(
                        Icons.keyboard_arrow_down_rounded,
                        semanticLabel: 'Toggle summary details',
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
          AnimatedSize(
            duration: const Duration(milliseconds: 240),
            curve: Curves.easeOutCubic,
            child: expanded
                ? Padding(
                    padding: const EdgeInsets.only(top: 18),
                    child: Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [
                        _SummaryChip(
                          icon: Icons.fact_check_rounded,
                          label: 'Bias audit completed',
                        ),
                        _SummaryChip(
                          icon: Icons.rule_folder_outlined,
                          label: 'Plain-English explanation included',
                        ),
                        const _SummaryChip(
                          icon: Icons.public_rounded,
                          label: 'Mapped to SDG 10.3, 8.5, 16.b',
                        ),
                      ],
                    ),
                  )
                : const SizedBox.shrink(),
          ),
        ],
      ),
    );
  }
}

class _RecommendationTile extends StatelessWidget {
  const _RecommendationTile({
    required this.item,
  });

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final priority = item['priority']?.toString() ?? 'review';
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.unBlue.withOpacity(0.08),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.unBlue.withOpacity(0.18)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(
              Icons.rule_rounded,
              color: AppColors.unBlue,
              semanticLabel: 'Recommendation',
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item['title']?.toString() ?? 'Recommended action',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    item['action']?.toString() ?? '',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Priority: $priority',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: AppColors.unBlue,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuestionAnswerTile extends StatelessWidget {
  const _QuestionAnswerTile({
    required this.item,
  });

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            item['question']?.toString() ?? 'Audit question',
            style: theme.textTheme.titleMedium,
          ),
          const SizedBox(height: 4),
          Text(
            item['answer']?.toString() ?? '',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

class _CandidateFlagTile extends StatelessWidget {
  const _CandidateFlagTile({
    required this.item,
  });

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final drivers = item['primary_drivers'];
    final driverText =
        drivers is List ? drivers.join(', ') : drivers?.toString() ?? '';
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.danger.withOpacity(0.08),
          borderRadius: BorderRadius.circular(18),
        ),
        child: Row(
          children: [
            const Icon(
              Icons.person_search_rounded,
              color: AppColors.danger,
              semanticLabel: 'Flagged decision',
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item['row_id']?.toString() ?? 'Flagged row',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Group: ${item['protected_group'] ?? 'Unknown'}',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  if (driverText.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      'Drivers: $driverText',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryChip extends StatelessWidget {
  const _SummaryChip({
    required this.icon,
    required this.label,
  });

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Theme.of(context).brightness == Brightness.dark
            ? Colors.white.withOpacity(0.05)
            : Colors.white.withOpacity(0.84),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: theme.colorScheme.outline.withOpacity(0.24),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon,
              size: 16, color: AppColors.accentAmber, semanticLabel: label),
          const SizedBox(width: 8),
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurface,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({
    required this.child,
  });

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final bool isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(isDark ? 0.20 : 0.05),
            blurRadius: 18,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: child,
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.name,
    required this.value,
    required this.status,
  });

  final String name;
  final double value;
  final _MetricStatus status;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: status.color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: status.color.withOpacity(0.18),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  name,
                  style: theme.textTheme.titleMedium?.copyWith(
                    color: theme.colorScheme.onSurface,
                  ),
                ),
              ),
              Text(
                status.icon,
                style: const TextStyle(fontSize: 20),
              ),
            ],
          ),
          const Spacer(),
          Text(
            value.toStringAsFixed(3),
            style: theme.textTheme.headlineMedium?.copyWith(
              color: status.color,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            status.label,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: status.color,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            status.description,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricStatus {
  const _MetricStatus({
    required this.icon,
    required this.label,
    required this.description,
    required this.color,
  });

  const _MetricStatus.good()
      : this(
          icon: '✅',
          label: 'Good',
          description: 'This metric is within a healthy fairness range.',
          color: AppColors.success,
        );

  const _MetricStatus.warning()
      : this(
          icon: '⚠️',
          label: 'Needs Attention',
          description: 'This metric is elevated and should be reviewed.',
          color: AppColors.warning,
        );

  const _MetricStatus.critical()
      : this(
          icon: '❌',
          label: 'Critical',
          description: 'This metric suggests a strong fairness concern.',
          color: AppColors.danger,
        );

  final String icon;
  final String label;
  final String description;
  final Color color;
}
