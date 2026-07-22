import 'package:flutter/material.dart';
import 'dart:convert';
import '../utils/storage.dart';
import '../screens/login_screen.dart';
import 'package:provider/provider.dart';
import '../utils/theme_provider.dart';
import '../utils/colors.dart';
import '../services/api_service.dart';
import '../constants/api_constants.dart';
import '../services/screenshot_audit_service.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  String? _userName;
  String? _userPhone;
  String? _userId;
  List<String> _assignedVillages = [];
  bool _isLoadingVillages = false;

  @override
  void initState() {
    super.initState();
    ScreenshotAuditService.instance.setContext(screenName: 'Profile', clearSurvey: true);
    _loadUserName();
  }

  Future<void> _loadUserName() async {
    final name = await getAsyncItem(USER_NAME_KEY);
    final phone = await getAsyncItem(USER_PHONE_KEY);
    final id = await getAsyncItem(USER_ID_KEY);
    setState(() {
      _userName = name;
      _userPhone = phone;
      _userId = id;
    });

    if (id != null) {
      _fetchAssignedVillages(id);
    }
  }

  Future<void> _fetchAssignedVillages(String userId) async {
    setState(() => _isLoadingVillages = true);
    try {
      final response = await ApiService.get('${ApiEndpoints.userProjects}?user_id=$userId');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final departments = data['data'] ?? [];
        Set<String> villageNames = {};
        
        for (var dept in departments) {
          final projects = dept['projects'] ?? [];
          for (var proj in projects) {
            final villages = proj['villages'] ?? [];
            for (var vill in villages) {
              if (vill['name'] != null) {
                villageNames.add(vill['name'].toString());
              }
            }
          }
        }
        
        setState(() {
          _assignedVillages = villageNames.toList();
          _isLoadingVillages = false;
        });
      }
    } catch (e) {
      debugPrint("Error fetching villages: $e");
      setState(() => _isLoadingVillages = false);
    }
  }

  Future<void> _handleLogout() async {
    await clearAuthState();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final themeProvider = Provider.of<ThemeProvider>(context);
    final isDark = themeProvider.isDarkMode;

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: themeProvider.currentGradientColors,
          ),
        ),
        child: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header Row: Version and Profile Info
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 10, 24, 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _userName ?? "Guest User",
                                style: const TextStyle(
                                  fontSize: 28, 
                                  fontWeight: FontWeight.w900, 
                                  color: Colors.white,
                                  letterSpacing: -0.5
                                ),
                              ),
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: Colors.white.withValues(alpha: 0.2),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: const Text(
                                      "राजस्व सर्वेक्षक",
                                      style: TextStyle(fontSize: 10, color: Colors.white, fontWeight: FontWeight.bold),
                                    ),
                                  ),
                                  if (_userPhone != null && _userPhone!.isNotEmpty) ...[
                                    const SizedBox(width: 8),
                                    Text(
                                      "+91 $_userPhone",
                                      style: const TextStyle(fontSize: 13, color: Colors.white70, fontWeight: FontWeight.w500),
                                    ),
                                  ],
                                ],
                              ),
                            ],
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.white24,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: Colors.white12),
                          ),
                          child: const Text(
                            "V 1.2",
                            style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w900),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              // Assigned Villages Section
              if (_assignedVillages.isNotEmpty || _isLoadingVillages)
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: Colors.white10),
                    boxShadow: [
                      BoxShadow(color: Colors.black26, blurRadius: 10, offset: const Offset(0, 4))
                    ]
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(6),
                            decoration: BoxDecoration(color: Colors.white12, borderRadius: BorderRadius.circular(8)),
                            child: const Icon(Icons.holiday_village_rounded, color: Colors.white, size: 16),
                          ),
                          const SizedBox(width: 12),
                          const Text(
                            "निर्धारित ग्राम (Assigned Villages)",
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: Colors.white, letterSpacing: 0.3),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      if (_isLoadingVillages)
                        const Center(child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70)))
                      else
                        Wrap(
                          spacing: 8,
                          runSpacing: 10,
                          children: _assignedVillages.map((v) => Container(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                            decoration: BoxDecoration(
                              color: Colors.white12,
                              borderRadius: BorderRadius.circular(30),
                              border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
                            ),
                            child: Text(
                              v,
                              style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                            ),
                          )).toList(),
                        ),
                    ],
                  ),
                ),
              
              const SizedBox(height: 10),

              // Menu Options
              Expanded(
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 30),
                  decoration: BoxDecoration(
                    color: isDark ? AppColors.darkInputBg : Colors.white,
                    borderRadius: const BorderRadius.only(topLeft: Radius.circular(35), topRight: Radius.circular(35)),
                    boxShadow: [
                      if (!isDark) BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 20, offset: const Offset(0, -5))
                    ]
                  ),
                  child: SingleChildScrollView(
                    child: Column(
                      children: [
                        _buildMenuOption(Icons.person_outline_rounded, "Edit Profile", () {}),
                        _buildMenuOption(Icons.language_rounded, "Change Language", () {}),
                        _buildMenuOption(Icons.help_outline_rounded, "Help & Support", () {}),
                        _buildMenuOption(Icons.privacy_tip_outlined, "Privacy Policy", () {}),
                        
                        const SizedBox(height: 40),
                        
                        SizedBox(
                          width: double.infinity,
                          height: 54,
                          child: ElevatedButton(
                            onPressed: _handleLogout,
                            style: ElevatedButton.styleFrom(
                               backgroundColor: isDark ? Colors.red.withValues(alpha: 0.15) : Colors.red.shade50,
                               foregroundColor: Colors.red,
                               elevation: 0,
                               shadowColor: Colors.transparent,
                               shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: Colors.red.withValues(alpha: 0.1)))
                            ),
                            child: const Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.logout_rounded, size: 20),
                                SizedBox(width: 10),
                                Text("Logout", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 100), // Extra space for scrolling
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildVerticalDivider() {
    return Container(height: 30, width: 1, color: Colors.white30);
  }

  Widget _buildStatItem(String label, String value) {
    return Column(
      children: [
        Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(fontSize: 12, color: Colors.white70)),
      ],
    );
  }

  Widget _buildMenuOption(IconData icon, String title, VoidCallback onTap) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final itemBg = isDark ? const Color(0xFF383838) : Colors.grey.shade50;
    final iconBg = isDark ? const Color(0xFF4A4A4A) : Colors.white;
    final iconColor = isDark ? Colors.blue[300] : const Color(0xFF104E8B);
    final borderColor = isDark ? Colors.white.withValues(alpha: 0.05) : Colors.grey.shade200;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: itemBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: borderColor)
      ),
      child: ListTile(
        leading: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(color: iconBg, shape: BoxShape.circle, border: Border.all(color: borderColor)),
          child: Icon(icon, color: iconColor, size: 20),
        ),
        title: Text(title, style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15, color: isDark ? Colors.white : Colors.black)),
        trailing: Icon(Icons.arrow_forward_ios, size: 14, color: isDark ? Colors.grey[400] : Colors.grey),
        onTap: onTap,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
      ),
    );
  }
}
