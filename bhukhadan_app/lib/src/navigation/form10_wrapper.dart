import 'package:flutter/material.dart';
import '../screens/pdf_view_screen.dart';
import '../utils/storage.dart';
import 'package:provider/provider.dart';
import '../utils/theme_provider.dart';

class Form10Wrapper extends StatefulWidget {
  const Form10Wrapper({super.key});

  @override
  State<Form10Wrapper> createState() => _Form10WrapperState();
}

class _Form10WrapperState extends State<Form10Wrapper> {
  String? _villageId;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadVillageId();
  }

  Future<void> _loadVillageId() async {
    final villageId = await getAsyncItem(SELECTED_VILLAGE_ID_KEY);
    setState(() {
      _villageId = villageId;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    final themeProvider = Provider.of<ThemeProvider>(context);
    final isDark = themeProvider.isDarkMode;

    if (_villageId == null || _villageId!.isEmpty) {
      return Scaffold(
        backgroundColor: isDark ? const Color(0xFF1F1F1F) : Colors.white,
        appBar: AppBar(
          title: const Text('Form 10'),
          flexibleSpace: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: themeProvider.currentGradientColors,
              ),
            ),
          ),
        ),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.info_outline, size: 64, color: Colors.blue.shade300),
                const SizedBox(height: 16),
                Text(
                  'कृपया Home पर जाकर ग्राम चुनें\nPlease select a village from Home screen',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 16, color: isDark ? Colors.white : Colors.black),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return PdfViewScreen(villageId: _villageId);
  }
}
