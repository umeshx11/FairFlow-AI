import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';

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
    _auth.authStateChanges().listen((_) {
      _emitCurrentSession();
    });
  }

  static final AuthService instance = AuthService._();

  final FirebaseAuth _auth = FirebaseAuth.instance;
  final StreamController<AuthSession?> _sessionController =
      StreamController<AuthSession?>.broadcast();
  Map<String, dynamic>? _preloadedGuestAudit;

  Stream<AuthSession?> get authStateChanges async* {
    yield currentSession;
    yield* _sessionController.stream;
  }

  User? get currentUser => _auth.currentUser;

  AuthSession? get currentSession => _mapFirebaseUser(_auth.currentUser);

  bool get isGuest => currentSession?.isGuest ?? false;

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
    if (kIsWeb) {
      final provider = GoogleAuthProvider();
      provider.addScope('email');
      return _auth.signInWithPopup(provider);
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
    return _auth.signInWithCredential(credential);
  }

  Future<Map<String, dynamic>?> signInAsGuest() async {
    try {
      await _auth.signInAnonymously();
      _preloadedGuestAudit = await FirebaseService.instance.fetchSampleAudit();
    } catch (error) {
      await _auth.signOut().catchError((_) {});
      throw Exception(
        'Guest demo requires Firebase anonymous auth and the Firestore sample audit. $error',
      );
    }
    _emitCurrentSession();
    return _preloadedGuestAudit;
  }

  Future<void> signOut() async {
    _preloadedGuestAudit = null;
    try {
      await GoogleSignIn().signOut();
    } catch (_) {}
    try {
      await _auth.signOut();
    } catch (_) {}
    _emitCurrentSession();
  }
}
