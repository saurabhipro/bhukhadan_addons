import 'package:flutter/material.dart';
import 'dart:convert';
import '../constants/assets.dart';
import '../utils/colors.dart';
import '../utils/storage.dart';
// Import this

import '../constants/api_constants.dart';
import '../services/api_service.dart';
import '../utils/globals.dart'; // Import globals
import '../utils/localization.dart';
import '../components/language_selector.dart';
import 'package:provider/provider.dart';
import '../utils/theme_provider.dart';
import '../services/screenshot_audit_service.dart';



class HomeScreen extends StatefulWidget {
  final Function(int)? onSwitchTab;
  const HomeScreen({super.key, this.onSwitchTab});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String? _userId;
  String? _userName;
  List<dynamic> _allProjects = [];
  List<dynamic> _departments = [];
  List<dynamic> _projects = [];
  List<dynamic> _areas = [];
  List<dynamic> _villages = [];
  
  String? _selectedDepartmentId;
  String? _selectedProjectId;
  String? _selectedAreaId;
  String? _selectedVillageId;
  
  Map<String, dynamic>? _stats;
  String? _authToken;
  bool _loadingAreas = false;
  bool _loadingVillages = false;

  @override
  void initState() {
    super.initState();
    ScreenshotAuditService.instance.setContext(screenName: 'Home', clearSurvey: true);
    _loadInitialData();
  }

  Future<void> _loadInitialData() async {
    final userId = await getAsyncItem(USER_ID_KEY);
    final userName = await getAsyncItem(USER_NAME_KEY);
    final token = await getAsyncItem(AUTH_TOKEN_KEY);
    final savedDept = await getAsyncItem(SELECTED_DEPARTMENT_ID_KEY);
    final savedProj = await getAsyncItem(SELECTED_PROJECT_ID_KEY);
    final savedArea = await getAsyncItem(SELECTED_AREA_ID_KEY);
    final savedVill = await getAsyncItem(SELECTED_VILLAGE_ID_KEY);

    setState(() {
      _userId = userId;
      _userName = userName;
      _authToken = token;
      _selectedDepartmentId = savedDept;
      _selectedProjectId = savedProj;
      _selectedAreaId = savedArea;
      _selectedVillageId = savedVill;
    });

    if (token != null && token.isNotEmpty) {
      await _fetchProjects();
    }
  }

  Future<void> _fetchProjects() async {
    if (_authToken == null) return;
    try {
      final response = await ApiService.get(ApiEndpoints.projects);
      if (response.statusCode != 200) return;

      final data = jsonDecode(response.body);
      final projects = List<dynamic>.from(data['data'] ?? []);

      // Build department list from projects
      final Map<String, Map<String, dynamic>> deptMap = {};
      for (final p in projects) {
        final deptId = p['department_id']?.toString();
        if (deptId != null && deptId.isNotEmpty && deptId != 'null') {
          deptMap.putIfAbsent(deptId, () => {
            'id': p['department_id'],
            'name': p['department_name'] ?? 'Department $deptId',
          });
        }
      }

      setState(() {
        _allProjects = projects;
        _departments = deptMap.values.toList();

        if (_selectedDepartmentId != null) {
          final exists = _departments.any((d) => d['id'].toString() == _selectedDepartmentId);
          if (!exists) {
            _selectedDepartmentId = null;
            _selectedProjectId = null;
            _selectedAreaId = null;
            _selectedVillageId = null;
          }
        }
      });

      if (_selectedDepartmentId != null) {
        _filterProjectsByDepartment(_selectedDepartmentId!);
      } else if (_departments.isEmpty) {
        setState(() => _projects = projects);
      } else {
        setState(() => _projects = []);
      }

      if (_selectedProjectId != null) {
        await _fetchAreas(_selectedProjectId!);
      }
      if (_selectedProjectId != null && _selectedAreaId != null) {
        await _fetchVillages(_selectedProjectId!, _selectedAreaId!);
      }
      if (_selectedVillageId != null) {
        _fetchDashboard(_selectedVillageId!);
      }
    } catch (e) {
      debugPrint("Error fetching projects: $e");
    }
  }

  void _filterProjectsByDepartment(String deptId) {
    final filtered = _allProjects
        .where((p) => p['department_id']?.toString() == deptId)
        .toList();
    setState(() {
      _projects = filtered;
      if (_selectedProjectId != null) {
        final exists = _projects.any((p) => p['id'].toString() == _selectedProjectId);
        if (!exists) {
          _selectedProjectId = null;
          _selectedAreaId = null;
          _selectedVillageId = null;
          _areas = [];
          _villages = [];
        }
      }
    });
  }

