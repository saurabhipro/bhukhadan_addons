import 'package:flutter/material.dart';
import 'dart:io';
import 'dart:convert';
import 'package:image_picker/image_picker.dart';
import '../services/api_service.dart';
import '../constants/api_constants.dart';
// Import AppAssets
import 'package:provider/provider.dart';
import '../utils/localization.dart';
import '../utils/theme_provider.dart';
import '../components/custom_button.dart';
import '../components/language_selector.dart';
import '../components/photo_picker_modal.dart';
import 'package:geolocator/geolocator.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'dart:ui';
import 'package:geocoding/geocoding.dart';
import 'package:image/image.dart' as img;
import 'package:intl/intl.dart';
import 'create_survey_screen.dart';
import '../services/screenshot_audit_service.dart';

class SurveyDetailsScreen extends StatefulWidget {
  final int surveyId;
  final List<int>? allSurveyIds;
  
  const SurveyDetailsScreen({super.key, required this.surveyId, this.allSurveyIds});

  @override
  State<SurveyDetailsScreen> createState() => _SurveyDetailsScreenState();
}

class _SurveyDetailsScreenState extends State<SurveyDetailsScreen> {
  late PageController _pageController;
  late List<int> _ids;
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    ScreenshotAuditService.instance.setContext(
      screenName: 'Survey Details',
      surveyId: widget.surveyId,
    );
    _ids = widget.allSurveyIds ?? [widget.surveyId];
    _currentIndex = _ids.indexOf(widget.surveyId);
    if (_currentIndex == -1) {
       _ids = [widget.surveyId];
       _currentIndex = 0;
    }
    _pageController = PageController(initialPage: _currentIndex);
  }
  
  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PageView.builder(
      controller: _pageController,
      itemCount: _ids.length,
      physics: const BouncingScrollPhysics(),
      onPageChanged: (index) {
        _currentIndex = index;
        ScreenshotAuditService.instance.setContext(
          screenName: 'Survey Details',
          surveyId: _ids[index],
        );
      },
      itemBuilder: (context, index) {
        return SurveyDetailsContent(surveyId: _ids[index]);
      },
    );
  }
}

class SurveyDetailsContent extends StatefulWidget {
  final int surveyId;
  const SurveyDetailsContent({super.key, required this.surveyId});

  @override
  State<SurveyDetailsContent> createState() => _SurveyDetailsContentState();
}

class _SurveyDetailsContentState extends State<SurveyDetailsContent> {
  Map<String, dynamic>? _surveyData;
  bool _isLoading = true;
  bool _isSubmitting = false;
  bool _showPhotoPicker = false;
  final ImagePicker _picker = ImagePicker();
  bool _isPhotoUploading = false;

