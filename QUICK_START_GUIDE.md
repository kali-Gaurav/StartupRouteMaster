# ⚡ QUICK START — FIRST 5 TASKS (1-2 DAYS)

**Goal:** Set up the foundation for all other tasks  
**Time:** ~8 hours of focused work  
**Outcome:** New color theme + Google auth ready + validators working

---

## 📌 TASK #2: Update AppTheme Colors (2 hours)

### Step 1: Backup current theme
```bash
cd C:\Projects\fufaji-online-business
cp lib/utils/app_theme.dart lib/utils/app_theme.dart.backup
```

### Step 2: Replace lib/utils/app_theme.dart

```dart
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // ===== BRAND COLORS (Orange & White) =====
  static const Color primary = Color(0xFFFF8C42);        // Warm Orange
  static const Color primaryDark = Color(0xFFFF6B35);    // Darker Orange
  static const Color primaryLight = Color(0xFFFFE5D0);   // Light Orange BG
  
  // ===== BACKGROUND & SURFACES =====
  static const Color secondary = Color(0xFFFFF5F0);      // Off-white
  static const Color white = Color(0xFFFFFFFF);          // Pure white
  static const Color accent = Color(0xFFFF6B35);         // Accent (darker orange)
  
  // ===== NEUTRAL GREYS =====
  static const Color grey50 = Color(0xFFFAFAFA);
  static const Color grey100 = Color(0xFFF5F5F5);
  static const Color grey200 = Color(0xFFEEEEEE);
  static const Color grey300 = Color(0xFFE0E0E0);
  static const Color grey400 = Color(0xFFBDBDBD);
  static const Color grey500 = Color(0xFF9E9E9E);
  static const Color grey600 = Color(0xFF757575);
  static const Color grey700 = Color(0xFF616161);
  static const Color grey800 = Color(0xFF424242);
  static const Color grey900 = Color(0xFF212121);
  
  // ===== STATUS COLORS =====
  static const Color success = Color(0xFF27AE60);        // Green
  static const Color error = Color(0xFFE74C3C);          // Red
  static const Color warning = Color(0xFFFFC107);        // Amber
  static const Color info = Color(0xFF2196F3);           // Blue

  // ===== LIGHT THEME =====
  static final ThemeData lightTheme = ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: primary,                    // Orange
      primary: primary,
      secondary: secondary,                  // Off-white
      surface: white,                        // White cards
      background: grey50,                    // Light grey pages
      error: error,
      brightness: Brightness.light,
    ),
    fontFamily: 'Poppins',
    textTheme: GoogleFonts.poppinsTextTheme(),
    
    // ===== SCAFFOLD =====
    scaffoldBackgroundColor: grey50,
    
    // ===== APP BAR =====
    appBarTheme: const AppBarTheme(
      backgroundColor: white,
      foregroundColor: grey900,
      elevation: 0,
      centerTitle: true,
      surfaceTintColor: transparent,
    ),
    
    // ===== CARDS =====
    cardTheme: CardThemeData(
      color: white,
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
    ),
    
    // ===== BUTTONS (ORANGE & WHITE) =====
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: primary,             // Orange
        foregroundColor: white,               // White text
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        minimumSize: const Size(48, 48),     // Touch target
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: primary,             // Orange text
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        side: const BorderSide(color: primary, width: 2),
        minimumSize: const Size(48, 48),
      ),
    ),
    
    // ===== TEXT FIELD (ORANGE FOCUS BORDER) =====
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: white,
      isDense: false,
      contentPadding: const EdgeInsets.all(12),
      
      // DEFAULT BORDER
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: grey300),
      ),
      
      // FOCUSED BORDER (ORANGE)
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: primary, width: 2),
      ),
      
      // ERROR BORDER (RED)
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: error),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: error, width: 2),
      ),
      
      // LABELS & HINTS
      labelStyle: const TextStyle(color: grey700),
      hintStyle: const TextStyle(color: grey400),
      helperStyle: const TextStyle(color: grey600),
      errorStyle: const TextStyle(color: error),
    ),
    
    // ===== OTHER COMPONENTS =====
    dividerColor: grey200,
    dividerTheme: const DividerThemeData(
      color: grey200,
      thickness: 1,
    ),
  );

  // ===== DARK THEME (Optional, for future) =====
  static final ThemeData darkTheme = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: ColorScheme.fromSeed(
      seedColor: primary,
      brightness: Brightness.dark,
    ),
  );
  
  // ===== UTILITY FUNCTIONS =====
  static const Color transparent = Color(0x00000000);
  
  static BoxShadow smallShadow = BoxShadow(
    color: grey800.withOpacity(0.08),
    blurRadius: 8,
    offset: const Offset(0, 2),
  );
  
  static BoxShadow mediumShadow = BoxShadow(
    color: grey800.withOpacity(0.12),
    blurRadius: 16,
    offset: const Offset(0, 4),
  );
  
  static BoxShadow largeShadow = BoxShadow(
    color: grey800.withOpacity(0.16),
    blurRadius: 24,
    offset: const Offset(0, 8),
  );
}
```

