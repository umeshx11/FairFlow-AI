class AppRuntime {
  AppRuntime._();

  static const String _firebaseApiKey = String.fromEnvironment(
    'FIREBASE_API_KEY',
    defaultValue: 'demo-api-key',
  );
  static const String _firebaseAppId = String.fromEnvironment(
    'FIREBASE_APP_ID',
    defaultValue: '1:1234567890:web:demo',
  );
  static const String _firebaseMessagingSenderId = String.fromEnvironment(
    'FIREBASE_MESSAGING_SENDER_ID',
    defaultValue: '1234567890',
  );
  static const String _firebaseProjectId = String.fromEnvironment(
    'FIREBASE_PROJECT_ID',
    defaultValue: 'unbiased-ai-demo',
  );
  static const String _firebaseAuthDomain = String.fromEnvironment(
    'FIREBASE_AUTH_DOMAIN',
    defaultValue: 'unbiased-ai-demo.firebaseapp.com',
  );
  static const String _firebaseStorageBucket = String.fromEnvironment(
    'FIREBASE_STORAGE_BUCKET',
    defaultValue: 'unbiased-ai-demo.appspot.com',
  );

  static bool get firebaseWebConfigured {
    return !_isPlaceholder(_firebaseApiKey) &&
        !_isPlaceholder(_firebaseAppId) &&
        !_isPlaceholder(_firebaseMessagingSenderId) &&
        !_isPlaceholder(_firebaseProjectId) &&
        !_isPlaceholder(_firebaseAuthDomain) &&
        !_isPlaceholder(_firebaseStorageBucket);
  }

  static bool get localDemoMode => !firebaseWebConfigured;

  static bool _isPlaceholder(String value) {
    final normalized = value.trim().toLowerCase();
    if (normalized.isEmpty) {
      return true;
    }
    const exactPlaceholders = <String>{
      'demo-api-key',
      '1:1234567890:web:demo',
      '1234567890',
      'unbiased-ai-demo',
      'unbiased-ai-demo.firebaseapp.com',
      'unbiased-ai-demo.appspot.com',
      'your_firebase_web_api_key',
      'your_firebase_web_app_id',
      'your_sender_id',
      'your_firebase_project_id',
      'your-project.firebaseapp.com',
      'your-project.appspot.com',
    };
    if (exactPlaceholders.contains(normalized)) {
      return true;
    }
    if (normalized.startsWith('your_')) {
      return true;
    }
    if (normalized.contains('your-project')) {
      return true;
    }
    return false;
  }
}