  Future<void> _quickAddPhoto() async {
    try {
      // Get location first
      Position? position;
      try {
        bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
        if (!serviceEnabled) {
          debugPrint("Location services are disabled.");
        } else {
          LocationPermission permission = await Geolocator.checkPermission();
          if (permission == LocationPermission.denied) {
            permission = await Geolocator.requestPermission();
          }
          if (permission == LocationPermission.always || permission == LocationPermission.whileInUse) {
            position = await Geolocator.getCurrentPosition(
              desiredAccuracy: LocationAccuracy.high,
              timeLimit: const Duration(seconds: 5),
            );
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
        final double? lat = position?.latitude;
        final double? lng = position?.longitude;
        debugPrint("Captured Photo with Location: $lat, $lng");
        
        File imageToUpload = File(photo.path);
        
        // Apply Watermark if location is available
        if (position != null) {
           try {
             if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(duration: Duration(seconds: 1), content: Text("Processing image with watermarks...")));
             final watermarked = await _watermarkImage(imageToUpload, position);
             if (watermarked != null) {
                imageToUpload = watermarked;
             }
           } catch (e) {
             debugPrint("Watermark failed: $e");
           }
        }
        
        await _uploadSinglePhoto(imageToUpload, lat: lat, lng: lng);
      }
    } catch (e) {
      debugPrint("Error picking photo: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Error picking photo: $e")));
      }
    }
  }

  Future<void> _uploadSinglePhoto(File file, {double? lat, double? lng}) async {
    setState(() => _isPhotoUploading = true);
    try {
      // Step 1: Get presigned URL
      final fileName = file.path.split('/').last;
      final urlResponse = await ApiService.post(ApiEndpoints.presignedUrls, {
        'survey_id': widget.surveyId,
        'file_names': [fileName],
      });

      if (urlResponse.statusCode != 200 && urlResponse.statusCode != 201) {
        throw "Failed to get presigned URL";
      }

      final data = jsonDecode(urlResponse.body);
      final presignedUrls = (data['data']?['presigned_urls'] ?? data['presigned_urls'] ?? []) as List;
      
      if (presignedUrls.isEmpty) throw "No presigned URL returned";
      
      final uploadItem = presignedUrls[0];
      String? uploadUrl = uploadItem is String ? uploadItem : uploadItem['presigned_url'] ?? uploadItem['url'];
      String? s3Key = uploadItem is Map ? uploadItem['s3_key'] : null;

      if (uploadUrl == null) throw "Upload URL is null";

      // Step 2: Upload to S3
      final bytes = await file.readAsBytes();
      final putResponse = await ApiService.putFileDirectly(uploadUrl, bytes, 'image/jpeg');

      if (putResponse.statusCode != 200 && putResponse.statusCode != 201 && putResponse.statusCode != 204) {
        throw "S3 Upload failed";
      }

      // Step 3: Register Photo
      if (s3Key != null) {
        String domain = Uri.parse(uploadUrl).host;
        final photoUrl = 'https://$domain/$s3Key';
        
        final payload = {
          'photos': [{
            's3_url': photoUrl,
            'latitude': lat,
            'longitude': lng,
            'filename': fileName,
            'file_size': await file.length(),
            'photo_type_id': 1 // Default to general photo
          }]
        };
        
        await ApiService.post("${ApiEndpoints.photoUpload}?survey_id=${widget.surveyId}", payload);
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Photo uploaded successfully!")));
      }
      // Small delay to allow backend to propagate
      await Future.delayed(const Duration(milliseconds: 1000));
      _fetchDetails(); // Refresh
    } catch (e) {
      debugPrint("Upload error: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Upload failed: $e")));
      }
    } finally {
      if (mounted) setState(() => _isPhotoUploading = false);
    }
  }

  Future<File?> _watermarkImage(File file, Position pos) async {
    try {
      // 1. Decode Image
      final bytes = await file.readAsBytes();
      img.Image? originalImage = img.decodeImage(bytes);
      if (originalImage == null) return null;
      
      // OPTIMIZATION: Resize image if too large (e.g., > 1600px width)
      // This serves two purposes:
      // 1. Makes the fixed-size font (arial48) appear larger/readable relative to the image.
      // 2. Reduces upload size/bandwidth.
      if (originalImage.width > 1600) {
        originalImage = img.copyResize(originalImage, width: 1600);
      }

      // 2. Get Address
      String addressText = "Unknown Location";
      String cityState = "";
      try {
        List<Placemark> placemarks = await placemarkFromCoordinates(pos.latitude, pos.longitude);
        if (placemarks.isNotEmpty) {
           final p = placemarks.first;
           // Format: "Street, SubLocality"
           addressText = "${p.street}, ${p.subLocality}";
           if (addressText.startsWith(", ")) addressText = addressText.substring(2);
           
           // Format: "Locality, State, Country - Pin"
           cityState = "${p.locality}, ${p.administrativeArea}, ${p.country}";
           // Append pin to address line to mimic screenshot
           addressText += ", ${p.postalCode}, ${p.country}";
        }
      } catch (e) {
        debugPrint("Geocoding error: $e");
      }

      // 3. Prepare Text with Timezone
      final now = DateTime.now();
      final offset = now.timeZoneOffset;
      final sign = offset.isNegative ? '-' : '+';
      final hours = offset.inHours.abs().toString().padLeft(2, '0');
      final minutes = (offset.inMinutes.abs() % 60).toString().padLeft(2, '0');
      final gmtString = "GMT $sign$hours:$minutes";
      
      final dateStr = "${DateFormat('EEEE, dd/MM/yyyy hh:mm a').format(now)} $gmtString";
      final latLongStr = "Lat ${pos.latitude.toStringAsFixed(6)}° Long ${pos.longitude.toStringAsFixed(6)}°";
      
      // 4. Draw Overlay settings
      int w = originalImage.width;
      int h = originalImage.height;
      int fontSize = 48; 
      int lineHeight = fontSize + 12; // increased spacing
      int padding = 40;
      
      // We need about 5 lines of text height plus padding
      int boxHeight = (lineHeight * 5) + (padding * 2);
      
      // Fill bottom rect with semi-transparent black
      img.fillRect(
        originalImage, 
        x1: 0, 
        y1: h - boxHeight, 
        x2: w, 
        y2: h, 
        color: img.ColorRgba8(0, 0, 0, 160) 
      );
      
      // Text Color: White
      final textColor = img.ColorRgba8(255, 255, 255, 255);
      
      int currentY = h - boxHeight + padding;
      
      // Line 1: City/State (Header)
      img.drawString(originalImage, cityState.isNotEmpty ? cityState : "Location Details", font: img.arial48, x: padding, y: currentY, color: textColor);
      currentY += lineHeight + 10; // Extra gap after header
      
      // Line 2: Address (wrapped if needed, simpler truncation for now)
      if (addressText.length > 55) addressText = "${addressText.substring(0, 52)}...";
      img.drawString(originalImage, addressText, font: img.arial48, x: padding, y: currentY, color: textColor);
      currentY += lineHeight;
      
      // Line 3: Lat/Long
      img.drawString(originalImage, latLongStr, font: img.arial48, x: padding, y: currentY, color: textColor);
      currentY += lineHeight;
      
      // Line 4: Date
      img.drawString(originalImage, dateStr, font: img.arial48, x: padding, y: currentY, color: textColor);

      // 5. Save to new file
      final newPath = file.path.replaceFirst('.jpg', '_watermarked.jpg');
      final newFile = File(newPath);
      await newFile.writeAsBytes(img.encodeJpg(originalImage, quality: 90));
      
      return newFile;
    } catch (e) {
      debugPrint("Watermarking process failed: $e");
      return null;
    }
  }


  @override
  void initState() {
    super.initState();
    ScreenshotAuditService.instance.setContext(
      screenName: 'Survey Details',
      surveyId: widget.surveyId,
    );
    _fetchDetails();
  }

  Future<void> _fetchDetails() async {
    try {
      final response = await ApiService.get('${ApiEndpoints.survey}/${widget.surveyId}');
      
      // Dedicated fetch for images as per user requirement
      final imagesResponse = await ApiService.get('${ApiEndpoints.surveyImages}?survey_id=${widget.surveyId}');
      debugPrint("Images Response for Survey ${widget.surveyId}: ${imagesResponse.body}");
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body)['data'];
        debugPrint("SURVEY DETAILS RAW KEYS: ${data.keys.toList()}");
        debugPrint("SURVEY PHOTOS VALUE: ${data['photos']}");
        debugPrint("SURVEY_IMAGE VALUE: ${data['survey_image']}");
        
        if (imagesResponse.statusCode == 200) {
          try {
            final imagesData = jsonDecode(imagesResponse.body);
            if (imagesData is Map && imagesData.containsKey('error')) {
              debugPrint("Server-side error in images endpoint: ${imagesData['error']}");
            } else {
              dynamic photoList = [];
              if (imagesData is List) {
                photoList = imagesData;
              } else if (imagesData is Map) {
                // Priority 1: data key which might be a list or map
                final d = imagesData['data'];
                if (d is List) {
                   photoList = d;
                } else if (d is Map) {
                   if (d['images'] is List) {
                     photoList = d['images'];
                   } else if (d['photos'] is List) photoList = d['photos'];
                   else if (d['survey_images'] is List) photoList = d['survey_images'];
                }
                
                // Priority 2: root keys if list is still empty
                if (photoList.isEmpty) {
                   if (imagesData['images'] is List) {
                     photoList = imagesData['images'];
                   } else if (imagesData['photos'] is List) photoList = imagesData['photos'];
                   else if (imagesData['survey_images'] is List) photoList = imagesData['survey_images'];
                   else if (imagesData['data'] is List) photoList = imagesData['data']; // Fallback if data was list but missed
                }
              }
              data['fetched_images'] = photoList;
              debugPrint("Successfully fetched ${photoList.length} images from dedicated endpoint");
            }
          } catch (e) {
            debugPrint("Failed to parse images response: $e");
          }
        }

        setState(() {
          _surveyData = data;
        });
      }
    } catch (e) {
      debugPrint("Error fetching details: $e");
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _confirmDeletePhoto(dynamic photoId) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("Delete Photo"),
        content: const Text("Are you sure you want to delete this photo?"),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text("Cancel")),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true), 
            child: const Text("Delete", style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );

    if (confirm == true) {
      _deletePhoto(photoId);
    }
  }

  Future<void> _deletePhoto(dynamic photoId) async {
    setState(() => _isLoading = true);
    try {
      // Endpoint: DELETE /api/bhuarjan/photo/<photo_id>
      debugPrint("Attempting DELETE: ${ApiEndpoints.deletePhoto}/$photoId");
      final response = await ApiService.delete('${ApiEndpoints.deletePhoto}/$photoId');
      
      if (response.statusCode == 200 || response.statusCode == 204) {
         if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Photo deleted successfully")));
         _fetchDetails(); // Refresh
      } else {
         debugPrint("Delete failed status: ${response.statusCode}, body: ${response.body}");
         if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Delete failed (${response.statusCode}): ${response.reasonPhrase ?? 'Unknown error'}")));
      }
    } catch (e) {
      debugPrint("Delete photo error: $e");
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Delete failed: $e")));
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _handleSubmit() async {
    // Submit survey (change state to submitted)
    setState(() => _isSubmitting = true);
    try {
       final response = await ApiService.patch(
         '/bhuarjan/survey/${widget.surveyId}', 
         {'state': 'submitted'}
       );
       
       if (response.statusCode == 200) {
         if (!mounted) return;
         ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Survey Submitted Successfully")));
         // Refresh
         _fetchDetails();
       } else {
         throw Exception("Failed to submit");
       }
    } catch (e) {
       if (!mounted) return;
       ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Error: $e")));
    } finally {
       setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_surveyData == null) {
      return Scaffold(appBar: AppBar(), body: const Center(child: Text("Error loading survey")));
    }
    
    final themeProvider = Provider.of<ThemeProvider>(context);
    final isDark = themeProvider.isDarkMode;
    final s = _surveyData!;
    final landowners = (s['landowner_ids'] as List?) ?? [];

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
                     // Back Button
                     IconButton(
                       onPressed: () => Navigator.pop(context),
                       icon: const Icon(Icons.arrow_back, color: Colors.white, size: 24),
                       padding: EdgeInsets.zero,
                       constraints: const BoxConstraints(),
                     ),
                     const SizedBox(width: 12),
                     const Expanded(
                       child: Text(
                         "Survey Details",
                         style: TextStyle(
                           color: Colors.white,
                           fontSize: 18,
                           fontWeight: FontWeight.w900,
                           letterSpacing: 0.5,
                         ),
                       ),
                     ),
                     // Language Selector
                     const LanguageSelector(),
                     const SizedBox(width: 8),
                     // Theme Toggle
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
                child: RefreshIndicator(
                  onRefresh: _fetchDetails,
                  child: SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(), // Ensure scroll works for refresh even if content is short
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
             _buildSectionCard(
                "1. Project & Location Details", 
                [
                   Row(
                     mainAxisAlignment: MainAxisAlignment.spaceBetween,
                     crossAxisAlignment: CrossAxisAlignment.start,
                     children: [
                        const Expanded(child: SizedBox()),
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                              decoration: BoxDecoration(
                                color: (s['survey_type'] == 'rural')
                                    ? Colors.green.withValues(alpha: 0.12)
                                    : Colors.grey.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(20),
                                border: Border.all(
                                  color: (s['survey_type'] == 'rural') ? Colors.green : Colors.grey,
                                  width: 1.2,
                                ),
                              ),
                              child: Text(
                                (s['survey_type'] == 'rural') ? 'ग्रामीण' : 'शहरी',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: (s['survey_type'] == 'rural') ? Colors.green : Colors.grey[600],
                                ),
                              ),
                            ),
                            const SizedBox(width: 6),
                            Container(
                               padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                               decoration: BoxDecoration(
                                  color: (s['state']?.toString().toLowerCase() == 'approved') ? Colors.green.withValues(alpha: 0.1) : Colors.orange.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(20),
                                  border: Border.all(color: (s['state']?.toString().toLowerCase() == 'approved') ? Colors.green : Colors.orange, width: 1)
                               ),
                               child: Row(
                                  children: [
                                    Icon((s['state']?.toString().toLowerCase() == 'approved') ? Icons.check_circle : Icons.info, size: 14, color: (s['state']?.toString().toLowerCase() == 'approved') ? Colors.green : Colors.orange),
                                    const SizedBox(width: 4),
                                    Text(s['state']?.toString().toUpperCase() ?? 'N/A', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: (s['state']?.toString().toLowerCase() == 'approved') ? Colors.green : Colors.orange)),
                                  ],
                               ),
                            )
                          ],
                        )
                     ],
                   ),
                   Divider(height: 24, thickness: 1, color: isDark ? Colors.grey[800] : Colors.grey[200]),
                   Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                         Icon(Icons.location_on_outlined, size: 18, color: isDark ? Colors.blue[300] : const Color(0xFF104E8B)),
                         const SizedBox(width: 8),
                         Expanded(
                            child: RichText(
                               text: TextSpan(
                                  style: TextStyle(fontSize: 14, color: isDark ? Colors.grey[300] : const Color(0xFF2D3436), height: 1.4),
                                  children: [
                                     TextSpan(text: "${s['village_name'] ?? '-'}, ", style: const TextStyle(fontWeight: FontWeight.bold)),
                                     TextSpan(text: "${s['tehsil_name'] ?? '-'}, "),
                                     TextSpan(text: "${s['district_name'] ?? '-'}", style: const TextStyle(color: Colors.grey)),
                                  ]
                               )
                            ),
                         )
                      ],
                   ),
                   const SizedBox(height: 12),
                   Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                         color: isDark ? Colors.black26 : Colors.grey[50],
                         borderRadius: BorderRadius.circular(8),
                      ),
                      child: Column(
                         children: [
                            Row(
                               children: [
                                  Icon(Icons.apartment, size: 16, color: Colors.grey[600]),
                                  const SizedBox(width: 8),
                                  Expanded(child: Text("${s['department_name'] ?? 'N/A'}", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600))),
                               ],
                            ),
                            const SizedBox(height: 8),
                            Row(
                               children: [
                                  Icon(Icons.assignment_outlined, size: 16, color: Colors.grey[600]),
                                  const SizedBox(width: 8),
                                  Expanded(child: Text("${s['project_name'] ?? 'N/A'}", style: TextStyle(fontSize: 13))),
                               ],
                            ),
                         ],
                      ),
                   ),
                ],
                icon: Icons.business
             ),
             const SizedBox(height: 16),
             _buildSectionCard(
                "2. Land Information",
                [
                   _buildReadOnlyField("Khasra Number", "${s['khasra_number'] ?? 'N/A'}", labelIcon: Icons.grid_on),
                   _buildReadOnlyField("Total Area", s['total_area']?.toString() ?? '0.0', labelIcon: Icons.crop_square),
                   _buildReadOnlyField("Acquired Area", s['acquired_area']?.toString() ?? '0.0', labelIcon: Icons.pie_chart),
                   // Distance from Main Road
                   Builder(builder: (context) {
                      String dist = s['distance']?.toString() ?? "";
                      if (dist.isEmpty && s['remarks'] != null) {
                         final remarks = s['remarks'].toString();
                         if (remarks.contains("Distance: ")) {
                            try {
                               dist = remarks.split("Distance: ")[1].split("m")[0];
                            } catch (_) {}
                         }
                      }
                      return _buildReadOnlyField("Distance from Main Road", dist.isNotEmpty ? "$dist m" : "-", labelIcon: Icons.add_road);
                   }),

                   
                   if (s['has_traded_land'] == 'yes')
                      _buildReadOnlyField("Diverted Land Area", s['traded_land_area']?.toString() ?? '0.0', labelIcon: Icons.area_chart),
                   
                   if (s['crop_type_name'] != null || s['crop_type'] != null)
                      _buildReadOnlyField("Land Type", "${s['crop_type_name'] ?? "Type ${s['crop_type']}"}", labelIcon: Icons.landscape),
                   if (s['irrigation_type'] != null)
                      _buildReadOnlyField("Irrigation", "${s['irrigation_type']}", labelIcon: Icons.opacity),

                ],
                icon: Icons.location_on
             ),

             const SizedBox(height: 16),

             _buildSectionCard(
                "3. Landowners",
                [
                   if (landowners.isEmpty)
                      const Text("No landowner information available", style: TextStyle(color: Colors.grey))
                   else
                      ...landowners.asMap().entries.map((e) {
                         final l = e.value;
                         final index = e.key;
                         final isLast = index == landowners.length - 1;
                         
                         // Determine Father/Spouse Name
                         String fsName = l['father_name'] ?? l['spouse_name'] ?? 'N/A';
                         if (l['father_name'] != null && l['spouse_name'] != null) {
                            fsName = "${l['father_name']} / ${l['spouse_name']}";
                         }

                         return Column(
                           children: [
                             Row(
                               crossAxisAlignment: CrossAxisAlignment.center,
                               children: [
                                 Container(
                                   padding: const EdgeInsets.all(10),
                                   decoration: BoxDecoration(
                                     color: isDark ? Colors.blue.withValues(alpha: 0.2) : const Color(0xFFE3F2FD),
                                     shape: BoxShape.circle
                                   ),
                                   child: Icon(Icons.person, size: 20, color: isDark ? Colors.blue[200] : const Color(0xFF1565C0)),
                                 ),
                                 const SizedBox(width: 14),
                                 Expanded(
                                   child: Column(
                                     crossAxisAlignment: CrossAxisAlignment.start,
                                     children: [
                                       Text(
                                         l['name'] ?? 'Unknown',
                                         style: TextStyle(
                                           fontWeight: FontWeight.bold,
                                           fontSize: 15,
                                           color: isDark ? Colors.white : const Color(0xFF2D3436)
                                         ),
                                       ),
                                       const SizedBox(height: 2),
                                       Text(
                                         "Father/Spouse: $fsName",
                                         style: TextStyle(
                                            fontSize: 13,
                                            color: isDark ? Colors.grey[400] : const Color(0xFF636E72)
                                         ),
                                       ),
                                     ],
                                   ),
                                 ),
                               ],
                             ),
                             if (!isLast)
                               Padding(
                                 padding: const EdgeInsets.only(left: 54, top: 12, bottom: 12),
                                 child: Divider(height: 1, thickness: 1, color: isDark ? Colors.grey[800] : Colors.grey[200]),
                               ),
                           ],
                         );
                      }),
                ],
                icon: Icons.people
             ),

             const SizedBox(height: 16),

             _buildSectionCard(
                "4. Structure Details",
                [
                   _buildReadOnlyField("Has House", (s['has_house']?.toString().toLowerCase().startsWith('y') == true) ? 'Yes' : 'No', labelIcon: Icons.house),
                   if (s['has_house'] == 'yes') ...[
                      _buildReadOnlyField("House Type", "${s['house_type'] ?? 'N/A'}", labelIcon: Icons.house),
                      _buildReadOnlyField("House Area", s['house_area']?.toString() ?? '0.0', labelIcon: Icons.square_foot),
                      const SizedBox(height: 8),
                   ],

                   _buildReadOnlyField("Has Shed/Structure", (s['has_shed']?.toString().toLowerCase().startsWith('y') == true) ? 'Yes' : 'No', labelIcon: Icons.storefront),
                   if (s['has_shed'] == 'yes') ...[
                      _buildReadOnlyField("Shed Area", s['shed_area']?.toString() ?? '0.0', labelIcon: Icons.storefront),
                   ],
                ],
                icon: Icons.home_work
             ),

             const SizedBox(height: 16),

             _buildSectionCard(
                "5. Tree Details",
                [
                   if (s['tree_lines'] == null || (s['tree_lines'] as List).isEmpty)
                      const Text("No trees added", style: TextStyle(color: Colors.grey, fontStyle: FontStyle.italic))
                   else
                       Column(
                        children: (s['tree_lines'] as List).asMap().entries.map((entry) {
                               final index = entry.key;
                               final t = entry.value;
                               final isLast = index == (s['tree_lines'] as List).length - 1;

                               // Determine stage icon
                               IconData stageIcon = Icons.help_outline;
                               Color stageColor = Colors.grey;
                               String stage = (t['development_stage']?.toString() ?? "").toLowerCase();
                               
                               if (stage.contains('semi')) {
                                  stageIcon = Icons.star_half;
                                  stageColor = Colors.orangeAccent;
                               } else if (stage.contains('under') || stage.contains('sapling')) {
                                  stageIcon = Icons.grass;
                                  stageColor = Colors.lightGreen;
                               } else if (stage.contains('fully') || stage.contains('mature')) {
                                  stageIcon = Icons.stars;
                                  stageColor = const Color(0xFF27AE60);
                               }

                               return Column(
                                 children: [
                                   Padding(
                                     padding: const EdgeInsets.symmetric(vertical: 8.0),
                                     child: Row(children: [
                                        // 1. Tree Icon
                                        Container(
                                          padding: const EdgeInsets.all(8),
                                          decoration: BoxDecoration(
                                            color: const Color(0xFF27AE60).withValues(alpha: 0.1),
                                            shape: BoxShape.circle,
                                          ),
                                          child: const Icon(Icons.park, size: 20, color: Color(0xFF27AE60)),
                                        ),
                                        const SizedBox(width: 16),
                                        
                                        // 2. Tree Name & Type
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Text(
                                                "${t['tree_name'] ?? 'Tree'} (${t['development_stage'] ?? 'N/A'})",
                                                style: TextStyle(
                                                  fontWeight: FontWeight.bold,
                                                  fontSize: 14,
                                                  color: isDark ? Colors.white : Colors.black87,
                                                ),
                                              ),
                                              if (t['girth_cm'] != null && t['girth_cm'].toString() != '0' && t['girth_cm'].toString() != '0.0')
                                                Text(
                                                  "Girth: ${t['girth_cm']} cm",
                                                  style: TextStyle(
                                                     fontSize: 12,
                                                     color: isDark ? Colors.grey[400] : Colors.grey.shade600
                                                  )
                                                )
                                            ],
                                          ),
                                        ),
                                        
                                        // 3. Stage Icon (visual indicator for semi/under/fully)
                                        if (stage.isNotEmpty) ...[
                                           Tooltip(
                                             message: t['development_stage']?.toString() ?? '',
                                             child: Container(
                                                padding: const EdgeInsets.all(6),
                                                decoration: BoxDecoration(
                                                  color: stageColor.withValues(alpha: 0.1),
                                                  borderRadius: BorderRadius.circular(8),
                                                ),
                                                child: Icon(stageIcon, size: 18, color: stageColor),
                                             ),
                                           ),
                                           const SizedBox(width: 12),
                                        ],

                                        // 4. Quantity Badge
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                          decoration: BoxDecoration(
                                            color: const Color(0xFF27AE60),
                                            borderRadius: BorderRadius.circular(20),
                                          ),
                                          child: Row(
                                            children: [
                                              const Icon(Icons.format_list_numbered, size: 14, color: Colors.white),
                                              const SizedBox(width: 4),
                                              Text(
                                                "${t['quantity']}",
                                                style: const TextStyle(
                                                  fontWeight: FontWeight.bold,
                                                  fontSize: 14,
                                                  color: Colors.white,
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                     ]),
                                   ),
                                   if (!isLast)
                                      Divider(height: 1, color: isDark ? Colors.grey[800] : Colors.grey[200]),
                                 ],
                               );
                            }).toList(),
                         ),
                ],
                icon: Icons.forest
             ),

             const SizedBox(height: 16),

             _buildSectionCard(
                "6. Infrastructural Information",
                [
                   _buildReadOnlyField("Has Well", (s['has_well'] == 'yes') ? 'Yes' : 'No', labelIcon: Icons.waves),
                   if (s['has_well'] == 'yes') ...[
                      _buildReadOnlyField("Well Type", "${s['well_type'] ?? '-'}", labelIcon: Icons.waves),
                      _buildReadOnlyField("Well Count", s['well_count']?.toString() ?? '0', labelIcon: Icons.numbers),
                   ],

                   _buildReadOnlyField("Has Tubewell", (s['has_tubewell'] == 'yes') ? 'Yes' : 'No', labelIcon: Icons.settings_input_component),
                   if (s['has_tubewell'] == 'yes') ...[
                      _buildReadOnlyField("Tubewell Count", s['tubewell_count']?.toString() ?? '0', labelIcon: Icons.settings_input_component),
                   ],

                   _buildReadOnlyField("Has Pond", s['has_pond'] == 'yes' ? 'Yes' : 'No', labelIcon: Icons.pool),
                   
                   _buildReadOnlyField("Has Boundary Wall", (s['has_boundary_wall'] == 'yes') ? 'Yes' : 'No', labelIcon: Icons.fence),
                   if (s['has_boundary_wall'] == 'yes') ...[
                      _buildReadOnlyField("Boundary Wall Length", "${s['boundary_wall_length']} m", labelIcon: Icons.linear_scale),
                   ],
                   
                    if (s['remarks'] != null && s['remarks'].toString().isNotEmpty)
                       _buildReadOnlyField("Remarks", "${s['remarks']}", labelIcon: Icons.comment),
                ],
                icon: Icons.build
             ),

             const SizedBox(height: 16),
             
             // Captured Photos Section
             Builder(
               builder: (context) {
                   final photosData = s['fetched_images'] ?? s['photos'] ?? s['survey_photos'] ?? s['survey_image'] ?? s['images'] ?? [];
                   final List allPhotos = photosData is List ? photosData : [photosData];
                   final List photos = allPhotos.where((p) => p != null && p != "" && p != false).toList();
                   
                   return _buildSectionCard(
                      "7. Captured Photos",
                      [
                         if (photos.isNotEmpty)
                            GridView.builder(
                               shrinkWrap: true,
                               physics: const NeverScrollableScrollPhysics(),
                               gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                                  crossAxisCount: 2,
                                  crossAxisSpacing: 10,
                                  mainAxisSpacing: 10,
                                  childAspectRatio: 1.0,
                               ),
                               itemCount: photos.length,
                               itemBuilder: (context, index) {
                                  final photo = photos[index];
                                  String url = "";
                                  dynamic photoId;
                                  
                                  if (photo is String) {
                                     url = photo;
                                  } else if (photo is Map) {
                                     url = photo['s3_url'] ?? photo['photo_url'] ?? photo['file_path'] ?? photo['url'] ?? photo['photo_url'] ?? photo['path'] ?? photo['photo'] ?? photo['image'] ?? photo['file'] ?? "";
                                     // Check various keys for ID
                                     photoId = photo['id'] ?? photo['photo_id'] ?? photo['image_id'];
                                  }
                                  
                                  // Robust URL construction
                                  if (!url.startsWith('http')) {
                                     var base = ApiEndpoints.baseUrl; 
                                     
                                     // S3 Handling: If it contains surveys/, it's likely S3
                                     if (url.startsWith('surveys/') || url.startsWith('/surveys/')) {
                                        base = "https://bhuarjan.s3.amazonaws.com";
                                        if (url.startsWith('/')) url = url.substring(1); // Remove leading slash for consistency
                                     } else if (base.endsWith('/api') && (url.startsWith('storage') || url.startsWith('/storage'))) {
                                        // Local storage handling: Strip /api
                                        base = base.replaceAll('/api', '');
                                     }
                                     
                                     if (!url.startsWith('/')) url = '/$url';
                                     if (base.endsWith('/')) base = base.substring(0, base.length - 1);
                                     
                                     url = "$base$url";
                                  }

                                  return Container(
                                     decoration: BoxDecoration(
                                        borderRadius: BorderRadius.circular(12),
                                        border: Border.all(color: Colors.grey.shade300),
                                     ),
                                     child: ClipRRect(
                                        borderRadius: BorderRadius.circular(12),
                                        child: Stack(
                                          children: [
                                            Positioned.fill(
                                              child: Image.network(
                                                url, 
                                                fit: BoxFit.cover,
                                                errorBuilder: (context, error, stackTrace) {
                                                  return Center(
                                                    child: Column(
                                                      mainAxisAlignment: MainAxisAlignment.center,
                                                      children: [
                                                        const Icon(Icons.broken_image, color: Colors.blueGrey, size: 24),
                                                        const SizedBox(height: 4),
                                                        Text("No Preview", style: TextStyle(color: Colors.grey.shade500, fontSize: 10)),
                                                      ],
                                                    ),
                                                  );
                                                },
                                              ),
                                            ),
                                            Positioned.fill(
                                              child: Material(
                                                color: Colors.transparent,
                                                child: InkWell(
                                                   onTap: () => _showPhotoPreview(context, photos, index),
                                                ),
                                              ),
                                            ),
                                            if (s['state']?.toString().toLowerCase() != 'approved' && photoId != null)
                                              Positioned(
                                                top: 6,
                                                right: 6,
                                                child: InkWell(
                                                  onTap: () => _confirmDeletePhoto(photoId),
                                                  child: Container(
                                                    padding: const EdgeInsets.all(6),
                                                    decoration: BoxDecoration(
                                                      color: Colors.white,
                                                      shape: BoxShape.circle,
                                                      boxShadow: [
                                                         BoxShadow(color: Colors.black26, blurRadius: 4)
                                                      ]
                                                    ),
                                                    child: const Icon(Icons.delete_outline, color: Colors.red, size: 20),
                                                  ),
                                                ),
                                              ),
                                          ],
                                        ),
                                     ),
                                  );
                               }
                            )

                          else 
                           Container(
                             width: double.infinity,
                             padding: const EdgeInsets.symmetric(vertical: 24),
                             child: Column(
                               mainAxisAlignment: MainAxisAlignment.center,
                               children: [
                                 Container(
                                   padding: const EdgeInsets.all(16),
                                   decoration: BoxDecoration(
                                     color: (Theme.of(context).brightness == Brightness.dark) ? const Color(0xFF2C2C2C) : Colors.grey.shade100,
                                     shape: BoxShape.circle,
                                   ),
                                   child: Icon(
                                     Icons.add_a_photo_outlined, 
                                     size: 32, 
                                     color: (Theme.of(context).brightness == Brightness.dark) ? Colors.grey.shade400 : Colors.grey.shade500
                                   ),
                                 ),
                                 const SizedBox(height: 12),
                                 Text(
                                   "No photos uploaded yet", 
                                   style: TextStyle(
                                     fontSize: 15,
                                     fontWeight: FontWeight.w600,
                                     color: (Theme.of(context).brightness == Brightness.dark) ? Colors.grey.shade300 : Colors.grey.shade700
                                   )
                                 ),
                                 const SizedBox(height: 4),
                                 Padding(
                                   padding: const EdgeInsets.symmetric(horizontal: 20),
                                   child: Text(
                                     "Capture site photos to document this survey", 
                                     textAlign: TextAlign.center,
                                     style: TextStyle(
                                       fontSize: 13,
                                       color: (Theme.of(context).brightness == Brightness.dark) ? Colors.grey.shade500 : Colors.grey.shade600
                                     )
                                   ),
                                 ),
                               ],
                             ),
                           ),
                         
                         const SizedBox(height: 12),
                         // Add Photo Button
                         SizedBox(
                           width: double.infinity,
                           child: TextButton.icon(
                              onPressed: _quickAddPhoto,
                              icon: _isPhotoUploading ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.camera_alt),
                              label: Text(_isPhotoUploading ? "Uploading..." : "Add Photo (Direct Camera)"),
                              style: TextButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 12),
                                backgroundColor: isDark ? Colors.white10 : Colors.blue.withValues(alpha: 0.1),
                                foregroundColor: isDark ? Colors.white : Colors.blue.shade800,
                                 shape: RoundedRectangleBorder(
                                   borderRadius: BorderRadius.circular(10),
                                   side: BorderSide(color: isDark ? Colors.white24 : Colors.blue.withValues(alpha: 0.3))
                                 )
                              ),
                           ),
                         )
                      ],
                      icon: Icons.camera_alt
                   );
               }
             ),
                
                          const SizedBox(height: 30),
             if (s['state']?.toString().toLowerCase() == 'draft')
                CustomButton(
                   title: "Submit", 
                   onPress: _handleSubmit, 
                   isLoading: _isSubmitting,
                   color: themeProvider.currentGradientColors.first,
                ),
                
             const SizedBox(height: 120),
                   ],
                 ),
               ),
             ),
           ),
                ],
              ),
            ),
            
             // Sticky Action Bar (Edit if not approved, Close)
            Align(
              alignment: Alignment.bottomCenter,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF1E1E1E) : Colors.white,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.1),
                      blurRadius: 10,
                      offset: const Offset(0, -5),
                    )
                  ],
                ),
                child: SafeArea(
                  top: false,
                  child: Row(
                    children: [
                      if (s['state']?.toString().toLowerCase() != 'approved') ...[
                        Expanded(
                          child: CustomButton(
                            title: "Edit Survey", 
                            onPress: () {
                              Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (context) => CreateSurveyScreen(prefilledData: s),
                                ),
                              ).then((_) => _fetchDetails());
                            },
                            filled: false,
                            color: Colors.blueAccent,
                            textColor: Colors.blueAccent,
                          ),
                        ),
                        const SizedBox(width: 12),
                      ],
                      Expanded(
                        child: CustomButton(
                          title: "Close", 
                          onPress: () => Navigator.pop(context),
                          filled: true,
                          color: Colors.redAccent,
                          textColor: Colors.white,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            
            // Photo Picker Modal
            if (_showPhotoPicker)
              PhotoPickerModal(
                visible: _showPhotoPicker,
                surveyId: widget.surveyId,
                onRequestClose: () => setState(() => _showPhotoPicker = false),
                onPhotosAdded: () {
                   _fetchDetails(); // Refresh details to show new photos
                },
              ),
          ],
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
       margin: const EdgeInsets.only(bottom: 12),
       decoration: BoxDecoration(
          color: bodyColor,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: borderColor, width: 1),
          boxShadow: [
             BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.05),
                blurRadius: 4,
                offset: const Offset(0, 1)
             )
          ]
       ),
       child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
             // Solid Header
             Container(
               padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
               decoration: BoxDecoration(
                 color: headerColor,
                 borderRadius: const BorderRadius.only(
                    topLeft: Radius.circular(11), 
                    topRight: Radius.circular(11)
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
                        width: 24, height: 24,
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
                              fontSize: 12
                           ),
                        ),
                     )
                 ],
               ),
             ),
             Padding(
               padding: const EdgeInsets.all(12),
               child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: children.isNotEmpty 
                      ? children 
                      : [
                          Container(
                             width: double.infinity,
                             padding: const EdgeInsets.all(20),
                             child: Column(
                               children: [
                                  Icon(Icons.folder_off_outlined, size: 40, color: Colors.grey.withValues(alpha: 0.5)),
                                  const SizedBox(height: 8),
                                  Text(
                                     "No information available",
                                     style: TextStyle(
                                        color: Colors.grey.withValues(alpha: 0.7),
                                        fontSize: 14,
                                        fontStyle: FontStyle.italic
                                     ),
                                  ),
                               ],
                             ),
                          )
                        ]
               ),
             )
          ],
       ),
    );
  }

  Widget _buildReadOnlyField(String label, String value, {IconData? labelIcon}) {
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

    // Check if this is a status field and determine icon/color
    IconData? statusIcon;
    Color? statusColor;
    if (label.toLowerCase() == 'status') {
      final statusValue = value.toLowerCase();
      if (statusValue == 'approved') {
        statusIcon = Icons.check_circle;
        statusColor = const Color(0xFF27AE60); // Green
        valueColor = statusColor;
      } else if (statusValue == 'rejected') {
        statusIcon = Icons.cancel;
        statusColor = const Color(0xFFE74C3C); // Red
        valueColor = statusColor;
      } else if (statusValue == 'pending') {
        statusIcon = Icons.hourglass_bottom;
        statusColor = const Color(0xFFF39C12); // Orange
        valueColor = statusColor;
      } else if (statusValue == 'submitted') {
        statusIcon = Icons.send;
        statusColor = const Color(0xFF2980B9); // Blue
        valueColor = statusColor;
      }
    }
    
     return Padding(
       padding: const EdgeInsets.only(bottom: 12),
       child: Row(
         crossAxisAlignment: CrossAxisAlignment.start,
         children: [
           // Icon + Label using fluid width (60%)
           Expanded(
             flex: 6,
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
           // Value using fluid width (40%)
           Expanded(
             flex: 4,
             child: Row(
               children: [
                 if (statusIcon != null) ...[
                   Icon(statusIcon, size: 18, color: statusColor),
                   const SizedBox(width: 6),
                 ],
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

   void _showPhotoPreview(BuildContext context, List<dynamic> photos, int initialIndex) {
    showGeneralDialog(
      context: context,
      barrierDismissible: true,
      barrierLabel: "PhotoPreview",
      barrierColor: Colors.black.withValues(alpha: 0.95),
      transitionDuration: const Duration(milliseconds: 300),
      pageBuilder: (context, anim1, anim2) {
        return _PhotoPreviewOverlay(photos: photos, initialIndex: initialIndex);
      },
    );
  }
}

class _PhotoPreviewOverlay extends StatefulWidget {
  final List<dynamic> photos;
  final int initialIndex;

  const _PhotoPreviewOverlay({required this.photos, required this.initialIndex});

  @override
  State<_PhotoPreviewOverlay> createState() => _PhotoPreviewOverlayState();
}

class _PhotoPreviewOverlayState extends State<_PhotoPreviewOverlay> {
  late PageController _pageController;
  late int _currentIndex;
  bool _isMapView = false;
  
  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialIndex;
    _pageController = PageController(initialPage: widget.initialIndex);
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  String _resolveUrl(dynamic photo) {
    String url = "";
    if (photo is String) {
       url = photo;
    } else if (photo is Map) {
       url = photo['s3_url'] ?? photo['photo_url'] ?? photo['file_path'] ?? photo['url'] ?? photo['photo_url'] ?? photo['path'] ?? photo['photo'] ?? photo['image'] ?? photo['file'] ?? "";
    }
    
    if (!url.startsWith('http')) {
       var base = ApiEndpoints.baseUrl; 
       if (url.startsWith('surveys/') || url.startsWith('/surveys/')) {
          base = "https://bhuarjan.s3.amazonaws.com";
          if (url.startsWith('/')) url = url.substring(1);
       } else if (base.endsWith('/api') && (url.startsWith('storage') || url.startsWith('/storage'))) {
          base = base.replaceAll('/api', '');
       }
       
       if (!url.startsWith('/')) url = '/$url';
       if (base.endsWith('/')) base = base.substring(0, base.length - 1);
       url = "$base$url";
    }
    return url;
  }

  @override
  Widget build(BuildContext context) {
    final currentPhoto = widget.photos[_currentIndex];
    final photoData = currentPhoto is Map ? currentPhoto : {};
    final lat = photoData['latitude'];
    final lng = photoData['longitude'];
    final hasLocation = lat != null && lng != null;
    final imageUrl = _resolveUrl(currentPhoto);

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(
        children: [
          // Main Content (PageView or Map)
          Positioned.fill(
             child: AnimatedSwitcher(
               duration: const Duration(milliseconds: 300),
               child: _isMapView && hasLocation
                   ? Container(
                       key: const ValueKey('map'),
                       margin: const EdgeInsets.fromLTRB(0, 80, 0, 100), // Adjusted map margin
                       child: WebViewWidget(
                         controller: WebViewController()
                           ..setJavaScriptMode(JavaScriptMode.unrestricted)
                           ..setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
                           ..setNavigationDelegate(
                             NavigationDelegate(
                               onNavigationRequest: (NavigationRequest request) {
                                 if (request.url.startsWith('intent://') || request.url.startsWith('market://')) {
                                   return NavigationDecision.prevent;
                                 }
                                 return NavigationDecision.navigate;
                               },
                             ),
                           )
                           ..loadRequest(Uri.parse("https://www.google.com/maps?q=$lat,$lng&z=15")),
                       ),
                     )
                   : PageView.builder(
                       key: const ValueKey('gallery'),
                       controller: _pageController,
                       itemCount: widget.photos.length,
                       onPageChanged: (index) {
                         setState(() {
                           _currentIndex = index;
                           _isMapView = false; // Reset map view on slide
                         });
                       },
                       itemBuilder: (context, index) {
                         final photo = widget.photos[index];
                         final url = _resolveUrl(photo);
                         return InteractiveViewer(
                           minScale: 0.5,
                           maxScale: 4.0,
                           child: Image.network(
                             url,
                             fit: BoxFit.contain,
                             errorBuilder: (_, __, ___) => const Center(child: Column(
                               mainAxisSize: MainAxisSize.min,
                               children: [
                                 Icon(Icons.broken_image, color: Colors.white54, size: 40),
                                 SizedBox(height: 8),
                                 Text("Image not available", style: TextStyle(color: Colors.white54)),
                               ],
                             )),
                           ),
                         );
                       },
                     ),
             ),
          ),

          // Top Control Bar
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: Container(
              padding: EdgeInsets.fromLTRB(20, MediaQuery.of(context).padding.top + 10, 20, 20),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Colors.black.withValues(alpha: 0.8), Colors.transparent],
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                   Text(
                    "${_currentIndex + 1} / ${widget.photos.length}",
                    style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  Row(
                    children: [
                      if (hasLocation)
                        GestureDetector(
                          onTap: () => setState(() => _isMapView = !_isMapView),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            margin: const EdgeInsets.only(right: 12),
                            decoration: BoxDecoration(
                              color: _isMapView ? Colors.white : Colors.white.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(30),
                              border: Border.all(color: Colors.white24),
                            ),
                            child: Row(
                              children: [
                                Icon(
                                  _isMapView ? Icons.image : Icons.map,
                                  color: _isMapView ? Colors.black : Colors.white,
                                  size: 16,
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  _isMapView ? "Show Image" : "Show Map",
                                  style: TextStyle(
                                    color: _isMapView ? Colors.black : Colors.white,
                                    fontWeight: FontWeight.w600,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      GestureDetector(
                        onTap: () => Navigator.pop(context),
                        child: Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.2), 
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.close, color: Colors.white, size: 24),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),

          // Bottom Info Bar
          if (!_isMapView && hasLocation)
            Positioned(
              bottom: 40,
              left: 20,
              right: 20,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 15, sigmaY: 15),
                  child: Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.4),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: Colors.white.withValues(alpha: 0.1)),
                      boxShadow: [
                         BoxShadow(
                           color: Colors.black.withValues(alpha: 0.2),
                           blurRadius: 10,
                           spreadRadius: 2,
                         )
                      ]
                    ),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: Colors.redAccent.withValues(alpha: 0.2),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.location_on, color: Colors.redAccent, size: 24),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                "Location Details", 
                                style: TextStyle(color: Colors.grey[300], fontSize: 12, fontWeight: FontWeight.w500)
                              ),
                              const SizedBox(height: 4),
                              Text(
                                "$lat, $lng",
                                style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold, letterSpacing: 0.5),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
