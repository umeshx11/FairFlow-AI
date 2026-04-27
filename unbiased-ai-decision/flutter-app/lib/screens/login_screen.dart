import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/auth_service.dart';
import '../theme/app_theme.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with TickerProviderStateMixin {
  bool _loadingGoogle = false;
  bool _loadingGuest = false;

  late final AnimationController _entryController;
  late final AnimationController _backdropController;
  late final Animation<double> _cardOpacity;
  late final Animation<Offset> _cardOffset;

  @override
  void initState() {
    super.initState();
    _entryController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 850),
    );
    _backdropController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 9000),
    )..repeat();

    _cardOpacity = CurvedAnimation(
      parent: _entryController,
      curve: Curves.easeOut,
    );
    _cardOffset = Tween<Offset>(
      begin: const Offset(0, 0.05),
      end: Offset.zero,
    ).animate(
      CurvedAnimation(
        parent: _entryController,
        curve: Curves.easeOutCubic,
      ),
    );

    _entryController.forward();
  }

  @override
  void dispose() {
    _entryController.dispose();
    _backdropController.dispose();
    super.dispose();
  }

  Future<void> _signInWithGoogle() async {
    setState(() => _loadingGoogle = true);
    try {
      await AuthService.instance.signInWithGoogle();
    } catch (error) {
      _showError(error);
    } finally {
      if (mounted) {
        setState(() => _loadingGoogle = false);
      }
    }
  }

  Future<void> _signInAsGuest() async {
    setState(() => _loadingGuest = true);
    try {
      await AuthService.instance.signInAsGuest();
    } catch (error) {
      _showError(error);
    } finally {
      if (mounted) {
        setState(() => _loadingGuest = false);
      }
    }
  }

  Future<void> _openSdgLink() async {
    final uri = Uri.parse('https://sdgs.un.org/goals/goal10');
    if (!await launchUrl(uri) && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Could not open the SDG 10 page right now.'),
        ),
      );
    }
  }

  void _showError(Object error) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          error.toString().replaceFirst('Exception: ', ''),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final bool isDark = theme.brightness == Brightness.dark;
    final bool googleAvailable = AuthService.instance.googleSignInAvailable;

    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [
              AppColors.deepNavy,
              Color(0xFF223158),
              Color(0xFF374B7A),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Stack(
          children: [
            Positioned.fill(
              child: IgnorePointer(
                child: AnimatedBuilder(
                  animation: _backdropController,
                  builder: (context, child) {
                    return CustomPaint(
                      painter: _LoginBackdropPainter(
                        progress: _backdropController.value,
                        isDark: isDark,
                      ),
                    );
                  },
                ),
              ),
            ),
            Positioned.fill(
              child: IgnorePointer(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        Colors.white.withOpacity(0.03),
                        Colors.transparent,
                        AppColors.accentAmber.withOpacity(0.06),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                ),
              ),
            ),
            SafeArea(
              child: Center(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 28,
                  ),
                  child: FadeTransition(
                    opacity: _cardOpacity,
                    child: SlideTransition(
                      position: _cardOffset,
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 500),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(32),
                          child: BackdropFilter(
                            filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
                            child: Container(
                              padding: const EdgeInsets.fromLTRB(
                                28,
                                32,
                                28,
                                24,
                              ),
                              decoration: BoxDecoration(
                                gradient: isDark
                                    ? AppGradients.darkGlass
                                    : LinearGradient(
                                        colors: [
                                          Colors.white.withOpacity(0.90),
                                          const Color(0xFFF8FAFF)
                                              .withOpacity(0.88),
                                        ],
                                        begin: Alignment.topLeft,
                                        end: Alignment.bottomRight,
                                      ),
                                borderRadius: BorderRadius.circular(32),
                                border: Border.all(
                                  color: Colors.white.withOpacity(0.18),
                                ),
                                boxShadow: [
                                  BoxShadow(
                                    color: Colors.black.withOpacity(0.16),
                                    blurRadius: 28,
                                    offset: const Offset(0, 16),
                                  ),
                                ],
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  Hero(
                                    tag: 'app-logo',
                                    child: Container(
                                      width: 84,
                                      height: 84,
                                      decoration: BoxDecoration(
                                        gradient: AppGradients.accent,
                                        shape: BoxShape.circle,
                                        boxShadow: [
                                          BoxShadow(
                                            color: AppColors.accentAmber
                                                .withOpacity(0.28),
                                            blurRadius: 24,
                                            offset: const Offset(0, 10),
                                          ),
                                        ],
                                      ),
                                      alignment: Alignment.center,
                                      child: Semantics(
                                        label:
                                            'Unbiased AI Decision logo showing a fairness shield',
                                        child: Icon(
                                          Icons.gpp_good_rounded,
                                          size: 40,
                                          color: AppColors.deepNavy,
                                        ),
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 24),
                                  Text(
                                    'Fair AI for everyone',
                                    style: textTheme.bodyMedium?.copyWith(
                                      color: AppColors.accentAmber,
                                      fontWeight: FontWeight.w700,
                                      letterSpacing: 0.3,
                                    ),
                                  ),
                                  const SizedBox(height: 10),
                                  Text(
                                    'Unbiased AI Decision',
                                    style: textTheme.headlineLarge?.copyWith(
                                      color: isDark
                                          ? Colors.white
                                          : AppColors.deepNavy,
                                    ),
                                  ),
                                  const SizedBox(height: 14),
                                  Text(
                                    'Check hiring, lending, and care decisions for hidden bias with clear explanations your whole team can understand.',
                                    style: textTheme.bodyLarge?.copyWith(
                                      color: isDark
                                          ? Colors.white.withOpacity(0.78)
                                          : AppColors.textSecondary,
                                    ),
                                  ),
                                  const SizedBox(height: 28),
                                  _GoogleSignInButton(
                                    loading: _loadingGoogle,
                                    onPressed: !googleAvailable ||
                                            _loadingGoogle ||
                                            _loadingGuest
                                        ? null
                                        : _signInWithGoogle,
                                  ),
                                  if (!googleAvailable) ...[
                                    const SizedBox(height: 10),
                                    Text(
                                      'Local demo mode is active. Add real Firebase web keys to enable Google sign-in.',
                                      style: textTheme.bodySmall?.copyWith(
                                        color: isDark
                                            ? Colors.white.withOpacity(0.72)
                                            : AppColors.textSecondary,
                                      ),
                                    ),
                                  ],
                                  const SizedBox(height: 18),
                                  Row(
                                    children: [
                                      Expanded(
                                        child: Divider(
                                          color: isDark
                                              ? Colors.white.withOpacity(0.12)
                                              : const Color(0xFFD6DEEB),
                                        ),
                                      ),
                                      Padding(
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 14,
                                        ),
                                        child: Text(
                                          'or',
                                          style: textTheme.bodyMedium?.copyWith(
                                            color: isDark
                                                ? Colors.white.withOpacity(0.70)
                                                : AppColors.textSecondary,
                                          ),
                                        ),
                                      ),
                                      Expanded(
                                        child: Divider(
                                          color: isDark
                                              ? Colors.white.withOpacity(0.12)
                                              : const Color(0xFFD6DEEB),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 18),
                                  OutlinedButton.icon(
                                    onPressed: _loadingGuest || _loadingGoogle
                                        ? null
                                        : _signInAsGuest,
                                    icon: _loadingGuest
                                        ? SizedBox(
                                            width: 20,
                                            height: 20,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2.4,
                                              color: isDark
                                                  ? Colors.white
                                                  : AppColors.deepNavy,
                                            ),
                                          )
                                        : Semantics(
                                            label: 'Continue as guest',
                                            child: Icon(
                                              Icons.person_outline_rounded,
                                            ),
                                          ),
                                    label: const Text(
                                      'Try as Guest — no sign-up needed',
                                    ),
                                    style: OutlinedButton.styleFrom(
                                      minimumSize: const Size.fromHeight(56),
                                      side: BorderSide(
                                        color: AppColors.accentAmber
                                            .withOpacity(0.85),
                                        width: 1.4,
                                      ),
                                      foregroundColor: isDark
                                          ? Colors.white
                                          : AppColors.deepNavy,
                                      backgroundColor: isDark
                                          ? Colors.white.withOpacity(0.04)
                                          : Colors.white.withOpacity(0.54),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(18),
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 14,
                                      vertical: 12,
                                    ),
                                    decoration: BoxDecoration(
                                      color: isDark
                                          ? Colors.white.withOpacity(0.05)
                                          : const Color(0xFFFFFBEB),
                                      borderRadius: BorderRadius.circular(16),
                                      border: Border.all(
                                        color: isDark
                                            ? Colors.white.withOpacity(0.08)
                                            : const Color(0xFFFFE08A),
                                      ),
                                    ),
                                    child: Row(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        const Padding(
                                          padding: EdgeInsets.only(top: 1.5),
                                          child: Icon(
                                            Icons.verified_user_outlined,
                                            size: 18,
                                            color: AppColors.accentAmber,
                                            semanticLabel:
                                                'Trust statement icon',
                                          ),
                                        ),
                                        const SizedBox(width: 10),
                                        Expanded(
                                          child: Text(
                                            'Firebase guest demo. No sign-up needed.',
                                            style:
                                                textTheme.bodyMedium?.copyWith(
                                              color: isDark
                                                  ? Colors.white
                                                      .withOpacity(0.82)
                                                  : AppColors.textPrimary,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  const SizedBox(height: 22),
                                  Center(
                                    child: Tooltip(
                                      message:
                                          'SDG 10 supports reducing inequalities of outcome and improving equal opportunity.',
                                      waitDuration:
                                          const Duration(milliseconds: 300),
                                      child: Material(
                                        color: Colors.transparent,
                                        child: InkWell(
                                          borderRadius:
                                              BorderRadius.circular(999),
                                          onTap: () {
                                            _openSdgLink();
                                          },
                                          child: Ink(
                                            padding: const EdgeInsets.symmetric(
                                              horizontal: 14,
                                              vertical: 10,
                                            ),
                                            decoration: BoxDecoration(
                                              color:
                                                  AppColors.unBlue.withOpacity(
                                                isDark ? 0.24 : 0.12,
                                              ),
                                              borderRadius:
                                                  BorderRadius.circular(999),
                                              border: Border.all(
                                                color: AppColors.unBlue
                                                    .withOpacity(0.38),
                                              ),
                                            ),
                                            child: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                const Icon(
                                                  Icons.public_rounded,
                                                  size: 16,
                                                  color: AppColors.unBlue,
                                                  semanticLabel: 'SDG 10 badge',
                                                ),
                                                const SizedBox(width: 8),
                                                Text(
                                                  'SDG 10 — Reduced Inequalities',
                                                  style: textTheme.bodyMedium
                                                      ?.copyWith(
                                                    color: isDark
                                                        ? Colors.white
                                                        : AppColors.unBlue,
                                                    fontWeight: FontWeight.w700,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GoogleSignInButton extends StatelessWidget {
  const _GoogleSignInButton({
    required this.loading,
    required this.onPressed,
  });

  final bool loading;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bool isDark = theme.brightness == Brightness.dark;

    return SizedBox(
      height: 56,
      child: ElevatedButton(
        onPressed: onPressed,
        style: ElevatedButton.styleFrom(
          elevation: 2,
          backgroundColor: Colors.white,
          foregroundColor: AppColors.deepNavy,
          disabledBackgroundColor: Colors.white.withOpacity(0.88),
          padding: const EdgeInsets.symmetric(horizontal: 18),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
            side: BorderSide(
              color: isDark
                  ? const Color(0xFFD7DEED).withOpacity(0.12)
                  : const Color(0xFFD8DEE9),
            ),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const _GoogleMark(),
            const SizedBox(width: 14),
            Flexible(
              child: Text(
                loading ? 'Connecting to Google...' : 'Sign in with Google',
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.labelLarge?.copyWith(
                  color: AppColors.deepNavy,
                ),
              ),
            ),
            if (loading) ...[
              const SizedBox(width: 12),
              const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2.2,
                  color: AppColors.deepNavy,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _GoogleMark extends StatelessWidget {
  const _GoogleMark();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: const Size(22, 22),
      painter: _GoogleMarkPainter(),
    );
  }
}

class _GoogleMarkPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final stroke = size.width * 0.18;
    final rect = Rect.fromCircle(center: center, radius: size.width / 2.5);

    final blue = Paint()
      ..color = const Color(0xFF4285F4)
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;
    final red = Paint()
      ..color = const Color(0xFFEA4335)
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;
    final yellow = Paint()
      ..color = const Color(0xFFFBBC05)
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;
    final green = Paint()
      ..color = const Color(0xFF34A853)
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;

    canvas.drawArc(rect, -0.15, 1.1, false, blue);
    canvas.drawArc(rect, 1.05, 1.15, false, red);
    canvas.drawArc(rect, 2.22, 0.95, false, yellow);
    canvas.drawArc(rect, 3.10, 1.12, false, green);

    final bar = Paint()
      ..color = const Color(0xFF4285F4)
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round;

    canvas.drawLine(
      Offset(size.width * 0.54, size.height * 0.53),
      Offset(size.width * 0.90, size.height * 0.53),
      bar,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _LoginBackdropPainter extends CustomPainter {
  _LoginBackdropPainter({
    required this.progress,
    required this.isDark,
  });

  final double progress;
  final bool isDark;

  @override
  void paint(Canvas canvas, Size size) {
    final waveOne = Paint()
      ..color = Colors.white.withOpacity(isDark ? 0.05 : 0.08)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;
    final waveTwo = Paint()
      ..color = AppColors.accentAmber.withOpacity(0.14)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;

    final pathOne = Path();
    final pathTwo = Path();

    for (double x = 0; x <= size.width; x += 6) {
      final y1 = size.height * 0.22 +
          math.sin((x / size.width * 2.8 * math.pi) + progress * 2 * math.pi) *
              18;
      final y2 = size.height * 0.78 +
          math.sin((x / size.width * 3.2 * math.pi) - progress * 2 * math.pi) *
              20;

      if (x == 0) {
        pathOne.moveTo(x, y1);
        pathTwo.moveTo(x, y2);
      } else {
        pathOne.lineTo(x, y1);
        pathTwo.lineTo(x, y2);
      }
    }

    canvas.drawPath(pathOne, waveOne);
    canvas.drawPath(pathTwo, waveTwo);

    final particlePaint = Paint()..style = PaintingStyle.fill;
    final particles = <_Particle>[
      _Particle(0.12, 0.18, 2.4, Colors.white.withOpacity(0.15)),
      _Particle(0.22, 0.68, 3.1, Colors.white.withOpacity(0.10)),
      _Particle(0.74, 0.26, 2.6, AppColors.accentAmber.withOpacity(0.18)),
      _Particle(0.86, 0.64, 4.0, Colors.white.withOpacity(0.08)),
      _Particle(0.58, 0.12, 2.2, AppColors.accentAmber.withOpacity(0.14)),
      _Particle(0.40, 0.84, 3.4, Colors.white.withOpacity(0.10)),
    ];

    for (final particle in particles) {
      final dx = (particle.x * size.width) +
          math.sin((progress * 2 * math.pi) + particle.x * 6) * 10;
      final dy = (particle.y * size.height) +
          math.cos((progress * 2 * math.pi) + particle.y * 5) * 12;
      particlePaint.color = particle.color;
      canvas.drawCircle(Offset(dx, dy), particle.radius, particlePaint);
    }
  }

  @override
  bool shouldRepaint(covariant _LoginBackdropPainter oldDelegate) {
    return oldDelegate.progress != progress || oldDelegate.isDark != isDark;
  }
}

class _Particle {
  const _Particle(this.x, this.y, this.radius, this.color);

  final double x;
  final double y;
  final double radius;
  final Color color;
}
