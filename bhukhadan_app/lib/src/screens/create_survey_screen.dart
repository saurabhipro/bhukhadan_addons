import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../utils/storage.dart';
import '../services/api_service.dart';
import '../components/text_input_field.dart';
import '../components/custom_button.dart';
import '../components/user_picker_modal.dart';
import '../models/picker_user.dart';
import '../utils/localization.dart';
import '../constants/api_constants.dart';
import 'package:provider/provider.dart';
import '../utils/theme_provider.dart';
import '../components/language_selector.dart';
import '../utils/colors.dart';
import '../services/screenshot_audit_service.dart';

class CreateSurveyScreen extends StatefulWidget {
  final Map<String, dynamic>? prefilledData;
  
  const CreateSurveyScreen({super.key, this.prefilledData});

  @override
  State<CreateSurveyScreen> createState() => _CreateSurveyScreenState();
}

class _CreateSurveyScreenState extends State<CreateSurveyScreen> {
  // Scroll Controller
  final ScrollController _scrollController = ScrollController();
  
  // Field Keys
  final Map<String, GlobalKey> _fieldKeys = {
    'project': GlobalKey(),
    'department': GlobalKey(),
    'village': GlobalKey(),
    'district': GlobalKey(),
    'tehsil': GlobalKey(),
    'khasra': GlobalKey(),
    'totalArea': GlobalKey(),
    'acquiredArea': GlobalKey(),
    'landowner': GlobalKey(),
    'hasTradedLand': GlobalKey(),
    'tradedLandArea': GlobalKey(),
    'cropType': GlobalKey(),
    'irrigationType': GlobalKey(),
    'hasTrees': GlobalKey(),
    'treeLines': GlobalKey(),
    'hasHouse': GlobalKey(),
    'houseType': GlobalKey(),
    'houseArea': GlobalKey(),
    'hasShed': GlobalKey(),
    'shedArea': GlobalKey(),
    'hasWell': GlobalKey(),
    'wellType': GlobalKey(),
    'wellCount': GlobalKey(),
    'hasTubewell': GlobalKey(),
    'tubewellCount': GlobalKey(),
    'hasPond': GlobalKey(),
  };

  // State Variables
  bool _isEditMode = false;
  String? _surveyId;
  String? _surveyName; // For display in edit mode

  // Selections
  String? _selectedProjectId;
  String? _selectedAreaId;
  String? _selectedVillageId;
  String? _selectedDepartmentId;
  String? _selectedDistrictId;
  String? _selectedTehsilId;
  
  // Display Names
  String _projectName = "";
  String _areaName = "";
  String _villageName = "";
  String _departmentName = "";
  String _districtName = "";
  String _tehsilName = "";

  // Form Controllers
  final _khasraController = TextEditingController();
  final _totalAreaController = TextEditingController();
  final _acquiredAreaController = TextEditingController();
  final _tradedLandAreaController = TextEditingController();
  final _houseAreaController = TextEditingController();
  final _shedAreaController = TextEditingController();
  final _wellCountController = TextEditingController();
  final _tubewellCountController = TextEditingController();
  final _remarksController = TextEditingController();
  final _distanceController = TextEditingController();
  final _mbDeclDateController = TextEditingController();

  // Dropdown States
  String? _cropType;
  String? _irrigationType = 'unirrigated'; // Default for radio
  String? _hasHouse = 'no';
  String? _houseType = 'pakka'; // Default for radio if toggled yes
  String? _hasShed = 'no';
  String? _hasWell = 'no';
  String? _wellType = 'pakka'; // Default for radio if toggled yes
  String? _hasTubewell = 'no';
  String? _hasPond = 'no';
  String? _hasTrees = 'no';
  String? _hasTradedLand = 'no';
  String? _surveyType = 'rural';

  // Document checklist (Measuring Book)
  bool _mbDeclNoClaim = false;
  bool _mbDeclDocs = false;
  bool _mbDeclGps = false;

  // Lists
  List<PickerUser> _landowners = [];
  List<PickerUser> _selectedLandowners = [];
  List<dynamic> _treesList = [];
  List<dynamic> _landTypes = [];
  List<Map<String, dynamic>> _treeLines = []; 

  // Loading & Errors
  bool _isLoading = false;
  bool _isInitialLoading = false;
  Map<String, String> _errors = {};

  // Change Detection (Basic)
  Map<String, dynamic>? _originalData;

  @override
  void initState() {
    super.initState();
    final editId = widget.prefilledData?['id'];
    ScreenshotAuditService.instance.setContext(
      screenName: editId != null ? 'Edit Survey' : 'Create Survey',
      surveyId: editId is int ? editId : int.tryParse('${editId ?? ''}'),
      clearSurvey: editId == null,
    );
    _initScreen();
  }

  Future<void> _initScreen() async {
    setState(() => _isInitialLoading = true);
    await Localization.loadLanguage();
    await _fetchLandTypes();
    await _fetchTrees();
    await _loadInitialData();
    setState(() => _isInitialLoading = false);
  }

  Future<void> _loadInitialData() async {
    // 1. Handle Edit/Copy Mode
    if (widget.prefilledData != null) {
       if (widget.prefilledData!['id'] != null) {
          // Edit Mode: Fetch full details from API to ensure all fields are populated
          _isEditMode = true;
          _surveyId = widget.prefilledData!['id'].toString();
          await _fetchSurveyDetails(_surveyId!);
       } else {
          // Copy Mode (New survey but prefilled): Use data as is
          _populateForm(widget.prefilledData!);
          
          // Fallback: If names are missing (e.g. copied from list with sparse data), try to use storage values if context matches
           // Fallback: Default to current global selection if fields are missing in cloned data
          if (_projectName.isEmpty) {
             final globalId = await getAsyncItem(SELECTED_PROJECT_ID_KEY);
             if (_selectedProjectId == null || _selectedProjectId == globalId) {
                _selectedProjectId = globalId;
                final val = await getAsyncItem(SELECTED_PROJECT_NAME_KEY);
                if (val != null) setState(() => _projectName = val);
             }
          }
          if (_areaName.isEmpty) {
             final globalId = await getAsyncItem(SELECTED_AREA_ID_KEY);
             if (_selectedAreaId == null || _selectedAreaId == globalId) {
                _selectedAreaId = globalId;
                final val = await getAsyncItem(SELECTED_AREA_NAME_KEY);
                if (val != null) setState(() => _areaName = val);
             }
          }
          
          if (_departmentName.isEmpty) {
             final globalId = await getAsyncItem(SELECTED_DEPARTMENT_ID_KEY);
             if (_selectedDepartmentId == null || _selectedDepartmentId == globalId) {
                _selectedDepartmentId = globalId;
                final val = await getAsyncItem(SELECTED_DEPARTMENT_NAME_KEY);
                if (val != null) setState(() => _departmentName = val);
             }
          }

           // Try to load District/Tehsil/Village names from storage if village matches or is missing (Clone Scenario)
           final globalVillageId = await getAsyncItem(SELECTED_VILLAGE_ID_KEY);
           if (_selectedVillageId == globalVillageId) {
               if (_villageName.isEmpty) {
                  final val = await getAsyncItem(SELECTED_VILLAGE_NAME_KEY);
                  if (val != null) setState(() => _villageName = val);
               }
               
               // Populate District ID and Name if missing
               if (_selectedDistrictId == null) {
                  _selectedDistrictId = await getAsyncItem(SELECTED_DISTRICT_ID_KEY);
                  if (_districtName.isEmpty) {
                     final val = await getAsyncItem(SELECTED_DISTRICT_NAME_KEY);
                     if (val != null) setState(() => _districtName = val);
                  }
               }
               
               // Populate Tehsil ID and Name if missing (Fix for Tehsil is missing error on clone)
               if (_selectedTehsilId == null) {
                  _selectedTehsilId = await getAsyncItem(SELECTED_TEHSIL_ID_KEY);
                  if (_tehsilName.isEmpty) {
                     final val = await getAsyncItem(SELECTED_TEHSIL_NAME_KEY);
                     if (val != null) setState(() => _tehsilName = val);
                  }
               }
           }
       }
    } else {
       // 2. New Mode: Load defaults from storage
       _selectedProjectId = await getAsyncItem(SELECTED_PROJECT_ID_KEY);
       _selectedAreaId = await getAsyncItem(SELECTED_AREA_ID_KEY);
       _selectedDepartmentId = await getAsyncItem(SELECTED_DEPARTMENT_ID_KEY);
       _selectedVillageId = await getAsyncItem(SELECTED_VILLAGE_ID_KEY);
       
       _projectName = await getAsyncItem(SELECTED_PROJECT_NAME_KEY) ?? "";
       _areaName = await getAsyncItem(SELECTED_AREA_NAME_KEY) ?? "";
       _departmentName = await getAsyncItem(SELECTED_DEPARTMENT_NAME_KEY) ?? "";
       _villageName = await getAsyncItem(SELECTED_VILLAGE_NAME_KEY) ?? "";
       
       _selectedDistrictId = await getAsyncItem(SELECTED_DISTRICT_ID_KEY);
       _districtName = await getAsyncItem(SELECTED_DISTRICT_NAME_KEY) ?? "";
       _selectedTehsilId = await getAsyncItem(SELECTED_TEHSIL_ID_KEY);
       _tehsilName = await getAsyncItem(SELECTED_TEHSIL_NAME_KEY) ?? "";
    }

     // 3. Always fetch landowners and other info if village is selected
     if (_selectedVillageId != null) {
        await _fetchVillageInfo(_selectedVillageId!);
        await _fetchLandowners(_selectedVillageId!);
     }
  }

