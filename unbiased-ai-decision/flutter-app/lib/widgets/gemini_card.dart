import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'sdg_badge.dart';

class GeminiCard extends StatefulWidget {
  const GeminiCard({
    super.key,
    required this.explanation,
  });

  final String explanation;

  @override
  State<GeminiCard> createState() => _GeminiCardState();
}

class _GeminiCardState extends State<GeminiCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _typingController;
  bool _expanded = false;

  @override
  void initState() {
    super.initState();
    _typingController = AnimationController(
      vsync: this,
      duration: Duration(
        milliseconds:
            ((widget.explanation.length * 22).clamp(1000, 4200)).toInt(),
      ),
    )..forward();
  }

  @override
  void didUpdateWidget(covariant GeminiCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.explanation != widget.explanation) {
      _typingController.duration = Duration(
        milliseconds:
            ((widget.explanation.length * 22).clamp(1000, 4200)).toInt(),
      );
      _typingController
        ..reset()
        ..forward();
    }
  }

  @override
  void dispose() {
    _typingController.dispose();
    super.dispose();
  }

  String _visibleText() {
    final count =
        (widget.explanation.length * _typingController.value).floor().clamp(
              0,
              widget.explanation.length,
            );
    return widget.explanation.substring(0, count);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;

    return AnimatedBuilder(
      animation: _typingController,
      builder: (context, _) {
        return Container(
          width: double.infinity,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: isDark
                  ? [
                      const Color(0xFF202944),
                      const Color(0xFF171F36),
                    ]
                  : [
                      Colors.white,
                      const Color(0xFFFFFCF0),
                    ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(26),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(isDark ? 0.20 : 0.06),
                blurRadius: 20,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 16,
                ),
                decoration: BoxDecoration(
                  gradient: AppGradients.accent,
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(26),
                  ),
                ),
                child: Row(
                  children: [
                    const Icon(
                      Icons.auto_awesome_rounded,
                      color: AppColors.deepNavy,
                      semanticLabel: 'AI fairness insight',
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'AI Fairness Insight',
                        style: theme.textTheme.titleMedium?.copyWith(
                          color: AppColors.deepNavy,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _visibleText(),
                      style: theme.textTheme.bodyLarge?.copyWith(
                        color: theme.colorScheme.onSurface,
                        height: 1.7,
                      ),
                    ),
                    if (_typingController.value < 1) ...[
                      const SizedBox(height: 6),
                      Text(
                        'Generating explanation...',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    const SizedBox(height: 18),
                    Material(
                      color: Colors.transparent,
                      child: InkWell(
                        onTap: () => setState(() => _expanded = !_expanded),
                        borderRadius: BorderRadius.circular(18),
                        child: Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: isDark
                                ? Colors.white.withOpacity(0.05)
                                : const Color(0xFFF8FAFF),
                            borderRadius: BorderRadius.circular(18),
                            border: Border.all(
                              color: isDark
                                  ? Colors.white.withOpacity(0.08)
                                  : const Color(0xFFE4EAF6),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      'What does this mean?',
                                      style:
                                          theme.textTheme.titleMedium?.copyWith(
                                        color: theme.colorScheme.onSurface,
                                      ),
                                    ),
                                  ),
                                  AnimatedRotation(
                                    turns: _expanded ? 0.5 : 0,
                                    duration: const Duration(milliseconds: 220),
                                    child: Icon(
                                      Icons.keyboard_arrow_down_rounded,
                                      color: theme.colorScheme.onSurfaceVariant,
                                      semanticLabel:
                                          'Expand plain English explanation',
                                    ),
                                  ),
                                ],
                              ),
                              AnimatedSize(
                                duration: const Duration(milliseconds: 220),
                                curve: Curves.easeOutCubic,
                                child: _expanded
                                    ? Padding(
                                        padding: const EdgeInsets.only(top: 12),
                                        child: Text(
                                          'This section translates the audit into everyday language: what may be disadvantaging people, why that matters in the real world, and the first fix an organization should make before trusting the model again.',
                                          style: theme.textTheme.bodyMedium
                                              ?.copyWith(
                                            color: theme
                                                .colorScheme.onSurfaceVariant,
                                            height: 1.6,
                                          ),
                                        ),
                                      )
                                    : const SizedBox.shrink(),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    const SdgBadge(compact: true),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
