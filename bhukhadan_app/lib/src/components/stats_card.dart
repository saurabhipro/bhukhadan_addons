import 'package:flutter/material.dart';
import '../utils/colors.dart';

class StatsCard extends StatelessWidget {
  final String title;
  final dynamic value;
  final String? subtitle;
  final String iconPath;
  final Color? textColor;
  final VoidCallback? onPress;

  const StatsCard({
    super.key,
    required this.title,
    required this.value,
    required this.iconPath,
    this.subtitle,
    this.textColor,
    this.onPress,
  });

  @override
  Widget build(BuildContext context) {
    final cardContent = Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
           Image.asset(iconPath, width: 24, height: 24),
           const SizedBox(height: 8),
           Text(
             title,
             style: TextStyle(
               fontSize: 16,
               color: textColor ?? AppColors.gray700,
             ),
           ),
           const SizedBox(height: 8),
           Text(
             (value is num) ? value.toString().padLeft(2, '0') : value.toString(),
             style: const TextStyle(
               fontSize: 36,
               fontWeight: FontWeight.bold,
               color: AppColors.h1,
             ),
           ),
           if (subtitle != null) ...[
             const SizedBox(height: 8),
             Text(
               subtitle!,
               style: const TextStyle(fontSize: 14, color: AppColors.secondary),
             ),
           ]
        ],
      ),
    );

    return Container(
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.stroke),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            offset: const Offset(0, 1),
            blurRadius: 8,
          )
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: (value == 0 || onPress == null) ? null : onPress,
          child: cardContent,
        ),
      ),
    );
  }
}
