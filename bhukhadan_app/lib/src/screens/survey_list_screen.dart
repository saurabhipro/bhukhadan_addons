import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:convert';
import 'package:image_picker/image_picker.dart';
import '../utils/storage.dart';
import '../utils/theme_provider.dart';
import '../constants/api_constants.dart';
import '../services/api_service.dart';
import '../utils/globals.dart';
import '../utils/localization.dart';
import 'pdf_view_screen.dart';
import 'create_survey_screen.dart';
import '../components/language_selector.dart';
import '../components/photo_picker_modal.dart';
import 'package:geolocator/geolocator.dart';
import 'dart:io';
import 'dart:async';
import '../services/screenshot_audit_service.dart';

class SurveyListScreen extends StatefulWidget {
  final bool isActive;
  const SurveyListScreen({super.key, this.isActive = false});

  @override
  State<SurveyListScreen> createState() => _SurveyListScreenState();
}

class _SurveyListScreenState extends State<SurveyListScreen> {
  List<dynamic> _surveys = [];
  bool _isLoading = true;
  String? _projectId;
  String? _villageId;
  String _khasraFilter = "";
  bool _showPhotoPicker = false;
  int? _selectedSurveyIdForPhoto;
  final Set<int> _uploadingSurveyIds = {};
  final ImagePicker _picker = ImagePicker();
  String? _activeFilter; // Store the active filter locally
  
  // Search & Pagination
  Timer? _searchDebounce;
  int _offset = 0;
  final int _limit = 100;
  bool _hasMore = true;
  bool _isSearching = false;
  final ScrollController _scrollController = ScrollController();
  final TextEditingController _searchController = TextEditingController();



