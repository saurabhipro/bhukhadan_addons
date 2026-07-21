import 'dart:io';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:geolocator/geolocator.dart';
import '../services/api_service.dart';
import '../constants/api_constants.dart';

class PhotoPickerModal extends StatefulWidget {
  final bool visible;
  final int surveyId;
  final VoidCallback onRequestClose;
  final VoidCallback onPhotosAdded;

  const PhotoPickerModal({
    super.key,
    required this.visible,
    required this.surveyId,
    required this.onRequestClose,
    required this.onPhotosAdded,
  });

  @override
  State<PhotoPickerModal> createState() => _PhotoPickerModalState();
}

class _PhotoPickerModalState extends State<PhotoPickerModal> {
  final ImagePicker _picker = ImagePicker();
  final List<Map<String, dynamic>> _capturedPhotos = []; // { 'file': File, 'lat': double?, 'lng': double? }
  bool _isUploading = false;

  Future<void> _pickPhoto() async {
    try {
      // Get location first for better accuracy
      Position? position;
      try {
        LocationPermission permission = await Geolocator.checkPermission();
        if (permission == LocationPermission.denied) {
          permission = await Geolocator.requestPermission();
        }
        if (permission == LocationPermission.always || permission == LocationPermission.whileInUse) {
          position = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
        }
      } catch (e) {
        debugPrint("Location error: $e");
      }

      final XFile? photo = await _picker.pickImage(
        source: ImageSource.camera,
        imageQuality: 50,
      );
      
      if (photo != null) {
        setState(() {
          _capturedPhotos.add({
            'file': File(photo.path),
            'lat': position?.latitude,
            'lng': position?.longitude,
            'fileName': photo.name
          });
        });
      }
    } catch (e) {
      debugPrint("Error picking photo: $e");
    }
  }

