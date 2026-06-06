import 'dart:convert';
import 'dart:math' as math;

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

import '../services/api_service.dart';
import '../services/auth_service.dart';
import '../services/firebase_service.dart';
import '../theme/app_theme.dart';
import 'report_screen.dart';

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final TextEditingController _modelNameController = TextEditingController();
  final TextEditingController _displayNameController = TextEditingController();
  final TextEditingController _outcomeColumnController =
      TextEditingController();
  final TextEditingController _protectedAttrsController =
      TextEditingController();
  final TextEditingController _featureColumnsController =
      TextEditingController();
  final TextEditingController _requiredColumnsController =
      TextEditingController();
  final TextEditingController _subjectLabelController = TextEditingController();
  final TextEditingController _outcomeLabelController = TextEditingController();
  final TextEditingController _positiveValueController =
      TextEditingController();

  PlatformFile? _datasetFile;
  PlatformFile? _modelFile;
  List<Map<String, dynamic>> _templates = const <Map<String, dynamic>>[];
  Map<String, dynamic>? _selectedTemplate;
  List<String> _foundHeaders = const <String>[];
  List<String> _missingHeaders = const <String>[];
  bool _loading = false;
  bool _loadingTemplates = true;
  bool _showAdvancedSchema = false;
  String? _activeAuditId;
  int? _launchTargetTab;

  @override
  void initState() {
    super.initState();
    _loadTemplates();
  }

  Future<void> _loadTemplates() async {
    setState(() => _loadingTemplates = true);
    try {
      final templates = await ApiService.instance.fetchDomainTemplates();
      final defaultTemplate = templates.firstWhere(
        (item) => item['domain'] == 'hiring',
        orElse: () =>
            templates.isNotEmpty ? templates.first : <String, dynamic>{},
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _templates = templates;
        _loadingTemplates = false;
      });
      if (defaultTemplate.isNotEmpty) {
        _applyTemplate(defaultTemplate);
      }
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _templates = const <Map<String, dynamic>>[];
        _loadingTemplates = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', ''))),
      );
    }
  }

  void _applyTemplate(Map<String, dynamic> template) {
    final protected = _listToCsv(template['protected_attributes']);
    final features = _listToCsv(template['feature_columns']);
    final required = _listToCsv(template['required_columns']);
    setState(() {
      _selectedTemplate = Map<String, dynamic>.from(template);
      _showAdvancedSchema = template['domain'] == 'custom';
      _foundHeaders = const <String>[];
      _missingHeaders = const <String>[];
    });
    _displayNameController.text =
        template['display_name']?.toString() ?? 'Custom';
    _outcomeColumnController.text =
        template['outcome_column']?.toString() ?? 'outcome';
    _protectedAttrsController.text = protected;
    _featureColumnsController.text = features;
    _requiredColumnsController.text = required;
    _subjectLabelController.text =
        template['subject_label']?.toString() ?? 'Record';
    _outcomeLabelController.text =
        template['outcome_label']?.toString() ?? 'Outcome';
    _positiveValueController.text =
        template['outcome_positive_value']?.toString() ?? '1';
  }

  String _listToCsv(dynamic value) {
    if (value is List) {
      return value.map((item) => item.toString()).join(', ');
    }
    return value?.toString() ?? '';
  }

  List<String> _csvToList(String raw) {
    return raw
        .split(',')
        .map(_normalizeHeader)
        .where((item) => item.isNotEmpty)
        .toList(growable: false);
  }

  String _normalizeHeader(String raw) {
    return raw.trim().toLowerCase().replaceAll('-', '_').replaceAll(' ', '_');
  }

  Future<void> _pickDataset() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      withData: true,
      allowedExtensions: const ['csv'],
    );
    if (result == null || !mounted) {
      return;
    }
    final file = result.files.single;
    setState(() => _datasetFile = file);
    await _inspectDataset(file);
  }

  Future<void> _pickModel() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      withData: true,
      allowedExtensions: const ['pkl', 'h5'],
    );
    if (result != null && mounted) {
      setState(() => _modelFile = result.files.single);
    }
  }

  Future<void> _inspectDataset(PlatformFile file) async {
    try {
      final bytes = file.bytes;
      if (bytes == null) {
        return;
      }
      final text = utf8.decode(bytes, allowMalformed: true);
      final firstLine = text
          .split(RegExp(r'\r?\n'))
          .firstWhere((line) => line.trim().isNotEmpty, orElse: () => '');
      final headers = firstLine
          .split(',')
          .map(_normalizeHeader)
          .where((item) => item.isNotEmpty)
          .toList(growable: false);
      final required = _csvToList(_requiredColumnsController.text);
      final missing =
          required.where((item) => !headers.contains(item)).toList();
      final found = required.where(headers.contains).toList();
      if (!mounted) {
        return;
      }
      setState(() {
        _foundHeaders = found;
        _missingHeaders = missing;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _foundHeaders = const <String>[];
        _missingHeaders = const <String>['Could not read CSV headers'];
      });
    }
  }

  Map<String, dynamic> _currentDomainConfig() {
    final template = _selectedTemplate ?? const <String, dynamic>{};
    final domain = template['domain']?.toString() ?? 'hiring';
    return {
      'domain': domain,
      'display_name': _displayNameController.text.trim().isEmpty
          ? (template['display_name']?.toString() ?? 'Custom')
          : _displayNameController.text.trim(),
      'outcome_column': _normalizeHeader(_outcomeColumnController.text),
      'outcome_positive_value': _positiveValueController.text.trim().isEmpty
          ? 1
          : _positiveValueController.text.trim(),
      'protected_attributes': _csvToList(_protectedAttrsController.text),
      'feature_columns': _csvToList(_featureColumnsController.text),
      'required_columns': _csvToList(_requiredColumnsController.text),
      'subject_label': _subjectLabelController.text.trim().isEmpty
          ? 'Record'
          : _subjectLabelController.text.trim(),
      'outcome_label': _outcomeLabelController.text.trim().isEmpty
          ? 'Outcome'
          : _outcomeLabelController.text.trim(),
      'column_map': template['column_map'] is Map
          ? Map<String, dynamic>.from(template['column_map'] as Map)
          : <String, dynamic>{},
    };
  }

  Future<void> _runAudit({int initialTabIndex = 0}) async {
    final session = AuthService.instance.currentSession;
    if (_datasetFile == null || session == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Choose a CSV and sign in first.')),
      );
      return;
    }
    if (_missingHeaders.isNotEmpty &&
        !_missingHeaders.contains('Could not read CSV headers')) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Add the missing required columns first: ${_missingHeaders.join(', ')}',
          ),
        ),
      );
      return;
    }

    final template = _selectedTemplate;
    if (template == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Choose an audit template first.')),
      );
      return;
    }

    final auditId = FirebaseService.instance.createAuditId();
    setState(() {
      _loading = true;
      _activeAuditId = auditId;
      _launchTargetTab = initialTabIndex;
    });
    try {
      final response = await ApiService.instance.runAudit(
        datasetFile: _datasetFile!,
        modelFile: _modelFile,
        modelName: _modelNameController.text.trim().isEmpty
            ? 'Uploaded Decision Model'
            : _modelNameController.text.trim(),
        userId: session.uid,
        domain: template['domain']?.toString() ?? 'hiring',
        domainConfig: _currentDomainConfig(),
        auditId: auditId,
      );
      if (!mounted) {
        return;
      }
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ReportScreen(
            initialAudit: response,
            initialTabIndex: initialTabIndex,
          ),
        ),
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
      if (mounted) {
        setState(() {
          _loading = false;
          _activeAuditId = null;
          _launchTargetTab = null;
        });
      }
    }
  }

  String _fileSize(PlatformFile file) {
    final bytes = file.size.toDouble();
    if (bytes < 1024) {
      return '${bytes.toStringAsFixed(0)} B';
    }
    if (bytes < 1024 * 1024) {
      return '${(bytes / 1024).toStringAsFixed(1)} KB';
    }
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  String _previewList(List<String> values, {int maxItems = 2}) {
    if (values.isEmpty) {
      return 'Not configured yet';
    }
    if (values.length <= maxItems) {
      return values.join(', ');
    }
    return '${values.take(maxItems).join(', ')} +${values.length - maxItems}';
  }

  String _launchStatusLabel() {
    if (_datasetFile == null) {
      return 'Choose a CSV to launch this module';
    }
    if (_missingHeaders.isNotEmpty &&
        !_missingHeaders.contains('Could not read CSV headers')) {
      return 'Fix missing required columns first';
    }
    return 'Run the audit and land here first';
  }

  String _launchLoadingLabel() {
    return switch (_launchTargetTab) {
      1 => 'Opening records workspace...',
      2 => 'Opening mitigation workspace...',
      3 => 'Opening governance workspace...',
      _ => 'Running fairness analysis...',
    };
  }

  @override
  void dispose() {
    _modelNameController.dispose();
    _displayNameController.dispose();
    _outcomeColumnController.dispose();
    _protectedAttrsController.dispose();
    _featureColumnsController.dispose();
    _requiredColumnsController.dispose();
    _subjectLabelController.dispose();
    _outcomeLabelController.dispose();
    _positiveValueController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final session = AuthService.instance.currentSession;
    final selectedDomain = _selectedTemplate?['domain']?.toString();
    final protectedAttributes = _csvToList(_protectedAttrsController.text);
    final featureColumns = _csvToList(_featureColumnsController.text);
    final requiredColumns = _csvToList(_requiredColumnsController.text);
    final subjectLabel = _subjectLabelController.text.trim().isEmpty
        ? 'Record'
        : _subjectLabelController.text.trim();
    final outcomeLabel = _outcomeLabelController.text.trim().isEmpty
        ? 'Outcome'
        : _outcomeLabelController.text.trim();
    final launchStatusLabel = _launchStatusLabel();

    return Scaffold(
      appBar: AppBar(title: const Text('Create Audit Workspace')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 36),
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: isDark ? AppGradients.darkGlass : AppGradients.glass,
              borderRadius: BorderRadius.circular(28),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(isDark ? 0.24 : 0.06),
                  blurRadius: 18,
                  offset: const Offset(0, 12),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.unBlue.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    'Preset and custom audit blueprints',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: AppColors.unBlue,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  'Build the exact fairness audit your team needs, then open it in a full review workspace.',
                  style: theme.textTheme.headlineMedium,
                ),
                const SizedBox(height: 10),
                Text(
                  'Choose a domain template or define your own outcome, protected attributes, and required columns before the dataset is uploaded.',
                  style: theme.textTheme.bodyLarge?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Text('Audit Blueprint', style: theme.textTheme.titleLarge),
          const SizedBox(height: 12),
          if (_loadingTemplates)
            const _TemplateSkeleton()
          else
            SizedBox(
              height: 170,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                physics: const BouncingScrollPhysics(),
                itemBuilder: (context, index) {
                  final template = _templates[index];
                  return _TemplateCard(
                    template: template,
                    selected: selectedDomain == template['domain']?.toString(),
                    onTap: () => _applyTemplate(template),
                  );
                },
                separatorBuilder: (_, __) => const SizedBox(width: 14),
                itemCount: _templates.length,
              ),
            ),
          const SizedBox(height: 24),
          _SchemaEditorCard(
            selectedTemplate: _selectedTemplate,
            displayNameController: _displayNameController,
            outcomeColumnController: _outcomeColumnController,
            protectedAttrsController: _protectedAttrsController,
            featureColumnsController: _featureColumnsController,
            requiredColumnsController: _requiredColumnsController,
            subjectLabelController: _subjectLabelController,
            outcomeLabelController: _outcomeLabelController,
            positiveValueController: _positiveValueController,
            showAdvancedSchema: _showAdvancedSchema,
            onToggleAdvanced: () {
              setState(() => _showAdvancedSchema = !_showAdvancedSchema);
            },
          ),
          const SizedBox(height: 24),
          _DashedUploadZone(
            icon: Icons.table_chart_rounded,
            title: 'Upload dataset CSV',
            subtitle:
                'Bring in the decision dataset you want to audit for fairness risk.',
            hint: 'Accepted format: .csv',
            selectedFile: _datasetFile,
            fileMeta: _datasetFile == null ? null : _fileSize(_datasetFile!),
            onTap: _loading ? null : _pickDataset,
          ),
          if (_datasetFile != null) ...[
            const SizedBox(height: 12),
            _SelectedFileChip(
              fileName: _datasetFile!.name,
              meta: _fileSize(_datasetFile!),
            ),
          ],
          const SizedBox(height: 18),
          _DashedUploadZone(
            icon: Icons.memory_rounded,
            title: 'Attach model file (optional)',
            subtitle:
                'Include a trained model when you want the audit to travel with a specific release candidate.',
            hint: 'Accepted formats: .pkl, .h5',
            selectedFile: _modelFile,
            fileMeta: _modelFile == null ? null : _fileSize(_modelFile!),
            onTap: _loading ? null : _pickModel,
          ),
          if (_modelFile != null) ...[
            const SizedBox(height: 12),
            _SelectedFileChip(
              fileName: _modelFile!.name,
              meta: _fileSize(_modelFile!),
            ),
          ],
          const SizedBox(height: 24),
          Text('Model name', style: theme.textTheme.titleMedium),
          const SizedBox(height: 10),
          TextField(
            controller: _modelNameController,
            enabled: !_loading,
            textInputAction: TextInputAction.done,
            decoration: const InputDecoration(
              hintText: 'Hiring Funnel Model v4',
              helperText:
                  'This label appears in the history and workspace views.',
              prefixIcon: Icon(Icons.label_outline_rounded),
            ),
          ),
          const SizedBox(height: 24),
          _HeaderValidationCard(
            requiredColumns: _csvToList(_requiredColumnsController.text),
            foundHeaders: _foundHeaders,
            missingHeaders: _missingHeaders,
          ),
          const SizedBox(height: 24),
          Text('Workspace modules', style: theme.textTheme.titleLarge),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, constraints) => GridView.count(
              crossAxisCount: constraints.maxWidth >= 960 ? 2 : 1,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 14,
              crossAxisSpacing: 14,
              childAspectRatio: constraints.maxWidth >= 960 ? 1.18 : 1.55,
              children: [
                _WorkspaceModuleCard(
                  icon: Icons.insights_rounded,
                  title: 'Overview',
                  body:
                      'Risk summary, SHAP drivers, causal path, and plain-language explanation.',
                  accent: AppColors.unBlue,
                  active: _launchTargetTab == 0,
                  statusLabel: launchStatusLabel,
                  previewItems: [
                    MapEntry(
                      'Template',
                      _displayNameController.text.trim().isEmpty
                          ? 'Custom blueprint'
                          : _displayNameController.text.trim(),
                    ),
                    MapEntry('Outcome', outcomeLabel),
                    MapEntry('Protected', '${protectedAttributes.length} tracked'),
                  ],
                  onTap: _loading ? null : () => _runAudit(initialTabIndex: 0),
                ),
                _WorkspaceModuleCard(
                  icon: Icons.people_alt_outlined,
                  title: 'Records',
                  body:
                      'Searchable candidate review with flagged cases and what-if detail.',
                  accent: AppColors.warning,
                  active: _launchTargetTab == 1,
                  statusLabel: launchStatusLabel,
                  previewItems: [
                    MapEntry('Subject', subjectLabel),
                    MapEntry('Dataset', _datasetFile?.name ?? 'No CSV selected'),
                    MapEntry(
                      'Schema check',
                      '${_foundHeaders.length}/${requiredColumns.length} required columns',
                    ),
                  ],
                  onTap: _loading ? null : () => _runAudit(initialTabIndex: 1),
                ),
                _WorkspaceModuleCard(
                  icon: Icons.tune_rounded,
                  title: 'Mitigation',
                  body:
                      'Strategy comparison, fairness lift, and synthetic patch testing.',
                  accent: AppColors.success,
                  active: _launchTargetTab == 2,
                  statusLabel: launchStatusLabel,
                  previewItems: [
                    MapEntry('Protected attrs', _previewList(protectedAttributes)),
                    MapEntry('Features', _previewList(featureColumns)),
                    MapEntry(
                      'Positive value',
                      _positiveValueController.text.trim().isEmpty
                          ? '1'
                          : _positiveValueController.text.trim(),
                    ),
                  ],
                  onTap: _loading ? null : () => _runAudit(initialTabIndex: 2),
                ),
                _WorkspaceModuleCard(
                  icon: Icons.verified_user_outlined,
                  title: 'Governance',
                  body:
                      'Policy verdicts, proxy findings, and fairness certificate status.',
                  accent: AppColors.danger,
                  active: _launchTargetTab == 3,
                  statusLabel: launchStatusLabel,
                  previewItems: [
                    MapEntry('Required', '${requiredColumns.length} columns'),
                    MapEntry('Headers', _previewList(_foundHeaders, maxItems: 3)),
                    MapEntry('Auth', session == null ? 'Sign in required' : 'Session ready'),
                  ],
                  onTap: _loading ? null : () => _runAudit(initialTabIndex: 3),
                ),
              ],
            ),
          ),
          if (_activeAuditId != null) ...[
            const SizedBox(height: 24),
            _AuditStatusTimeline(auditId: _activeAuditId!),
          ],
          const SizedBox(height: 26),
          _GradientActionButton(
            label: 'Launch Audit Workspace',
            loadingLabel: _launchLoadingLabel(),
            icon: Icons.play_arrow_rounded,
            loading: _loading,
            enabled: !_loading,
            onPressed: () => _runAudit(initialTabIndex: 0),
          ),
          const SizedBox(height: 14),
          Text(
            'Tap a module to launch the audit and open that tab first. The main action button opens the full workspace on Overview.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

class _SchemaEditorCard extends StatelessWidget {
  const _SchemaEditorCard({
    required this.selectedTemplate,
    required this.displayNameController,
    required this.outcomeColumnController,
    required this.protectedAttrsController,
    required this.featureColumnsController,
    required this.requiredColumnsController,
    required this.subjectLabelController,
    required this.outcomeLabelController,
    required this.positiveValueController,
    required this.showAdvancedSchema,
    required this.onToggleAdvanced,
  });

  final Map<String, dynamic>? selectedTemplate;
  final TextEditingController displayNameController;
  final TextEditingController outcomeColumnController;
  final TextEditingController protectedAttrsController;
  final TextEditingController featureColumnsController;
  final TextEditingController requiredColumnsController;
  final TextEditingController subjectLabelController;
  final TextEditingController outcomeLabelController;
  final TextEditingController positiveValueController;
  final bool showAdvancedSchema;
  final VoidCallback onToggleAdvanced;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final template = selectedTemplate;
    final isCustom = template?['domain'] == 'custom';
    final isDark = theme.brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(isDark ? 0.18 : 0.05),
            blurRadius: 18,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isCustom
                          ? 'Custom schema'
                          : 'Preset schema with overrides',
                      style: theme.textTheme.titleLarge,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      isCustom
                          ? 'Define your own outcome, entity labels, and required columns.'
                          : 'Review the default audit shape and open advanced controls only when your data needs it.',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              TextButton.icon(
                onPressed: onToggleAdvanced,
                icon: Icon(
                  showAdvancedSchema ? Icons.expand_less : Icons.tune_rounded,
                ),
                label: Text(showAdvancedSchema ? 'Hide fields' : 'Edit fields'),
              ),
            ],
          ),
          const SizedBox(height: 18),
          TextField(
            controller: displayNameController,
            decoration: const InputDecoration(
              labelText: 'Display name',
              hintText: 'Custom workforce audit',
              prefixIcon: Icon(Icons.dashboard_customize_outlined),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: outcomeColumnController,
                  decoration: const InputDecoration(
                    labelText: 'Outcome column',
                    hintText: 'hired',
                    prefixIcon: Icon(Icons.flag_outlined),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: positiveValueController,
                  decoration: const InputDecoration(
                    labelText: 'Positive value',
                    hintText: '1',
                    prefixIcon: Icon(Icons.filter_1_rounded),
                  ),
                ),
              ),
            ],
          ),
          if (showAdvancedSchema || isCustom) ...[
            const SizedBox(height: 16),
            TextField(
              controller: protectedAttrsController,
              decoration: const InputDecoration(
                labelText: 'Protected attributes',
                hintText: 'gender, ethnicity, age',
                helperText: 'Comma-separated list',
                prefixIcon: Icon(Icons.security_outlined),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: featureColumnsController,
              decoration: const InputDecoration(
                labelText: 'Feature columns',
                hintText: 'years_experience, education_level',
                helperText: 'Comma-separated list',
                prefixIcon: Icon(Icons.scatter_plot_outlined),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: requiredColumnsController,
              minLines: 2,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Required columns',
                hintText: 'name, gender, age, outcome',
                helperText:
                    'Columns that must be present before upload continues',
                prefixIcon: Icon(Icons.rule_rounded),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: subjectLabelController,
                    decoration: const InputDecoration(
                      labelText: 'Subject label',
                      hintText: 'Candidate',
                      prefixIcon: Icon(Icons.person_outline_rounded),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: outcomeLabelController,
                    decoration: const InputDecoration(
                      labelText: 'Outcome label',
                      hintText: 'Hired',
                      prefixIcon: Icon(Icons.task_alt_rounded),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _TemplateCard extends StatelessWidget {
  const _TemplateCard({
    required this.template,
    required this.selected,
    required this.onTap,
  });

  final Map<String, dynamic> template;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final required = template['required_columns'];
    final count = required is List ? required.length : 0;

    return AnimatedScale(
      duration: const Duration(milliseconds: 180),
      scale: selected ? 1 : 0.985,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(26),
          child: Ink(
            width: 260,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: selected ? AppGradients.hero : AppGradients.glass,
              borderRadius: BorderRadius.circular(26),
              border: Border.all(
                color: selected
                    ? Colors.transparent
                    : theme.colorScheme.outline.withOpacity(0.28),
              ),
              boxShadow: [
                BoxShadow(
                  color: selected
                      ? AppColors.deepNavy.withOpacity(0.24)
                      : Colors.black.withOpacity(0.05),
                  blurRadius: 18,
                  offset: const Offset(0, 12),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: selected
                        ? Colors.white.withOpacity(0.14)
                        : AppColors.accentAmber.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    template['domain']?.toString().toUpperCase() ?? 'AUDIT',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: selected ? Colors.white : AppColors.accentAmber,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const Spacer(),
                Text(
                  template['display_name']?.toString() ?? 'Template',
                  style: theme.textTheme.headlineMedium?.copyWith(
                    color:
                        selected ? Colors.white : theme.colorScheme.onSurface,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '$count required columns',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: selected
                        ? Colors.white.withOpacity(0.78)
                        : theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final field
                        in (required is List ? required.take(3) : const []))
                      _MiniPill(
                        label: field.toString(),
                        inverted: selected,
                      ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _TemplateSkeleton extends StatelessWidget {
  const _TemplateSkeleton();

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final baseColor =
        isDark ? const Color(0xFF202945) : const Color(0xFFE9EDF7);
    final highlightColor =
        isDark ? const Color(0xFF2A3558) : const Color(0xFFF8FAFF);

    return Shimmer.fromColors(
      baseColor: baseColor,
      highlightColor: highlightColor,
      child: SizedBox(
        height: 170,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemBuilder: (_, __) => Container(
            width: 260,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(26),
            ),
          ),
          separatorBuilder: (_, __) => const SizedBox(width: 14),
          itemCount: 3,
        ),
      ),
    );
  }
}

class _MiniPill extends StatelessWidget {
  const _MiniPill({
    required this.label,
    required this.inverted,
  });

  final String label;
  final bool inverted;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: inverted
            ? Colors.white.withOpacity(0.14)
            : AppColors.unBlue.withOpacity(0.10),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: inverted ? Colors.white : AppColors.unBlue,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

class _HeaderValidationCard extends StatelessWidget {
  const _HeaderValidationCard({
    required this.requiredColumns,
    required this.foundHeaders,
    required this.missingHeaders,
  });

  final List<String> requiredColumns;
  final List<String> foundHeaders;
  final List<String> missingHeaders;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final statusText = requiredColumns.isEmpty
        ? 'Add the required columns for this audit blueprint.'
        : missingHeaders.isEmpty
            ? 'The selected CSV matches every required column.'
            : 'The CSV is still missing a few required columns.';

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: theme.colorScheme.outline.withOpacity(0.24),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Client-side schema check', style: theme.textTheme.titleMedium),
          const SizedBox(height: 6),
          Text(
            statusText,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: requiredColumns.map((column) {
              final present = foundHeaders.contains(column);
              return Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: present
                      ? AppColors.success.withOpacity(0.12)
                      : AppColors.danger.withOpacity(0.10),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  column,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: present ? AppColors.success : AppColors.danger,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              );
            }).toList(),
          ),
          if (missingHeaders.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              'Missing: ${missingHeaders.join(', ')}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: AppColors.danger,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _WorkspaceModuleCard extends StatelessWidget {
  const _WorkspaceModuleCard({
    required this.icon,
    required this.title,
    required this.body,
    required this.accent,
    required this.previewItems,
    required this.statusLabel,
    required this.onTap,
    this.active = false,
  });

  final IconData icon;
  final String title;
  final String body;
  final Color accent;
  final List<MapEntry<String, String>> previewItems;
  final String statusLabel;
  final VoidCallback? onTap;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
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
              color: active
                  ? accent.withOpacity(0.85)
                  : theme.colorScheme.outline.withOpacity(0.20),
              width: active ? 1.6 : 1,
            ),
            boxShadow: active
                ? [
                    BoxShadow(
                      color: accent.withOpacity(0.18),
                      blurRadius: 18,
                      offset: const Offset(0, 10),
                    ),
                  ]
                : null,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: accent.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    alignment: Alignment.center,
                    child: Icon(icon, color: accent),
                  ),
                  const Spacer(),
                  Icon(
                    Icons.arrow_outward_rounded,
                    color: active
                        ? accent
                        : theme.colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Theme.of(context).brightness == Brightness.dark
                      ? Colors.white.withOpacity(0.05)
                      : const Color(0xFFF8FAFF),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Column(
                  children: [
                    for (var index = 0; index < previewItems.length; index++) ...[
                      _ModulePreviewRow(entry: previewItems[index]),
                      if (index < previewItems.length - 1)
                        const SizedBox(height: 10),
                    ],
                  ],
                ),
              ),
              const Spacer(),
              Text(title, style: theme.textTheme.titleMedium),
              const SizedBox(height: 6),
              Text(
                body,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                statusLabel,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: active ? accent : theme.colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ModulePreviewRow extends StatelessWidget {
  const _ModulePreviewRow({
    required this.entry,
  });

  final MapEntry<String, String> entry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Text(
            entry.key,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Flexible(
          child: Text(
            entry.value,
            textAlign: TextAlign.right,
            style: theme.textTheme.bodySmall?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}

class _AuditStatusTimeline extends StatelessWidget {
  const _AuditStatusTimeline({
    required this.auditId,
  });

  final String auditId;

  static const _stages = <String>[
    'uploading',
    'computing_metrics',
    'generating_shap',
    'running_counterfactuals',
    'applying_mitigation',
    'complete',
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return StreamBuilder<Map<String, dynamic>?>(
      stream: FirebaseService.instance.streamAudit(auditId),
      builder: (context, snapshot) {
        final audit = snapshot.data;
        final stage = audit?['stage']?.toString() ?? 'uploading';
        final status = audit?['status']?.toString() ?? 'processing';
        final activeIndex =
            _stages.contains(stage) ? _stages.indexOf(stage) : 0;

        return Container(
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
                  const Icon(
                    Icons.cloud_sync_rounded,
                    color: AppColors.unBlue,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Live audit status',
                      style: theme.textTheme.titleMedium,
                    ),
                  ),
                  Text(
                    status,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: status == 'failed'
                          ? AppColors.danger
                          : AppColors.unBlue,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (var index = 0; index < _stages.length; index++)
                    _StageChip(
                      label: _stages[index].replaceAll('_', ' '),
                      active: index == activeIndex,
                      complete: index < activeIndex || stage == 'complete',
                    ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

class _StageChip extends StatelessWidget {
  const _StageChip({
    required this.label,
    required this.active,
    required this.complete,
  });

  final String label;
  final bool active;
  final bool complete;

  @override
  Widget build(BuildContext context) {
    final color = complete
        ? AppColors.success
        : active
            ? AppColors.unBlue
            : Theme.of(context).colorScheme.onSurfaceVariant;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: color.withOpacity(active || complete ? 0.14 : 0.08),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: color,
              fontWeight:
                  active || complete ? FontWeight.w800 : FontWeight.w600,
            ),
      ),
    );
  }
}

class _DashedUploadZone extends StatelessWidget {
  const _DashedUploadZone({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.hint,
    required this.selectedFile,
    required this.fileMeta,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String hint;
  final PlatformFile? selectedFile;
  final String? fileMeta;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final hasFile = selectedFile != null;
    final accent = hasFile ? AppColors.success : AppColors.accentAmber;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: Ink(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            gradient: isDark ? AppGradients.darkGlass : AppGradients.glass,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(isDark ? 0.20 : 0.05),
                blurRadius: 18,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          child: CustomPaint(
            painter: _DashedBorderPainter(
              color: accent.withOpacity(isDark ? 0.70 : 0.90),
            ),
            child: Padding(
              padding: const EdgeInsets.all(22),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 60,
                    height: 60,
                    decoration: BoxDecoration(
                      color: accent.withOpacity(0.14),
                      borderRadius: BorderRadius.circular(18),
                    ),
                    alignment: Alignment.center,
                    child: Icon(icon, color: accent),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(title, style: theme.textTheme.titleLarge),
                        const SizedBox(height: 8),
                        Text(
                          subtitle,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 10,
                          runSpacing: 10,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 8,
                              ),
                              decoration: BoxDecoration(
                                color: accent.withOpacity(0.12),
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(
                                hint,
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: accent,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            if (hasFile && fileMeta != null)
                              Text(
                                fileMeta!,
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: theme.colorScheme.onSurfaceVariant,
                                ),
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _SelectedFileChip extends StatelessWidget {
  const _SelectedFileChip({
    required this.fileName,
    required this.meta,
  });

  final String fileName;
  final String meta;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.success.withOpacity(0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: AppColors.success.withOpacity(0.28),
        ),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.check_circle_rounded,
            color: AppColors.success,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              fileName,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: AppColors.success,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Text(
            meta,
            style: theme.textTheme.bodySmall?.copyWith(
              color: AppColors.success,
            ),
          ),
        ],
      ),
    );
  }
}

class _GradientActionButton extends StatelessWidget {
  const _GradientActionButton({
    required this.label,
    required this.loadingLabel,
    required this.icon,
    required this.loading,
    required this.enabled,
    required this.onPressed,
  });

  final String label;
  final String loadingLabel;
  final IconData icon;
  final bool loading;
  final bool enabled;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Opacity(
      opacity: enabled ? 1 : 0.92,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: enabled
              ? AppGradients.accent
              : LinearGradient(
                  colors: [
                    AppColors.accentAmber.withOpacity(0.6),
                    AppColors.accentAmber.withOpacity(0.45),
                  ],
                ),
          borderRadius: BorderRadius.circular(999),
          boxShadow: [
            BoxShadow(
              color: AppColors.accentAmber.withOpacity(0.24),
              blurRadius: 18,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: ElevatedButton(
          onPressed: enabled ? onPressed : null,
          style: ElevatedButton.styleFrom(
            minimumSize: const Size.fromHeight(58),
            backgroundColor: Colors.transparent,
            shadowColor: Colors.transparent,
            foregroundColor: AppColors.deepNavy,
            disabledBackgroundColor: Colors.transparent,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(999),
            ),
          ),
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 220),
            child: loading
                ? Shimmer.fromColors(
                    key: const ValueKey('loading'),
                    baseColor: AppColors.deepNavy.withOpacity(0.45),
                    highlightColor: AppColors.deepNavy,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                          width: 18,
                          height: 18,
                          decoration: const BoxDecoration(
                            color: AppColors.deepNavy,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          loadingLabel,
                          style: theme.textTheme.labelLarge?.copyWith(
                            color: AppColors.deepNavy,
                          ),
                        ),
                      ],
                    ),
                  )
                : Row(
                    key: const ValueKey('idle'),
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(icon),
                      const SizedBox(width: 10),
                      Text(label),
                    ],
                  ),
          ),
        ),
      ),
    );
  }
}

class _DashedBorderPainter extends CustomPainter {
  _DashedBorderPainter({
    required this.color,
  });

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    const radius = Radius.circular(24);
    final rect = RRect.fromRectAndRadius(
      Offset.zero & size,
      radius,
    );
    final path = Path()..addRRect(rect);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6;

    for (final metric in path.computeMetrics()) {
      double distance = 0;
      while (distance < metric.length) {
        const dashLength = 8.0;
        const gapLength = 7.0;
        final end = math.min(distance + dashLength, metric.length);
        canvas.drawPath(metric.extractPath(distance, end), paint);
        distance += dashLength + gapLength;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DashedBorderPainter oldDelegate) {
    return oldDelegate.color != color;
  }
}
