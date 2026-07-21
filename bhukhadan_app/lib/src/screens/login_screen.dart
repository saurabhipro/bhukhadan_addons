import 'dart:io';
import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:pinput/pinput.dart';
import 'package:smart_auth/smart_auth.dart';
import '../constants/assets.dart';
import '../utils/colors.dart';
import '../utils/storage.dart';
import '../constants/api_constants.dart';
import '../services/api_service.dart';
import '../navigation/bottom_navigation.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _otpController = TextEditingController();
  bool _isLoginStep = false; 
  bool _isLoading = false;
  String? _error;
  
  late final SmsRetriever smsRetriever;
  late final SmartAuth smartAuth;
  
  // ignore: unused_field
  String? _appSignature; 

  @override
  void dispose() {
    _phoneController.dispose();
    _otpController.dispose();
    smsRetriever.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    smartAuth = SmartAuth();
    smsRetriever = SmsRetrieverImpl(smartAuth);
  }

  Future<void> _handleSendOTP() async {
    final phone = _phoneController.text.trim();
    if (phone.length != 10) {
      setState(() => _error = "Please enter a valid 10-digit phone number");
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      await InternetAddress.lookup('google.com');
    } catch (_) {
      setState(() {
         _error = "Device is Offline. Check Data/Wi-Fi.";
         _isLoading = false;
      });
      return;
    }

    try {
      final response = await ApiService.post(
        ApiEndpoints.requestOtp,
        {'mobile': phone},
      );

      final data = jsonDecode(response.body);
      
      var otp = data['mobile_otp'] ?? data['otp'];
      if (otp == null && data['details'] != null) {
         final details = data['details'].toString();
         if (details.length == 4 && int.tryParse(details) != null) {
            otp = details;
         }
      }

      if (response.statusCode == 200 || response.statusCode == 201) {
        if (otp != null) {
           _otpController.text = otp.toString();
           Future.delayed(const Duration(milliseconds: 500), () {
              if (mounted) _handleVerifyOTP();
           });
        }

        ScaffoldMessenger.of(context).showSnackBar(
           SnackBar(content: Text("OTP Sent: ${data['details'] ?? ''}")),
        );
        setState(() {
          _isLoginStep = true;
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = data['error'] ?? 'Failed to send OTP';
          _isLoading = false;
        });
      }
    } catch (e) {
        String msg = "Something went wrong";
        if (e.toString().contains("SocketException")) {
           msg = "No Internet Connection or Server Unreachable";
        } else {
           msg = e.toString().replaceAll("Exception:", "").trim();
        }
        setState(() {
          _error = msg;
          _isLoading = false;
        });
    }
  }

  Future<void> _handleVerifyOTP() async {
     final otp = _otpController.text.trim();
     if (otp.length != 4) {
       setState(() => _error = "Please enter valid 4-digit OTP");
       return;
     }
     
     setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final response = await ApiService.post(
        ApiEndpoints.login,
        {
          'mobile': _phoneController.text.trim(),
          'otp_input': otp,
          'channel_id': 1
        },
      );

      final data = jsonDecode(response.body);

      if (response.statusCode == 200 || response.statusCode == 201) {
        if (data['token'] != null) {
          await setAsyncItem(AUTH_TOKEN_KEY, data['token']);
          await setAsyncItem(USER_ID_KEY, data['user_id']?.toString() ?? '');
          await setAsyncItem(USER_NAME_KEY, data['user_name'] ?? data['name'] ?? '');
          await setAsyncItem(USER_PHONE_KEY, _phoneController.text.trim());
          
          if (!mounted) return;
          Navigator.of(context).pushAndRemoveUntil(
             MaterialPageRoute(builder: (_) => const BottomNavigation()),
             (route) => false,
          );
        } else {
           setState(() {
            _error = "Invalid response from server";
            _isLoading = false;
          });
        }
      } else {
        setState(() {
          _error = data['error'] ?? 'Invalid OTP';
          _isLoading = false;
        });
      }
    } catch (e) {
        debugPrint("[LoginScreen] Error: $e");
        String msg = "Something went wrong";
        if (e.toString().contains("SocketException")) {
           msg = "No Internet Connection or Server Unreachable";
        } else {
           msg = e.toString().replaceAll("Exception:", "").trim();
        }
        setState(() {
          _error = msg;
          _isLoading = false;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
     return Scaffold(
       resizeToAvoidBottomInset: true,
       backgroundColor: Colors.white,
       body: LayoutBuilder(
         builder: (context, constraints) {
           return SingleChildScrollView(
             child: ConstrainedBox(
               constraints: BoxConstraints(
                 minHeight: constraints.maxHeight,
               ),
               child: IntrinsicHeight(
                 child: Stack(
                   children: [
                     // Background
                     Positioned.fill(
                       child: Image.asset(
                         'assets/images/background1.webp', 
                         fit: BoxFit.cover,
                       ),
                     ),
                     Positioned.fill(
                       child: Container(
                         decoration: BoxDecoration(
                           gradient: LinearGradient(
                             begin: Alignment.topCenter,
                             end: Alignment.bottomCenter,
                             colors: [
                               Colors.black.withValues(alpha: 0.4),
                               Colors.transparent,
                               Colors.black.withValues(alpha: 0.5),
                             ],
                           ),
                         ),
                       ),
                     ),
                     Column(
                       children: [
                         const SizedBox(height: 70),
                         // Logo 1
                         Container(
                           width: 120,
                           height: 120,
                           decoration: BoxDecoration(
                             shape: BoxShape.circle,
                             color: Colors.white,
                             boxShadow: [
                               BoxShadow(
                                 color: Colors.black.withValues(alpha: 0.3),
                                 blurRadius: 15,
                                 offset: const Offset(0, 5),
                               )
                             ],
                           ),
                           child: Padding(
                             padding: const EdgeInsets.all(8.0),
                             child: Image.asset(
                               AppAssets.cgLogo, 
                               fit: BoxFit.contain,
                             ),
                           ),
                         ),
                         
                         const SizedBox(height: 24),
                         const Text(
                           "BhuKhadan",
                           textAlign: TextAlign.center,
                           style: TextStyle(
                             color: Colors.white,
                             fontSize: 40,
                             fontWeight: FontWeight.w900,
                             letterSpacing: 1.5,
                             shadows: [Shadow(color: Colors.black45, blurRadius: 10, offset: Offset(0, 4))]
                           ),
                         ),
                         const SizedBox(height: 40),

                         const Spacer(),
                         // Bottom Sheet
                         Container(
                           width: double.infinity,
                           decoration: const BoxDecoration(
                             color: Colors.white,
                             borderRadius: BorderRadius.only(
                               topLeft: Radius.circular(32),
                               topRight: Radius.circular(32),
                             ),
                           ),
                           child: SafeArea(
                             top: false,
                             child: Padding(
                               padding: const EdgeInsets.fromLTRB(30, 35, 30, 25),
                               child: Column(
                                 crossAxisAlignment: CrossAxisAlignment.start,
                                 mainAxisSize: MainAxisSize.min,
                                 children: [
                                   Text(
                                     _isLoginStep ? 'OTP Verification' : 'Login',
                                     style: const TextStyle(
                                       fontSize: 18,
                                       fontWeight: FontWeight.w900,
                                       color: Color(0xFF2D3436),
                                       letterSpacing: -0.5,
                                     ),
                                   ),
                                   const SizedBox(height: 8),
                                   Text(
                                     _isLoginStep 
                                       ? "Enter 4-digit code sent to +91${_phoneController.text}"
                                       : "Enter your phone number to continue", 
                                     style: TextStyle(
                                       color: Colors.grey.shade600, 
                                       fontSize: 16,
                                     ),
                                   ),
                                   const SizedBox(height: 35),
                                   
                                   if (!_isLoginStep) ...[
                                      TextField(
                                        controller: _phoneController,
                                        keyboardType: TextInputType.phone,
                                        maxLength: 10,
                                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, letterSpacing: 1.5),
                                        decoration: InputDecoration(
                                           labelText: "Mobile Number",
                                           prefixText: "+91 ",
                                           prefixStyle: const TextStyle(fontWeight: FontWeight.bold, color: Colors.black),
                                           border: OutlineInputBorder(
                                             borderRadius: BorderRadius.circular(15),
                                             borderSide: BorderSide(color: Colors.grey.shade300),
                                           ),
                                           filled: true,
                                           fillColor: Colors.grey.shade50,
                                           errorText: _error,
                                        ),
                                      ),
                                   ] else ...[
                                      Center(
                                        child: Pinput(
                                          controller: _otpController,
                                          length: 4,
                                          smsRetriever: smsRetriever,
                                          defaultPinTheme: PinTheme(
                                            width: 60,
                                            height: 60,
                                            textStyle: const TextStyle(fontSize: 24, color: AppColors.primary, fontWeight: FontWeight.bold),
                                            decoration: BoxDecoration(
                                              color: Colors.grey.shade50,
                                              border: Border.all(color: Colors.grey.shade300),
                                              borderRadius: BorderRadius.circular(12),
                                            ),
                                          ),
                                          focusedPinTheme: PinTheme(
                                            width: 60,
                                            height: 60,
                                            textStyle: const TextStyle(fontSize: 24, color: AppColors.primary, fontWeight: FontWeight.bold),
                                            decoration: BoxDecoration(
                
                                              border: Border.all(color: AppColors.primary, width: 2),
                                              borderRadius: BorderRadius.circular(12),
                                            ),
                                          ),
                                          onCompleted: (pin) {
                                            if (!_isLoading) _handleVerifyOTP();
                                          },
                                        ),
                                      ),
                                      if (_error != null) Padding(
                                         padding: const EdgeInsets.only(top: 15.0),
                                         child: Center(child: Text(_error!, style: const TextStyle(color: Colors.red, fontWeight: FontWeight.w600))),
                                      ),
                                      const SizedBox(height: 10),
                                      Center(
                                        child: TextButton(
                                          onPressed: _isLoading ? null : _handleSendOTP,
                                          child: const Text("Resend OTP", style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold)),
                                        ),
                                      ),
                                   ],
                                   
                                   const SizedBox(height: 35),
                                   SizedBox(
                                     width: double.infinity,
                                     height: 56,
                                     child: ElevatedButton(
                                       onPressed: _isLoading ? null : (_isLoginStep ? _handleVerifyOTP : _handleSendOTP),
                                       style: ElevatedButton.styleFrom(
                                         backgroundColor: AppColors.primary,
                                         foregroundColor: Colors.white,
                                         elevation: 5,
                                         shadowColor: AppColors.primary.withValues(alpha: 0.5),
                                         shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
                                       ),
                                       child: _isLoading 
                                         ? const CircularProgressIndicator(color: Colors.white)
                                         : Text(
                                             _isLoginStep ? 'VERIFY & LOGIN' : 'CONTINUE', 
                                             style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, letterSpacing: 1.2),
                                           ),
                                     ),
                                   ),
                                   const SizedBox(height: 20), // Padding to ensure the button is not cut off by navigation bar
                                 ],
                               ),
                             ),
                           ),
                         ),
                       ],
                     ),
                   ],
                 ),
               ),
             ),
           );
         },
       ),
     );
  }
}

class SmsRetrieverImpl implements SmsRetriever {
  const SmsRetrieverImpl(this.smartAuth);

  final SmartAuth smartAuth;

  @override
  Future<void> dispose() {
    return smartAuth.removeSmsListener();
  }

  @override
  Future<String?> getSmsCode() async {
    final res = await smartAuth.getSmsCode(
      useUserConsentApi: true,
      matcher: r'\d{4}',
    );
    if (res.succeed && res.codeFound) {
      return res.code!;
    }
    return null;
  }

  @override
  bool get listenForMultipleSms => false;
}
