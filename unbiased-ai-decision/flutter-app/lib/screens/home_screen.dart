import 'dart:ui';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:lottie/lottie.dart';
import 'package:shimmer/shimmer.dart';

import '../services/auth_service.dart';
import '../services/firebase_service.dart';
import '../theme/app_theme.dart';
import 'history_screen.dart';
import 'report_screen.dart';
import 'upload_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  late Future<Map<String, dynamic>> _summaryFuture;
  late final AnimationController _fabController;
  late final Animation<double> _fabScale;

  @override
  void initState() {
    super.initState();
    _summaryFuture = _loadSummary();
    _fabController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    );
    _fabScale = Tween<double>(begin: 0.84, end: 1).animate(
      CurvedAnimation(
        parent: _fabController,
        curve: Curves.elasticOut,
      ),
    );
    _fabController.forward();
  }

  @override
  void dispose() {
    _fabController.dispose();
    super.dispose();
  }

  Future<Map<String, dynamic>> _loadSummary() async {
    final session = AuthService.instance.currentSession;
    if (session == null) {
      return {
        'auditsRun': 0,
        'avgBiasScore': 0.0,
        'sdgAlignment': 'SDG 10.3, 8.5, 16.b',
        'recentAudits': <Map<String, dynamic>>[],
      };
    }

    final summary = await FirebaseService.instance.computeDashboardSummary(
      session.uid,
      includeSample: session.isGuest,
    );
    final cachedAudit = AuthService.instance.consumePreloadedGuestAudit();
    final recentAudits =
        (summary['recentAudits'] as List?)?.cast<Map<String, dynamic>>() ??
            <Map<String, dynamic>>[];

    if (cachedAudit != null && recentAudits.isEmpty) {
      return {
        ...summary,
        'recentAudits': [cachedAudit],
        'auditsRun': 1,
        'avgBiasScore': (cachedAudit['bias_score'] as num?)?.toDouble() ?? 0.0,
      };
    }

    return summary;
  }

  Future<void> _refresh() async {
    setState(() {
      _summaryFuture = _loadSummary();
    });
    await _summaryFuture;
  }

  Future<void> _logout() async {
    try {
      await AuthService.instance.signOut();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            error.toString().replaceFirst('Exception: ', ''),
          ),
        ),
      );
    }
  }

  void _openUpload() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const UploadScreen()),
    );
  }

  void _openHistory() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const HistoryScreen()),
    );
  }

  String _displayName(AuthSession? session) {
    if (session == null) return 'there';
    if (session.isGuest) return 'Guest';
    if ((session.name ?? '').trim().isNotEmpty) {
      return session.name!.trim().split(' ').first;
    }
    final email = session.email ?? '';
    if (email.isNotEmpty) {
      final token = email.split('@').first;
      if (token.isNotEmpty) {
        return token[0].toUpperCase() + token.substring(1);
      }
    }
    return 'there';
  }

  String _formatDate(dynamic value) {
    if (value == null) return 'Unknown date';
    if (value is Timestamp) {
      return DateFormat.yMMMd().format(value.toDate());
    }
    if (value is DateTime) {
      return DateFormat.yMMMd().format(value);
    }
    return value.toString();
  }

  double _scoreOf(Map<String, dynamic> audit) {
    return (audit['bias_score'] as num?)?.toDouble() ?? 0;
  }

  Color _severityColor(double score) {
    if (score <= 30) return AppColors.success;
    if (score <= 60) return AppColors.warning;
    return AppColors.danger;
  }

  String _severityLabel(double score) {
    if (score <= 30) return 'Low Bias Risk';
    if (score <= 60) return 'Moderate Bias Risk';
    return 'High Bias Risk';
  }

  String _avgTone(double average) {
    if (average <= 30) return 'Healthy';
    if (average <= 60) return 'Watch Closely';
    return 'Needs Action';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final bool isDark = theme.brightness == Brightness.dark;
    final session = AuthService.instance.currentSession;
    final name = _displayName(session);

    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 78,
        titleSpacing: 20,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              'Unbiased AI Decision',
              style: textTheme.titleLarge?.copyWith(
                color: theme.colorScheme.onSurface,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              'Executive fairness dashboard',
              style: textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: _TopActionButton(
              label: 'Open history',
              icon: Icons.history_rounded,
              onTap: _openHistory,
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: _TopActionButton(
              label: 'Sign out',
              icon: Icons.logout_rounded,
              onTap: _logout,
            ),
          ),
        ],
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
      floatingActionButton: ScaleTransition(
        scale: _fabScale,
        child: FloatingActionButton.extended(
          heroTag: 'home-new-audit',
          onPressed: _openUpload,
          icon: const Icon(
            Icons.add_circle_outline_rounded,
            semanticLabel: 'Create a new audit',
          ),
          label: const Text('New Audit +'),
        ),
      ),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _summaryFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const _HomeSkeleton();
          }

          final summary = snapshot.data ??
              {
                'auditsRun': 0,
                'avgBiasScore': 0.0,
                'sdgAlignment': 'SDG 10.3, 8.5, 16.b',
                'recentAudits': <Map<String, dynamic>>[],
              };

          final recentAudits = (summary['recentAudits'] as List?)
                  ?.cast<Map<String, dynamic>>() ??
              <Map<String, dynamic>>[];
          final double avgBias =
              (summary['avgBiasScore'] as num?)?.toDouble() ?? 0.0;

          return RefreshIndicator(
            onRefresh: _refresh,
            color: AppColors.accentAmber,
            child: ListView(
              physics: const BouncingScrollPhysics(
                parent: AlwaysScrollableScrollPhysics(),
              ),
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 110),
              children: [
                _GreetingPanel(
                  name: name,
                  isGuest: session?.isGuest ?? false,
                ),
                const SizedBox(height: 24),
                Text(
                  'Snapshot of your audit health',
                  style: textTheme.titleLarge,
                ),
                const SizedBox(height: 6),
                Text(
                  'Scroll sideways to review your most important fairness signals at a glance.',
                  style: textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  height: 154,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    physics: const BouncingScrollPhysics(),
                    children: [
                      _GlassStatCard(
                        title: 'Audits Run',
                        value: '${summary['auditsRun'] ?? 0}',
                        subtitle: recentAudits.isEmpty
                            ? 'Start with a guest demo or a CSV upload'
                            : '${recentAudits.length} recent audits available',
                        icon: Icons.analytics_outlined,
                        accent: const Color(0xFF7C9DFF),
                      ),
                      const SizedBox(width: 14),
                      _GlassStatCard(
                        title: 'Avg Bias Score',
                        value: '${avgBias.toStringAsFixed(0)}/100',
                        subtitle: _avgTone(avgBias),
                        icon: Icons.auto_graph_rounded,
                        accent: _severityColor(avgBias),
                      ),
                      const SizedBox(width: 14),
                      const _GlassStatCard(
                        title: 'SDG Alignment',
                        value: '3 targets',
                        subtitle: '10.3, 8.5, and 16.b mapped',
                        icon: Icons.verified_rounded,
                        accent: AppColors.unBlue,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 28),
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Recent Audits',
                            style: textTheme.headlineMedium?.copyWith(
                              fontSize: 24,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Open a report to see the risk score, feature drivers, and plain-English guidance.',
                            style: textTheme.bodyMedium?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 12),
                    TextButton.icon(
                      onPressed: _openHistory,
                      icon: const Icon(
                        Icons.arrow_forward_rounded,
                        semanticLabel: 'View full history',
                      ),
                      label: const Text('View all'),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                if (recentAudits.isEmpty)
                  _HomeEmptyState(onPrimaryAction: _openUpload)
                else
                  ...recentAudits.asMap().entries.map(
                        (entry) => Padding(
                          padding: EdgeInsets.only(
                            bottom:
                                entry.key == recentAudits.length - 1 ? 0 : 14,
                          ),
                          child: _AuditPreviewCard(
                            audit: entry.value,
                            formattedDate:
                                _formatDate(entry.value['created_at']),
                            score: _scoreOf(entry.value),
                            severityColor:
                                _severityColor(_scoreOf(entry.value)),
                            severityLabel:
                                _severityLabel(_scoreOf(entry.value)),
                          ),
                        ),
                      ),
                if (isDark) ...[
                  const SizedBox(height: 14),
                  Text(
                    'Tip: Pull down to refresh your dashboard after a new audit completes.',
                    style: textTheme.bodySmall?.copyWith(
                      color: Colors.white.withOpacity(0.72),
                    ),
                  ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

class _GreetingPanel extends StatelessWidget {
  const _GreetingPanel({
    required this.name,
    required this.isGuest,
  });

  final String name;
  final bool isGuest;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isDark
              ? [
                  const Color(0xFF1C2746),
                  const Color(0xFF18213A),
                  const Color(0xFF131B31),
                ]
              : [
                  Colors.white,
                  const Color(0xFFF6F8FF),
                  const Color(0xFFFFF8E1),
                ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(isDark ? 0.26 : 0.08),
            blurRadius: 24,
            offset: const Offset(0, 16),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
                  color: AppColors.accentAmber.withOpacity(0.16),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.waving_hand_rounded,
                      size: 16,
                      color: AppColors.accentAmber,
                      semanticLabel: 'Greeting icon',
                    ),
                    const SizedBox(width: 8),
                    Text(
                      isGuest ? 'Guest mode active' : 'Workspace overview',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: AppColors.accentAmber,
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ],
                ),
              ),
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
                  'SDG 10.3, 8.5, 16.b',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: AppColors.unBlue,
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Text(
            "Hello, $name 👋 Here's your AI audit summary",
            style: theme.textTheme.headlineLarge?.copyWith(
              color: isDark ? Colors.white : AppColors.deepNavy,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Review the latest fairness signals, spot elevated model risk faster, and open any audit report for a plain-language explanation.',
            style: theme.textTheme.bodyLarge?.copyWith(
              color: isDark
                  ? Colors.white.withOpacity(0.78)
                  : AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}

class _GlassStatCard extends StatelessWidget {
  const _GlassStatCard({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.icon,
    required this.accent,
  });

  final String title;
  final String value;
  final String subtitle;
  final IconData icon;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;

    return ConstrainedBox(
      constraints: const BoxConstraints(minWidth: 228, maxWidth: 252),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 260),
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: isDark
                    ? [
                        Colors.white.withOpacity(0.08),
                        Colors.white.withOpacity(0.04),
                      ]
                    : [
                        Colors.white.withOpacity(0.88),
                        const Color(0xFFF5F7FF),
                      ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(
                color: isDark
                    ? Colors.white.withOpacity(0.08)
                    : Colors.white.withOpacity(0.72),
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(isDark ? 0.18 : 0.06),
                  blurRadius: 18,
                  offset: const Offset(0, 12),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: accent.withOpacity(0.14),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  alignment: Alignment.center,
                  child: Icon(
                    icon,
                    color: accent,
                    semanticLabel: title,
                  ),
                ),
                const Spacer(),
                Text(
                  title,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  value,
                  style: theme.textTheme.headlineMedium?.copyWith(
                    color: theme.colorScheme.onSurface,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  subtitle,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall?.copyWith(
                    height: 1.4,
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

class _AuditPreviewCard extends StatelessWidget {
  const _AuditPreviewCard({
    required this.audit,
    required this.formattedDate,
    required this.score,
    required this.severityColor,
    required this.severityLabel,
  });

  final Map<String, dynamic> audit;
  final String formattedDate;
  final double score;
  final Color severityColor;
  final String severityLabel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final String modelName =
        audit['model_name']?.toString() ?? 'Untitled Model';
    final String datasetName = audit['dataset_name']?.toString() ?? '';
    final String auditId =
        audit['audit_id']?.toString() ?? modelName.hashCode.toString();

    return _PressableScaleCard(
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => ReportScreen(initialAudit: audit),
          ),
        );
      },
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              Theme.of(context).cardColor,
              Theme.of(context).cardColor.withOpacity(0.92),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(24),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(
                Theme.of(context).brightness == Brightness.dark ? 0.22 : 0.06,
              ),
              blurRadius: 18,
              offset: const Offset(0, 12),
            ),
          ],
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Hero(
                        tag: 'audit-card-$auditId',
                        child: Material(
                          color: Colors.transparent,
                          child: Text(
                            modelName,
                            style: theme.textTheme.titleLarge?.copyWith(
                              color: theme.colorScheme.onSurface,
                            ),
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: severityColor.withOpacity(0.12),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          '${score.toStringAsFixed(0)}/100',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: severityColor,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    formattedDate,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  if (datasetName.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Text(
                      datasetName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: _BiasSeverityBar(
                          score: score,
                          color: severityColor,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Text(
                        severityLabel,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: severityColor,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 14),
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: severityColor.withOpacity(0.10),
                borderRadius: BorderRadius.circular(16),
              ),
              alignment: Alignment.center,
              child: Icon(
                Icons.chevron_right_rounded,
                color: severityColor,
                semanticLabel: 'Open audit report',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BiasSeverityBar extends StatelessWidget {
  const _BiasSeverityBar({
    required this.score,
    required this.color,
  });

  final double score;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final normalized = (score / 100).clamp(0.0, 1.0);

    return LayoutBuilder(
      builder: (context, constraints) {
        return Container(
          height: 10,
          decoration: BoxDecoration(
            color: Theme.of(context).brightness == Brightness.dark
                ? Colors.white.withOpacity(0.08)
                : const Color(0xFFE6EBF5),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Align(
            alignment: Alignment.centerLeft,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 800),
              curve: Curves.easeOutCubic,
              width: constraints.maxWidth * normalized,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    color.withOpacity(0.78),
                    color,
                  ],
                ),
                borderRadius: BorderRadius.circular(999),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _HomeEmptyState extends StatelessWidget {
  const _HomeEmptyState({
    required this.onPrimaryAction,
  });

  final VoidCallback onPrimaryAction;

  static const String _emptyStateLottieUrl =
      'https://assets1.lottiefiles.com/packages/lf20_qp1q7mct.json';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isDark
              ? [
                  const Color(0xFF1B2542),
                  const Color(0xFF141C32),
                ]
              : [
                  Colors.white,
                  const Color(0xFFF5F8FF),
                ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
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
        children: [
          SizedBox(
            height: 170,
            child: Lottie.network(
              _emptyStateLottieUrl,
              repeat: true,
              fit: BoxFit.contain,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'No audits yet',
            style: theme.textTheme.headlineMedium?.copyWith(fontSize: 24),
          ),
          const SizedBox(height: 10),
          Text(
            'Run your first bias check to see score trends, fairness signals, and a plain-English explanation for non-technical teams.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: onPrimaryAction,
              icon: const Icon(
                Icons.add_task_rounded,
                semanticLabel: 'Start first audit',
              ),
              label: const Text('Run Your First Audit'),
            ),
          ),
        ],
      ),
    );
  }
}

class _HomeSkeleton extends StatelessWidget {
  const _HomeSkeleton();

  @override
  Widget build(BuildContext context) {
    final bool isDark = Theme.of(context).brightness == Brightness.dark;
    final baseColor =
        isDark ? const Color(0xFF202945) : const Color(0xFFE9EDF7);
    final highlightColor =
        isDark ? const Color(0xFF2A3558) : const Color(0xFFF8FAFF);

    return Shimmer.fromColors(
      baseColor: baseColor,
      highlightColor: highlightColor,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 110),
        children: [
          _SkeletonBox(
            height: 188,
            borderRadius: BorderRadius.circular(28),
          ),
          const SizedBox(height: 24),
          const _SkeletonLine(widthFactor: 0.48),
          const SizedBox(height: 10),
          const _SkeletonLine(widthFactor: 0.82),
          const SizedBox(height: 16),
          SizedBox(
            height: 154,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: 3,
              separatorBuilder: (_, __) => const SizedBox(width: 14),
              itemBuilder: (_, __) => const _SkeletonBox(
                width: 238,
                height: 154,
                borderRadius: BorderRadius.all(Radius.circular(24)),
              ),
            ),
          ),
          const SizedBox(height: 28),
          const _SkeletonLine(widthFactor: 0.42),
          const SizedBox(height: 18),
          const _SkeletonBox(
            height: 148,
            borderRadius: BorderRadius.all(Radius.circular(24)),
          ),
          const SizedBox(height: 14),
          const _SkeletonBox(
            height: 148,
            borderRadius: BorderRadius.all(Radius.circular(24)),
          ),
        ],
      ),
    );
  }
}

class _SkeletonLine extends StatelessWidget {
  const _SkeletonLine({
    required this.widthFactor,
  });

  final double widthFactor;

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      widthFactor: widthFactor,
      child: const _SkeletonBox(
        height: 18,
        borderRadius: BorderRadius.all(Radius.circular(999)),
      ),
    );
  }
}

class _SkeletonBox extends StatelessWidget {
  const _SkeletonBox({
    this.width,
    this.height = 16,
    this.borderRadius = const BorderRadius.all(Radius.circular(16)),
  });

  final double? width;
  final double height;
  final BorderRadius borderRadius;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: borderRadius,
      ),
    );
  }
}

class _TopActionButton extends StatelessWidget {
  const _TopActionButton({
    required this.label,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final bool isDark = Theme.of(context).brightness == Brightness.dark;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Ink(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: isDark
                ? Colors.white.withOpacity(0.06)
                : Colors.white.withOpacity(0.94),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isDark
                  ? Colors.white.withOpacity(0.08)
                  : const Color(0xFFD9E1EF),
            ),
          ),
          child: Tooltip(
            message: label,
            child: Icon(
              icon,
              semanticLabel: label,
            ),
          ),
        ),
      ),
    );
  }
}

class _PressableScaleCard extends StatefulWidget {
  const _PressableScaleCard({
    required this.child,
    required this.onTap,
  });

  final Widget child;
  final VoidCallback onTap;

  @override
  State<_PressableScaleCard> createState() => _PressableScaleCardState();
}

class _PressableScaleCardState extends State<_PressableScaleCard> {
  bool _pressed = false;

  void _setPressed(bool value) {
    if (_pressed == value) return;
    setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedScale(
      scale: _pressed ? 0.97 : 1,
      duration: const Duration(milliseconds: 140),
      curve: Curves.easeOut,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: widget.onTap,
          borderRadius: BorderRadius.circular(24),
          onHighlightChanged: _setPressed,
          child: widget.child,
        ),
      ),
    );
  }
}
