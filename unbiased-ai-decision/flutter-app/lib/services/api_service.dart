import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:http/http.dart' as http;

class ApiService {
  ApiService._();

  static final ApiService instance = ApiService._();

  final String baseUrl = const String.fromEnvironment(
    'FLUTTER_API_BASE_URL',
    defaultValue: 'https://fairflow-ai-1056539416381.asia-south1.run.app',
  );

  Future<Map<String, dynamic>> fetchHealth() async {
    final response = await http.get(Uri.parse('$baseUrl/health'));
    return _decodeMapResponse(response, fallbackError: 'Health check failed.');
  }

  Future<List<Map<String, dynamic>>> fetchDomainTemplates() async {
    final response = await http.get(Uri.parse('$baseUrl/domain/templates'));
    final decoded = _decodeMapResponse(
      response,
      fallbackError: 'Could not load audit templates.',
    );
    final rawTemplates = decoded['templates'];
    if (rawTemplates is! List) {
      return const <Map<String, dynamic>>[];
    }
    return rawTemplates
        .whereType<Map>()
        .map((item) => item.cast<String, dynamic>())
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> runAudit({
    required PlatformFile datasetFile,
    PlatformFile? modelFile,
    required String modelName,
    required String userId,
    required String domain,
    Map<String, dynamic>? domainConfig,
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
    if (domainConfig != null) {
      request.fields['domain_config'] = jsonEncode(domainConfig);
    }

    request.files.add(await _buildFile('dataset_file', datasetFile));
    if (modelFile != null) {
      request.files.add(await _buildFile('model_file', modelFile));
    }

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);
    return _decodeMapResponse(
      response,
      fallbackError: 'Audit upload failed.',
    );
  }

  Future<Map<String, dynamic>> fetchAudit(String auditId) async {
    final response = await http.get(Uri.parse('$baseUrl/audit/$auditId'));
    return _decodeMapResponse(
      response,
      fallbackError: 'Could not load audit.',
    );
  }

  Future<List<Map<String, dynamic>>> fetchAuditHistory(String userId) async {
    final response =
        await http.get(Uri.parse('$baseUrl/audit/history/$userId'));
    return _decodeListResponse(
      response,
      fallbackError: 'Could not load audit history.',
    );
  }

  Future<Map<String, dynamic>> fetchCandidates(
    String auditId, {
    int page = 1,
    int pageSize = 20,
    String search = '',
    String biasStatus = 'all',
  }) async {
    final uri = Uri.parse('$baseUrl/candidates/$auditId').replace(
      queryParameters: {
        'page': '$page',
        'page_size': '$pageSize',
        'search': search,
        'bias_status': biasStatus,
      },
    );
    final response = await http.get(uri);
    return _decodeMapResponse(
      response,
      fallbackError: 'Could not load candidate records.',
    );
  }

  Future<Map<String, dynamic>> fetchCandidateDetail(
    String auditId,
    String candidateId,
  ) async {
    final response = await http.get(
      Uri.parse('$baseUrl/candidates/$auditId/$candidateId'),
    );
    return _decodeMapResponse(
      response,
      fallbackError: 'Could not load the selected record.',
    );
  }

  Future<Map<String, dynamic>> runMitigation(String auditId) async {
    final response = await http.post(Uri.parse('$baseUrl/mitigate/$auditId'));
    return _decodeMapResponse(
      response,
      fallbackError: 'Mitigation analysis failed.',
    );
  }

  Future<Map<String, dynamic>> runSyntheticPatch(
    String auditId, {
    String targetAttribute = 'gender',
  }) async {
    final uri = Uri.parse('$baseUrl/mitigate/synthetic/$auditId').replace(
      queryParameters: {'target_attribute': targetAttribute},
    );
    final response = await http.post(uri);
    return _decodeMapResponse(
      response,
      fallbackError: 'Synthetic patch generation failed.',
    );
  }

  Future<Map<String, dynamic>> runGovernance(String auditId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/governance/auditor/$auditId'),
    );
    return _decodeMapResponse(
      response,
      fallbackError: 'Could not generate governance guidance.',
    );
  }

  Future<Map<String, dynamic>> fetchDeepInspection(String auditId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/inspection/deep/$auditId'),
    );
    return _decodeMapResponse(
      response,
      fallbackError: 'Could not load deep inspection.',
    );
  }

  Future<Map<String, dynamic>> fetchCertificate(String auditId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/certificate/$auditId'),
    );
    return _decodeMapResponse(
      response,
      fallbackError: 'Could not load the fairness certificate.',
    );
  }

  Future<http.MultipartFile> _buildFile(
    String fieldName,
    PlatformFile file,
  ) async {
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

  Map<String, dynamic> _decodeMapResponse(
    http.Response response, {
    required String fallbackError,
  }) {
    if (response.statusCode >= 400) {
      throw Exception(_errorMessage(response.body, fallbackError));
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map) {
      throw Exception(fallbackError);
    }
    return decoded.cast<String, dynamic>();
  }

  List<Map<String, dynamic>> _decodeListResponse(
    http.Response response, {
    required String fallbackError,
  }) {
    if (response.statusCode >= 400) {
      throw Exception(_errorMessage(response.body, fallbackError));
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! List) {
      throw Exception(fallbackError);
    }
    return decoded
        .whereType<Map>()
        .map((item) => item.cast<String, dynamic>())
        .toList(growable: false);
  }

  String _errorMessage(String body, String fallbackError) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map) {
        final detail = decoded['detail'];
        if (detail is String && detail.trim().isNotEmpty) {
          return detail;
        }
        if (detail is Map && detail['message'] is String) {
          return detail['message'] as String;
        }
        if (decoded['message'] is String) {
          return decoded['message'] as String;
        }
      }
    } catch (_) {}
    if (body.trim().isNotEmpty) {
      return body;
    }
    return fallbackError;
  }
}