  Future<void> _fetchAreas(String projectId) async {
    setState(() {
      _loadingAreas = true;
      _areas = [];
    });
    try {
      final response = await ApiService.get(
        '${ApiEndpoints.areas}?project_id=$projectId',
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final areas = List<dynamic>.from(data['data'] ?? []);
        setState(() {
          _areas = areas;
          if (_selectedAreaId != null) {
            final exists = _areas.any((a) => a['id'].toString() == _selectedAreaId);
            if (!exists) {
              _selectedAreaId = null;
              _selectedVillageId = null;
              _villages = [];
              setAsyncItem(SELECTED_AREA_ID_KEY, '');
              setAsyncItem(SELECTED_VILLAGE_ID_KEY, '');
            }
          }
        });
      }
    } catch (e) {
      debugPrint("Error fetching areas: $e");
    } finally {
      if (mounted) setState(() => _loadingAreas = false);
    }
  }

  Future<void> _fetchVillages(String projectId, String areaId) async {
    setState(() {
      _loadingVillages = true;
      _villages = [];
    });
    try {
      final response = await ApiService.get(
        '${ApiEndpoints.villages}?project_id=$projectId&area_id=$areaId',
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final villages = List<dynamic>.from(data['data'] ?? []);
        setState(() {
          _villages = villages;
          if (_selectedVillageId != null) {
            final exists = _villages.any((v) => v['id'].toString() == _selectedVillageId);
            if (!exists) {
              _selectedVillageId = null;
              setAsyncItem(SELECTED_VILLAGE_ID_KEY, '');
            }
          }
        });
      }
    } catch (e) {
      debugPrint("Error fetching villages: $e");
    } finally {
      if (mounted) setState(() => _loadingVillages = false);
    }
  }

