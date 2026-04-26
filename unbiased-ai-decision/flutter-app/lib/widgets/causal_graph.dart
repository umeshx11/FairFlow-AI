import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class CausalGraph extends StatelessWidget {
  const CausalGraph({
    super.key,
    required this.graph,
  });

  final Map<String, dynamic> graph;

  List<Map<String, dynamic>> get _nodes {
    final raw = graph['nodes'];
    if (raw is! List) {
      return <Map<String, dynamic>>[];
    }
    return raw
        .whereType<Map>()
        .map((item) => item.cast<String, dynamic>())
        .toList();
  }

  List<Map<String, dynamic>> get _edges {
    final raw = graph['edges'];
    if (raw is! List) {
      return <Map<String, dynamic>>[];
    }
    return raw
        .whereType<Map>()
        .map((item) => item.cast<String, dynamic>())
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    if (_nodes.isEmpty) {
      return const SizedBox(
        height: 180,
        child: Center(
            child: Text('No causal graph was generated for this audit.')),
      );
    }

    return AspectRatio(
      aspectRatio: 1.45,
      child: CustomPaint(
        painter: _CausalGraphPainter(
          nodes: _nodes,
          edges: _edges,
          textColor: Theme.of(context).colorScheme.onSurface,
          accentColor: AppColors.unBlue,
          dangerColor: AppColors.danger,
        ),
      ),
    );
  }
}

class _CausalGraphPainter extends CustomPainter {
  _CausalGraphPainter({
    required this.nodes,
    required this.edges,
    required this.textColor,
    required this.accentColor,
    required this.dangerColor,
  });

  final List<Map<String, dynamic>> nodes;
  final List<Map<String, dynamic>> edges;
  final Color textColor;
  final Color accentColor;
  final Color dangerColor;

  @override
  void paint(Canvas canvas, Size size) {
    final positions = _nodePositions(size);
    final edgePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    for (final edge in edges) {
      final source = edge['source']?.toString();
      final target = edge['target']?.toString();
      final start = positions[source];
      final end = positions[target];
      if (start == null || end == null) {
        continue;
      }

      final weight = (edge['weight'] as num?)?.toDouble() ?? 0.1;
      final normalizedWeight = weight.clamp(0.0, 1.0).toDouble();
      edgePaint
        ..color = Color.lerp(accentColor, dangerColor, normalizedWeight)!
            .withOpacity(0.76)
        ..strokeWidth = 1.6 + (normalizedWeight * 3);
      canvas.drawLine(start, end, edgePaint);
      _drawArrow(canvas, start, end, edgePaint.color);
    }

    for (final node in nodes) {
      final id = node['id']?.toString() ?? '';
      final position = positions[id];
      if (position == null) {
        continue;
      }
      _drawNode(canvas, position, id);
    }
  }

  Map<String, Offset> _nodePositions(Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) * 0.34;
    final result = <String, Offset>{};
    for (var index = 0; index < nodes.length; index++) {
      final id = nodes[index]['id']?.toString() ?? 'node-$index';
      final angle = -math.pi / 2 + (2 * math.pi * index / nodes.length);
      result[id] = Offset(
        center.dx + math.cos(angle) * radius,
        center.dy + math.sin(angle) * radius,
      );
    }
    return result;
  }

  void _drawArrow(Canvas canvas, Offset start, Offset end, Color color) {
    final direction = end - start;
    final angle = math.atan2(direction.dy, direction.dx);
    final tip = Offset(
      end.dx - math.cos(angle) * 32,
      end.dy - math.sin(angle) * 32,
    );
    final path = Path()
      ..moveTo(tip.dx, tip.dy)
      ..lineTo(
        tip.dx - math.cos(angle - math.pi / 7) * 9,
        tip.dy - math.sin(angle - math.pi / 7) * 9,
      )
      ..moveTo(tip.dx, tip.dy)
      ..lineTo(
        tip.dx - math.cos(angle + math.pi / 7) * 9,
        tip.dy - math.sin(angle + math.pi / 7) * 9,
      );
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round,
    );
  }

  void _drawNode(Canvas canvas, Offset center, String label) {
    final rect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: center, width: 110, height: 46),
      const Radius.circular(16),
    );
    canvas.drawRRect(
      rect,
      Paint()
        ..color = Colors.white
        ..style = PaintingStyle.fill,
    );
    canvas.drawRRect(
      rect,
      Paint()
        ..color = accentColor.withOpacity(0.32)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.4,
    );

    final textPainter = TextPainter(
      text: TextSpan(
        text: label.replaceAll('_', ' '),
        style: TextStyle(
          color: textColor,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
      maxLines: 2,
      ellipsis: '...',
      textAlign: TextAlign.center,
      textDirection: TextDirection.ltr,
    )..layout(maxWidth: 88);
    textPainter.paint(
      canvas,
      Offset(center.dx - textPainter.width / 2,
          center.dy - textPainter.height / 2),
    );
  }

  @override
  bool shouldRepaint(covariant _CausalGraphPainter oldDelegate) {
    return oldDelegate.nodes != nodes || oldDelegate.edges != edges;
  }
}
