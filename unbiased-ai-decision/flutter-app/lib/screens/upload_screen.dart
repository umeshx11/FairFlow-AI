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
  PlatformFile? _datasetFile;
  PlatformFile? _modelFile;
  final TextEditingController _modelNameController = TextEditingController();
  bool _loading = false;
  String? _activeAuditId;
  String _selectedDomain = 'hiring';

  Future<void> _pickDataset() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      withData: true,
      allowedExtensions: ['csv'],
    );
    if (result != null && mounted) {
      setState(() => _datasetFile = result.files.single);
    }
  }

  Future<void> _pickModel() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      withData: true,
      allowedExtensions: ['pkl', 'h5'],
    );
    if (result != null && mounted) {
      setState(() => _modelFile = result.files.single);
    }
  }

  Future<void> _runAudit() async {
    final session = AuthService.instance.currentSession;
    if (_datasetFile == null || session == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Choose a CSV and sign in first.')),
      );
      return;
    }

    final auditId = FirebaseService.instance.createAuditId();
    setState(() {
      _loading = true;
      _activeAuditId = auditId;
    });
    try {
      final response = await ApiService.instance.runAudit(
        datasetFile: _datasetFile!,
        modelFile: _modelFile,
        modelName: _modelNameController.text.trim().isEmpty
            ? 'Uploaded Decision Model'
            : _modelNameController.text.trim(),
        userId: session.uid,
        domain: _selectedDomain,
        auditId: auditId,
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ReportScreen(initialAudit: response),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            error.toString().replaceFirst('Exception: ', ''),
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
          _activeAuditId = null;
        });
      }
    }
  }

  @override
  void dispose() {
    _modelNameController.dispose();
    super.dispose();
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

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Create a New Audit'),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: isDark
                    ? [
                        const Color(0xFF1B2441),
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
                  color: Colors.black.withOpacity(isDark ? 0.22 : 0.06),
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
                    color: AppColors.accentAmber.withOpacity(0.14),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    'Simple 3-step upload flow',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: AppColors.accentAmber,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                Text(
                  'Upload your decision data and let the app run a fairness review for you.',
                  style: theme.textTheme.headlineMedium?.copyWith(
                    color: theme.colorScheme.onSurface,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'Start with the CSV dataset, optionally attach a model file, then give the audit a clear model name so your team can recognize it later.',
                  style: theme.textTheme.bodyLarge?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          _DashedUploadZone(
            icon: Icons.table_chart_rounded,
            emoji: '📂',
            title: 'Tap to upload Dataset CSV',
            subtitle:
                'Upload the decision data you want to audit for hidden bias.',
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
            emoji: '🤖',
            title: 'Tap to upload Model File (optional)',
            subtitle:
                'Attach a trained model file if you want the audit to evaluate it directly.',
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
          Text(
            'Domain',
            style: theme.textTheme.titleMedium,
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            value: _selectedDomain,
            items: const [
              DropdownMenuItem(
                value: 'hiring',
                child: Text('Hiring'),
              ),
              DropdownMenuItem(
                value: 'lending',
                child: Text('Lending'),
              ),
              DropdownMenuItem(
                value: 'medical',
                child: Text('Medical'),
              ),
            ],
            onChanged: _loading
                ? null
                : (value) {
                    if (value == null) return;
                    setState(() => _selectedDomain = value);
                  },
            decoration: const InputDecoration(
              helperText: 'Choose the schema that matches your CSV columns.',
              prefixIcon: Icon(
                Icons.category_outlined,
                semanticLabel: 'Audit domain',
              ),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            'Model Name',
            style: theme.textTheme.titleMedium,
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _modelNameController,
            enabled: !_loading,
            textInputAction: TextInputAction.done,
            decoration: const InputDecoration(
              hintText: 'Loan Approval Model v2',
              helperText: 'e.g. Loan Approval Model v2',
              prefixIcon: Icon(
                Icons.label_outline_rounded,
                semanticLabel: 'Model name',
              ),
            ),
          ),
          const SizedBox(height: 28),
          if (_activeAuditId != null) ...[
            _AuditStatusTimeline(auditId: _activeAuditId!),
            const SizedBox(height: 18),
          ],
          _GradientActionButton(
            label: 'Run Bias Audit',
            loadingLabel: 'Running fairness analysis...',
            icon: Icons.play_arrow_rounded,
            loading: _loading,
            enabled: !_loading,
            onPressed: _runAudit,
          ),
          const SizedBox(height: 14),
          Text(
            'Your report will include a bias score, Gemini guidance, feature impact, causal graph, and SDG target mapping.',
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

class _AuditStatusTimeline extends StatelessWidget {
  const _AuditStatusTimeline({
    required this.auditId,
  });

  final String auditId;

  static const _stages = <String>[
    'uploading',
    'uploaded',
    'preparing_features',
    'calling_vertex_endpoint',
    'running_predictions',
    'generating_shap',
    'building_causal_graph',
    'computing_fairness_metrics',
    'generating_gemini',
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
        final activeIndex = _stages.indexOf(stage).clamp(0, _stages.length - 1);

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
                    semanticLabel: 'Live Firestore status',
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Live Firestore audit status',
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
    required this.emoji,
    required this.title,
    required this.subtitle,
    required this.hint,
    required this.selectedFile,
    required this.fileMeta,
    required this.onTap,
  });

  final IconData icon;
  final String emoji;
  final String title;
  final String subtitle;
  final String hint;
  final PlatformFile? selectedFile;
  final String? fileMeta;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;
    final bool hasFile = selectedFile != null;
    final Color accent = hasFile ? AppColors.success : AppColors.accentAmber;

    return Semantics(
      button: true,
      label: title,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(24),
          child: Ink(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(24),
              gradient: LinearGradient(
                colors: isDark
                    ? [
                        const Color(0xFF19213A),
                        const Color(0xFF12192D),
                      ]
                    : [
                        Colors.white,
                        const Color(0xFFF8FAFF),
                      ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
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
                      width: 64,
                      height: 64,
                      decoration: BoxDecoration(
                        color: accent.withOpacity(0.14),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      alignment: Alignment.center,
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            emoji,
                            style: const TextStyle(fontSize: 18),
                          ),
                          const SizedBox(height: 4),
                          Icon(
                            icon,
                            color: accent,
                            size: 20,
                            semanticLabel: title,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            style: theme.textTheme.titleLarge?.copyWith(
                              color: theme.colorScheme.onSurface,
                              fontSize: 18,
                            ),
                          ),
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
                            crossAxisAlignment: WrapCrossAlignment.center,
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

    return AnimatedContainer(
      duration: const Duration(milliseconds: 220),
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
            semanticLabel: 'File selected',
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
            minimumSize: const Size.fromHeight(56),
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
                      Icon(
                        icon,
                        semanticLabel: label,
                      ),
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