  Future<void> _fetchDashboard(String villageId) async {
    if (_authToken == null) return;
    try {
      final response = await ApiService.get(
        '${ApiEndpoints.dashboardVillage}?village_id=$villageId',
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _stats = data['data']?['statistics'];
        });
      }
    } catch (e) {
      setState(() => _stats = null);
    }
  }

  Future<void> _onDepartmentChanged(String? val) async {
    if (val == null) return;
    final dept = _departments.firstWhere(
      (d) => d['id'].toString() == val,
      orElse: () => {'name': ''},
    );
    setState(() {
      _selectedDepartmentId = val;
      _selectedProjectId = null;
      _selectedAreaId = null;
      _selectedVillageId = null;
      _areas = [];
      _villages = [];
      _stats = null;
    });
    await setAsyncItem(SELECTED_DEPARTMENT_ID_KEY, val);
    await setAsyncItem(SELECTED_DEPARTMENT_NAME_KEY, dept['name']?.toString() ?? '');
    await setAsyncItem(SELECTED_PROJECT_ID_KEY, '');
    await setAsyncItem(SELECTED_AREA_ID_KEY, '');
    await setAsyncItem(SELECTED_VILLAGE_ID_KEY, '');
    _filterProjectsByDepartment(val);
    globalSelectionChanged.value++;
  }

  Future<void> _onProjectChanged(String? val) async {
    if (val == null) return;
    final proj = _projects.firstWhere(
      (p) => p['id'].toString() == val,
      orElse: () => {'name': ''},
    );
    setState(() {
      _selectedProjectId = val;
      _selectedAreaId = null;
      _selectedVillageId = null;
      _villages = [];
      _stats = null;
    });
    await setAsyncItem(SELECTED_PROJECT_ID_KEY, val);
    await setAsyncItem(SELECTED_PROJECT_NAME_KEY, proj['name']?.toString() ?? '');
    await setAsyncItem(SELECTED_AREA_ID_KEY, '');
    await setAsyncItem(SELECTED_AREA_NAME_KEY, '');
    await setAsyncItem(SELECTED_VILLAGE_ID_KEY, '');
    await setAsyncItem(SELECTED_VILLAGE_NAME_KEY, '');

    // Persist department from project when available
    if (proj['department_id'] != null) {
      await setAsyncItem(SELECTED_DEPARTMENT_ID_KEY, proj['department_id'].toString());
      await setAsyncItem(
        SELECTED_DEPARTMENT_NAME_KEY,
        proj['department_name']?.toString() ?? '',
      );
    }

    await _fetchAreas(val);
    globalSelectionChanged.value++;
  }

  Future<void> _onAreaChanged(String? val) async {
    if (val == null || _selectedProjectId == null) return;
    final area = _areas.firstWhere(
      (a) => a['id'].toString() == val,
      orElse: () => {'name': '', 'dropdown_label': ''},
    );
    final areaName = area['dropdown_label'] ?? area['name'] ?? '';
    setState(() {
      _selectedAreaId = val;
      _selectedVillageId = null;
      _stats = null;
    });
    await setAsyncItem(SELECTED_AREA_ID_KEY, val);
    await setAsyncItem(SELECTED_AREA_NAME_KEY, areaName.toString());
    await setAsyncItem(SELECTED_VILLAGE_ID_KEY, '');
    await setAsyncItem(SELECTED_VILLAGE_NAME_KEY, '');
    await _fetchVillages(_selectedProjectId!, val);
    globalSelectionChanged.value++;
  }

  Future<void> _onVillageChanged(String? val) async {
    if (val == null) return;
    final vill = _villages.firstWhere(
      (v) => v['id'].toString() == val,
      orElse: () => {'name': '', 'dropdown_label': ''},
    );
    final villName = vill['dropdown_label'] ?? vill['name'] ?? '';
    setState(() {
      _selectedVillageId = val;
    });
    await setAsyncItem(SELECTED_VILLAGE_ID_KEY, val);
    await setAsyncItem(SELECTED_VILLAGE_NAME_KEY, villName.toString());
    if (vill['tehsil_id'] != null) {
      await setAsyncItem(SELECTED_TEHSIL_ID_KEY, vill['tehsil_id'].toString());
    }
    _fetchDashboard(val);
    globalSelectionChanged.value++;
  }


  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<Locale>(
      valueListenable: Localization.currentLocale,
      builder: (context, locale, child) {
        return Consumer<ThemeProvider>(
          builder: (context, themeProvider, _) {
            return Scaffold(
              body: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: themeProvider.currentGradientColors,
                    stops: const [0.0, 0.6, 1.0],
                  ),
                ),
            child: SafeArea(
              bottom: false, // Let content flow behind bottom nav
              child: Column(
                children: [
                  const SizedBox(height: 8),
                  // Header with Logo
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 5, 20, 10),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                            Image.asset(
                              AppAssets.newIcon, 
                              height: 30,
                              fit: BoxFit.contain,
                            ),
                            Row(
                               children: [
                                  const LanguageSelector(),
                                  const SizedBox(width: 8),
                                  // Theme Toggle
                                   Container(
                                     decoration: BoxDecoration(
                                       color: themeProvider.glassColor,
                                       shape: BoxShape.circle,
                                       border: Border.all(color: themeProvider.glassBorderColor),
                                     ),
                                     child: IconButton(
                                       onPressed: () => themeProvider.toggleTheme(),
                                       icon: AnimatedSwitcher(
                                         duration: const Duration(milliseconds: 300),
                                         transitionBuilder: (child, animation) {
                                           return RotationTransition(
                                             turns: animation,
                                             child: child,
                                           );
                                         },
                                         child: Icon(
                                           themeProvider.isDarkMode ? Icons.wb_sunny : Icons.nightlight_round,
                                           key: ValueKey(themeProvider.isDarkMode),
                                           color: Colors.white,
                                           size: 20,
                                         ),
                                       ),
                                       padding: EdgeInsets.zero,
                                       constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                                     ),
                                   ),
                               ]
                            )
                      ],
                    ),
                  ),

                  // Scrollable Content
                  Expanded(
                    child: SingleChildScrollView(
                      physics: const BouncingScrollPhysics(),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 0),
                        child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                // Filter Selection Box - Modernized
                                Container(
                            padding: const EdgeInsets.all(20),
                            decoration: BoxDecoration(
                              color: themeProvider.glassColor,
                              borderRadius: BorderRadius.circular(24),
                              border: Border.all(color: themeProvider.glassBorderColor),
                              boxShadow: [
                                 BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 10, offset: const Offset(0, 5))
                              ]
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                _buildDropdownLabel("${Localization.t('select_dept_label')} *"),
                                _buildDropdown(
                                   icon: Icons.business_rounded,
                                   value: _selectedDepartmentId,
                                   hint: Localization.t('select_dept_hint'),
                                   items: _departments.map((d) => DropdownMenuItem(
                                      value: d['id'].toString(),
                                      child: Text(d['name']),
                                   )).toList(),
                                   onChanged: (val) => _onDepartmentChanged(val?.toString()),
                                ),
                                
                                const SizedBox(height: 20), 
                                
                                _buildDropdownLabel("${Localization.t('select_project_label')} *"),
                                _buildDropdown(
                                   icon: Icons.assignment_rounded,
                                   value: _selectedProjectId,
                                   hint: Localization.t('select_project_hint'),
                                   items: _projects.map((p) => DropdownMenuItem(
                                      value: p['id'].toString(),
                                      child: Text(p['name'], overflow: TextOverflow.ellipsis),
                                   )).toList(),
                                   onChanged: (val) => _onProjectChanged(val?.toString()),
                                ),

                                const SizedBox(height: 20),

                                _buildDropdownLabel("${Localization.t('select_area_label')} *"),
                                _buildDropdown(
                                   icon: Icons.map_rounded,
                                   value: _selectedAreaId,
                                   hint: _loadingAreas
                                       ? 'Loading...'
                                       : (_selectedProjectId == null
                                           ? Localization.t('select_project_hint')
                                           : Localization.t('select_area_hint')),
                                   items: _areas.map((a) => DropdownMenuItem(
                                      value: a['id'].toString(),
                                      child: Text(
                                        '${a['dropdown_label'] ?? a['name'] ?? ''}'
                                        '${a['village_count'] != null ? ' (${a['village_count']})' : ''}',
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                   )).toList(),
                                   onChanged: _selectedProjectId == null
                                       ? null
                                       : (val) => _onAreaChanged(val?.toString()),
                                ),

                                const SizedBox(height: 20),

                                _buildDropdownLabel("${Localization.t('select_village_label')} *"),
                                _buildDropdown(
                                   icon: Icons.location_on_rounded,
                                   value: _selectedVillageId,
                                   hint: _loadingVillages
                                       ? 'Loading...'
                                       : (_selectedAreaId == null
                                           ? Localization.t('select_area_hint')
                                           : Localization.t('select_village_hint')),
                                   items: _villages.map((v) => DropdownMenuItem(
                                      value: v['id'].toString(),
                                      child: Text(
                                        v['dropdown_label'] ?? v['name'] ?? '',
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                   )).toList(),
                                   onChanged: _selectedAreaId == null
                                       ? null
                                       : (val) => _onVillageChanged(val?.toString()),
                                ),
                              ],
                            ),
                          ),

                          const SizedBox(height: 12),

                           if (_selectedVillageId != null && _stats != null) ...[
                            // Dashboard Container
                            Container(
                              padding: const EdgeInsets.all(0),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.08),
                                borderRadius: BorderRadius.circular(28),
                                border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Padding(
                                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                                    child: Row(
                                      children: [
                                        Container(
                                          padding: const EdgeInsets.all(6),
                                          decoration: BoxDecoration(color: Colors.white12, borderRadius: BorderRadius.circular(10)),
                                          child: const Icon(
                                            Icons.analytics_rounded, 
                                            size: 18, 
                                            color: Colors.white
                                          ),
                                        ),
                                        const SizedBox(width: 12),
                                        Text(
                                          Localization.t('dashboard_stats').toUpperCase(), 
                                          style: const TextStyle(
                                             color: Colors.white, 
                                             fontSize: 14, 
                                             fontWeight: FontWeight.w800, 
                                             letterSpacing: 1.2
                                          )
                                        ),
                                      ],
                                    ),
                                  ),
                                  Padding(
                                    padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
                                    child: GridView.count(
                                       shrinkWrap: true,
                                       crossAxisCount: 2,
                                       crossAxisSpacing: 12,
                                       mainAxisSpacing: 12,
                                       childAspectRatio: 1.05, 
                                       physics: const NeverScrollableScrollPhysics(),
                                       children: [
                                          _buildStatCard(Localization.t('total_surveys'), _stats!['total_surveys'] ?? 0, const Color(0xFF104E8B), Icons.grid_view_rounded, "total"),
                                          _buildStatCard(Localization.t('approved'), _stats!['approved'] ?? 0, const Color(0xFF27AE60), Icons.check_circle_rounded, "approved"),
                                          _buildStatCard(Localization.t('rejected'), _stats!['rejected'] ?? 0, const Color(0xFFE74C3C), Icons.cancel_rounded, "rejected"),
                                          _buildStatCard(Localization.t('pending'), _stats!['pending'] ?? 0, const Color(0xFFF39C12), Icons.hourglass_empty_rounded, "pending"),
                                       ],
                                     ),
                                  ),
                                ],
                              ),
                            ),
                          ] else ...[
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.symmetric(vertical: 60),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.touch_app_outlined, size: 64, color: Colors.white.withValues(alpha: 0.2)),
                                  const SizedBox(height: 16),
                                  Text(
                                    Localization.t('msg_select_village'), 
                                    style: TextStyle(color: Colors.white.withValues(alpha: 0.5), fontSize: 16, fontWeight: FontWeight.w500)
                                  ), 
                                ],
                              ),
                            ),
                          ],
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
          },
        );
      },
    );
  }

  Widget _buildDropdownLabel(String label) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 2.0, left: 2.0), 
      child: Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 11)), 
    );
  }

  Widget _buildDropdown({required IconData icon, required String? value, required String hint, required List<DropdownMenuItem<Object>>? items, required Function(dynamic)? onChanged}) {
     final isDark = Theme.of(context).brightness == Brightness.dark;
     final bgColor = isDark ? AppColors.darkInputBg : Colors.white;
     final textColor = isDark ? AppColors.darkText : const Color(0xFF2D3436);
     final iconColor = isDark ? Colors.blue[300] : const Color(0xFF104E8B);
     final enabled = onChanged != null;

     return Opacity(
       opacity: enabled ? 1.0 : 0.55,
       child: Container(
       height: 40,
       padding: const EdgeInsets.symmetric(horizontal: 10),
       decoration: BoxDecoration(
         color: bgColor,
         borderRadius: BorderRadius.circular(10),
         boxShadow: [
           BoxShadow(color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.12), blurRadius: 6, offset: const Offset(0, 3))
         ]
       ),
       child: Row(
         children: [
           Icon(icon, size: 18, color: iconColor),
           const SizedBox(width: 10),
           Expanded(
             child: DropdownButtonHideUnderline(
               child: DropdownButton(
                 value: value,
                 hint: Text(hint, style: TextStyle(color: isDark ? Colors.grey[400] : Colors.grey.shade600, fontSize: 13, fontWeight: FontWeight.w500)),
                 isExpanded: true,
                 icon: Icon(Icons.arrow_drop_down, color: isDark ? Colors.grey[400] : Colors.black54),
                 items: items,
                 onChanged: onChanged,
                 dropdownColor: bgColor,
                 style: TextStyle(color: textColor, fontSize: 14, fontWeight: FontWeight.w700),
                 borderRadius: BorderRadius.circular(10),
               ),
             ),
           ),
         ],
       ),
     ),
     );
  }

    Widget _buildStatCard(String title, dynamic value, Color color, IconData icon, String filterKey) {
      final isDark = Theme.of(context).brightness == Brightness.dark;
      final cardBg = isDark ? AppColors.darkInputBg : Colors.white;
      final titleColor = isDark ? Colors.grey[400] : Colors.blueGrey.shade800;

      return InkWell(
        onTap: () {
           globalSurveyFilter = filterKey;
           if (widget.onSwitchTab != null) {
             widget.onSwitchTab!(1);
           }
        },
        borderRadius: BorderRadius.circular(24),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
             color: cardBg,
             borderRadius: BorderRadius.circular(24),
             boxShadow: [
                BoxShadow(
                  color: color.withValues(alpha: isDark ? 0.05 : 0.12), 
                  blurRadius: 12, 
                  offset: const Offset(0, 6)
                )
             ],
             border: Border.all(color: color.withValues(alpha: isDark ? 0.1 : 0.05), width: 1),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Container(
                     padding: const EdgeInsets.all(10),
                     decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.12), 
                        borderRadius: BorderRadius.circular(16)
                     ),
                     child: Icon(icon, color: color, size: 24),
                  ),
                  Text(
                    value.toString(), 
                    style: TextStyle(
                      color: color, 
                      fontWeight: FontWeight.w900, 
                      fontSize: 34, 
                      letterSpacing: -1
                    )
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                title.toUpperCase(), 
                style: TextStyle(
                  color: titleColor, 
                  fontSize: 12, 
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.8
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ), 
            ],
          ),
        ),
      );
    }

  Widget _buildLangOption(String code, String label, bool isSelected) {
    return InkWell(
      onTap: () => Localization.changeLanguage(code),
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? Colors.white : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? const Color(0xFF104E8B) : Colors.white,
            fontWeight: FontWeight.bold,
            fontSize: 12
          ),
        ),
      ),
    );
  }
}
