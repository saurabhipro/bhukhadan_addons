import 'package:shared_preferences/shared_preferences.dart';

const String AUTH_TOKEN_KEY = 'auth_token';
const String USER_ID_KEY = 'user_id';
const String USER_NAME_KEY = 'user_name';
const String USER_PHONE_KEY = 'user_phone';

// Selection Keys
const String SELECTED_DEPARTMENT_ID_KEY = 'selected_department_id';
const String SELECTED_DEPARTMENT_NAME_KEY = 'selected_department_name';
const String SELECTED_PROJECT_ID_KEY = 'selected_project_id';
const String SELECTED_PROJECT_NAME_KEY = 'selected_project_name';
const String SELECTED_AREA_ID_KEY = 'selected_area_id';
const String SELECTED_AREA_NAME_KEY = 'selected_area_name';
const String SELECTED_VILLAGE_ID_KEY = 'selected_village_id';
const String SELECTED_VILLAGE_NAME_KEY = 'selected_village_name';
const String SELECTED_DISTRICT_ID_KEY = 'selected_district_id';
const String SELECTED_DISTRICT_NAME_KEY = 'selected_district_name';
const String SELECTED_TEHSIL_ID_KEY = 'selected_tehsil_id';
const String SELECTED_TEHSIL_NAME_KEY = 'selected_tehsil_name';

/// JSON list of pending screenshot audit events for offline retry.
const String SCREENSHOT_AUDIT_QUEUE_KEY = 'screenshot_audit_queue';

Future<String?> getAsyncItem(String key) async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getString(key);
}

Future<void> setAsyncItem(String key, String value) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(key, value);
}

Future<void> removeAsyncItem(String key) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.remove(key);
}

Future<void> clearAuthState() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.remove(AUTH_TOKEN_KEY);
  await prefs.remove(USER_ID_KEY);
  await prefs.remove(USER_NAME_KEY);
  await prefs.remove(USER_PHONE_KEY);
}