  Future<void> _fetchVillageInfo(String villageId) async {
     // Fetch village details to get district and tehsil names if missing
     // Relaxed check: Fetch if names AND IDs are missing or incomplete
     if (_districtName.isNotEmpty && _tehsilName.isNotEmpty && _selectedDistrictId != null && _selectedTehsilId != null) return;
     
     debugPrint("Fetching Village Info for ID: $villageId");
     try {
        final uri = '${ApiEndpoints.dashboardVillage}?village_id=$villageId';
        debugPrint("API URL: $uri");
        final response = await ApiService.get(uri);
        debugPrint("Village API Status: ${response.statusCode}");
        debugPrint("Village API Response: ${response.body}");
        
        if (response.statusCode == 200) {
           final data = jsonDecode(response.body);
           // Handle both nested and flat structures
           final v = (data['data'] != null && data['data'] is Map && data['data'].containsKey('village')) 
               ? data['data']['village'] 
               : (data['data'] ?? data);

           if (v != null && v is Map) {
              debugPrint("Village Info Resolved: $v");
              setState(() {
                 if (v.containsKey('district_name')) _districtName = v['district_name'] ?? _districtName;
                 if (v.containsKey('tehsil_name')) _tehsilName = v['tehsil_name'] ?? _tehsilName;
                 if (_selectedDistrictId == null && v.containsKey('district_id')) {
                    _selectedDistrictId = v['district_id'].toString();
                 }
                 if (_selectedTehsilId == null && v.containsKey('tehsil_id')) {
                    _selectedTehsilId = v['tehsil_id'].toString();
                 }
              });
           } else {
              debugPrint("Failed to resolve village info from response: ${data['data'] ?? data}");
           }
        }
     } catch (e) {
        debugPrint("Error fetching village info: $e");
     }
  }

