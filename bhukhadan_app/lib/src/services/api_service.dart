import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../utils/storage.dart';
import '../utils/globals.dart';
import '../constants/api_constants.dart';
import '../screens/login_screen.dart';

class ApiService {
  static const String baseUrl = ApiEndpoints.baseUrl;

  static Future<Map<String, String>> _getHeaders() async {
    final token = await getAsyncItem(AUTH_TOKEN_KEY);
    return {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'App-Version-Code': '1',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  static Future<http.Response> get(String endpoint) async {
    final headers = await _getHeaders();
    final response = await http.get(Uri.parse('$baseUrl$endpoint'), headers: headers);
    _handleAuthError(response);
    return response;
  }

  static Future<http.Response> post(String endpoint, Map<String, dynamic> body) async {
    final url = Uri.parse('$baseUrl$endpoint');
    debugPrint("[ApiService] POST: $url");
    debugPrint("[ApiService] Body: ${jsonEncode(body)}");
    
    final headers = await _getHeaders();
    final response = await http.post(
      url,
      headers: headers,
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 30));
    
    debugPrint("[ApiService] Status: ${response.statusCode}");
    _handleAuthError(response);
    return response;
  }

  static Future<http.Response> patch(String endpoint, Map<String, dynamic> body) async {
    final headers = await _getHeaders();
    final response = await http.patch(
      Uri.parse('$baseUrl$endpoint'),
      headers: headers,
      body: jsonEncode(body),
    );
    _handleAuthError(response);
    return response;
  }

  static Future<http.Response> delete(String endpoint) async {
    final headers = await _getHeaders();
    final response = await http.delete(Uri.parse('$baseUrl$endpoint'), headers: headers);
    _handleAuthError(response);
    return response;
  }

  
  static Future<http.Response> postMultipart(String endpoint, Map<String, String> fields, List<http.MultipartFile> files) async {
     final token = await getAsyncItem(AUTH_TOKEN_KEY);
     var request = http.MultipartRequest('POST', Uri.parse('$baseUrl$endpoint'));
     
     request.headers.addAll({
       'App-Version-Code': '1',
       if (token != null) 'Authorization': 'Bearer $token',
     });
     
     request.fields.addAll(fields);
     request.files.addAll(files);
     
     final streamedResponse = await request.send();
     final response = await http.Response.fromStream(streamedResponse);
     _handleAuthError(response);
     return response;
  }

  static Future<http.Response> putFileDirectly(String fullUrl, List<int> bytes, String contentType) async {
    return await http.put(
      Uri.parse(fullUrl),
      headers: {
        'Content-Type': contentType,
      },
      body: bytes,
    );
  }

  static void _handleAuthError(http.Response response) {
    if (response.statusCode == 401) {
      debugPrint('[ApiService] 401 Unauthorized - Logging out');
      clearAuthState();
      if (navigatorKey.currentState != null) {
        navigatorKey.currentState!.pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => const LoginScreen()),
          (route) => false,
        );
      }
    }
  }
}
