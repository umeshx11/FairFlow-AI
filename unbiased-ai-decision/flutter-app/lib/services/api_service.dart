import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:http/http.dart' as http;

class ApiService {
  ApiService._();

  static final ApiService instance = ApiService._();

  final String baseUrl = const String.fromEnvironment(
    'FLUTTER_API_BASE_URL',
    defaultValue: 'http://localhost:8080',
  );

  Future<Map<String, dynamic>> fetchHealth() async {
    final response = await http.get(Uri.parse('$baseUrl/health'));
    if (response.statusCode >= 400) {
      throw Exception('Health check failed: ${response.body}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> runAudit({
    required PlatformFile datasetFile,
    PlatformFile? modelFile,
    required String modelName,
    required String userId,
    required String domain,
    String? auditId,
  }) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/audit'),
    )
      ..fields['model_name'] = modelName
      ..fields['user_id'] = userId
      ..fields['domain'] = domain;
    if (auditId != null) {
      request.fields['audit_id'] = auditId;
    }

    request.files.add(await _buildFile('dataset_file', datasetFile));
    if (modelFile != null) {
      request.files.add(await _buildFile('model_file', modelFile));
    }

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);
    if (response.statusCode >= 400) {
      throw Exception(response.body);
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchAudit(String auditId) async {
    final response = await http.get(Uri.parse('$baseUrl/audit/$auditId'));
    if (response.statusCode >= 400) {
      throw Exception(response.body);
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> fetchAuditHistory(String userId) async {
    final response = await http.get(Uri.parse('$baseUrl/audit/history/$userId'));
    if (response.statusCode >= 400) {
      throw Exception(response.body);
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw Exception('Unexpected audit history response.');
    }

    return decoded
        .whereType<Map>()
        .map((item) => item.cast<String, dynamic>())
        .toList(growable: false);
  }

  Future<http.MultipartFile> _buildFile(String fieldName, PlatformFile file) async {
    if (file.bytes != null) {
      return http.MultipartFile.fromBytes(
        fieldName,
        file.bytes!,
        filename: file.name,
      );
    }
    if (file.path != null) {
      return http.MultipartFile.fromPath(fieldName, file.path!);
    }
    throw Exception('No bytes or path available for ${file.name}.');
  }
}
