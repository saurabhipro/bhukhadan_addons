import 'package:flutter/material.dart';
import '../utils/localization.dart';

class LanguageSelector extends StatelessWidget {
  const LanguageSelector({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder(
      valueListenable: Localization.currentLocale,
      builder: (context, locale, _) {
        return Container(
           decoration: BoxDecoration(
             color: Colors.white.withValues(alpha: 0.2),
             borderRadius: BorderRadius.circular(20),
             border: Border.all(color: Colors.white.withValues(alpha: 0.3))
           ),
           child: Row(
             mainAxisSize: MainAxisSize.min,
             children: [
               _buildOption('en', 'En', locale.languageCode == 'en'),
               Container(width: 1, height: 16, color: Colors.white.withValues(alpha: 0.3)),
               _buildOption('hi', 'Hi', locale.languageCode == 'hi'),
             ],
           ),
        );
      },
    );
  }

  Widget _buildOption(String code, String label, bool isSelected) {
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
}