  Future<void> _fetchSurveyDetails(String id) async {
    try {
      final response = await ApiService.get('${ApiEndpoints.survey}/$id');
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body)['data'];
        _originalData = data; // Keep for comparison if needed
        _populateForm(data);
        
        if (_selectedVillageId != null) {
           await _fetchLandowners(_selectedVillageId!);
        }
      } else {
        throw Exception("Failed to load survey details");
      }
    } catch (e) {
      debugPrint("Error fetching survey details: $e");
      // Handle error navigation or alert
    }
  }

  void _populateForm(Map<String, dynamic> rawData) {
    debugPrint("Populating form with data: $rawData");
    // Handle multiple potential nesting levels: { "data": { "survey": { ... } } } or { "survey": { ... } } or { ... }
    Map<String, dynamic> data;
    if (rawData.containsKey('survey') && rawData['survey'] is Map) {
       data = rawData['survey'] as Map<String, dynamic>;
    } else if (rawData.containsKey('data') && rawData['data'] is Map && (rawData['data'] as Map).containsKey('survey')) {
       data = rawData['data']['survey'] as Map<String, dynamic>;
    } else {
       data = rawData;
    }

    setState(() {
      _surveyName = data['name'] ?? data['survey_name'];
      
      _selectedProjectId = data['project_id']?.toString();
      _selectedAreaId = data['area_id']?.toString();
      _selectedVillageId = data['village_id']?.toString();
      _selectedDepartmentId = data['department_id']?.toString();
      _selectedDistrictId = data['district_id']?.toString(); // Might need logic if nested
      _selectedTehsilId = data['tehsil_id']?.toString();
      
      _projectName = data['project_name'] ?? "";
      _areaName = data['area_name'] ?? "";
      _villageName = data['village_name'] ?? "";
      _departmentName = data['department_name'] ?? "";
      _districtName = data['district_name'] ?? "";
      _tehsilName = data['tehsil_name'] ?? "";
      
      _khasraController.text = data['khasra_number'] ?? "";
      _totalAreaController.text = data['total_area']?.toString() ?? "";
      _acquiredAreaController.text = data['acquired_area']?.toString() ?? "";
      
      _mbDeclDateController.text = data['mb_owner_decl_date']?.toString() ?? "";
      _mbDeclNoClaim = data['mb_decl_no_claim_pending'] == true;
      _mbDeclDocs = data['mb_decl_documents_received'] == true;
      _mbDeclGps = data['mb_decl_gps_photo_video'] == true;
      
      String toYesNo(dynamic val, [bool fallbackToNo = true]) {
        if (val == null) return fallbackToNo ? 'no' : 'no'; // Default to 'no' if null
        if (val is bool) return val ? 'yes' : 'no';
        final s = val.toString().toLowerCase();
        if (s == '1' || s == 'yes' || s == 'true') return 'yes';
        return 'no';
      }

      _cropType = data['crop_type_id']?.toString()
          ?? data['crop_type']?.toString()
          ?? data['land_type_id']?.toString();
      _irrigationType = data['irrigation_type'] ?? data['irrigation'];
      _surveyType = data['survey_type'] ?? data['type'] ?? 'rural';

      _hasHouse = toYesNo(data['has_house']);
      final rawHouseType = data['house_type'];
      if (rawHouseType is String && rawHouseType.isNotEmpty) {
         _houseType = rawHouseType;
      }
      _houseAreaController.text = data['house_area']?.toString() ?? "";
      
      _hasShed = toYesNo(data['has_shed']);
      _shedAreaController.text = data['shed_area']?.toString() ?? "";
      
      _hasWell = toYesNo(data['has_well']);
      final rawWellType = data['well_type'];
      if (rawWellType is String && rawWellType.isNotEmpty) {
         _wellType = rawWellType;
      }
      _wellCountController.text = data['well_count']?.toString() ?? "";
      
      _hasTubewell = toYesNo(data['has_tubewell']);
      _tubewellCountController.text = data['tubewell_count']?.toString() ?? "";
      
      _hasPond = toYesNo(data['has_pond']);
      _hasTradedLand = toYesNo(data['has_traded_land']);
      _tradedLandAreaController.text = data['traded_land_area']?.toString() ?? "";

      String rawRemarks = data['remarks'] ?? "";
      _remarksController.text = rawRemarks;
      
      // Parse Distance
      String dist = data['distance_from_main_road']?.toString()
          ?? data['distance']?.toString()
          ?? "";
      if (dist.isEmpty && rawRemarks.contains("Distance: ")) {
         try {
            dist = rawRemarks.split("Distance: ")[1].split("m")[0];
            // Optionally clean up remarks to not show the prefix in the field
            if (rawRemarks.contains("m. ")) {
               _remarksController.text = rawRemarks.split("m. ")[1];
            }
         } catch (_) {}
      }
      _distanceController.text = dist;

      // Tree Lines
      if (data['tree_lines'] != null && (data['tree_lines'] as List).isNotEmpty) {
        _hasTrees = 'yes';
        _treeLines = (data['tree_lines'] as List).map<Map<String, dynamic>>((l) => {
          'tree_master_id': l['tree_master_id'],
          'quantity': l['quantity']?.toString() ?? '',
          'development_stage': l['development_stage']?.toString(),
          'girth_cm': l['girth_cm']?.toString() ?? '',
          'tree_name': l['tree_name']
        }).toList();
      } else {
        _hasTrees = 'no';
        _treeLines = [];
      }

      // Robust Landowners Population - checking all possible keys in both data and rawData
      final possibleKeys = [
         'landowner_ids', 'landowners', 'owners', 
         'landowner_master_ids', 'survey_landowners', 
         'landowner_details', 'landowner_id'
      ];
      
      dynamic rawLandowners;
      for (var key in possibleKeys) {
         if (data[key] != null) {
            rawLandowners = data[key];
            break;
         }
         if (rawData[key] != null) {
            rawLandowners = rawData[key];
            break;
         }
      }
                            
      if (rawLandowners != null) {
         debugPrint("Found rawLandowners: $rawLandowners");
         final List list = rawLandowners is List ? rawLandowners : [rawLandowners];
         _selectedLandowners = list.map((u) {
           if (u is Map) {
              final landowner = PickerUser.fromJson(u as Map<String, dynamic>);
              debugPrint("Parsed landowner from map: ${landowner.name} (ID: ${landowner.id})");
              return landowner;
           } else if (u != null) {
              final idStr = u.toString();
              debugPrint("Created placeholder for landowner ID: $idStr");
              return PickerUser(id: idStr, name: "ID: $idStr");
           }
           return null;
         }).whereType<PickerUser>().toList();
         
         debugPrint("Total selected landowners after population: ${_selectedLandowners.length}");
         if (_landowners.isNotEmpty) {
            _resolveSelectedLandownerNames();
         }
      } else {
         debugPrint("No landowners found in any expected keys: $possibleKeys");
         debugPrint("Available keys in data: ${data.keys.toList()}");
         debugPrint("Available keys in root response (rawData): ${rawData.keys.toList()}");
      }
    });
  }

  // --- API Fetches ---
  Future<void> _fetchTrees() async {
    try {
      final response = await ApiService.get('${ApiEndpoints.trees}?limit=100&offset=0');
      if (response.statusCode == 200) {
        setState(() => _treesList = jsonDecode(response.body)['data'] ?? []);
      }
    } catch(e) { debugPrint("Tree fetch error: $e"); }
  }
  
  Future<void> _fetchLandTypes() async {
    try {
      final response = await ApiService.get('${ApiEndpoints.landTypes}?limit=100&offset=0&active=true');
      if (response.statusCode == 200) {
        setState(() => _landTypes = jsonDecode(response.body)['data'] ?? []);
      }
    } catch(e) { debugPrint("LandType fetch error: $e"); }
  }

   Future<void> _fetchLandowners(String villageId) async {
    debugPrint("Fetching all available landowners for village: $villageId");
    try {
      final response = await ApiService.get('${ApiEndpoints.landowners}?village_id=$villageId&limit=100&offset=0');
      if (response.statusCode == 200) {
         final List list = jsonDecode(response.body)['data'] ?? [];
         debugPrint("Fetched ${list.length} available landowners for this village");
         setState(() {
           final fetchedLandowners = list.map((u) => PickerUser.fromJson(u)).toList();
           
           // Ensure any already selected landowners are in the list if they're not there
           // This prevents them from being "unselected" if they aren't in the first 100
           int addedCount = 0;
           for (var selected in _selectedLandowners) {
              if (!fetchedLandowners.any((l) => l.id == selected.id)) {
                 fetchedLandowners.add(selected);
                 addedCount++;
              }
           }
           if (addedCount > 0) debugPrint("Added $addedCount previously selected landowners to the pool");
           
           _landowners = fetchedLandowners;
           _resolveSelectedLandownerNames();
         });
      }
    } catch(e) { debugPrint("Landowner fetch error: $e"); }
  }

  void _resolveSelectedLandownerNames() {
    debugPrint("Resolving landowner names for ${_selectedLandowners.length} selections against ${_landowners.length} available pool");
    if (_selectedLandowners.isEmpty || _landowners.isEmpty) {
       debugPrint("Cannot resolve: selected=${_selectedLandowners.length}, pool=${_landowners.length}");
       return;
    }
    
    bool changed = false;
    final updatedList = _selectedLandowners.map((selected) {
      // Always try to resolve if name is basic placeholder
      if (selected.name == "Loading..." || selected.name.isEmpty || selected.name.startsWith("ID: ")) {
         debugPrint("  Attempting to resolve name for ID: ${selected.id}");
         final match = _landowners.firstWhere(
           (l) => l.id.toString() == selected.id.toString(), 
           orElse: () => selected
         );
         
         if (match != selected) {
           debugPrint("    Resolved match: ${match.name}");
           changed = true;
           return match;
         } else {
           debugPrint("    No match found in pool for ID: ${selected.id}");
         }
      }
      return selected;
    }).toList();
    
    if (changed) {
      debugPrint("Updated _selectedLandowners with resolved names");
      setState(() {
        _selectedLandowners = updatedList;
      });
    }
  }

  // --- Helpers ---
  bool _isNumber(String? s) => s != null && double.tryParse(s) != null;
  bool _isInteger(String? s) => s != null && int.tryParse(s) != null;
  
  void _scrollToFirstError() {
    if (_errors.isNotEmpty) {
      final firstKey = _errors.keys.first;
      final key = _fieldKeys[firstKey];
      if (key?.currentContext != null) {
        Scrollable.ensureVisible(
          key!.currentContext!,
          duration: const Duration(milliseconds: 300),
          alignment: 0.1,
        );
      }
    }
  }

  // --- Validation ---
  bool _validate() {
    final newErrors = <String, String>{};
    
    if (_selectedProjectId == null) newErrors['project'] = "Project is required";
    if (_selectedDepartmentId == null) newErrors['department'] = "Department is required";
    if (_selectedAreaId == null) newErrors['area'] = "Area is required";
    if (_selectedVillageId == null) newErrors['village'] = "Village is required";
    
    if (_surveyType == null) newErrors['surveyType'] = "Survey Type is required";

    if (_khasraController.text.trim().isEmpty) newErrors['khasra'] = "Khasra Number is required";
    
    if (_totalAreaController.text.trim().isEmpty) {
       newErrors['totalArea'] = "Total Area is required";
    } else if (!_isNumber(_totalAreaController.text)) {
       newErrors['totalArea'] = "Enter a valid number";
    }

    if (_acquiredAreaController.text.trim().isEmpty) {
       newErrors['acquiredArea'] = "Acquired Area is required";
    } else if (!_isNumber(_acquiredAreaController.text)) {
       newErrors['acquiredArea'] = "Enter a valid number";
    } else if (_isNumber(_totalAreaController.text) && 
               double.parse(_acquiredAreaController.text) > double.parse(_totalAreaController.text)) {
       newErrors['acquiredArea'] = "Cannot be greater than Total Area";
    }

    if (_selectedLandowners.isEmpty) newErrors['landowner'] = "Landowner is required";
    
    if (_hasTradedLand == 'yes') {
       if (_tradedLandAreaController.text.trim().isEmpty) {
          newErrors['tradedLandArea'] = "Area is required";
       } else if (!_isNumber(_tradedLandAreaController.text)) {
          newErrors['tradedLandArea'] = "Enter a valid number";
       }
    }

    if (_cropType == null) newErrors['cropType'] = "Land Type is required";
    if (_cropType != '13') { // Assuming 13 is the logic for not needing irrigation
       if (_irrigationType == null) newErrors['irrigationType'] = "Irrigation Type is required";
    }

    if (_hasTrees == 'yes') {
       if (_treeLines.isEmpty) {
         newErrors['treeLines'] = "Add at least one tree line";
       } else {
         for (int i = 0; i < _treeLines.length; i++) {
            if (_treeLines[i]['tree_master_id'] == null || 
                _treeLines[i]['development_stage'] == null || 
                _treeLines[i]['quantity'].toString().isEmpty) {
               newErrors['treeLines'] = "Complete all tree details";
               break; 
            }
         }
       }
    }

    if (_hasHouse == 'yes') {
       if (_houseType == null) newErrors['houseType'] = "House Type is required";
       if (_houseAreaController.text.trim().isEmpty) newErrors['houseArea'] = "Area is required";
    }

    if (_hasShed == 'yes') {
       if (_shedAreaController.text.trim().isEmpty) newErrors['shedArea'] = "Area is required";
    }

    if (_hasWell == 'yes') {
       if (_wellType == null) newErrors['wellType'] = "Well Type is required";
       if (_wellCountController.text.trim().isEmpty) newErrors['wellCount'] = "Count is required";
    }

    if (_hasTubewell == 'yes') {
       if (_tubewellCountController.text.trim().isEmpty) newErrors['tubewellCount'] = "Count is required";
    }

    if (_hasTradedLand == null && !_isEditMode) newErrors['hasTradedLand'] = "Selection required"; 
    // In edit mode original might be null if not set, but better enforce validation if interacted
    
    if (newErrors.isNotEmpty) {
       setState(() => _errors = newErrors);
       _scrollToFirstError();
       
       // Map keys to readable names
       final keyMap = {
          'project': 'Project', 'department': 'Department', 'village': 'Village',
          'khasra': 'Khasra Number', 'totalArea': 'Total Area', 'acquiredArea': 'Acquired Area',
          'landowner': 'Landowner', 'hasTradedLand': 'Diverted Land?', 'tradedLandArea': 'Diverted Area',
          'cropType': 'Land Type', 'irrigationType': 'Irrigation', 
          'hasTrees': 'Has Trees?', 'treeLines': 'Tree Details',
          'hasHouse': 'Has House?', 'houseType': 'House Type', 'houseArea': 'House Area',
          'hasShed': 'Has Shed?', 'shedArea': 'Shed Area',
          'hasWell': 'Has Well?', 'wellType': 'Well Type', 'wellCount': 'Well Count',
          'hasTubewell': 'Has Tubewell?', 'tubewellCount': 'Tubewell Count',
          'hasPond': 'Has Pond?'
       };
       
       final missingFields = newErrors.keys
           .map((k) => keyMap[k] ?? k) // Fallback to key if not found
           .take(3) // Show first 3
           .join(", ");
       
       final suffix = newErrors.length > 3 ? " and ${newErrors.length - 3} more" : "";
       
       final messenger = ScaffoldMessenger.of(context);
       messenger.showSnackBar(
          SnackBar(
             content: Text("Missing: $missingFields$suffix", style: const TextStyle(color: Colors.white)),
             backgroundColor: Colors.red,
             behavior: SnackBarBehavior.floating,
             action: SnackBarAction(
                label: 'Dismiss',
                textColor: Colors.white,
                onPressed: () => messenger.hideCurrentSnackBar(),
             ),
          )
       );
       return false;
    }
    return true;
  }

  // --- Submit ---
  Future<void> _handleSubmit() async {
    if (!_validate()) return;
    
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
         title: Text(_isEditMode ? "Confirm Update" : "Confirm Submission"),
         content: const Text("Are you sure you want to save these changes?"),
         actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text("Cancel"),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text("Yes"),
            )
         ],
      )
    );
    
    if (confirm != true) return;
    
    setState(() => _isLoading = true);
    try {
       final payload = {
          if (!_isEditMode) ...{
            'project_id': int.tryParse(_selectedProjectId ?? '0'),
            'area_id': int.tryParse(_selectedAreaId ?? '0'),
            'village_id': int.tryParse(_selectedVillageId ?? '0'),
            'department_id': int.tryParse(_selectedDepartmentId ?? '0'),
            'district_id': int.tryParse(_selectedDistrictId ?? '0'),
            'tehsil_id': int.tryParse(_selectedTehsilId ?? '0'),
            'survey_type': _surveyType,
          },
          if (_isEditMode && _selectedAreaId != null)
            'area_id': int.tryParse(_selectedAreaId ?? '0'),
          // Send names for proper display
          if (_districtName.isNotEmpty) 'district_name': _districtName,
          if (_tehsilName.isNotEmpty) 'tehsil_name': _tehsilName,
          
          'khasra_number': _khasraController.text.trim(),
          'total_area': double.tryParse(_totalAreaController.text),
          'acquired_area': double.tryParse(_acquiredAreaController.text),
          
          'crop_type_id': int.tryParse(_cropType ?? ''),
          'irrigation_type': (_cropType != '13') ? _irrigationType : null,
          
          'has_house': _hasHouse,
          'house_type': _hasHouse == 'yes' ? _houseType : null,
          'house_area': _hasHouse == 'yes' ? double.tryParse(_houseAreaController.text) : null,
          
          'has_shed': _hasShed,
          'shed_area': _hasShed == 'yes' ? double.tryParse(_shedAreaController.text) : null,
          
          'has_well': _hasWell,
          'well_type': _hasWell == 'yes' ? _wellType : null,
          'well_count': _hasWell == 'yes' ? int.tryParse(_wellCountController.text) : null,
          
          'has_tubewell': _hasTubewell,
          'tubewell_count': _hasTubewell == 'yes' ? int.tryParse(_tubewellCountController.text) : null,
          
          'has_pond': _hasPond,
          
          'has_traded_land': _hasTradedLand,
          'traded_land_area': _hasTradedLand == 'yes' ? double.tryParse(_tradedLandAreaController.text) : null,
          
          'landowner_ids': _selectedLandowners.map((u) {
             final idVal = int.tryParse(u.id);
             return idVal ?? u.id;
          }).toList(),
          
          'tree_lines': _hasTrees == 'yes' ? _treeLines.map((l) => {
             'tree_master_id': l['tree_master_id'],
             'quantity': int.tryParse(l['quantity'].toString()) ?? 0,
             'development_stage': l['development_stage'],
             'girth_cm': double.tryParse(l['girth_cm'].toString()) ?? 0,
          }).toList() : [],
          
          'remarks': _remarksController.text.trim(),
          'distance_from_main_road': double.tryParse(_distanceController.text) ?? 0.0,
          if (_mbDeclDateController.text.trim().isNotEmpty)
            'mb_owner_decl_date': _mbDeclDateController.text.trim(),
          'mb_decl_no_claim_pending': _mbDeclNoClaim,
          'mb_decl_documents_received': _mbDeclDocs,
          'mb_decl_gps_photo_video': _mbDeclGps,
          if (!_isEditMode) 'state': 'submitted', 
          // Don't override state in edit usually unless requested
          if (!_isEditMode) 'survey_date': DateTime.now().toIso8601String().split('T')[0],
       };

       http.Response response;
       if (_isEditMode) {
          response = await ApiService.patch('${ApiEndpoints.survey}/$_surveyId', payload);
       } else {
          response = await ApiService.post(ApiEndpoints.survey, payload);
       }
       
       if (response.statusCode == 200 || response.statusCode == 201) {
          if (!mounted) return;
          showDialog(
             context: context,
             builder: (_) => AlertDialog(
                title: Text(Localization.t('success')),
                content: Text(_isEditMode ? "Survey Updated Successfully" : "Survey Saved Successfully"),
                actions: [
                   TextButton(
                      onPressed: () {
                         Navigator.pop(context); 
                         Navigator.of(context).pop(); // Back to list
                         // If deep stack, maybe check `route.isFirst` logic
                      },
                      child: Text(Localization.t('success')), // Using 'success' or 'ok'
                   )
                ],
             )
          );
       } else {
          throw Exception(jsonDecode(response.body)['message'] ?? response.body);
       }
    } catch (e) {
       debugPrint("Submit Error: $e");
       ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Error: $e")));
    } finally {
       setState(() => _isLoading = false);
    }
  }

  void _addTreeLine() {
    setState(() {
      _treeLines.add({'tree_master_id': null, 'quantity': '', 'development_stage': null, 'girth_cm': ''});
    });
  }

  void _removeTreeLine(int index) {
    setState(() {
      _treeLines.removeAt(index);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_isInitialLoading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    final themeProvider = Provider.of<ThemeProvider>(context);
    final isDark = themeProvider.isDarkMode;

    return ValueListenableBuilder(
      valueListenable: Localization.currentLocale,
      builder: (context, locale, child) {
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
              child: Column(
                children: [
                   // Header with Back Button, Language Selector, and Theme Toggle (Consistent UI)
                   Container(
                     padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                     decoration: BoxDecoration(
                       color: Colors.black.withValues(alpha: 0.2),
                       borderRadius: const BorderRadius.only(
                         bottomLeft: Radius.circular(20),
                         bottomRight: Radius.circular(20),
                       ),
                     ),
                     child: Row(
                       children: [
                         IconButton(
                           icon: const Icon(Icons.arrow_back, color: Colors.white), 
                           onPressed: () => Navigator.pop(context),
                           padding: EdgeInsets.zero,
                           constraints: const BoxConstraints(),
                         ),
                         const SizedBox(width: 12),
                         Expanded(
                           child: Text(
                             _isEditMode ? Localization.t('edit_survey') : Localization.t('new_survey'), 
                             style: const TextStyle(
                               color: Colors.white,
                               fontSize: 20,
                               fontWeight: FontWeight.w900,
                               letterSpacing: 0.5,
                             ),
                           ),
                         ),
                         const LanguageSelector(),
                         const SizedBox(width: 8),
                         Consumer<ThemeProvider>(
                           builder: (context, themeProvider, _) {
                             return InkWell(
                               onTap: () => themeProvider.toggleTheme(),
                               borderRadius: BorderRadius.circular(20),
                               child: Container(
                                 padding: const EdgeInsets.all(7),
                                 decoration: BoxDecoration(
                                   color: Colors.white.withValues(alpha: 0.2),
                                   borderRadius: BorderRadius.circular(20),
                                   border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
                                 ),
                                 child: AnimatedSwitcher(
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
                                     size: 18,
                                   ),
                                 ),
                               ),
                             );
                           },
                         ),
                       ],
                     ),
                   ),
                   Expanded(
                      child: SingleChildScrollView(
                         controller: _scrollController,
                         padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                         child: Column(
                            children: [
                               const SizedBox(height: 10),
                    if (false) 
                       _buildSectionCard(Localization.t('survey_form'), [
                          _buildReadOnlyField(Localization.t('survey_form'), _surveyName!, labelIcon: Icons.description),
                       ], icon: Icons.description),
                    
                    const SizedBox(height: 12),
                      
                   _buildSectionCard("1. Project & Location Details", [
                      _buildReadOnlyField(Localization.t('department'), _departmentName, key: _fieldKeys['department'], labelIcon: Icons.apartment),
                      _buildReadOnlyField(Localization.t('project'), _projectName, key: _fieldKeys['project'], labelIcon: Icons.assignment),
                      _buildReadOnlyField(Localization.t('area'), _areaName, key: _fieldKeys['area'], labelIcon: Icons.map),
                      _buildReadOnlyField(Localization.t('village'), _villageName, key: _fieldKeys['village'], labelIcon: Icons.holiday_village),
                      _buildReadOnlyField(Localization.t('tehsil'), _tehsilName, key: _fieldKeys['tehsil'], labelIcon: Icons.location_city),
                      
                      const SizedBox(height: 16),
                      CustomRadioGroup<String>(
                          label: "सर्वे का प्रकार",

                         required: true,
                         options: [
                             CustomRadioOption(label: "ग्रामीण", value: "rural", icon: Icons.landscape),
                             CustomRadioOption(label: "शहरी", value: "urban", icon: Icons.location_city),

                         ],
                         selectedValue: _surveyType,
                         errorMessage: _errors['surveyType'],
                         onSelect: (val) => setState(() => _surveyType = val),
                      ),
                   ], icon: Icons.business),

                   const SizedBox(height: 16),
                   _buildSectionCard("2. Land Information", [
                      TextInputField(
                         key: _fieldKeys['khasra'],
                         label: Localization.t('affected_khasra'),
                         required: true,
                         controller: _khasraController,
                         errorMessage: _errors['khasra'],
                         labelIcon: Icons.grid_on,
                      ),
                      TextInputField(
                         key: _fieldKeys['totalArea'],
                         label: Localization.t('total_area'),
                         required: true,
                         controller: _totalAreaController,
                         keyboardType: TextInputType.numberWithOptions(decimal: true),
                         errorMessage: _errors['totalArea'],
                         labelIcon: Icons.crop_square,
                      ),
                      TextInputField(
                         key: _fieldKeys['acquiredArea'],
                         label: Localization.t('acquired_area'),
                         required: true,
                         controller: _acquiredAreaController,
                         keyboardType: TextInputType.numberWithOptions(decimal: true),
                         errorMessage: _errors['acquiredArea'],
                         labelIcon: Icons.pie_chart,
                      ),
                       TextInputField(
                          label: "Distance from Main Road (m)",
                          controller: _distanceController,
                          keyboardType: TextInputType.number,
                          labelIcon: Icons.add_road,
                       ),
                       
                     ], icon: Icons.landscape),
                    
                    const SizedBox(height: 16),
                    _buildSectionCard("3. Landowners", [
                       // Landowner
                       Padding(
                          key: _fieldKeys['landowner'],
                          padding: const EdgeInsets.only(top: 8.0),
                         child: Builder(
                             builder: (context) {
                               final isDark = Theme.of(context).brightness == Brightness.dark;
                               return Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                     Row(
                                       children: [
                                         Icon(Icons.person, size: 20, color: isDark ? Colors.blue[300] : const Color(0xFF104E8B)),
                                         const SizedBox(width: 8),
                                         Text("Landowners *", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17, color: isDark ? Colors.grey[300] : const Color(0xFF2D3436))),
                                       ],
                                     ),
                                     const SizedBox(height: 8),
                                     InkWell(
                                        onTap: _openUserPicker,
                                        child: Container(
                                           width: double.infinity,
                                           padding: const EdgeInsets.all(12),
                                           decoration: BoxDecoration(
                                              color: isDark ? AppColors.darkInputBg : Colors.white,
                                              borderRadius: BorderRadius.circular(10),
                                              border: Border.all(color: _errors.containsKey('landowner') ? Colors.red : (isDark ? Colors.grey[600]! : Colors.black), width: 1.5)
                                           ),
                                           child: Text(
                                              _selectedLandowners.isEmpty ? Localization.t('select_landowners') : "${_selectedLandowners.length} Landowners Selected",
                                              style: TextStyle(fontSize: 16, color: (_selectedLandowners.isEmpty && isDark) ? Colors.grey[400] : (isDark ? Colors.white : Colors.black))
                                           ),
                                        ),
                                     ),
                                     if (_selectedLandowners.isNotEmpty) ...[
                                       const SizedBox(height: 8),
                                       Container(
                                         width: double.infinity,
                                         padding: const EdgeInsets.all(8),
                                         decoration: BoxDecoration(
                                           color: isDark ? Colors.white.withValues(alpha: 0.05) : Colors.black.withValues(alpha: 0.03),
                                           borderRadius: BorderRadius.circular(8),
                                           border: Border.all(color: isDark ? Colors.white10 : Colors.black12),
                                         ),
                                         child: Wrap(
                                           spacing: 8,
                                           runSpacing: 8,
                                           children: _selectedLandowners.map((u) => Container(
                                             padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                             decoration: BoxDecoration(
                                               color: const Color(0xFF104E8B).withValues(alpha: 0.1),
                                               borderRadius: BorderRadius.circular(20),
                                               border: Border.all(color: const Color(0xFF104E8B).withValues(alpha: 0.3)),
                                             ),
                                             child: Row(
                                               mainAxisSize: MainAxisSize.min,
                                               children: [
                                                  const Icon(Icons.person, size: 14, color: Color(0xFF104E8B)),
                                                  const SizedBox(width: 6),
                                                  Text(u.name, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Color(0xFF104E8B))),
                                                  const SizedBox(width: 4),
                                                  GestureDetector(
                                                    onTap: () => setState(() => _selectedLandowners.removeWhere((l) => l.id == u.id)),
                                                    child: const Icon(Icons.close, size: 14, color: Color(0xFF104E8B)),
                                                  ),
                                               ],
                                             ),
                                           )).toList(),
                                         ),
                                       ),
                                     ],
                               if (_errors.containsKey('landowner'))
                                  Padding(
                                    padding: const EdgeInsets.only(top: 4.0),
                                    child: Text(_errors['landowner']!, style: const TextStyle(color: Colors.red, fontSize: 12)),
                                  )
                                  ],
                               );
                             }
                           ),
                         ),
                    ], icon: Icons.people),
                    
                    const SizedBox(height: 16),
                    _buildSectionCard("4. Crop & Tree Details", [
                       const SizedBox(height: 8),
                      YesNoSelector(
                         key: _fieldKeys['hasTradedLand'],
                         label: Localization.t('diverted_land'),
                         required: true,
                         selectedValue: _hasTradedLand,
                         errorMessage: _errors['hasTradedLand'],
                         onSelect: (val) => setState(() => _hasTradedLand = val),
                      ),
                      
                      if (_hasTradedLand == 'yes')
                         TextInputField(
                            key: _fieldKeys['tradedLandArea'],
                            label: Localization.t('diverted_land_area'),
                            required: true,
                            controller: _tradedLandAreaController,
                            keyboardType: TextInputType.numberWithOptions(decimal: true),
                            errorMessage: _errors['tradedLandArea'],
                            labelIcon: Icons.area_chart,
                         ),
                      
                       const SizedBox(height: 8),
                      Container(key: _fieldKeys['cropType']),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(Icons.landscape, size: 20, color: isDark ? Colors.blue[300] : const Color(0xFF104E8B)),
                              const SizedBox(width: 8),
                              Text(
                                Localization.t('land_type'), 
                                style: TextStyle(
                                  fontWeight: FontWeight.bold, 
                                  fontSize: 17, 
                                  color: isDark ? Colors.white : const Color(0xFF2D3436)
                                )
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          // First row: Ek Fasli and Do Fasli
                          Row(
                            children: _landTypes.take(2).map<Widget>((l) {
                              final isSelected = _cropType == l['id'].toString();
                              final color = const Color(0xFF104E8B);
                              return Expanded(
                                child: Padding(
                                  padding: const EdgeInsets.only(right: 8.0, bottom: 8.0),
                                  child: InkWell(
                                    onTap: () => setState(() => _cropType = l['id'].toString()),
                                    borderRadius: BorderRadius.circular(12),
                                    child: AnimatedContainer(
                                      duration: const Duration(milliseconds: 250),
                                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                                      decoration: BoxDecoration(
                                        color: isSelected ? color : Colors.white,
                                        borderRadius: BorderRadius.circular(12),
                                        border: Border.all(color: isSelected ? color : const Color(0xFFE9ECEF), width: 1.5),
                                        boxShadow: isSelected ? [BoxShadow(color: color.withValues(alpha: 0.2), blurRadius: 8, offset: const Offset(0, 4))] : null,
                                      ),
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        mainAxisAlignment: MainAxisAlignment.center,
                                        children: [
                                          Icon(isSelected ? Icons.check_circle : Icons.circle_outlined, 
                                               color: isSelected ? Colors.white : Colors.grey.shade400, size: 18),
                                          const SizedBox(width: 8),
                                          Flexible(
                                            child: Text(l['name'], style: TextStyle(
                                              color: isSelected ? Colors.white : Colors.grey.shade800, 
                                              fontWeight: FontWeight.w700,
                                              fontSize: 14
                                            ), overflow: TextOverflow.ellipsis, textAlign: TextAlign.center),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                              );
                            }).toList(),
                          ),
                          // Second row: Naparti (if exists)
                          if (_landTypes.length > 2)
                            Row(
                              children: [
                                Expanded(
                                  child: Builder(
                                    builder: (context) {
                                      final l = _landTypes[2];
                                      final isSelected = _cropType == l['id'].toString();
                                      final color = const Color(0xFF104E8B);
                                      return Padding(
                                        padding: const EdgeInsets.only(right: 8.0, bottom: 8.0),
                                        child: InkWell(
                                          onTap: () => setState(() => _cropType = l['id'].toString()),
                                          borderRadius: BorderRadius.circular(12),
                                          child: AnimatedContainer(
                                            duration: const Duration(milliseconds: 250),
                                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                                            decoration: BoxDecoration(
                                              color: isSelected ? color : Colors.white,
                                              borderRadius: BorderRadius.circular(12),
                                              border: Border.all(color: isSelected ? color : const Color(0xFFE9ECEF), width: 1.5),
                                              boxShadow: isSelected ? [BoxShadow(color: color.withValues(alpha: 0.2), blurRadius: 8, offset: const Offset(0, 4))] : null,
                                            ),
                                            child: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              mainAxisAlignment: MainAxisAlignment.center,
                                              children: [
                                                Icon(isSelected ? Icons.check_circle : Icons.circle_outlined, 
                                                     color: isSelected ? Colors.white : Colors.grey.shade400, size: 18),
                                                const SizedBox(width: 8),
                                                Flexible(
                                                  child: Text(l['name'], style: TextStyle(
                                                    color: isSelected ? Colors.white : Colors.grey.shade800, 
                                                    fontWeight: FontWeight.w700,
                                                    fontSize: 14
                                                  ), overflow: TextOverflow.ellipsis, textAlign: TextAlign.center),
                                                ),
                                              ],
                                            ),
                                          ),
                                        ),
                                      );
                                    }
                                  ),
                                ),
                                const Expanded(child: SizedBox()), // Empty space to maintain layout
                              ],
                            ),
                          if (_errors.containsKey('cropType'))
                            Padding(
                              padding: const EdgeInsets.only(top: 4.0),
                              child: Text(_errors['cropType']!, style: const TextStyle(color: Colors.red, fontSize: 12)),
                            ),
                        ],
                      ),
                      
                      if (_cropType != '13') // If not barren?
                         Padding(
                           key: _fieldKeys['irrigationType'],
                           padding: const EdgeInsets.only(top: 16.0),
                            child: CustomRadioGroup<String>(
                               label: Localization.t('irrigation_type'),
                               required: true,
                               options: [CustomRadioOption(label: "Irrigated", value: "irrigated"), CustomRadioOption(label: "Unirrigated", value: "unirrigated")],
                               selectedValue: _irrigationType,
                               errorMessage: _errors['irrigationType'],
                               onSelect: (val) => setState(() => _irrigationType = val),
                            ),
                         ),
                   ], icon: Icons.landscape),

                   const SizedBox(height: 16),
                   _buildSectionCard("4. Structure Details", [
                       YesNoSelector(
                          key: _fieldKeys['hasHouse'],
                          label: Localization.t('has_house'),
                          required: true,
                          selectedValue: _hasHouse,
                          errorMessage: _errors['hasHouse'],
                          onSelect: (val) => setState(() => _hasHouse = val),
                       ),
                      if (_hasHouse == 'yes') ...[
                         Padding(
                           padding: const EdgeInsets.only(top: 16.0),
                            child: CustomRadioGroup<String>(
                               key: _fieldKeys['houseType'],
                               label: Localization.t('house_type'),
                               required: true,
                               options: [CustomRadioOption(label: "Kaccha", value: "kaccha"), CustomRadioOption(label: "Pakka", value: "pakka")],
                               selectedValue: _houseType,
                               errorMessage: _errors['houseType'],
                               onSelect: (val) => setState(() => _houseType = val),
                            ),
                         ),
                         TextInputField(
                            key: _fieldKeys['houseArea'],
                            label: Localization.t('house_area'),
                            required: true,
                            controller: _houseAreaController,
                            keyboardType: TextInputType.numberWithOptions(decimal: true),
                            errorMessage: _errors['houseArea'],
                            labelIcon: Icons.square_foot,
                         ),
                      ],
                      
                      const SizedBox(height: 16),
                      YesNoSelector(
                         key: _fieldKeys['hasShed'], // hasShed
                         label: Localization.t('has_shed'),
                         required: true,
                         selectedValue: _hasShed,
                         errorMessage: _errors['hasShed'],
                         onSelect: (val) => setState(() => _hasShed = val),
                      ),
                      if (_hasShed == 'yes')
                         TextInputField(
                            key: _fieldKeys['shedArea'],
                            label: Localization.t('shed_area'),
                            required: true, 
                            controller: _shedAreaController,
                            keyboardType: TextInputType.numberWithOptions(decimal: true),
                            errorMessage: _errors['shedArea'],
                            labelIcon: Icons.square_foot,
                         ),
                   ], icon: Icons.home),

                   const SizedBox(height: 16),
                   _buildSectionCard("5. Tree Details", [
                       YesNoSelector(
                          key: _fieldKeys['hasTrees'],
                          label: Localization.t('add_trees_q'),
                          required: true,
                          selectedValue: _hasTrees,
                          errorMessage: _errors['hasTrees'],
                          onSelect: (val) {
                             setState(() {
                                _hasTrees = val;
                                if (val == 'no') _treeLines.clear();
                             });
                          },
                       ),
                      
                      if (_hasTrees == 'yes') ...[
                         Container(key: _fieldKeys['treeLines']),
                         if (_errors.containsKey('treeLines'))
                            Padding(
                               padding: const EdgeInsets.symmetric(vertical: 8),
                               child: Text(_errors['treeLines']!, style: const TextStyle(color: Colors.red)),
                            ),
                         
                          if (_treeLines.isNotEmpty)
                             Padding(
                               padding: const EdgeInsets.only(top: 8.0),
                               child: Column(
                                  children: _treeLines.asMap().entries.map((entry) {
                                     final index = entry.key;
                                     final line = entry.value;
                                     final isDark = Theme.of(context).brightness == Brightness.dark;
                                     final condition = line['development_stage'] == 'fully_developed' ? 'Sound' : (line['development_stage'] == 'undeveloped' ? 'Unsound' : 'Semi');
                                     
                                     return Padding(
                                       padding: const EdgeInsets.only(bottom: 8.0),
                                       child: InkWell(
                                          onTap: () => _showAddTreeDialog(existingLine: line, index: index),
                                          borderRadius: BorderRadius.circular(8),
                                          child: Container(
                                             width: double.infinity,
                                             padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                                             decoration: BoxDecoration(
                                                color: isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.04),
                                                borderRadius: BorderRadius.circular(8),
                                                border: Border.all(color: isDark ? Colors.white12 : Colors.black12),
                                             ),
                                             child: Row(
                                                children: [
                                                   const Icon(Icons.park, size: 16, color: Colors.green),
                                                     Expanded(
                                                      child: Column(
                                                        crossAxisAlignment: CrossAxisAlignment.start,
                                                        children: [
                                                          Text(
                                                            "${line['tree_name'] ?? 'Tree'} ($condition)",
                                                            style: TextStyle(
                                                              fontWeight: FontWeight.bold,
                                                              fontSize: 14,
                                                              color: isDark ? Colors.white : Colors.black87,
                                                            ),
                                                          ),
                                                          if (line['girth_cm'] != null && line['girth_cm'].toString().isNotEmpty)
                                                            Text(
                                                              "Girth: ${line['girth_cm']} cm",
                                                              style: TextStyle(
                                                                color: isDark ? Colors.grey[400] : Colors.grey[600],
                                                                fontSize: 12,
                                                              ),
                                                            ),
                                                        ],
                                                      ),
                                                    ),
                                                   Text(
                                                     "x${line['quantity']}",
                                                     style: const TextStyle(
                                                       fontWeight: FontWeight.w900,
                                                       fontSize: 14,
                                                       color: Colors.blue,
                                                     ),
                                                   ),
                                                   const SizedBox(width: 12),
                                                   GestureDetector(
                                                      onTap: () => setState(() => _treeLines.removeAt(index)),
                                                      child: Icon(Icons.close, size: 16, color: isDark ? Colors.grey : Colors.grey.shade600),
                                                   )
                                                ],
                                             ),
                                          ),
                                       ),
                                     );
                                  }).toList(),
                               ),
                             ),
                          const SizedBox(height: 12),
                          Center(
                             child: TextButton.icon(
                                onPressed: () => _showAddTreeDialog(),
                                icon: const Icon(Icons.add_circle_outline, size: 18),
                                label: const Text("Add More Trees"),
                                style: TextButton.styleFrom(
                                   foregroundColor: const Color(0xFF104E8B),
                                   textStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                )
                             )
                          )
                      ]
                   ], icon: Icons.forest),

                   const SizedBox(height: 16),
                   _buildSectionCard("6. Infrastructural Information", [
                       YesNoSelector(
                          key: _fieldKeys['hasWell'],
                          label: Localization.t('has_well'),
                          required: true,
                          selectedValue: _hasWell,
                          errorMessage: _errors['hasWell'],
                          onSelect: (val) => setState(() {
                             _hasWell = val;
                             if (val == 'no') { _wellType = null; _wellCountController.clear(); }
                          }),
                       ),
                      if (_hasWell == 'yes') ...[
                         Padding(
                           padding: const EdgeInsets.only(top: 16.0),
                            child: CustomRadioGroup<String>(
                               key: _fieldKeys['wellType'],
                               label: Localization.t('well_type'),
                               required: true,
                               options: [CustomRadioOption(label: "Pakka", value: "pakka"), CustomRadioOption(label: "Kaccha", value: "kaccha")],
                               selectedValue: _wellType,
                               errorMessage: _errors['wellType'],
                               onSelect: (val) => setState(() => _wellType = val),
                            ),
                         ),
                         TextInputField(
                            key: _fieldKeys['wellCount'],
                            label: Localization.t('well_count'),
                            required: true,
                            controller: _wellCountController,
                            keyboardType: TextInputType.number,
                            errorMessage: _errors['wellCount'],
                            labelIcon: Icons.numbers,
                         ),
                      ],
                      
                      const SizedBox(height: 16),
                      YesNoSelector(
                         key: _fieldKeys['hasTubewell'],
                         label: Localization.t('has_tubewell'),
                         required: true,
                         selectedValue: _hasTubewell,
                         errorMessage: _errors['hasTubewell'],
                         onSelect: (val) => setState(() {
                            _hasTubewell = val;
                            if (val == 'no') _tubewellCountController.clear();
                         }),
                      ),
                      if (_hasTubewell == 'yes')
                         TextInputField(
                            key: _fieldKeys['tubewellCount'],
                            label: Localization.t('tubewell_count'),
                            required: true,
                            controller: _tubewellCountController,
                            keyboardType: TextInputType.number,
                            errorMessage: _errors['tubewellCount'],
                            labelIcon: Icons.numbers,
                         ),
                         
                      const SizedBox(height: 16),
                      YesNoSelector(
                         key: _fieldKeys['hasPond'],
                         label: Localization.t('has_pond'),
                         required: true,
                         selectedValue: _hasPond,
                         errorMessage: _errors['hasPond'],
                         onSelect: (val) => setState(() => _hasPond = val),
                      ),
                      
                      const SizedBox(height: 16),
                      TextInputField(
                         label: Localization.t('remarks'),
                         controller: _remarksController,
                         placeholder: "${Localization.t('remarks')}...",
                         labelIcon: Icons.comment,
                      ),
                   ], icon: Icons.build),

                   const SizedBox(height: 16),
                   _buildSectionCard(Localization.t('document_checklist'), [
                      TextInputField(
                         label: Localization.t('mb_decl_date'),
                         controller: _mbDeclDateController,
                         placeholder: 'YYYY-MM-DD',
                         labelIcon: Icons.event,
                      ),
                      const SizedBox(height: 8),
                      CheckboxListTile(
                         contentPadding: EdgeInsets.zero,
                         title: Text(Localization.t('mb_decl_no_claim'), style: const TextStyle(fontSize: 14)),
                         value: _mbDeclNoClaim,
                         onChanged: (v) => setState(() => _mbDeclNoClaim = v ?? false),
                         controlAffinity: ListTileControlAffinity.leading,
                      ),
                      CheckboxListTile(
                         contentPadding: EdgeInsets.zero,
                         title: Text(Localization.t('mb_decl_docs'), style: const TextStyle(fontSize: 14)),
                         value: _mbDeclDocs,
                         onChanged: (v) => setState(() => _mbDeclDocs = v ?? false),
                         controlAffinity: ListTileControlAffinity.leading,
                      ),
                      CheckboxListTile(
                         contentPadding: EdgeInsets.zero,
                         title: Text(Localization.t('mb_decl_gps'), style: const TextStyle(fontSize: 14)),
                         value: _mbDeclGps,
                         onChanged: (v) => setState(() => _mbDeclGps = v ?? false),
                         controlAffinity: ListTileControlAffinity.leading,
                      ),
                   ], icon: Icons.checklist),
                   
                ],
              ),
            ),
          ),
          
          // Sticky Submit Button
          Container(
             padding: const EdgeInsets.all(16),
             decoration: BoxDecoration(
                color: Theme.of(context).brightness == Brightness.dark ? const Color(0xFF1E1E1E) : Colors.white,
                boxShadow: [
                   BoxShadow(
                      color: Colors.black.withValues(alpha: 0.1),
                      blurRadius: 10,
                      offset: const Offset(0, -5),
                   )
                ]
             ),
             child: SafeArea(
               top: false,
               child: Row(
                 children: [
                   if (widget.prefilledData != null) 
                     Expanded(
                       child: CustomButton(
                         title: "Close",
                         filled: false,
                         color: Colors.redAccent,
                         textColor: Colors.redAccent,
                         onPress: () => Navigator.pop(context),
                       ),
                     ),
                   if (widget.prefilledData != null) const SizedBox(width: 12),
                   Expanded(
                     child: CustomButton(
                        title: _isEditMode ? Localization.t('update_survey') : 'Submit',
                        isLoading: _isLoading,
                        onPress: _handleSubmit,
                     ),
                   ),
                 ],
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
  } // Closing build
  
  Widget _buildLangOption(String code, String label, bool isSelected) {
    return InkWell(
      onTap: () => Localization.changeLanguage(code),
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
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


  Widget _buildSectionCard(String title, List<Widget> children, {IconData? icon}) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    // Solid Header Colors
    final headerColor = isDark ? const Color(0xFF1565C0) : const Color(0xFF1976D2); // Blue 700/800
    final bodyColor = isDark ? const Color(0xFF1E293B) : Colors.white;
    final borderColor = isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0);

    // Extract Number
    String number = "";
    String displayTitle = title;
    if (title.contains(". ")) {
       final parts = title.split(". ");
       if (parts.length > 1 && int.tryParse(parts[0]) != null) {
          number = parts[0];
          displayTitle = parts.sublist(1).join(". ");
       }
    }

    return Container(
       width: double.infinity,
       margin: const EdgeInsets.only(bottom: 16),
       decoration: BoxDecoration(
          color: bodyColor,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: borderColor, width: 1),
          boxShadow: [
             BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.05),
                blurRadius: 5,
                offset: const Offset(0, 2)
             )
          ]
       ),
       child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
             // Solid Header
             Container(
               padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
               decoration: BoxDecoration(
                 color: headerColor,
                 borderRadius: const BorderRadius.only(
                    topLeft: Radius.circular(15), 
                    topRight: Radius.circular(15)
                 ),
               ),
               child: Row(
                 mainAxisAlignment: MainAxisAlignment.spaceBetween,
                 children: [
                   Expanded(
                      child: Row(
                        children: [
                          if (icon != null) ...[
                            Icon(icon, color: Colors.white, size: 20),
                            const SizedBox(width: 12),
                          ],
                          Flexible(
                             child: Text(
                               Localization.t(displayTitle), 
                               style: const TextStyle(
                                 fontSize: 17, 
                                 fontWeight: FontWeight.bold, 
                                 color: Colors.white,
                                 letterSpacing: 0.5
                               )
                             ),
                          ),
                        ],
                      ),
                   ),
                   // Number
                   if (number.isNotEmpty)
                     Container(
                        width: 26, height: 26,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                           color: Colors.white.withValues(alpha: 0.2),
                           shape: BoxShape.circle,
                           border: Border.all(color: Colors.white.withValues(alpha: 0.5))
                        ),
                        child: Text(
                           number,
                           style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 13
                           ),
                        ),
                     )
                 ],
               ),
             ),
             Padding(
               padding: const EdgeInsets.all(16),
               child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: children
               ),
             )
          ],
       ),
    );
  }



  Widget _buildReadOnlyField(String label, String value, {Key? key, IconData? labelIcon}) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    // Determine if value is Yes or No and set color accordingly
    Color valueColor = isDark ? Colors.white : const Color(0xFF2D3436); // Default
    if (value.toLowerCase() == 'yes') {
      valueColor = const Color(0xFF27AE60); // Green
    } else if (value.toLowerCase() == 'no') {
      valueColor = const Color(0xFFE74C3C); // Red
    }
    
    final labelColor = isDark ? Colors.grey[400] : const Color(0xFF636E72);
    final iconColor = isDark ? Colors.grey[500] : const Color(0xFF636E72);
    
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Icon + Label using fluid width (40%)
          Expanded(
            flex: 4,
            child: Row(
              children: [
                if (labelIcon != null) ...[ 
                  Icon(labelIcon, size: 16, color: iconColor),
                  const SizedBox(width: 8),
                ],
                Flexible(
                  child: Text(
                    "$label:", 
                    style: TextStyle(
                      fontSize: 14, 
                      color: labelColor,
                      fontWeight: FontWeight.w600,
                      height: 1.5,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          // Value using fluid width (60%)
          Expanded(
            flex: 6,
            child: Row(
              children: [
                Flexible(
                  child: Text(
                    value.isEmpty ? "—" : value, 
                    style: TextStyle(
                      fontSize: 14, 
                      fontWeight: FontWeight.w700, 
                      color: valueColor,
                      height: 1.5,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _openUserPicker() {
    debugPrint("Opening user picker with:");
    debugPrint("  District ID: $_selectedDistrictId");
    debugPrint("  Tehsil ID: $_selectedTehsilId");
    debugPrint("  Village ID: $_selectedVillageId");
    debugPrint("  Total available landowners in pool: ${_landowners.length}");
    debugPrint("  Previously selected landowners count: ${_selectedLandowners.length}");
    
    showDialog(
      context: context,
      builder: (_) => UserPickerModal(
        users: _landowners,
        selectedUserIds: _selectedLandowners.map((u) => u.id).toList(),
        districtId: _selectedDistrictId ?? '',
        tehsilId: _selectedTehsilId ?? '',
        villageId: _selectedVillageId ?? '',
        onConfirmSelection: (users) {
            setState(() {
              _selectedLandowners = users;
              _errors.remove('landowner'); // Clear error on select
            });
        },
        onSaveNewUser: (userData) async {
            try {
              debugPrint("Creating new landowner with data: $userData");
              final response = await ApiService.post(ApiEndpoints.landowner, userData);
              debugPrint("Create landowner response status: ${response.statusCode}");
              debugPrint("Create landowner response body: ${response.body}");
              
              if (response.statusCode == 200 || response.statusCode == 201) {
                final json = jsonDecode(response.body);
                final newUser = PickerUser.fromJson(json['data'] ?? json);
                
                // Refresh the landowners list
                if (_selectedVillageId != null) {
                  await _fetchLandowners(_selectedVillageId!);
                }
                
                return newUser;
              }
              throw Exception("Failed to add landowner: ${response.statusCode} - ${response.body}");
            } catch (e) {
              debugPrint("Error creating landowner: $e");
              rethrow;
            }
        },
        onUpdateUser: (id, userData) async {
            try {
              debugPrint("Updating landowner $id with data: $userData");
              final token = await getAsyncItem(AUTH_TOKEN_KEY);
              final headers = {
                 'Content-Type': 'application/json',
                 'App-Version-Code': '1',
                 if (token != null) 'Authorization': 'Bearer $token',
              };
              final response = await http.patch(
                 Uri.parse('${ApiService.baseUrl}${ApiEndpoints.landowner}/$id'),
                 headers: headers,
                 body: jsonEncode(userData)
              );
              
              debugPrint("Update landowner response status: ${response.statusCode}");
              debugPrint("Update landowner response body: ${response.body}");

              if (response.statusCode == 200) {
                final json = jsonDecode(response.body);
                final updatedUser = PickerUser.fromJson(json['data'] ?? json);
                
                // Refresh the landowners list
                if (_selectedVillageId != null) {
                  await _fetchLandowners(_selectedVillageId!);
                }
                
                return updatedUser;
              }
              throw Exception("Failed to update landowner: ${response.statusCode} - ${response.body}");
            } catch (e) {
              debugPrint("Error updating landowner: $e");
              rethrow;
            }
        },
      ),
    );
  }

  bool _isFruit(dynamic t) {
     final name = t['name']?.toString().toLowerCase() ?? '';
     
     // API Check
     if (t['is_fruit'] == 1 || t['is_fruit'] == true || t['is_fruit'] == 'yes') return true;
     if (t['category']?.toString().toLowerCase() == 'fruit') return true;
     
     // Keyword Check (English & Hindi/Transliterated & Devanagari)
     const keywords = [
        'mango', 'apple', 'banana', 'guava', 'orange', 'lemon', 'lime', 'papaya', 'pomegranate', 'custard apple', 'jackfruit', 'tamarind', 'berry', 'coconut', 'dates', 'fig', 'grape', 'litchi', 'pear', 'plum', 'sapota', 'watermelon',
        'aam', 'seb', 'kela', 'amrud', 'santra', 'mosambi', 'nimbu', 'papita', 'anar', 'sitaphal', 'kathal', 'imli', 'ber', 'nariyal', 'khajur', 'anjeer', 'angoor', 'nashpati', 'alubukhara', 'chikoo', 'tarbuj',
        'amla', 'aawla', 'awla', 'aanwala', 'jamun', 'jaamun', 'bel', 'bael', 'mahua', 'munga',
        'आम', 'सेब', 'केला', 'अमरूद', 'संतरा', 'मौसंबी', 'नींबू', 'पपीता', 'अनार', 'सीताफल', 'कटहल', 'इमली', 'बेर', 'नारियल', 'खजूर', 'अंजीर', 'अंगूर', 'लीची', 'नाशपाती', 'आलूबुखारा', 'चीकू', 'तरबूज',
        'आंवला', 'जामुन', 'बेल', 'महुआ', 'मुनगा'
     ];

     for (var k in keywords) {
        if (name.contains(k)) return true;
     }

     return false; 
  }

  void _showAddTreeDialog({Map<String, dynamic>? existingLine, int? index}) {
    String category = 'fruit';
    Map<String, dynamic>? selectedTree;
    String condition = 'fully_developed';
    int qty = 1;
    String girth = '';
    
    final girthController = TextEditingController();
    
    if (existingLine != null) {
       final treeId = existingLine['tree_master_id'];
       selectedTree = _treesList.firstWhere((t) => t['id'] == treeId, orElse: () => null);
       if (selectedTree != null) {
          category = _isFruit(selectedTree) ? 'fruit' : 'non_fruit';
       }
       condition = existingLine['development_stage'] ?? 'fully_developed';
       qty = int.tryParse(existingLine['quantity'].toString()) ?? 1;
       girth = existingLine['girth_cm']?.toString() ?? '';
       girthController.text = girth;
    }

    showDialog(
      context: context,
      builder: (ctx) {
         return StatefulBuilder(
            builder: (context, setStateDialog) {
               final isDark = Theme.of(context).brightness == Brightness.dark;
               final filteredTrees = _treesList.where((t) {
                   final isF = _isFruit(t);
                   return category == 'fruit' ? isF : !isF;
               }).toList();

               return AlertDialog(
                  backgroundColor: isDark ? const Color(0xFF1E1E1E) : Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  title: Text(existingLine == null ? "Add Tree" : "Edit Tree", style: TextStyle(color: isDark ? Colors.white : Colors.black)),
                  content: SingleChildScrollView(
                     child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                           // Category Radios
                           CustomRadioGroup<String>(
                              label: "Category",
                              options: [
                                 CustomRadioOption(label: "Fruit", value: 'fruit', color: Colors.green, icon: Icons.eco),
                                 CustomRadioOption(label: "Non-Fruit", value: 'non_fruit', color: Colors.red, icon: Icons.nature),
                              ],
                              selectedValue: category,
                              onSelect: (v) => setStateDialog(() { category = v; selectedTree = null; }),
                           ),
                           const SizedBox(height: 12),
                           
                           Text("Select Tree:", style: TextStyle(fontSize: 12, color: isDark ? Colors.grey : Colors.grey[600])),
                           const SizedBox(height: 4),
                           Container(
                              constraints: const BoxConstraints(maxHeight: 250),
                              width: double.infinity,
                              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
                              decoration: BoxDecoration(
                                 border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
                                 borderRadius: BorderRadius.circular(8)
                              ),
                              child: SingleChildScrollView(
                                 child: Wrap(
                                    spacing: 8, runSpacing: 8,
                                    children: filteredTrees.map((t) {
                                       final isSelected = selectedTree?['id'] == t['id'];
                                       final color = category == 'fruit' ? Colors.green : Colors.red;
                                       return ChoiceChip(
                                          label: Text(t['name'], style: TextStyle(color: isSelected ? Colors.white : color, fontSize: 11, fontWeight: FontWeight.w600)),
                                          selected: isSelected,
                                          selectedColor: color,
                                          backgroundColor: Colors.transparent,
                                          shape: RoundedRectangleBorder(
                                             borderRadius: BorderRadius.circular(20), 
                                             side: BorderSide(color: color.withValues(alpha: 0.5))
                                          ),
                                          onSelected: (sel) => setStateDialog(() => selectedTree = t),
                                          visualDensity: const VisualDensity(horizontal: -2, vertical: -4),
                                          padding: const EdgeInsets.symmetric(horizontal: 4),
                                       );
                                    }).toList(),
                                 ),
                              ),
                           ),
                           const SizedBox(height: 16),
                           
                           CustomRadioGroup<String>(
                              label: "Condition",
                              options: [
                                 CustomRadioOption(label: "Sound", value: 'fully_developed', color: Colors.green),
                                 CustomRadioOption(label: "Semi", value: 'semi_developed', color: Colors.orange),
                                 CustomRadioOption(label: "Unsound", value: 'undeveloped', color: Colors.red),
                              ],
                              selectedValue: condition,
                              onSelect: (v) => setStateDialog(() => condition = v),
                           ),
                           
                           const SizedBox(height: 16),
                           Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                 Text("Quantity", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: isDark ? Colors.white : Colors.black)),
                                 Row(
                                    children: [
                                       IconButton(
                                          onPressed: () => qty > 1 ? setStateDialog(() => qty--) : null, 
                                          icon: Icon(Icons.remove_circle_outline, color: isDark ? Colors.white70 : Colors.black54),
                                          iconSize: 20,
                                       ),
                                       Text("$qty", style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: isDark ? Colors.white : Colors.black)),
                                       IconButton(
                                          onPressed: () => setStateDialog(() => qty++), 
                                          icon: Icon(Icons.add_circle_outline, color: isDark ? Colors.white70 : Colors.black54),
                                          iconSize: 20,
                                       ),
                                    ],
                                 )
                              ],
                           ),
                           
                           const SizedBox(height: 16),
                           TextField(
                              controller: girthController,
                              keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              decoration: InputDecoration(
                                 labelText: "Girth (cm)",
                                 border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                                 filled: true,
                                 fillColor: isDark ? Colors.grey[800] : Colors.grey[100],
                                 labelStyle: TextStyle(color: isDark ? Colors.grey[400] : Colors.grey[600]),
                              ),
                              style: TextStyle(color: isDark ? Colors.white : Colors.black),
                              onChanged: (val) => girth = val,
                           ),
                        ],
                     ),
                  ),
                  actions: [
                     TextButton(
                        onPressed: () => Navigator.pop(ctx), 
                        child: const Text("Close", style: TextStyle(color: Colors.grey))
                     ),
                     ElevatedButton(
                        onPressed: selectedTree == null ? null : () {
                           setState(() {
                              final newLine = {
                                 'tree_master_id': selectedTree!['id'],
                                 'quantity': qty,
                                 'development_stage': condition,
                                 'tree_master_id': selectedTree!['id'],
                                 'quantity': qty,
                                 'development_stage': condition,
                                 'girth_cm': girth,
                                 'tree_name': selectedTree!['name'] 
                              };
                              if (index != null) {
                                 _treeLines[index] = newLine;
                              } else {
                                 _treeLines.add(newLine);
                              }
                           });
                           Navigator.pop(ctx);
                        },
                        child: const Text("Save")
                     )
                  ],
               );
            }
         );
      }
    );
  }
  
  Widget _buildDialogRadio(String label, String val, String current, bool isDark, Function(String) onTap) {
     final selected = val == current;
     return InkWell(
        onTap: () => onTap(val),
        child: Container(
           padding: const EdgeInsets.symmetric(vertical: 10),
           alignment: Alignment.center,
           decoration: BoxDecoration(
              color: selected ? const Color(0xFF104E8B) : Colors.transparent,
              border: Border.all(color: selected ? const Color(0xFF104E8B) : Colors.grey),
              borderRadius: BorderRadius.circular(8)
           ),
           child: Text(label, style: TextStyle(color: selected ? Colors.white : (isDark ? Colors.white : Colors.black), fontWeight: FontWeight.bold)),
        ),
     );
  }

  Widget _buildChoiceChip(String label, String val, String current, bool isDark, Function(String) onTap, {bool isSmall = false}) {
      final selected = val == current;
      return InkWell(
        onTap: () => onTap(val),
        child: Container(
           padding: EdgeInsets.symmetric(horizontal: isSmall ? 4 : 12, vertical: isSmall ? 4 : 6),
           alignment: Alignment.center,
           decoration: BoxDecoration(
              color: selected ? Colors.green.withValues(alpha: 0.2) : Colors.transparent,
              border: Border.all(color: selected ? Colors.green : Colors.grey),
              borderRadius: BorderRadius.circular(20)
           ),
           child: Text(label, style: TextStyle(color: selected ? Colors.green : (isDark ? Colors.white70 : Colors.black54), fontWeight: FontWeight.bold, fontSize: isSmall ? 10 : 13), textAlign: TextAlign.center, maxLines: 1),
        ),
      );
  }
}

class YesNoSelector extends StatelessWidget {
  final String label;
  final String? selectedValue;
  final Function(String) onSelect;
  final String? errorMessage;
  final bool required;

  const YesNoSelector({
    super.key,
    required this.label,
    required this.selectedValue,
    required this.onSelect,
    this.errorMessage,
    this.required = false,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final labelColor = isDark ? Colors.grey[300] : const Color(0xFF2D3436);
    final iconColor = isDark ? Colors.blue[300] : const Color(0xFF104E8B);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
           crossAxisAlignment: CrossAxisAlignment.start,
           children: [
              Padding(
                padding: const EdgeInsets.only(top: 2.0),
                child: Icon(label == Localization.t('has_house') ? Icons.house : (label == Localization.t('has_shed') ? Icons.storefront : Icons.help), size: 16, color: iconColor),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: RichText(
                  text: TextSpan(
                    text: label,
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: labelColor),
                    children: [
                      if (required)
                        const TextSpan(text: " *", style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold, fontSize: 15)),
                    ],
                  ),
                ),
              ),
           ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(child: _buildOption(context, 'yes')),
            const SizedBox(width: 12),
            Expanded(child: _buildOption(context, 'no')),
          ],
        ),
        if (errorMessage != null)
           Padding(
             padding: const EdgeInsets.only(top: 6.0),
             child: Text(errorMessage!, style: const TextStyle(color: Colors.red, fontSize: 12)),
           )
      ],
    );
  }

  Widget _buildOption(BuildContext context, String value) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isYes = value == 'yes';
    final isSelected = selectedValue == value;
    final color = isYes ? const Color(0xFF27AE60) : const Color(0xFFE74C3C);
    final icon = isYes ? Icons.check_circle : Icons.cancel;

    final bg = isDark ? AppColors.darkInputBg : Colors.white;
    final border = isDark ? Colors.grey[600]! : const Color(0xFFE9ECEF);
    final textColor = isDark ? Colors.grey[400] : Colors.grey.shade700;
    final iconColor = isDark ? Colors.grey[500] : Colors.grey.shade400;
    
    return InkWell(
      onTap: () => onSelect(value),
      borderRadius: BorderRadius.circular(12),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? color : bg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: isSelected ? color : border, width: 1.5),
          boxShadow: isSelected ? [BoxShadow(color: color.withValues(alpha: 0.2), blurRadius: 8, offset: const Offset(0, 4))] : null,
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(isSelected ? icon : (isYes ? Icons.check_circle_outline : Icons.cancel_outlined), 
                 color: isSelected ? Colors.white : iconColor, size: 20),
            const SizedBox(width: 8),
            Text(isYes ? "Yes" : "No", style: TextStyle(
              color: isSelected ? Colors.white : textColor, 
              fontWeight: FontWeight.w800,
              fontSize: 14
            )),
          ],
        ),
      ),
    );
  }
}

