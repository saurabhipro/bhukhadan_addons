import 'package:flutter/material.dart';
import '../utils/colors.dart';

class DropdownItem {
  final String label;
  final String value;
  final Widget? leading; // Added leading widget (image/icon)
  
  DropdownItem({required this.label, required this.value, this.leading});
}

class DropdownSelector extends StatelessWidget {
  final String label;
  final List<DropdownItem> items;
  final String? placeholder;
  final String? selectedValue;
  final Function(DropdownItem) onSelect;
  final bool required;
  final String? errorMessage;
  final bool disabled;
  final IconData? labelIcon;

  const DropdownSelector({
    super.key,
    required this.label,
    required this.items,
    required this.onSelect,
    this.placeholder,
    this.selectedValue,
    this.required = false,
    this.errorMessage,
    this.disabled = false,
    this.labelIcon,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final labelColor = isDark ? Colors.grey[300] : const Color(0xFF104E8B);
    final bgColor = isDark ? AppColors.darkInputBg : (disabled ? Colors.grey.shade100 : Colors.white);
    final iconColor = isDark ? Colors.blue[300] : const Color(0xFF104E8B);
    final textColor = isDark ? AppColors.darkText : const Color(0xFF2D3436);
    final placeholderColor = isDark ? Colors.grey[500] : Colors.grey.shade600;
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            if (labelIcon != null) ...[
               Icon(labelIcon, size: 20, color: iconColor), 
               const SizedBox(width: 8),
            ],
            Text(
              label,
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.bold,
                color: labelColor,
              ),
            ),
            if (required)
              const Text(" *", style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 8),
        Container(
          height: 52, // Slightly more height
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: bgColor,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: errorMessage != null ? Colors.red : (isDark ? Colors.grey[600]! : Colors.grey.shade400),
              width: 1.5,
            ),
            boxShadow: [
              if (!disabled) 
                BoxShadow(color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.05), blurRadius: 4, offset: const Offset(0, 2))
            ]
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: items.any((i) => i.value == selectedValue) ? selectedValue : null,
              hint: Text(
                 placeholder ?? "Select an option",
                 style: TextStyle(color: placeholderColor, fontSize: 16),
              ),
              isExpanded: true,
              dropdownColor: isDark ? AppColors.darkInputBg : Colors.white,
              icon: Icon(Icons.keyboard_arrow_down, color: iconColor),
              items: items.map((DropdownItem item) {
                return DropdownMenuItem<String>(
                  value: item.value,
                  child: Row(
                    children: [
                      if (item.leading != null) ...[
                        item.leading!,
                        const SizedBox(width: 12),
                      ],
                      Expanded(
                        child: Text(
                          item.label,
                          style: TextStyle(fontSize: 16, color: textColor, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
              onChanged: disabled 
                ? null 
                : (String? newValue) {
                    if (newValue != null) {
                       final selectedItem = items.firstWhere((i) => i.value == newValue);
                       onSelect(selectedItem);
                    }
                  },

              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        if (errorMessage != null)
          Padding(
            padding: const EdgeInsets.only(top: 4, left: 4),
            child: Text(
               errorMessage!,
               style: const TextStyle(fontSize: 12, color: Colors.red, fontWeight: FontWeight.w600),
            ),
          ),
        const SizedBox(height: 16),
      ],
    );
  }
}
