import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

import '../services/api_service.dart';
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
    this.initialTabIndex = 0,
  });

  final Map<String, dynamic> initialAudit;
  final int initialTabIndex;

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  late Map<String, dynamic> _audit;
  final TextEditingController _candidateSearchController =
      TextEditingController();

  bool _refreshingAudit = false;
  bool _loadingCandidates = false;
  bool _runningMitigation = false;
  bool _runningPatch = false;
  bool _runningGovernance = false;
  bool _loadingCertificate = false;

  String _candidateFilter = 'all';
  int _candidatePage = 1;
  int _candidateTotal = 0;
  List<Map<String, dynamic>> _candidates = const <Map<String, dynamic>>[];

  Map<String, dynamic>? _mitigation;
  Map<String, dynamic>? _syntheticPatch;
  Map<String, dynamic>? _governance;
  Map<String, dynamic>? _inspection;
  Map<String, dynamic>? _certificate;

  int get _initialTabIndex {
    if (widget.initialTabIndex < 0) {
      return 0;
    }
    if (widget.initialTabIndex > 4) {
      return 4;
    }
    return widget.initialTabIndex;
  }

  @override
  void initState() {
    super.initState();
    _audit = Map<String, dynamic>.from(widget.initialAudit);
    _mitigation = _mapFromValue(_audit['mitigation_results']);
    _governance = _mapFromValue(_audit['governance_summary']);
    _tabController = TabController(
      length: 5,
      vsync: this,
      initialIndex: _initialTabIndex,
    )
      ..addListener(_handleTabChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _refreshAudit();
      _loadTabDependencies(_tabController.index);
    });
  }

  void _handleTabChanged() {
    if (_tabController.indexIsChanging) {
      return;
    }
    _loadTabDependencies(_tabController.index);
  }

  void _loadTabDependencies(int index) {
    switch (index) {
      case 1:
        if (_candidates.isEmpty) {
          _loadCandidates();
        }
        break;
      case 3:
        if (_inspection == null && _governance == null) {
          _runGovernance(loadOnly: true);
        }
        break;
      case 4:
        if (_certificate == null) {
          _loadCertificate();
        }
        break;
    }
  }

  @override
  void dispose() {
    _candidateSearchController.dispose();
    _tabController.removeListener(_handleTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  String get _auditId =>
      _audit['audit_id']?.toString() ??
      widget.initialAudit['audit_id']?.toString() ??
      'audit-report';

  Future<void> _refreshAudit() async {
    if (_refreshingAudit) {
      return;
    }
    setState(() => _refreshingAudit = true);
    try {
      final fresh = await ApiService.instance.fetchAudit(_auditId);
      if (!mounted) {
        return;
      }
      setState(() {
        _audit = fresh;
        _mitigation = _mapFromValue(fresh['mitigation_results']) ?? _mitigation;
        _governance = _mapFromValue(fresh['governance_summary']) ?? _governance;
      });
    } catch (_) {
      // Keep the initial payload if the refresh misses.
    } finally {
      if (mounted) {
        setState(() => _refreshingAudit = false);
      }
    }
  }

  Future<void> _loadCandidates({int? page}) async {
    setState(() {
      _loadingCandidates = true;
      if (page != null) {
        _candidatePage = page;
      }
    });
    try {
      final response = await ApiService.instance.fetchCandidates(
        _auditId,
        page: page ?? _candidatePage,
        pageSize: 12,
        search: _candidateSearchController.text.trim(),
        biasStatus: _candidateFilter,
      );
      final rawItems = response['items'];
      if (!mounted) {
        return;
      }
      setState(() {
        _candidates = rawItems is List
            ? rawItems
                .whereType<Map>()
                .map((item) => item.cast<String, dynamic>())
                .toList(growable: false)
            : const <Map<String, dynamic>>[];
        _candidateTotal = (response['total'] as num?)?.toInt() ?? 0;
        _candidatePage = (response['page'] as num?)?.toInt() ?? _candidatePage;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', ''))),
      );
    } finally {
      if (mounted) {
        setState(() => _loadingCandidates = false);
      }
    }
  }

  Future<void> _openCandidate(Map<String, dynamic> candidate) async {
    try {
      final detail = await ApiService.instance.fetchCandidateDetail(
        _auditId,
        candidate['id']?.toString() ?? candidate['row_id']?.toString() ?? '',
      );
      if (!mounted) {
        return;
      }
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: Colors.transparent,
        builder: (context) => _CandidateDetailsSheet(candidate: detail),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', ''))),
      );
    } finally {
      // No persistent selection state is needed once the sheet closes.
    }
  }

  Future<void> _runMitigation() async {
    setState(() => _runningMitigation = true);
    try {
      final result = await ApiService.instance.runMitigation(_auditId);
      if (!mounted) {
        return;
      }
      setState(() => _mitigation = result);
      await _refreshAudit();
      await _loadCandidates(page: 1);
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', ''))),
      );
    } finally {
      if (mounted) {
        setState(() => _runningMitigation = false);
      }
    }
  }

  Future<void> _runSyntheticPatch() async {
    setState(() => _runningPatch = true);
    try {
      final protectedAttrs =
          _listStrings(_domainConfig['protected_attributes']);
      final result = await ApiService.instance.runSyntheticPatch(
        _auditId,
        targetAttribute:
            protectedAttrs.isNotEmpty ? protectedAttrs.first : 'gender',
      );
      if (!mounted) {
        return;
      }
      setState(() => _syntheticPatch = result);
      await _refreshAudit();
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', ''))),
      );
    } finally {
      if (mounted) {
        setState(() => _runningPatch = false);
      }
    }
  }

  Future<void> _runGovernance({bool loadOnly = false}) async {
    setState(() => _runningGovernance = true);
    try {
      final governance = await ApiService.instance.runGovernance(_auditId);
      final inspection =
          await ApiService.instance.fetchDeepInspection(_auditId);
      if (!mounted) {
        return;
      }
      setState(() {
        _governance = governance;
        _inspection = inspection;
      });
      if (!loadOnly) {
        await _refreshAudit();
      }
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', ''))),
      );
    } finally {
      if (mounted) {
        setState(() => _runningGovernance = false);
      }
    }
  }

  Future<void> _loadCertificate() async {
    setState(() => _loadingCertificate = true);
    try {
      final certificate = await ApiService.instance.fetchCertificate(_auditId);
      if (!mounted) {
        return;
      }
      setState(() => _certificate = certificate);
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', ''))),
      );
    } finally {
      if (mounted) {
        setState(() => _loadingCertificate = false);
      }
    }
  }

  Future<void> _sharePdf() async {
    final pdf = pw.Document();
    final modelName = _audit['model_name']?.toString() ?? 'Fairness Audit';
    final score = _biasScore();
    final metrics = _metricSummary();

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
          pw.Text('Bias score: ${score.toStringAsFixed(0)}/100'),
          pw.Text('Risk level: ${_severityLabel(score)}'),
          pw.Text('Dataset: ${_audit['dataset_name'] ?? 'Unknown'}'),
          pw.Text('Domain: ${_audit['domain'] ?? 'general'}'),
          pw.Text('Created: ${_formatDate(_audit['created_at'])}'),
          pw.SizedBox(height: 18),
          pw.Text(
            'AI Fairness Insight',
            style: pw.TextStyle(
              fontSize: 16,
              fontWeight: pw.FontWeight.bold,
            ),
          ),
          pw.SizedBox(height: 8),
          pw.Text(_audit['gemini_explanation']?.toString() ?? ''),
          pw.SizedBox(height: 18),
          pw.Text(
            'Fairness Metrics',
            style: pw.TextStyle(
              fontSize: 16,
              fontWeight: pw.FontWeight.bold,
            ),
          ),
          pw.SizedBox(height: 8),
          for (final item in metrics)
            pw.Bullet(text: '${item['label']}: ${item['value']}'),
        ],
      ),
    );
    await Printing.sharePdf(
      bytes: await pdf.save(),
      filename: 'fairness-audit-workspace.pdf',
    );
  }

  void _startNewAudit() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const UploadScreen()),
    );
  }

  Map<String, dynamic> get _domainConfig =>
      _mapFromValue(_audit['domain_config']) ?? const <String, dynamic>{};

  List<Map<String, dynamic>> _listMaps(dynamic raw) {
    if (raw is List) {
      return raw
          .whereType<Map>()
          .map((item) => item.cast<String, dynamic>())
          .toList(growable: false);
    }
    return const <Map<String, dynamic>>[];
  }

  List<String> _listStrings(dynamic raw) {
    if (raw is List) {
      return raw.map((item) => item.toString()).toList(growable: false);
    }
    return const <String>[];
  }

  Map<String, dynamic>? _mapFromValue(dynamic raw) {
    if (raw is Map) {
      return raw.cast<String, dynamic>();
    }
    return null;
  }

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

  double _metric(String key) {
    final raw = _audit[key];
    if (raw is num) {
      return raw.toDouble();
    }
    final nested = _mapFromValue(_audit['fairness_metrics']);
    if (nested != null && nested[key] is num) {
      return (nested[key] as num).toDouble();
    }
    return 0;
  }

  double _biasScore() => (_audit['bias_score'] as num?)?.toDouble() ?? 0;

  Color _severityColor(double score) {
    if (score <= 30) {
      return AppColors.success;
    }
    if (score <= 60) {
      return AppColors.warning;
    }
    return AppColors.danger;
  }

  String _severityLabel(double score) {
    if (score <= 30) {
      return 'Low Risk';
    }
    if (score <= 60) {
      return 'Moderate Risk';
    }
    return 'High Risk';
  }

  List<Map<String, dynamic>> _sdgRows() {
    final raw = _mapFromValue(_audit['sdg_mapping']);
    if (raw == null || raw.isEmpty) {
      return const <Map<String, dynamic>>[];
    }
    return raw.entries.map((entry) {
      final data = entry.value is Map
          ? (entry.value as Map).cast<String, dynamic>()
          : const <String, dynamic>{};
      return {
        'target': data['target']?.toString() ?? entry.key.replaceAll('_', '.'),
        'title': data['target_text']?.toString() ?? 'Mapped fairness target',
        'status': data['pass'] == true ? 'aligned' : 'tracked',
      };
    }).toList(growable: false);
  }

  List<Map<String, dynamic>> _metricSummary() {
    return <Map<String, dynamic>>[
      {
        'label': 'Demographic parity',
        'value': _metric('demographic_parity').toStringAsFixed(3),
      },
      {
        'label': 'Equalized odds',
        'value': _metric('equalized_odds').toStringAsFixed(3),
      },
      {
        'label': 'Individual fairness',
        'value': _metric('individual_fairness').toStringAsFixed(3),
      },
      {
        'label': 'Calibration error',
        'value': _metric('calibration_error').toStringAsFixed(3),
      },
      {
        'label': 'Disparate impact',
        'value': _metric('disparate_impact').toStringAsFixed(3),
      },
    ];
  }

  int get _candidatePages =>
      _candidateTotal == 0 ? 1 : ((_candidateTotal - 1) ~/ 12) + 1;

  @override
  Widget build(BuildContext context) {
    final score = _biasScore();
    final severityColor = _severityColor(score);
    final severityLabel = _severityLabel(score);
    final shapValues = _listMaps(_audit['shap_values']);
    final recommendations = _listMaps(_audit['gemini_recommendations']);
    final candidateFlags = _listMaps(_audit['candidate_flags']);
    final jurisdictionRisks = _listMaps(_audit['jurisdiction_risks']);
    final auditQa = _listMaps(_audit['gemini_audit_qa']);
    final causalGraph =
        _mapFromValue(_audit['causal_graph_json']) ?? const <String, dynamic>{};

    return Scaffold(
      appBar: AppBar(
        title: const Text('Audit Workspace'),
        actions: [
          IconButton(
            tooltip: 'Refresh audit',
            onPressed: _refreshingAudit ? null : _refreshAudit,
            icon: _refreshingAudit
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh_rounded),
          ),
          IconButton(
            tooltip: 'Share as PDF',
            onPressed: _sharePdf,
            icon: const Icon(Icons.share_rounded),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
            child: _WorkspaceHeader(
              modelName: _audit['model_name']?.toString() ?? 'Untitled model',
              datasetName:
                  _audit['dataset_name']?.toString() ?? 'Unknown dataset',
              createdAt: _formatDate(_audit['created_at']),
              score: score,
              severityColor: severityColor,
              severityLabel: severityLabel,
              subjectLabel:
                  _domainConfig['subject_label']?.toString() ?? 'Record',
              onNewAudit: _startNewAudit,
            ),
          ),
          const SizedBox(height: 12),
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 20),
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: Theme.of(context).cardColor,
              borderRadius: BorderRadius.circular(18),
            ),
            child: TabBar(
              controller: _tabController,
              indicator: BoxDecoration(
                color: AppColors.deepNavy,
                borderRadius: BorderRadius.circular(14),
              ),
              labelColor: Colors.white,
              unselectedLabelColor: Theme.of(context).colorScheme.onSurface,
              dividerColor: Colors.transparent,
              isScrollable: true,
              tabs: const [
                Tab(text: 'Overview'),
                Tab(text: 'Records'),
                Tab(text: 'Mitigation'),
                Tab(text: 'Governance'),
                Tab(text: 'Certificate'),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                ListView(
                  padding: const EdgeInsets.fromLTRB(20, 6, 20, 120),
                  children: [
                    _SectionCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Bias risk overview',
                              style:
                                  Theme.of(context).textTheme.headlineMedium),
                          const SizedBox(height: 8),
                          Text(
                            'This workspace starts with the fairness risk level, then opens into records, mitigation, and governance review.',
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium
                                ?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                          ),
                          const SizedBox(height: 16),
                          BiasGauge(score: score),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),
                    _SectionCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('AI fairness insight',
                              style:
                                  Theme.of(context).textTheme.headlineMedium),
                          const SizedBox(height: 12),
                          GeminiCard(
                            explanation: _audit['gemini_explanation']
                                    ?.toString() ??
                                'No explanation is available for this audit yet.',
                          ),
                        ],
                      ),
                    ),
                    if (recommendations.isNotEmpty) ...[
                      const SizedBox(height: 18),
                      _SectionCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Recommended actions',
                                style:
                                    Theme.of(context).textTheme.headlineMedium),
                            const SizedBox(height: 12),
                            for (final item in recommendations)
                              _RecommendationTile(item: item),
                          ],
                        ),
                      ),
                    ],
                    if (candidateFlags.isNotEmpty) ...[
                      const SizedBox(height: 18),
                      _SectionCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Flagged records',
                                style:
                                    Theme.of(context).textTheme.headlineMedium),
                            const SizedBox(height: 12),
                            for (final item in candidateFlags)
                              _CandidateFlagTile(item: item),
                          ],
                        ),
                      ),
                    ],
                    const SizedBox(height: 18),
                    _SectionCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Feature impact',
                              style:
                                  Theme.of(context).textTheme.headlineMedium),
                          const SizedBox(height: 8),
                          Text(
                            'The highest bars show which features are contributing most to the unfair outcome pattern.',
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium
                                ?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                          ),
                          const SizedBox(height: 16),
                          ShapChart(shapValues: shapValues),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),
                    _SectionCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Causal pathway',
                              style:
                                  Theme.of(context).textTheme.headlineMedium),
                          const SizedBox(height: 8),
                          Text(
                            _audit['causal_pathway']?.toString() ??
                                'No strong pathway detected.',
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium
                                ?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                          ),
                          const SizedBox(height: 14),
                          CausalGraph(graph: causalGraph),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),
                    SdgBadge(mapping: _sdgRows()),
                    const SizedBox(height: 18),
                    _SectionCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Fairness metrics',
                              style:
                                  Theme.of(context).textTheme.headlineMedium),
                          const SizedBox(height: 12),
                          Wrap(
                            spacing: 12,
                            runSpacing: 12,
                            children: _metricSummary()
                                .map((item) => _MetricPill(
                                      label: item['label']!.toString(),
                                      value: item['value']!.toString(),
                                    ))
                                .toList(growable: false),
                          ),
                          if ((_audit['gemini_legal_risk'] ?? '')
                              .toString()
                              .isNotEmpty) ...[
                            const SizedBox(height: 18),
                            Text(
                              _audit['gemini_legal_risk'].toString(),
                              style: Theme.of(context)
                                  .textTheme
                                  .bodyMedium
                                  ?.copyWith(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant,
                                  ),
                            ),
                          ],
                          if (auditQa.isNotEmpty) ...[
                            const SizedBox(height: 18),
                            for (final item in auditQa)
                              _QuestionAnswerTile(item: item),
                          ],
                          if (jurisdictionRisks.isNotEmpty) ...[
                            const SizedBox(height: 18),
                            for (final item in jurisdictionRisks)
                              _JurisdictionTile(item: item),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
                _buildRecordsTab(),
                _buildMitigationTab(),
                _buildGovernanceTab(),
                _buildCertificateTab(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecordsTab() {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 6, 20, 120),
      children: [
        _SectionCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Record explorer', style: theme.textTheme.headlineMedium),
              const SizedBox(height: 8),
              Text(
                'Search the audit, filter bias status, and open an individual record for feature impact and counterfactual detail.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _candidateSearchController,
                decoration: InputDecoration(
                  hintText: 'Search by record name or row id',
                  prefixIcon: const Icon(Icons.search_rounded),
                  suffixIcon: IconButton(
                    icon: const Icon(Icons.arrow_forward_rounded),
                    onPressed: _loadingCandidates
                        ? null
                        : () => _loadCandidates(page: 1),
                  ),
                ),
                onSubmitted: (_) => _loadCandidates(page: 1),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: _candidateFilter,
                items: const [
                  DropdownMenuItem(value: 'all', child: Text('All records')),
                  DropdownMenuItem(
                      value: 'flagged', child: Text('Flagged only')),
                  DropdownMenuItem(value: 'clean', child: Text('Clean only')),
                ],
                onChanged: (value) {
                  if (value == null) {
                    return;
                  }
                  setState(() => _candidateFilter = value);
                  _loadCandidates(page: 1);
                },
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.filter_alt_outlined),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        if (_loadingCandidates)
          const Center(
              child: Padding(
            padding: EdgeInsets.symmetric(vertical: 32),
            child: CircularProgressIndicator(),
          ))
        else if (_candidates.isEmpty)
          _SectionCard(
            child: Text(
              'No records are loaded yet. Refresh this tab after the audit completes or change the filter.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          )
        else
          ..._candidates.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _RecordPreviewCard(
                item: item,
                subjectLabel:
                    _domainConfig['subject_label']?.toString() ?? 'Record',
                outcomeLabel:
                    _domainConfig['outcome_label']?.toString() ?? 'Outcome',
                onTap: () => _openCandidate(item),
              ),
            ),
          ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: _candidatePage <= 1 || _loadingCandidates
                    ? null
                    : () => _loadCandidates(page: _candidatePage - 1),
                child: const Text('Previous page'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton(
                onPressed:
                    _candidatePage >= _candidatePages || _loadingCandidates
                        ? null
                        : () => _loadCandidates(page: _candidatePage + 1),
                child: Text('Next page (${_candidatePage}/$_candidatePages)'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildMitigationTab() {
    final theme = Theme.of(context);
    final mitigation = _mitigation;

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 6, 20, 120),
      children: [
        _SectionCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Mitigation center', style: theme.textTheme.headlineMedium),
              const SizedBox(height: 8),
              Text(
                'Compare fairness snapshots before and after mitigation, then test a synthetic patch when you want a faster what-if.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  FilledButton.icon(
                    onPressed: _runningMitigation ? null : _runMitigation,
                    icon: _runningMitigation
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.auto_fix_high_rounded),
                    label: Text(
                      _runningMitigation
                          ? 'Running mitigation...'
                          : 'Run mitigation analysis',
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: _runningPatch ? null : _runSyntheticPatch,
                    icon: _runningPatch
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.science_outlined),
                    label: Text(
                      _runningPatch ? 'Building patch...' : 'Synthetic patch',
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        if (mitigation == null)
          _SectionCard(
            child: Text(
              'Run mitigation to compare strategy stages and update the adjusted decisions in this audit.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          )
        else ...[
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Strategy comparison',
                    style: theme.textTheme.headlineMedium),
                const SizedBox(height: 14),
                for (final stage in <String>[
                  'original',
                  'after_reweighing',
                  'after_prejudice_remover',
                  'after_equalized_odds',
                ])
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: _MitigationStageCard(
                      title: _stageLabel(stage),
                      snapshot: _mapFromValue(mitigation[stage]) ??
                          const <String, dynamic>{},
                    ),
                  ),
                Text(
                  'Fairness score ${mitigation['fairness_score_before'] ?? 0} -> ${mitigation['fairness_score_after'] ?? 0} and ${mitigation['mitigated_candidates'] ?? 0} records changed.',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          if (_syntheticPatch != null) ...[
            const SizedBox(height: 18),
            _SectionCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Synthetic patch preview',
                      style: theme.textTheme.headlineMedium),
                  const SizedBox(height: 10),
                  Text(
                    _syntheticPatch!['reason']?.toString() ??
                        'Synthetic patch analysis completed.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Fairness lift: ${(_syntheticPatch!['fairness_lift'] as num?)?.toStringAsFixed(1) ?? '0.0'} points',
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: AppColors.success,
                    ),
                  ),
                  const SizedBox(height: 12),
                  for (final preview in _listMaps(_syntheticPatch!['preview']))
                    _CandidateFlagTile(item: preview),
                ],
              ),
            ),
          ],
        ],
      ],
    );
  }

  Widget _buildGovernanceTab() {
    final theme = Theme.of(context);
    final governance = _governance;
    final inspection = _inspection;
    final proxyFindings = inspection == null
        ? const <Map<String, dynamic>>[]
        : _listMaps(inspection['proxy_findings']);
    final memories = governance == null
        ? const <Map<String, dynamic>>[]
        : _listMaps(governance['recalled_memories']);

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 6, 20, 120),
      children: [
        _SectionCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Governance and proxy review',
                  style: theme.textTheme.headlineMedium),
              const SizedBox(height: 8),
              Text(
                'Run the policy view to get a rollout verdict, proxy findings, and memory-backed context from prior audits.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _runningGovernance ? null : _runGovernance,
                icon: _runningGovernance
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.verified_user_outlined),
                label: Text(
                  _runningGovernance
                      ? 'Running governance...'
                      : 'Run governance analysis',
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        if (governance != null)
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Release verdict', style: theme.textTheme.headlineMedium),
                const SizedBox(height: 12),
                _GovernanceBanner(
                  status: governance['status']?.toString() ?? 'flag',
                  recommendation:
                      governance['recommendation']?.toString() ?? '',
                  rationale: governance['rationale']?.toString() ?? '',
                ),
                const SizedBox(height: 16),
                for (final action in _listStrings(governance['actions']))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _MetricPill(
                      label: 'Action',
                      value: action,
                    ),
                  ),
              ],
            ),
          ),
        if (proxyFindings.isNotEmpty) ...[
          const SizedBox(height: 18),
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Proxy findings', style: theme.textTheme.headlineMedium),
                const SizedBox(height: 12),
                for (final item in proxyFindings.take(6))
                  _ProxyFindingTile(item: item),
              ],
            ),
          ),
        ],
        if (memories.isNotEmpty) ...[
          const SizedBox(height: 18),
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Audit memory timeline',
                    style: theme.textTheme.headlineMedium),
                const SizedBox(height: 12),
                for (final item in memories) _MemoryTile(item: item),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildCertificateTab() {
    final theme = Theme.of(context);
    final certificate = _certificate;

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 6, 20, 120),
      children: [
        _SectionCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Fairness certificate',
                  style: theme.textTheme.headlineMedium),
              const SizedBox(height: 8),
              Text(
                'Certificate status packages the fairness metrics, SDG mapping, and the SHA-256 audit fingerprint for a cleaner handoff.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: _loadingCertificate ? null : _loadCertificate,
                icon: _loadingCertificate
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.badge_outlined),
                label: Text(
                  _loadingCertificate
                      ? 'Loading certificate...'
                      : 'Refresh certificate',
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        if (certificate == null)
          _SectionCard(
            child: Text(
              'Load the certificate to see the signed audit hash and the current fairness pass status.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          )
        else
          _SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _CertificateBanner(
                  badgeLabel:
                      certificate['badge_label']?.toString() ?? 'CERTIFICATE',
                  certifiedFair: certificate['certified_fair'] == true,
                ),
                const SizedBox(height: 16),
                _MetricPill(
                  label: 'Certificate hash',
                  value: certificate['certificate_sha256']?.toString() ??
                      'Unavailable',
                ),
                const SizedBox(height: 12),
                for (final item in _metricSummary())
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _MetricPill(
                      label: item['label']!.toString(),
                      value: item['value']!.toString(),
                    ),
                  ),
                const SizedBox(height: 10),
                SdgBadge(mapping: _sdgRows()),
              ],
            ),
          ),
      ],
    );
  }

  String _stageLabel(String key) {
    switch (key) {
      case 'original':
        return 'Original';
      case 'after_reweighing':
        return 'Reweighing';
      case 'after_prejudice_remover':
        return 'Prejudice Remover';
      case 'after_equalized_odds':
        return 'Equalized Odds';
      default:
        return key;
    }
  }
}

