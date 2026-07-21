import 'package:flutter/material.dart';
import '../utils/colors.dart';

class SectionTitle extends StatelessWidget {
  final String title;
  final IconData? icon;
  
  const SectionTitle({super.key, required this.title, this.icon});

  IconData _getDefaultIcon() {
    final lowerTitle = title.toLowerCase();
    if (lowerTitle.contains('project')) return Icons.assignment_outlined;
    if (lowerTitle.contains('land')) return Icons.landscape_outlined;
    if (lowerTitle.contains('structure')) return Icons.home_work_outlined;
    if (lowerTitle.contains('tree')) return Icons.park_outlined;
    if (lowerTitle.contains('owner')) return Icons.person_outline;
    return Icons.info_outline;
  }

  @override
  Widget build(BuildContext context) {
    final displayIcon = icon ?? _getDefaultIcon();
    
    return Container(
      margin: const EdgeInsets.only(top: 20, bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: const Border(
          left: BorderSide(
            color: AppColors.primary,
            width: 3,
          ),
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Icon(
              displayIcon,
              size: 20,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(width: 10),
          Text(
            title,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w800,
              color: AppColors.h1,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }
}
