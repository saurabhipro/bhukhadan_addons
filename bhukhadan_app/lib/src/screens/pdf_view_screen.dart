import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_pdfview/flutter_pdfview.dart';
import 'package:http/http.dart' as http;
import '../utils/storage.dart';
import 'package:provider/provider.dart';
import '../utils/theme_provider.dart';

class PdfViewScreen extends StatefulWidget {
  final int? surveyId;
  final String? villageId;
  const PdfViewScreen({super.key, this.surveyId, this.villageId});

  @override
  State<PdfViewScreen> createState() => _PdfViewScreenState();
}

class _PdfViewScreenState extends State<PdfViewScreen> {
  String? _localFilePath;
  bool _isLoading = true;
  String? _error;
  int _totalPages = 0;
  int _currentPage = 0;
  bool _isReady = false;
  PDFViewController? _pdfViewController;

  @override
  void initState() {
    super.initState();
    _downloadPdf();
  }

  Future<void> _downloadPdf() async {
    // Check if we have either surveyId or villageId
    if (widget.surveyId == null && widget.villageId == null) {
      setState(() {
        _error = "Invalid parameters. Need either Survey ID or Village ID.";
        _isLoading = false;
      });
      return;
    }

    try {
      final token = await getAsyncItem(AUTH_TOKEN_KEY);
      
      // Determine which endpoint to use
      String url;
      String filename;
      
      if (widget.villageId != null) {
        // Form 10 endpoint
        url = 'https://bhuarjan.com/api/bhuarjan/form10/download?village_id=${widget.villageId}';
        filename = 'form10_village_${widget.villageId}.pdf';
      } else {
        // Survey PDF endpoint
        url = 'https://bhuarjan.com/api/bhuarjan/survey/pdf?survey_id=${widget.surveyId}';
        filename = 'survey_${widget.surveyId}.pdf';
      }
      
      debugPrint("Downloading PDF from: $url");

      final response = await http.get(
        Uri.parse(url),
        headers: {
          'Authorization': 'Bearer $token',
          'App-Version-Code': '1',
        },
      );

      if (response.statusCode == 200) {
        final bytes = response.bodyBytes;
        final dir = Directory.systemTemp;
        final file = File('${dir.path}/$filename');
        
        await file.writeAsBytes(bytes, flush: true);
        
        if (mounted) {
          setState(() {
            _localFilePath = file.path;
            _isLoading = false;
          });
        }
      } else {
        throw Exception("Server responded with ${response.statusCode}");
      }
    } catch (e) {
      debugPrint("PDF Download Error: $e");
      if (mounted) {
        setState(() {
          _error = "Failed to load PDF. Please try again.\n$e";
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final themeProvider = Provider.of<ThemeProvider>(context);

    return Scaffold(
      appBar: AppBar(
        flexibleSpace: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: themeProvider.currentGradientColors,
            ),
          ),
        ),
        title: Text(
          widget.villageId != null 
            ? "Form 10 - Village ${widget.villageId}" 
            : "Survey PDF - #${widget.surveyId}", 
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          if (_isReady)
            Center(
              child: Padding(
                padding: const EdgeInsets.only(right: 16.0),
                child: Text("${_currentPage + 1}/$_totalPages", style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
              ),
            )
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Colors.green))
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.error_outline, color: Colors.red, size: 48),
                        const SizedBox(height: 16),
                        Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.red)),
                      ],
                    ),
                  ),
                )
              : Stack(
                  children: [
                    PDFView(
                      filePath: _localFilePath,
                      enableSwipe: true,
                      swipeHorizontal: false, // Vertical scroll is better for forms
                      autoSpacing: false,
                      pageFling: false,
                      pageSnap: false,
                      nightMode: themeProvider.isDarkMode,
                      onRender: (pages) {
                        setState(() {
                          _totalPages = pages ?? 0;
                          _isReady = true;
                        });
                      },
                      onViewCreated: (PDFViewController pdfViewController) {
                        _pdfViewController = pdfViewController;
                      },
                      onPageChanged: (int? page, int? total) {
                        setState(() {
                          _currentPage = page ?? 0;
                        });
                      },
                      onError: (error) {
                        setState(() {
                          _error = error.toString();
                        });
                      },
                    ),
                    if (!_isReady)
                      const Center(child: CircularProgressIndicator()),
                  ],
                ),
      floatingActionButton: _isReady 
          ? FloatingActionButton(
              heroTag: "pdf_view_fab",
              onPressed: () {
                 // Idea: Share or full download?
                 ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("PDF is saved in temp storage")));
              },
              backgroundColor: const Color(0xFF104E8B),
              child: const Icon(Icons.download, color: Colors.white),
            )
          : null,
    );
  }
}