  Future<void> _uploadPhotos() async {
    if(_capturedPhotos.isEmpty) {
      widget.onRequestClose();
      return;
    }

    setState(() => _isUploading = true);

    try {
      // Step 1: Request presigned URLs
      final urlResponse = await ApiService.post(ApiEndpoints.presignedUrls, {
        'survey_id': widget.surveyId,
        'file_names': _capturedPhotos.map((f) => (f['file'] as File).path.split('/').last).toList(),
      });

      if (urlResponse.statusCode != 200 && urlResponse.statusCode != 201) {
        throw "Failed to get presigned URLs: ${urlResponse.body}";
      }

      final dynamic responseData = jsonDecode(urlResponse.body);
      final dataPart = responseData['data'] ?? responseData;
      List<dynamic> presignedData = [];
      if (dataPart is Map) {
        presignedData = dataPart['presigned_urls'] ?? dataPart['urls'] ?? [];
      } else if (dataPart is List) {
        presignedData = dataPart;
      }

      if (presignedData.isEmpty || presignedData.length < _capturedPhotos.length) {
        throw "Received fewer upload URLs than requested";
      }

      // Step 2: Upload each file to S3
      int successCount = 0;
      for (int i = 0; i < _capturedPhotos.length; i++) {
        final photoData = _capturedPhotos[i];
        final file = photoData['file'] as File;
        final uploadItem = presignedData[i];
        
        String? uploadUrl;
        if (uploadItem is String) {
          uploadUrl = uploadItem;
        } else if (uploadItem is Map) {
          uploadUrl = uploadItem['presigned_url'] ?? uploadItem['url'];
        }
        
        if (uploadUrl == null) continue;
        
        final bytes = await file.readAsBytes();
        final putResponse = await ApiService.putFileDirectly(uploadUrl, bytes, 'image/jpeg');

        if (putResponse.statusCode == 200 || putResponse.statusCode == 201 || putResponse.statusCode == 204) {
          successCount++;
        }
      }

      // Step 3: Register Photos
      if (successCount > 0) {
        final List<Map<String, dynamic>> photoPayload = [];
        for (int i = 0; i < _capturedPhotos.length; i++) {
           final item = presignedData[i];
           final captured = _capturedPhotos[i];
           final file = captured['file'] as File;
           
           String? s3Key = item is Map ? item['s3_key'] : null;
           if (s3Key != null) {
              String domain = "bhuarjan.s3.amazonaws.com";
              String? uploadUrl = item['presigned_url'] ?? item['url'];
              if (uploadUrl != null) {
                 try { domain = Uri.parse(uploadUrl).host; } catch(_) {}
              }
              photoPayload.add({
                's3_url': 'https://$domain/$s3Key',
                'latitude': captured['lat'],
                'longitude': captured['lng'],
                'filename': captured['fileName'] ?? file.path.split('/').last,
                'file_size': await file.length(),
                'photo_type_id': 1
              });
           }
        }

        if (photoPayload.isNotEmpty) {
           await ApiService.post(
             "${ApiEndpoints.photoUpload}?survey_id=${widget.surveyId}", 
             { 'photos': photoPayload }
           );
        }

        widget.onPhotosAdded();
        widget.onRequestClose();
      } else {
         throw "All uploads failed";
      }
    } catch (e) {
      debugPrint("S3 Upload Flow Error: $e");
      if(mounted) {
         ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Error: $e")));
      }
    } finally {
      if(mounted) setState(() => _isUploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.visible) return const SizedBox.shrink();
    
    return Container(
      color: Colors.black54,
      child: Center(
        child: Container(
           margin: const EdgeInsets.symmetric(horizontal: 20),
           padding: const EdgeInsets.all(24),
           decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
           child: Column(
             mainAxisSize: MainAxisSize.min,
             children: [
               Row(
                 mainAxisAlignment: MainAxisAlignment.spaceBetween,
                 children: [
                   const Text("Add Photos", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF2D3436))),
                   IconButton(
                     onPressed: widget.onRequestClose,
                     icon: const Icon(Icons.close, size: 20),
                     constraints: const BoxConstraints(),
                     padding: EdgeInsets.zero,
                   )
                 ],
               ),
               const SizedBox(height: 20),

               SizedBox(
                 width: double.infinity,
                 child: ElevatedButton.icon(
                   onPressed: _isUploading ? null : _pickPhoto,
                   icon: const Icon(Icons.add, color: Colors.white),
                   label: const Text("Capture Photo", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                   style: ElevatedButton.styleFrom(
                     backgroundColor: const Color(0xFF104E8B),
                     padding: const EdgeInsets.symmetric(vertical: 12),
                     shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                   ),
                 ),
               ),
               
               const SizedBox(height: 16),

               if (_capturedPhotos.isNotEmpty)
                 Container(
                   constraints: const BoxConstraints(maxHeight: 250),
                   child: GridView.builder(
                     shrinkWrap: true,
                     gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                       crossAxisCount: 2, 
                       crossAxisSpacing: 10, 
                       mainAxisSpacing: 10,
                       childAspectRatio: 1.0,
                     ),
                     itemCount: _capturedPhotos.length,
                     itemBuilder: (context, index) {
                       return Stack(
                         children: [
                           Positioned.fill(
                             child: ClipRRect(
                               borderRadius: BorderRadius.circular(8),
                               child: Image.file(_capturedPhotos[index]['file'] as File, fit: BoxFit.cover),
                             ),
                           ),
                           Positioned(
                             top: 4, right: 4,
                             child: GestureDetector(
                               onTap: () => setState(() => _capturedPhotos.removeAt(index)),
                               child: Container(
                                 decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
                                 padding: const EdgeInsets.all(4),
                                 child: const Icon(Icons.close, color: Colors.white, size: 12),
                               ),
                             ),
                           )
                         ],
                       );
                     },
                   ),
                 ),

               const SizedBox(height: 24),

               Row(
                 children: [
                   Expanded(
                     child: OutlinedButton(
                       onPressed: widget.onRequestClose,
                       child: const Text("Cancel"),
                     ),
                   ),
                   const SizedBox(width: 12),
                   Expanded(
                     child: ElevatedButton(
                       onPressed: _isUploading ? null : _uploadPhotos,
                       style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF104E8B)),
                       child: _isUploading 
                          ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                          : const Text("Upload All", style: TextStyle(color: Colors.white)),
                     ),
                   ),
                 ],
               )
             ],
           ),
        ),
      ),
    );
  }
}