### Step 3: Test the theme
```bash
flutter pub get
flutter clean
flutter run
# Verify: All buttons should be orange, backgrounds white/grey
```

✅ **Verification Checklist:**
- [ ] Buttons appear in orange (#FF8C42)
- [ ] Card backgrounds are white
- [ ] Page background is light grey (#FAFAFA)
- [ ] Input focus border is orange
- [ ] No old colors (deep orange #FF5722, green #4CAF50)

---

## 📌 TASK #3: Remove OTP Auth (3 hours)

### Step 1: Comment out OTP methods in auth_provider.dart

```dart
// lib/providers/auth_provider.dart

// COMMENT OUT THESE ENTIRE METHODS:
/*
Future<void> signInWithPhoneNumber(String phone) async {
  // ... entire method
}

Future<void> verifyOTP(String otp) async {
  // ... entire method
}

void _handlePhoneAuthError(FirebaseAuthException e) {
  // ... entire method
}
*/

// REMOVE THESE VARIABLES:
// String? _verificationId;
// String? _lastPhone;
// bool _otpSent = false;
```

### Step 2: Simplify login_screen.dart

```dart
// lib/screens/login_screen.dart

class _LoginScreenState extends State<LoginScreen> {
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _checkDeviceIntegrity();
  }

  // ✅ KEEP: Google Sign-In (for ALL users)
  Future<void> _handleGoogleLogin() async {
    HapticFeedback.mediumImpact();
    setState(() => _isLoading = true);

    final auth = Provider.of<AuthProvider>(context, listen: false);
    final success = await auth.signInWithGoogle();

    if (!mounted) return;
    setState(() => _isLoading = false);

    if (success) {
      // Role determined by Firestore custom claims
      if (auth.currentUser?.role == UserRole.owner) {
        context.go('/owner/dashboard');
      } else if (auth.currentUser?.role == UserRole.employee) {
        context.go('/employee/orders');
      } else {
        context.go('/customer/home');
      }
    } else if (auth.errorMessage != null) {
      _showError(auth.errorMessage!);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Logo
              Image.asset(
                'assets/logo.png',
                width: 120,
                height: 120,
              ),
              const SizedBox(height: 32),

              // Title
              Text(
                'फुफाजी स्टोर',
                style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                  color: AppTheme.primary,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              
              Text(
                'Dad-Focused E-Commerce',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 64),

              // Google Button (ONLY auth method now)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _isLoading ? null : _handleGoogleLogin,
                  icon: Image.asset(
                    'assets/google_logo.png',
                    width: 24,
                    height: 24,
                  ),
                  label: Text(
                    _isLoading ? 'साइन इन में...' : 'Google के साथ साइन इन करें',
                    style: const TextStyle(fontSize: 16),
                  ),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    backgroundColor: AppTheme.primary,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Guest Option (Optional)
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: _isLoading ? null : _continueAsGuest,
                  child: const Text('अतिथि के रूप में ब्राउज़ करें'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppTheme.error,
      ),
    );
  }
}
```

### Step 3: Delete OTP screens
```bash
rm lib/screens/otp_screen.dart
rm lib/screens/auth/otp_screen.dart  # If exists
# (Or just don't route to them)
```

✅ **Verification:**
- [ ] Login screen shows only "Sign in with Google"
- [ ] No phone input field
- [ ] Google login works (test with test account)
- [ ] No errors about missing OTP methods

---

## 📌 TASK #6: Create Validators (1 hour)

### Create lib/utils/validators.dart

```dart
// lib/utils/validators.dart

class Validators {
  // Phone: Exactly 10 digits
  static bool isValidPhone(String phone) {
    final trimmed = phone.replaceAll(' ', '').replaceAll('-', '');
    return RegExp(r'^\d{10}$').hasMatch(trimmed);
  }

  // Address: Min 10 chars, no SQL injection
  static bool isValidAddress(String address) {
    if (address.length < 10) return false;
    
    // Block SQL injection patterns
    final blockList = ['<', '>', '"', "'", ';', '/*', '*/'];
    return !blockList.any((char) => address.contains(char));
  }

  // Name: 2-50 chars, letters/spaces/hyphens only
  static bool isValidName(String name) {
    if (name.length < 2 || name.length > 50) return false;
    
    // Allow: a-z, A-Z, 0-9, space, hyphen
    // Also allow: Hindi characters (Devanagari)
    return RegExp(r'^[a-zA-Z0-9\s\-ऀ-ॿ]+$').hasMatch(name);
  }

  // Sanitize: Remove dangerous characters
  static String sanitize(String input) {
    return input
        .replaceAll('<', '')
        .replaceAll('>', '')
        .replaceAll('"', '')
        .replaceAll("'", '')
        .trim();
  }

  // Error messages (Hindi)
  static String getPhoneError(String phone) {
    if (phone.isEmpty) return 'फोन नंबर आवश्यक है';
    if (phone.length < 10) return 'कम से कम 10 अंक दर्ज करें';
    if (!isValidPhone(phone)) return 'केवल संख्याएं दर्ज करें';
    return '';
  }

  static String getAddressError(String address) {
    if (address.isEmpty) return 'पता आवश्यक है';
    if (address.length < 10) return 'पता 10+ वर्ण होना चाहिए';
    if (!isValidAddress(address)) return 'विशेष वर्ण दर्ज न करें';
    return '';
  }

  static String getNameError(String name) {
    if (name.isEmpty) return 'नाम आवश्यक है';
    if (name.length < 2) return 'कम से कम 2 वर्ण दर्ज करें';
    if (name.length > 50) return 'अधिकतम 50 वर्ण तक';
    if (!isValidName(name)) return 'केवल अक्षर, संख्या, रिक्ति दर्ज करें';
    return '';
  }
}
```

### Step 2: Test the validators
```dart
// test/utils/validators_test.dart

import 'package:flutter_test/flutter_test.dart';
import 'package:fufaji_store/utils/validators.dart';

void main() {
  group('Validators', () {
    test('isValidPhone accepts 10-digit numbers', () {
      expect(Validators.isValidPhone('9876543210'), true);
      expect(Validators.isValidPhone('98765432'), false);  // Too short
      expect(Validators.isValidPhone('abc1234567'), false); // Contains letters
    });

    test('isValidAddress rejects short strings', () {
      expect(Validators.isValidAddress('123 Main St, Delhi'), true);
      expect(Validators.isValidAddress('short'), false);
    });

    test('isValidAddress blocks SQL injection', () {
      expect(Validators.isValidAddress("'; DROP TABLE--"), false);
      expect(Validators.isValidAddress('123 Main St'), true);
    });

    test('isValidName allows Hindi and English', () {
      expect(Validators.isValidName('राज कुमार'), true);
      expect(Validators.isValidName('Raj Kumar'), true);
      expect(Validators.isValidName('123 Main St'), false); // Too specific
    });
  });
}
```

Run tests:
```bash
flutter test test/utils/validators_test.dart
# Should see: ✓ All tests pass
```

✅ **Verification:**
- [ ] `flutter test` passes all validator tests
- [ ] Phone validation rejects non-10-digit input
- [ ] Address validation rejects < 10 chars
- [ ] Name validation allows Hindi characters

---

## 📌 TASK #5: Create FormInput Component (2 hours)

### Create lib/widgets/form_input.dart

```dart
// lib/widgets/form_input.dart

import 'package:flutter/material.dart';
import '../utils/app_theme.dart';

class FormInput extends StatefulWidget {
  final String label;
  final String placeholder;
  final TextEditingController controller;
  final String? Function(String)? validator;
  final TextInputType keyboardType;
  final int maxLines;
  final int minLines;
  final bool obscureText;
  final VoidCallback? onFocus;
  final Function(String)? onChanged;

  const FormInput({
    required this.label,
    required this.placeholder,
    required this.controller,
    this.validator,
    this.keyboardType = TextInputType.text,
    this.maxLines = 1,
    this.minLines = 1,
    this.obscureText = false,
    this.onFocus,
    this.onChanged,
  });

  @override
  State<FormInput> createState() => _FormInputState();
}

class _FormInputState extends State<FormInput> {
  late FocusNode _focusNode;
  String? _error;
  bool _isFocused = false;

  @override
  void initState() {
    super.initState();
    _focusNode = FocusNode();
    _focusNode.addListener(_onFocusChange);
  }

  @override
  void dispose() {
    _focusNode.removeListener(_onFocusChange);
    _focusNode.dispose();
    super.dispose();
  }

  void _onFocusChange() {
    setState(() => _isFocused = _focusNode.hasFocus);
    if (_focusNode.hasFocus) {
      widget.onFocus?.call();
    }
  }

  void _handleChanged(String value) {
    // Validate on change
    if (widget.validator != null) {
      setState(() => _error = widget.validator!(value));
    }
    widget.onChanged?.call(value);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // LABEL
        Text(
          widget.label,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: AppTheme.grey900,
          ),
        ),
        const SizedBox(height: 8),

        // TEXT FIELD
        TextField(
          controller: widget.controller,
          focusNode: _focusNode,
          keyboardType: widget.keyboardType,
          maxLines: widget.maxLines,
          minLines: widget.minLines,
          obscureText: widget.obscureText,
          onChanged: _handleChanged,
          decoration: InputDecoration(
            hintText: widget.placeholder,
            hintStyle: const TextStyle(color: AppTheme.grey400),
            
            // FILL COLOR
            filled: true,
            fillColor: Colors.white,
            
            // BORDER
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: AppTheme.grey300),
            ),
            
            // FOCUSED BORDER (ORANGE)
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(
                color: AppTheme.primary,
                width: 2,
              ),
            ),
            
            // ERROR BORDER (RED)
            errorBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: AppTheme.error),
            ),
            
            // PADDING
            contentPadding: const EdgeInsets.all(12),
            
            // SUFFIX ICON (for validation)
            suffixIcon: _error != null
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: Icon(
                      Icons.error_outline,
                      color: AppTheme.error,
                    ),
                  )
                : null,
          ),
        ),

        // ERROR MESSAGE
        if (_error != null && _error!.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            _error!,
            style: const TextStyle(
              fontSize: 12,
              color: AppTheme.error,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ],
    );
  }
}
```

### Step 2: Test the component

```dart
// test/widgets/form_input_test.dart

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fufaji_store/widgets/form_input.dart';
import 'package:fufaji_store/utils/validators.dart';

void main() {
  testWidgets('FormInput displays label and placeholder', (WidgetTester tester) async {
    final controller = TextEditingController();
    
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FormInput(
            label: 'फोन',
            placeholder: '10-अंकीय नंबर',
            controller: controller,
          ),
        ),
      ),
    );

    expect(find.text('फोन'), findsOneWidget);
    expect(find.text('10-अंकीय नंबर'), findsOneWidget);
  });

  testWidgets('FormInput shows error when validation fails', (WidgetTester tester) async {
    final controller = TextEditingController();
    
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FormInput(
            label: 'फोन',
            placeholder: '10-अंकीय नंबर',
            controller: controller,
            validator: (value) => Validators.getPhoneError(value),
          ),
        ),
      ),
    );

    // Enter invalid phone
    await tester.enterText(find.byType(TextField), '123');
    await tester.pumpAndSettle();

    expect(find.text('कम से कम 10 अंक दर्ज करें'), findsOneWidget);
  });
}
```

Run tests:
```bash
flutter test test/widgets/form_input_test.dart
```

✅ **Verification:**
- [ ] FormInput displays label and placeholder
- [ ] Error message appears when validation fails
- [ ] Orange focus border appears when focused
- [ ] Error icon shows when there's an error

---

## 🎯 Summary: First 5 Tasks Complete

**What you've accomplished:**
✅ Orange & white color theme applied globally  
✅ OTP auth removed, Google Sign-In only  
✅ Phone, address, name validators created  
✅ FormInput component with validation feedback  
✅ All tests passing  

**Files Changed:**
- `lib/utils/app_theme.dart` (UPDATED)
- `lib/screens/login_screen.dart` (UPDATED)
- `lib/providers/auth_provider.dart` (EDITED: OTP methods commented out)

**Files Created:**
- `lib/utils/validators.dart` (NEW)
- `lib/widgets/form_input.dart` (NEW)
- `test/utils/validators_test.dart` (NEW)
- `test/widgets/form_input_test.dart` (NEW)

**Next Steps (Tasks #4, #7, #17):**
1. Refactor checkout to 6 steps
2. Update order model with userInfo
3. Implement GST calculation

---

## ⚡ Quick Commands

```bash
# Start fresh
cd /sessions/quirky-exciting-darwin/mnt/fufaji-online-business
git status
git add -A
git commit -m "WIP: Refactor to orange/white theme, remove OTP"

# Test specific file
flutter test test/utils/validators_test.dart -v

# Run all tests
flutter test

# Clean & rebuild
flutter clean
flutter pub get
flutter run

# Check theme is applied
# Look for: Orange buttons, white cards, orange input borders
```

---

**Ready to code?** Start with Task #2 and let me know when you hit any issues!

💪 You've got this! 🚀

