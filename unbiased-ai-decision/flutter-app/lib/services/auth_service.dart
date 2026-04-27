import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';

import 'app_runtime.dart';
import 'firebase_service.dart';

class AuthSession {
  const AuthSession({
    required this.uid,
    this.email,
    this.name,
    required this.isGuest,
    required this.isFirebaseBacked,
  });

  final String uid;
  final String? email;
  final String? name;
  final bool isGuest;
  final bool isFirebaseBacked;
}

class AuthService {
  AuthService._() {
    final auth = _auth;
    if (auth != null) {
      auth.authStateChanges().listen((_) {
        _emitCurrentSession();
      });
    }
  }

  static final AuthService instance = AuthService._();

  final FirebaseAuth? _auth =
      AppRuntime.firebaseWebConfigured ? FirebaseAuth.instance : null;
  final StreamController<AuthSession?> _sessionController =
      StreamController<AuthSession?>.broadcast();
  AuthSession? _localSession;
  Map<String, dynamic>? _preloadedGuestAudit;

  Stream<AuthSession?> get authStateChanges async* {
    yield currentSession;
    yield* _sessionController.stream;
  }

  User? get currentUser => _auth?.currentUser;

  AuthSession? get currentSession {
    final auth = _auth;
    if (auth == null) {
      return _localSession;
    }
    return _mapFirebaseUser(auth.currentUser);
  }

  bool get isGuest => currentSession?.isGuest ?? false;
  bool get googleSignInAvailable => _auth != null;

  Map<String, dynamic>? consumePreloadedGuestAudit() {
    final payload = _preloadedGuestAudit;
    _preloadedGuestAudit = null;
    return payload;
  }

  AuthSession? _mapFirebaseUser(User? user) {
    if (user == null) {
      return null;
    }

    return AuthSession(
      uid: user.uid,
      email: user.email,
      name: user.displayName,
      isGuest: user.isAnonymous,
      isFirebaseBacked: true,
    );
  }

  void _emitCurrentSession() {
    if (!_sessionController.isClosed) {
      _sessionController.add(currentSession);
    }
  }

  Future<UserCredential> signInWithGoogle() async {
    final auth = _auth;
    if (auth == null) {
      throw Exception(
        'Google sign-in requires Firebase web configuration. Use guest mode for local demos.',
      );
    }

    if (kIsWeb) {
      final provider = GoogleAuthProvider();
      provider.addScope('email');
      return auth.signInWithPopup(provider);
    }

    final googleUser = await GoogleSignIn(scopes: ['email']).signIn();
    if (googleUser == null) {
      throw Exception('Google sign-in was cancelled.');
    }

    final googleAuth = await googleUser.authentication;
    final credential = GoogleAuthProvider.credential(
      accessToken: googleAuth.accessToken,
      idToken: googleAuth.idToken,
    );
    return auth.signInWithCredential(credential);
  }

  Future<Map<String, dynamic>?> signInAsGuest() async {
    final auth = _auth;
    if (auth == null) {
      try {
        _localSession = const AuthSession(
          uid: 'guest-demo',
          name: 'Guest',
          isGuest: true,
          isFirebaseBacked: false,
        );
        _preloadedGuestAudit = await FirebaseService.instance.fetchSampleAudit();
        _emitCurrentSession();
        return _preloadedGuestAudit;
      } catch (error) {
        _localSession = null;
        throw Exception(
          'Local guest demo could not load the sample audit. $error',
        );
      }
    }

    try {
      await auth.signInAnonymously();
      _preloadedGuestAudit = await FirebaseService.instance.fetchSampleAudit();
    } catch (error) {
      await auth.signOut().catchError((_) {});
      throw Exception(
        'Guest demo requires Firebase anonymous auth and the Firestore sample audit. $error',
      );
    }
    _emitCurrentSession();
    return _preloadedGuestAudit;
  }

  Future<void> signOut() async {
    _preloadedGuestAudit = null;
    _localSession = null;
    try {
      await GoogleSignIn().signOut();
    } catch (_) {}
    try {
      await _auth?.signOut();
    } catch (_) {}
    _emitCurrentSession();
  }
}