class CustomRadioGroup<T> extends StatelessWidget {
  final String label;
  final T? selectedValue;
  final List<CustomRadioOption<T>> options;
  final Function(T) onSelect;
  final String? errorMessage;
  final bool isVertical;
  final bool required;

  final IconData? labelIcon;
  final int gridCount; // 0 for horizontal row, >0 for Grid

  const CustomRadioGroup({
    super.key,
    required this.label,
    required this.selectedValue,
    required this.options,
    required this.onSelect,
    this.errorMessage,
    this.isVertical = false,
    this.required = false,
    this.labelIcon,
    this.gridCount = 0,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final labelColor = isDark ? Colors.grey[300] : const Color(0xFF2D3436);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
                child: RichText(
                  text: TextSpan(
                    text: label,
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: labelColor),
                    children: [
                      if (required)
                        const TextSpan(text: " *", style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold, fontSize: 15)),
                    ],
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 10),
        isVertical ? 
        Column(
           crossAxisAlignment: CrossAxisAlignment.start,
           children: options.map((opt) => Padding(
             padding: const EdgeInsets.only(bottom: 8.0),
             child: _buildOption(context, opt),
           )).toList()
        ) : 
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
           child: Row(
              children: options.map((opt) => Padding(
                padding: const EdgeInsets.only(right: 12.0),
                child: _buildOption(context, opt),
              )).toList(),
           ),
        ),
        if (errorMessage != null)
           Padding(
             padding: const EdgeInsets.only(top: 4.0),
             child: Text(errorMessage!, style: const TextStyle(color: Colors.red, fontSize: 12)),
           )
      ],
    );
  }

  Widget _buildOption(BuildContext context, CustomRadioOption<T> option) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isSelected = selectedValue == option.value;
    final color = option.color ?? const Color(0xFF104E8B);

    final bg = isDark ? AppColors.darkInputBg : Colors.white;
    final border = isDark ? Colors.grey[600]! : const Color(0xFFE9ECEF);
    final textColor = isDark ? Colors.grey[300] : Colors.grey.shade800;
    final iconColor = isDark ? Colors.grey[500] : Colors.grey.shade400;
    
    return InkWell(
      onTap: () => onSelect(option.value),
      borderRadius: BorderRadius.circular(12),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? color : bg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: isSelected ? color : border, width: 1.5),
          boxShadow: isSelected ? [BoxShadow(color: color.withValues(alpha: 0.2), blurRadius: 8, offset: const Offset(0, 4))] : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(isSelected ? Icons.check_circle : (option.icon ?? Icons.circle_outlined), 
                 color: isSelected ? Colors.white : iconColor, size: 18),
            const SizedBox(width: 8),
            Flexible(
              child: Text(option.label, style: TextStyle(
                color: isSelected ? Colors.white : textColor, 
                fontWeight: FontWeight.w700,
                fontSize: 14
              ), overflow: TextOverflow.ellipsis),
            ),
          ],
        ),
      ),
    );
  }
}

class CustomRadioOption<T> {
  final String label;
  final T value;
  final IconData? icon;
  final Color? color;
  CustomRadioOption({required this.label, required this.value, this.icon, this.color});
}