class _WorkspaceHeader extends StatelessWidget {
  const _WorkspaceHeader({
    required this.modelName,
    required this.datasetName,
    required this.createdAt,
    required this.score,
    required this.severityColor,
    required this.severityLabel,
    required this.subjectLabel,
    required this.onNewAudit,
  });

  final String modelName;
  final String datasetName;
  final String createdAt;
  final double score;
  final Color severityColor;
  final String severityLabel;
  final String subjectLabel;
  final VoidCallback onNewAudit;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: AppGradients.hero,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: AppColors.deepNavy.withOpacity(0.24),
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
                        color: Colors.white.withOpacity(0.12),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        '$subjectLabel workspace',
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      modelName,
                      style: theme.textTheme.headlineMedium?.copyWith(
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      datasetName,
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: Colors.white.withOpacity(0.82),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      createdAt,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: Colors.white.withOpacity(0.72),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 14),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.12),
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
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: _HeaderStat(
                  label: 'Bias score',
                  value: '${score.toStringAsFixed(0)}/100',
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _HeaderStat(
                  label: 'Status',
                  value: severityLabel,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton(
                  onPressed: onNewAudit,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white,
                    side: BorderSide(color: Colors.white.withOpacity(0.28)),
                    minimumSize: const Size.fromHeight(68),
                  ),
                  child: const Text('New audit'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _HeaderStat extends StatelessWidget {
  const _HeaderStat({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.10),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Colors.white.withOpacity(0.72),
                ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Colors.white,
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
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

class _MetricPill extends StatelessWidget {
  const _MetricPill({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Theme.of(context).brightness == Brightness.dark
            ? Colors.white.withOpacity(0.05)
            : const Color(0xFFF8FAFF),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: theme.colorScheme.outline.withOpacity(0.16),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: theme.textTheme.titleMedium,
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
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.unBlue.withOpacity(0.08),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.unBlue.withOpacity(0.18)),
        ),
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
              'Priority: ${item['priority'] ?? 'review'}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: AppColors.unBlue,
                fontWeight: FontWeight.w800,
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
          Text(item['question']?.toString() ?? 'Audit question',
              style: theme.textTheme.titleMedium),
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

class _JurisdictionTile extends StatelessWidget {
  const _JurisdictionTile({
    required this.item,
  });

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = item['status']?.toString() ?? 'amber';
    final color = switch (status) {
      'green' => AppColors.success,
      'red' => AppColors.danger,
      _ => AppColors.warning,
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: color.withOpacity(0.10),
          borderRadius: BorderRadius.circular(18),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${item['jurisdiction'] ?? 'Jurisdiction'} - ${item['framework'] ?? 'Framework'}',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 6),
            Text(
              item['summary']?.toString() ?? '',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
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
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.person_search_rounded, color: AppColors.danger),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item['display_name']?.toString() ??
                        item['row_id']?.toString() ??
                        'Flagged row',
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

class _RecordPreviewCard extends StatelessWidget {
  const _RecordPreviewCard({
    required this.item,
    required this.subjectLabel,
    required this.outcomeLabel,
    required this.onTap,
  });

  final Map<String, dynamic> item;
  final String subjectLabel;
  final String outcomeLabel;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final probability = (item['approval_probability'] as num?)?.toDouble() ?? 0;
    final flagged = item['bias_flagged'] == true;
    final statusColor = flagged ? AppColors.warning : AppColors.success;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: Ink(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: theme.cardColor,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: theme.colorScheme.outline.withOpacity(0.18),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      item['display_name']?.toString() ??
                          item['row_id']?.toString() ??
                          subjectLabel,
                      style: theme.textTheme.titleMedium,
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: statusColor.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      flagged ? 'Flagged' : 'Clear',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: statusColor,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                '${item['sensitive_attribute'] ?? 'protected group'}: ${item[item['sensitive_attribute']] ?? item['protected_group'] ?? 'Unknown'}',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: _InlineStat(
                      label: outcomeLabel,
                      value: item['original_decision'] == true
                          ? outcomeLabel
                          : 'Not $outcomeLabel',
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _InlineStat(
                      label: 'Probability',
                      value: '${(probability * 100).toStringAsFixed(0)}%',
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InlineStat extends StatelessWidget {
  const _InlineStat({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).brightness == Brightness.dark
            ? Colors.white.withOpacity(0.05)
            : const Color(0xFFF8FAFF),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 6),
          Text(value, style: theme.textTheme.titleMedium),
        ],
      ),
    );
  }
}

class _CandidateDetailsSheet extends StatelessWidget {
  const _CandidateDetailsSheet({
    required this.candidate,
  });

  final Map<String, dynamic> candidate;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final impacts = candidate['feature_impacts'] is List
        ? (candidate['feature_impacts'] as List)
            .whereType<Map>()
            .map((item) => item.cast<String, dynamic>())
            .toList(growable: false)
        : const <Map<String, dynamic>>[];
    final counterfactual = candidate['counterfactual_result'] is Map
        ? (candidate['counterfactual_result'] as Map).cast<String, dynamic>()
        : const <String, dynamic>{};
    final suggestions = counterfactual['suggested_changes'] is List
        ? (counterfactual['suggested_changes'] as List)
            .whereType<Map>()
            .map((item) => item.cast<String, dynamic>())
            .toList(growable: false)
        : const <Map<String, dynamic>>[];

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 16),
        child: Container(
          decoration: BoxDecoration(
            color: theme.cardColor,
            borderRadius: BorderRadius.circular(30),
          ),
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: ListView(
              shrinkWrap: true,
              children: [
                Text(
                  candidate['display_name']?.toString() ??
                      candidate['row_id']?.toString() ??
                      'Record',
                  style: theme.textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Predicted probability ${(candidate['approval_probability'] as num? ?? 0).toDouble().toStringAsFixed(2)}',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 18),
                Text('Feature impact', style: theme.textTheme.titleLarge),
                const SizedBox(height: 10),
                for (final item in impacts)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _MetricPill(
                      label: item['feature']?.toString() ?? 'Feature',
                      value:
                          '${item['value'] ?? 0} (value ${item['current_value'] ?? 'n/a'})',
                    ),
                  ),
                const SizedBox(height: 12),
                Text('Counterfactual suggestions',
                    style: theme.textTheme.titleLarge),
                const SizedBox(height: 10),
                if (suggestions.isEmpty)
                  Text(
                    'No counterfactual change suggestions were generated for this record.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  )
                else
                  for (final item in suggestions)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: _MetricPill(
                        label: item['feature']?.toString() ?? 'Feature',
                        value:
                            '${item['direction'] ?? 'adjust'} to ${item['suggested_value'] ?? 'n/a'}',
                      ),
                    ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MitigationStageCard extends StatelessWidget {
  const _MitigationStageCard({
    required this.title,
    required this.snapshot,
  });

  final String title;
  final Map<String, dynamic> snapshot;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final passFlags = snapshot['pass_flags'] is Map
        ? (snapshot['pass_flags'] as Map).cast<String, dynamic>()
        : const <String, dynamic>{};
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).brightness == Brightness.dark
            ? Colors.white.withOpacity(0.05)
            : const Color(0xFFF8FAFF),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: theme.textTheme.titleMedium),
          const SizedBox(height: 10),
          for (final key in <String>[
            'disparate_impact',
            'stat_parity_diff',
            'equal_opp_diff',
            'avg_odds_diff',
          ])
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      key.replaceAll('_', ' '),
                      style: theme.textTheme.bodySmall,
                    ),
                  ),
                  Text(
                    '${snapshot[key] ?? 0}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w800,
                      color: passFlags[key] == true
                          ? AppColors.success
                          : AppColors.warning,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _GovernanceBanner extends StatelessWidget {
  const _GovernanceBanner({
    required this.status,
    required this.recommendation,
    required this.rationale,
  });

  final String status;
  final String recommendation;
  final String rationale;

  @override
  Widget build(BuildContext context) {
    final tone = switch (status) {
      'pass' => AppColors.success,
      'fail' => AppColors.danger,
      _ => AppColors.warning,
    };
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: tone.withOpacity(0.10),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            status.toUpperCase(),
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: tone,
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 8),
          Text(recommendation, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text(
            rationale,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ],
      ),
    );
  }
}

class _ProxyFindingTile extends StatelessWidget {
  const _ProxyFindingTile({
    required this.item,
  });

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final riskScore = (item['risk_score'] as num?)?.toDouble() ?? 0;
    final tone = riskScore >= 0.15 ? AppColors.danger : AppColors.warning;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: tone.withOpacity(0.10),
          borderRadius: BorderRadius.circular(18),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              item['feature']?.toString() ?? 'Feature',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 6),
            Text(
              item['explanation']?.toString() ?? '',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Risk ${riskScore.toStringAsFixed(3)}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: tone,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MemoryTile extends StatelessWidget {
  const _MemoryTile({
    required this.item,
  });

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Theme.of(context).brightness == Brightness.dark
              ? Colors.white.withOpacity(0.05)
              : const Color(0xFFF8FAFF),
          borderRadius: BorderRadius.circular(18),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${item['stage'] ?? 'audit'} - similarity ${(item['score'] as num? ?? 0).toDouble().toStringAsFixed(2)}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              item['memory_text']?.toString() ?? '',
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class _CertificateBanner extends StatelessWidget {
  const _CertificateBanner({
    required this.badgeLabel,
    required this.certifiedFair,
  });

  final String badgeLabel;
  final bool certifiedFair;

  @override
  Widget build(BuildContext context) {
    final color = certifiedFair ? AppColors.success : AppColors.warning;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(22),
      ),
      child: Row(
        children: [
          Icon(
            certifiedFair
                ? Icons.verified_rounded
                : Icons.warning_amber_rounded,
            color: color,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              badgeLabel,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w800,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}
