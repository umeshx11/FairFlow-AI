import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../theme/app_theme.dart';

class SdgBadge extends StatelessWidget {
  const SdgBadge({
    super.key,
    this.compact = false,
    this.mapping = const [],
  });

  final bool compact;
  final List<Map<String, dynamic>> mapping;

  static const _sdgUrl = 'https://sdgs.un.org/goals/goal10';

  Future<void> _open() async {
    await launchUrl(Uri.parse(_sdgUrl));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (compact) {
      return Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            _open();
          },
          borderRadius: BorderRadius.circular(999),
          child: Ink(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: AppColors.unBlue.withOpacity(0.12),
              borderRadius: BorderRadius.circular(999),
              border: Border.all(
                color: AppColors.unBlue.withOpacity(0.24),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.sync_rounded,
                  size: 16,
                  color: AppColors.unBlue,
                  semanticLabel: 'SDG badge',
                ),
                const SizedBox(width: 8),
                Text(
                  mapping.isEmpty ? 'SDG 10.3' : 'SDG 10.3 / 8.5 / 16.b',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: AppColors.unBlue,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final List<Map<String, dynamic>> rows = mapping.isEmpty
        ? const <Map<String, dynamic>>[
            {
              'target': 'SDG 10.3',
              'title':
                  'Ensure equal opportunity and reduce inequalities of outcome.',
              'status': 'tracked',
            },
            {
              'target': 'SDG 8.5',
              'title': 'Support equal access to productive employment.',
              'status': 'tracked',
            },
            {
              'target': 'SDG 16.b',
              'title': 'Support non-discriminatory policies and procedures.',
              'status': 'tracked',
            },
          ]
        : mapping;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () {
          _open();
        },
        borderRadius: BorderRadius.circular(24),
        child: Ink(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: AppColors.unBlue,
            borderRadius: BorderRadius.circular(24),
            boxShadow: [
              BoxShadow(
                color: AppColors.unBlue.withOpacity(0.24),
                blurRadius: 18,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(18),
                ),
                alignment: Alignment.center,
                child: const Icon(
                  Icons.sync_rounded,
                  color: Colors.white,
                  semanticLabel: 'SDG target mapping',
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'SDG Targets Live in This Audit',
                      style: theme.textTheme.titleLarge?.copyWith(
                        color: Colors.white,
                        fontSize: 18,
                      ),
                    ),
                    for (final item in rows) ...[
                      const SizedBox(height: 8),
                      _SdgTargetRow(item: item),
                    ],
                    const SizedBox(height: 12),
                    Text(
                      'Learn More',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SdgTargetRow extends StatelessWidget {
  const _SdgTargetRow({
    required this.item,
  });

  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final status = item['status']?.toString() ?? 'tracked';
    final aligned = status == 'aligned';
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          aligned ? Icons.check_circle_rounded : Icons.error_outline_rounded,
          size: 16,
          color: aligned ? Colors.white : const Color(0xFFFFE08A),
          semanticLabel: status,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: RichText(
            text: TextSpan(
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.white.withOpacity(0.94),
                    height: 1.4,
                  ),
              children: [
                TextSpan(
                  text: '${item['target'] ?? 'SDG'}: ',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                TextSpan(text: item['title']?.toString() ?? ''),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