  @override
  void didUpdateWidget(SurveyListScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isActive && !oldWidget.isActive) {
      // Store the filter locally when tab becomes active
      setState(() {
        _activeFilter = globalSurveyFilter;
      });
      _loadInitialData();
      
      // Force a rebuild after the frame to ensure filter chips update
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          setState(() {});
        }
      });
    }
  }

  @override
  void initState() {
    super.initState();
    ScreenshotAuditService.instance.setContext(screenName: 'Survey List', clearSurvey: true);
    _activeFilter = globalSurveyFilter;
    _scrollController.addListener(_onScroll);
    _loadInitialData();
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _scrollController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
      if (!_isLoading && _hasMore) {
        _fetchSurveys(_villageId!, loadMore: true, query: _khasraFilter);
      }
    }
  }

  Future<void> _loadInitialData() async {
    final proj = await getAsyncItem(SELECTED_PROJECT_ID_KEY);
    final vill = await getAsyncItem(SELECTED_VILLAGE_ID_KEY);
    setState(() {
      _projectId = proj;
      _villageId = vill;
    });

    if (vill != null) {
      _fetchSurveys(vill);
    } else {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _fetchSurveys(String villageId, {bool loadMore = false, String? query}) async {
    if (loadMore && !_hasMore) return;
    
    setState(() {
      if (loadMore) {
        // Just a flag for scrolling loader if needed
      } else {
        _isLoading = true;
        _offset = 0;
        _surveys = [];
      }
    });

    try {
      String url = '${ApiEndpoints.surveys}?village_id=$villageId&limit=$_limit&offset=$_offset';
      
      // Server-side search query
      if (query != null && query.isNotEmpty) {
        url += '&q=${Uri.encodeComponent(query)}';
      }
      
      // Filter by state if active
      if (_activeFilter != null && _activeFilter != 'all' && _activeFilter != 'total') {
        // Map 'pending' from dashboard to 'submitted' for the API
        String stateValue = _activeFilter!;
        if (stateValue == 'pending') {
          stateValue = 'submitted';
        }
        url += '&state=$stateValue';
      }

      final response = await ApiService.get(url);
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final List<dynamic> newSurveys = data['data'] ?? [];
        
        setState(() {
          if (loadMore) {
            _surveys.addAll(newSurveys);
          } else {
            _surveys = newSurveys;
          }
          _offset += newSurveys.length;
          _hasMore = newSurveys.length >= _limit;
        });
      }
    } catch (e) {
      debugPrint("Error fetching surveys: $e");
    } finally {
      setState(() {
        _isLoading = false;
        _isSearching = false;
      });
    }
  }

  void _onSearchChanged(String value) {
    setState(() {
      _khasraFilter = value;
      _isSearching = true;
    });

    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 600), () {
      if (_villageId != null) {
        _fetchSurveys(_villageId!, query: value);
      }
    });
  }

  Future<void> _quickAddPhoto(int surveyId) async {
    setState(() => _uploadingSurveyIds.add(surveyId));
    try {
      // Get location first
      Position? position;
      try {
        bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
        if (!serviceEnabled) {
          debugPrint("Location services are disabled.");
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Enable GPS for geotagging")));
        } else {
          LocationPermission permission = await Geolocator.checkPermission();
          if (permission == LocationPermission.denied) {
            permission = await Geolocator.requestPermission();
          }
          if (permission == LocationPermission.deniedForever) {
             ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Location permission permanently denied")));
          }
          
          if (permission == LocationPermission.always || permission == LocationPermission.whileInUse) {
            try {
               position = await Geolocator.getCurrentPosition(
                 desiredAccuracy: LocationAccuracy.best, // best accuracy
                 timeLimit: const Duration(seconds: 10), // increased timeout
               );
            } catch (e) {
               debugPrint("Current position failed, trying last known: $e");
            }
            // Fallback
            position ??= await Geolocator.getLastKnownPosition();
          }
        }
      } catch (e) {
        debugPrint("Location error: $e");
      }

      final XFile? photo = await _picker.pickImage(
        source: ImageSource.camera,
        imageQuality: 50,
      );
      
      if (photo != null) {
        await _uploadSinglePhoto(surveyId, File(photo.path), lat: position?.latitude, lng: position?.longitude);
      }
    } catch (e) {
      debugPrint("Error picking photo: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Error picking photo: $e")));
      }
    } finally {
      if (mounted) setState(() => _uploadingSurveyIds.remove(surveyId));
    }
  }

  Future<void> _uploadSinglePhoto(int surveyId, File file, {double? lat, double? lng}) async {
    try {
      final fileName = file.path.split('/').last;
      final urlResponse = await ApiService.post(ApiEndpoints.presignedUrls, {
        'survey_id': surveyId,
        'file_names': [fileName],
      });

      if (urlResponse.statusCode != 200 && urlResponse.statusCode != 201) throw "Failed to get presigned URL";

      final data = jsonDecode(urlResponse.body);
      final presignedUrls = (data['data']?['presigned_urls'] ?? data['presigned_urls'] ?? []) as List;
      if (presignedUrls.isEmpty) throw "No presigned URL returned";
      
      final uploadItem = presignedUrls[0];
      String? uploadUrl = uploadItem is String ? uploadItem : uploadItem['presigned_url'] ?? uploadItem['url'];
      String? s3Key = uploadItem is Map ? uploadItem['s3_key'] : null;

      if (uploadUrl == null) throw "Upload URL is null";

      final bytes = await file.readAsBytes();
      final putResponse = await ApiService.putFileDirectly(uploadUrl, bytes, 'image/jpeg');

      if (putResponse.statusCode != 200 && putResponse.statusCode != 201 && putResponse.statusCode != 204) throw "S3 Upload failed";

      if (s3Key != null) {
        String domain = Uri.parse(uploadUrl).host;
        final photoUrl = 'https://$domain/$s3Key';
        
        await ApiService.post("${ApiEndpoints.photoUpload}?survey_id=$surveyId", {
          'photos': [{
            's3_url': photoUrl,
            'latitude': lat,
            'longitude': lng,
            'filename': fileName,
            'file_size': await file.length(),
            'photo_type_id': 1
          }]
        });
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Photo uploaded successfully!")));
      }
      if (_villageId != null) _fetchSurveys(_villageId!);
    } catch (e) {
      debugPrint("Upload error: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Upload failed: $e")));
      }
    }
  }




  Future<void> _deleteSurvey(int surveyId) async {
    setState(() => _isLoading = true);
    try {
      final response = await ApiService.delete('${ApiEndpoints.survey}/$surveyId');
      if (response.statusCode == 200 || response.statusCode == 204) {
        if (mounted) {
           ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Survey deleted successfully")));
        }
        if (_villageId != null) _fetchSurveys(_villageId!, query: _khasraFilter);
      } else {
        throw "Failed to delete survey";
      }
    } catch (e) {
      debugPrint("Error deleting survey: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Delete failed: $e")));
      }
    } finally {
      setState(() => _isLoading = false);
    }
  }

  void _showDeleteConfirmation(dynamic survey) {
    final String khasra = survey['khasra_number']?.toString() ?? "";
    final TextEditingController confirmController = TextEditingController();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: isDark ? const Color(0xFF1E293B) : Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text("Confirm Deletion", style: TextStyle(fontWeight: FontWeight.w900, color: isDark ? Colors.white : Colors.black)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("Are you sure you want to delete Khasra #$khasra?", style: TextStyle(color: isDark ? Colors.white70 : Colors.black87)),
            const SizedBox(height: 16),
            Text("To confirm, please enter the Khasra number again:", style: TextStyle(fontSize: 12, color: isDark ? Colors.blueGrey[300] : Colors.grey)),
            const SizedBox(height: 8),
            TextField(
              controller: confirmController,
              textAlign: TextAlign.center,
              keyboardType: TextInputType.text,
              style: TextStyle(fontWeight: FontWeight.bold, color: isDark ? Colors.white : Colors.black),
              decoration: InputDecoration(
                hintText: "Type $khasra",
                hintStyle: TextStyle(color: isDark ? Colors.white24 : Colors.grey[400]),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                filled: true,
                fillColor: isDark ? Colors.black26 : Colors.grey[100],
              ),
            )
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("CANCEL", style: TextStyle(color: Colors.grey, fontWeight: FontWeight.bold))),
          Container(
            margin: const EdgeInsets.only(right: 8),
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFC62828),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onPressed: () {
                if (confirmController.text.trim() == khasra) {
                  Navigator.pop(ctx);
                  _deleteSurvey(survey['id']);
                } else {
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Khasra mismatch! Try again.")));
                }
              }, 
              child: const Text("DELETE", style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900))
            ),
          ),
        ],
      )
    );
  }

  List<dynamic> get _filteredSurveys {
    // With server-side search, we don't need additional local filtering for Khasra or State
    // because fetchSurveys already handles it.
    return _surveys;
  }


  @override
  Widget build(BuildContext context) {
    final themeProvider = Provider.of<ThemeProvider>(context);

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
        child: Stack(
          children: [
            SafeArea(
              child: Column(
                children: [
                  // Header with Back Button, Language Selector, and Theme Toggle
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
                        // Title
                        const Expanded(
                          child: Row(
                            children: [
                              Icon(Icons.assignment, color: Colors.white, size: 28),
                              SizedBox(width: 10),
                              Text(
                                "Surveys",
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 24,
                                  fontWeight: FontWeight.w900,
                                  letterSpacing: 0.5,
                                ),
                              ),
                            ],
                          ),
                        ),
                        // Language Selector (Height approx 30px)
                        const LanguageSelector(),
                        const SizedBox(width: 8),
                        
                        // Theme Toggle (Matched Height)
                        Consumer<ThemeProvider>(
                          builder: (context, themeProvider, _) {
                            return Container(
                              width: 36,
                              height: 36,
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.2),
                                shape: BoxShape.circle,
                                border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
                              ),
                              child: Material(
                                color: Colors.transparent,
                                child: InkWell(
                                  onTap: () => themeProvider.toggleTheme(),
                                  customBorder: const CircleBorder(),

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
                                        size: 20, // Smaller icon to fit height
                                      ),
                                    ),

                                ),
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                  
                  // Search Bar - Always visible
                  if (_surveys.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                      child: Container(
                        height: 45,
                        decoration: BoxDecoration(
                           color: Colors.white.withValues(alpha: 0.95),
                           borderRadius: BorderRadius.circular(25),
                           border: Border.all(color: Colors.grey.shade300, width: 1),
                           boxShadow: [
                              BoxShadow(
                                color: Colors.black.withValues(alpha: 0.05), 
                                blurRadius: 8, 
                                offset: const Offset(0, 2)
                              )
                           ]
                        ),
                        child: TextField(
                          controller: _searchController,
                          onChanged: _onSearchChanged,
                          style: const TextStyle(fontSize: 14, color: Colors.black87),
                          decoration: InputDecoration(
                            hintText: "Search server for Khasra...",
                            hintStyle: TextStyle(fontSize: 14, color: Colors.grey.shade500),
                            prefixIcon: Icon(Icons.search, color: Colors.grey.shade600, size: 20),
                            suffixIcon: _isSearching 
                              ? const SizedBox(width: 20, height: 20, child: Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator(strokeWidth: 2)))
                              : (_khasraFilter.isNotEmpty ? IconButton(icon: const Icon(Icons.close, size: 18), onPressed: () {
                                  _searchController.clear();
                                  _onSearchChanged("");
                                }) : null),
                            border: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          ),
                        ),
                      ),
                    ),
                  
                  // Status Filter Chips
                  if (_surveys.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      child: SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            _buildFilterChip('All', 'all', Icons.list_alt),
                            const SizedBox(width: 8),
                            _buildFilterChip('Submitted', 'submitted', Icons.send),
                            const SizedBox(width: 8),
                            _buildFilterChip('Approved', 'approved', Icons.check_circle),
                            const SizedBox(width: 8),
                            _buildFilterChip('Rejected', 'rejected', Icons.cancel),
                          ],
                        ),
                      ),
                    ),
                  
                  Expanded(
                    child: _isLoading 
                      ? const Center(child: CircularProgressIndicator(color: Colors.white))
                      : (_projectId == null || _villageId == null || _projectId!.isEmpty || _villageId!.isEmpty)
                        ? Center(child: Padding(
                            padding: const EdgeInsets.all(20.0),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.info_outline, size: 48, color: Colors.white.withValues(alpha: 0.7)),
                                const SizedBox(height: 16),
                                Text(
                                  Localization.t('msg_select_village'),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w500),
                                ),
                              ],
                            ),
                          ))
                        : RefreshIndicator(
                            onRefresh: () => _fetchSurveys(_villageId!),
                            child: _filteredSurveys.isEmpty
                              ? const Center(child: Text("No Surveys Found", style: TextStyle(color: Colors.white)))
                              : ListView.builder(
                                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 120),
                                  itemCount: _filteredSurveys.length + (_hasMore ? 1 : 0),
                                  controller: _scrollController,
                                  itemBuilder: (ctx, index) {
                                    if (index == _filteredSurveys.length) {
                                      return const Padding(
                                        padding: EdgeInsets.symmetric(vertical: 20),
                                        child: Center(child: CircularProgressIndicator(color: Colors.white)),
                                      );
                                    }
                                    final survey = _filteredSurveys[index];
                                    return _buildSurveyCard(survey);
                                  },
                                ),
                          ),
                  ),
                ],
              ),
            ),
            
            // Photo Picker Modal
            if (_showPhotoPicker && _selectedSurveyIdForPhoto != null)
              PhotoPickerModal(
                visible: _showPhotoPicker,
                surveyId: _selectedSurveyIdForPhoto!,
                onRequestClose: () {
                   setState(() {
                     _showPhotoPicker = false;
                     _selectedSurveyIdForPhoto = null;
                   });
                },
                onPhotosAdded: () {
                   if (_villageId != null) _fetchSurveys(_villageId!); // Refresh list
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildSurveyCard(dynamic survey) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    // Premium Status Colors
    Color statusColor = Colors.grey;
    IconData statusIcon = Icons.help_outline;
    final state = survey['state']?.toString().toLowerCase();
    
    if (state == 'approved') { 
      statusColor = const Color(0xFF2E7D32); // Premium Green
      statusIcon = Icons.check_circle; 
    }
    else if (state == 'rejected') { 
      statusColor = const Color(0xFFC62828); // Premium Red
      statusIcon = Icons.cancel; 
    }
    else if (state == 'submitted') { 
      statusColor = const Color(0xFFEF6C00); // Premium Orange
      statusIcon = Icons.send; 
    }
    else if (state == 'pending') { 
      statusColor = const Color(0xFFEA580C); // Deep Orange
      statusIcon = Icons.hourglass_bottom; 
    }

    final cardBg = isDark ? const Color(0xFF1E293B) : Colors.white;
    final primaryText = isDark ? Colors.white : const Color(0xFF1E293B);
    final secondaryText = isDark ? Colors.blueGrey[200] : Colors.blueGrey[600];
    final accentColor = isDark ? const Color(0xFF38BDF8) : const Color(0xFF0284C7);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: statusColor.withValues(alpha: 0.3), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: statusColor.withValues(alpha: isDark ? 0.1 : 0.15),
            blurRadius: 12,
            offset: const Offset(0, 6),
            spreadRadius: -2
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: [
                statusColor.withValues(alpha: isDark ? 0.25 : 0.15),
                statusColor.withValues(alpha: isDark ? 0.1 : 0.05),
                isDark ? cardBg.withValues(alpha: 0.8) : Colors.white.withValues(alpha: 0.8)
              ],
              stops: const [0.0, 0.4, 0.9]
            )
          ),
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Premium Left Status Strip
                Container(
                  width: 6, 
                  decoration: BoxDecoration(
                    color: statusColor,
                    boxShadow: [
                      BoxShadow(
                        color: statusColor.withValues(alpha: 0.5),
                        blurRadius: 4,
                        offset: const Offset(2, 0)
                      )
                    ]
                  ),
                ),
              
              // Main content
              Expanded(
                child: InkWell(
                  onTap: () async {
                    // Pass all IDs for swipe navigation
                    final allIds = _filteredSurveys.map((s) => s['id']).toList();
                    final result = await Navigator.pushNamed(context, '/survey-details', arguments: {
                       'id': survey['id'],
                       'allIds': allIds
                    });
                    if (result == true) _loadInitialData();
                  },
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Khasra & Status Row
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    "Khasra #${survey['khasra_number'] ?? 'N/A'}",
                                    style: TextStyle(
                                      fontWeight: FontWeight.w900,
                                      fontSize: 18, // Increased from 14
                                      color: primaryText,
                                      letterSpacing: -0.2,
                                    ),
                                  ),
                                  Text(
                                    "${survey['total_area']} ${Localization.t('hectare')}",
                                    style: TextStyle(
                                      fontSize: 15, // Increased from 12
                                      color: accentColor,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            // Compact Status Indicator
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                              decoration: BoxDecoration(
                                color: statusColor.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(20),
                                border: Border.all(color: statusColor.withValues(alpha: 0.2)),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(statusIcon, size: 10, color: statusColor),
                                  const SizedBox(width: 4),
                                  Text(
                                    (survey['state'] ?? 'Draft').toString().capitalize(),
                                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: statusColor),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        // Bottom Row: Date & Actions
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            // Date
                            Row(
                              children: [
                                Icon(Icons.calendar_month, size: 14, color: secondaryText),
                                const SizedBox(width: 4),
                                Text(
                                  survey['survey_date'] ?? 'N/A',
                                  style: TextStyle(fontSize: 12, color: secondaryText, fontWeight: FontWeight.w500),
                                ),
                              ],
                            ),
                            // Action Buttons Palette
                            Row(
                              children: [
                                _buildCompactActionButton(Icons.copy_all_rounded, isDark, () {
                                  final Map<String, dynamic> surveyCopy = Map.from(survey);
                                  surveyCopy.remove('id'); 
                                  surveyCopy.remove('state');
                                  surveyCopy.remove('created_at');
                                  surveyCopy.remove('updated_at');
                                  Navigator.of(context).push(MaterialPageRoute(builder: (_) => CreateSurveyScreen(prefilledData: surveyCopy)));
                                }),
                                const SizedBox(width: 6),
                                _buildCompactActionButton(Icons.picture_as_pdf_outlined, isDark, () {
                                  Navigator.of(context).push(MaterialPageRoute(builder: (_) => PdfViewScreen(villageId: survey['village_id']?.toString())));
                                }),
                                const SizedBox(width: 6),
                                _buildCompactActionButton(
                                  _uploadingSurveyIds.contains(survey['id']) ? Icons.sync : Icons.add_a_photo_outlined, 
                                  isDark, 
                                  () => _quickAddPhoto(survey['id'])
                                ),
                                if (state != 'approved') ...[
                                  const SizedBox(width: 6),
                                  _buildCompactActionButton(
                                    Icons.delete_forever_outlined, 
                                    isDark, 
                                    () => _showDeleteConfirmation(survey),
                                    isDelete: true,
                                  ),
                                ],
                              ],
                            ),
                          ],
                        ),
                        
                        const SizedBox(height: 12),
                        // Counts Row
                        Container(
                           margin: const EdgeInsets.only(top: 6),
                           padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
                           child: Row(
                              mainAxisAlignment: MainAxisAlignment.start,
                              children: [
                                 _buildCountBadge(
                                    Icons.people, 
                                    _parseCount(
                                       survey, 
                                       ['landowner_ids', 'landowners', 'landowner_master_ids', 'owners'], 
                                       ['no_of_landowners', 'landowner_count', 'total_landowners', 'landowners_count']
                                    ), 
                                    Colors.blue.shade700,
                                    Colors.blue.shade50,
                                    isDark
                                 ),
                                 const SizedBox(width: 8),
                                 _buildCountBadge(
                                    Icons.park, 
                                    _parseCount(
                                       survey, 
                                       ['tree_lines', 'trees'], 
                                       ['tree_count', 'total_trees']
                                    ),
                                    Colors.green.shade700,
                                    Colors.green.shade50,
                                    isDark
                                 ),
                                 const SizedBox(width: 8),
                                 _buildCountBadge(
                                    Icons.camera_alt, 
                                    _parseCount(
                                       survey, 
                                       ['photos', 'images', 'fetched_images', 'photo_urls', 'file_names'], 
                                       ['photo_count', 'image_count', 'no_of_images', 'images_count']
                                    ),
                                    Colors.orange.shade800,
                                    Colors.orange.shade50,
                                    isDark
                                 ),
                              ],
                           ),
                        )
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
      ),
    );
  }

  int _parseCount(Map<String, dynamic> data, List<String> listKeys, List<String> countKeys) {
    // 1. Check list keys (return length)
    for (var key in listKeys) {
      if (data[key] is List) {
        return (data[key] as List).length;
      }
    }
    // 2. Check direct count keys (int or String)
    for (var key in countKeys) {
      if (data[key] != null) {
        if (data[key] is int) return data[key];
        if (data[key] is String) return int.tryParse(data[key]) ?? 0;
      }
    }
    return 0;
  }

  Widget _buildCountBadge(IconData icon, int count, Color color, Color bgColor, bool isDark) {
      return Container(
         padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
         decoration: BoxDecoration(
            color: isDark ? color.withValues(alpha: 0.2) : bgColor,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: color.withValues(alpha: 0.3))
         ),
         child: Row(
            children: [
               Icon(icon, size: 14, color: color),
               const SizedBox(width: 6),
               Text(
                  "$count",
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: color)
               )
            ],
         ),
      );
  } 
  
  // Removed _buildVerticalDivider and _buildCountItem as they are replaced by _buildCountBadge

   Widget _buildActionButton(IconData icon, String label, VoidCallback onTap) {
      return InkWell(
         onTap: onTap,
         borderRadius: BorderRadius.circular(8),
          child: Column(
             mainAxisAlignment: MainAxisAlignment.center,
             children: [
                Icon(icon, color: const Color(0xFF104E8B), size: 22),
                const SizedBox(height: 4),
                Text(label, style: const TextStyle(color: Color(0xFF104E8B), fontSize: 11, fontWeight: FontWeight.bold), textAlign: TextAlign.center),
             ],
          ),
      );
   }

   Widget _buildCompactActionButton(IconData icon, bool isDark, VoidCallback onTap, {bool isDelete = false}) {
      return Material(
         color: isDelete 
          ? (isDark ? Colors.red.withValues(alpha: 0.1) : Colors.red.withValues(alpha: 0.05))
          : (isDark ? Colors.white.withValues(alpha: 0.05) : Colors.black.withValues(alpha: 0.03)),
         borderRadius: BorderRadius.circular(8),
         child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(8),
            child: Container(
               padding: const EdgeInsets.all(10), // Increased padding
               child: Icon(
                 icon, 
                 color: isDelete 
                  ? const Color(0xFFC62828) 
                  : (isDark ? Colors.white70 : const Color(0xFF0284C7)), 
                 size: 22 // Increased icon size
               ),
            ),
         ),
      );
   }

   Widget _buildFilterChip(String label, String filterValue, IconData icon) {
     bool isActive = false; if (_activeFilter == null || _activeFilter == 'all' || _activeFilter == 'total') { isActive = (filterValue == 'all'); } else if (_activeFilter == 'pending' || _activeFilter == 'submitted') { isActive = (filterValue == 'submitted'); } else { isActive = (_activeFilter == filterValue); }
     final isDark = Theme.of(context).brightness == Brightness.dark;
     
     // Color coding for different statuses
     Color getFilterColor() {
       switch (filterValue) {
         case 'submitted':
           return Colors.orange;
         case 'approved':
           return Colors.green;
         case 'rejected':
           return Colors.red;
         default:
           return const Color(0xFF104E8B);
       }
     }
     
     final filterColor = getFilterColor();
     
     return FilterChip(
       label: Row(
         mainAxisSize: MainAxisSize.min,
         children: [
           Icon(
             icon, 
             size: 16, 
             color: isActive ? Colors.white : filterColor
           ),
           const SizedBox(width: 6),
           Text(
             label,
             style: TextStyle(
               color: isActive ? Colors.white : filterColor,
               fontWeight: isActive ? FontWeight.w900 : FontWeight.w600,
               fontSize: 13,
             ),
           ),
         ],
       ),
       selected: isActive,
       onSelected: (selected) {
         setState(() {
           _activeFilter = filterValue;
           globalSurveyFilter = filterValue; }); if (_villageId != null) { _fetchSurveys(_villageId!, query: _khasraFilter); }
       },
       backgroundColor: isDark ? Colors.white.withValues(alpha: 0.1) : Colors.white,
       selectedColor: filterColor,
       checkmarkColor: Colors.white,
       shape: RoundedRectangleBorder(
         borderRadius: BorderRadius.circular(20),
         side: BorderSide(
           color: isActive ? filterColor : (isDark ? Colors.white30 : filterColor.withValues(alpha: 0.4)),
           width: isActive ? 2 : 1,
         ),
       ),
       elevation: isActive ? 6 : 1,
       shadowColor: filterColor.withValues(alpha: 0.4),
       padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
     );
   }
}

extension StringExtension on String {
    String capitalize() {
      return "${this[0].toUpperCase()}${substring(1)}";
    }
}


