import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:unbiased_ai_decision/widgets/bias_gauge.dart';
import 'package:unbiased_ai_decision/widgets/gemini_card.dart';
import 'package:unbiased_ai_decision/widgets/sdg_badge.dart';

Widget _wrap(Widget child) {
  return MaterialApp(
    home: Scaffold(
      body: child,
    ),
  );
}

void main() {
  testWidgets('GeminiCard renders header content', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const GeminiCard(explanation: 'Bias explanation for the audit.'),
      ),
    );

    expect(find.text('AI Fairness Insight'), findsOneWidget);
  });

  testWidgets('GeminiCard renders explanation text after typing animation', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const GeminiCard(explanation: 'Bias explanation for the audit.'),
      ),
    );

    await tester.pump(const Duration(seconds: 5));
    expect(find.text('Bias explanation for the audit.'), findsOneWidget);
  });

  testWidgets('GeminiCard shows generating status while typing', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const GeminiCard(explanation: 'Streaming text for a fairness summary.'),
      ),
    );

    expect(find.text('Generating explanation...'), findsOneWidget);
  });

  testWidgets('SdgBadge compact renders SDG 10.3 label', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const SdgBadge(compact: true),
      ),
    );

    expect(find.text('SDG 10.3'), findsOneWidget);
  });

  testWidgets('SdgBadge full renders the three default SDG rows', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const SdgBadge(),
      ),
    );

    expect(find.textContaining('SDG 10.3', findRichText: true), findsOneWidget);
    expect(find.textContaining('SDG 8.5', findRichText: true), findsOneWidget);
    expect(find.textContaining('SDG 16.b', findRichText: true), findsOneWidget);
  });

  testWidgets('BiasGauge renders with a score value and risk label', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const BiasGauge(score: 72),
      ),
    );

    await tester.pump(const Duration(milliseconds: 1400));
    expect(find.text('72'), findsOneWidget);
    expect(find.text('High Risk'), findsOneWidget);
    expect(find.text('Fairness Score'), findsOneWidget);
  });
}
