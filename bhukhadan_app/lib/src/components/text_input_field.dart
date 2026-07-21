import 'package:flutter/material.dart';

class TextInputField extends StatefulWidget {
  final String label;
  final TextEditingController? controller;
  final bool required;
  final String? helperText;
  final String? errorMessage;
  final bool readOnly;
  final VoidCallback? onTap;
  final TextInputType? keyboardType;
  final int? maxLength;
  final String? placeholder;
  final bool obscureText;
  final Function(String)? onChanged;
  final IconData? labelIcon;

  const TextInputField({
    super.key,
    this.label = "",
    this.controller,
    this.required = false,
    this.helperText,
    this.errorMessage,
    this.readOnly = false,
    this.onTap,
    this.keyboardType,
    this.maxLength,
    this.placeholder,
    this.obscureText = false,
    this.onChanged,
    this.labelIcon,
  });

  @override
  State<TextInputField> createState() => _TextInputFieldState();
}

class _TextInputFieldState extends State<TextInputField> {
  final FocusNode _focusNode = FocusNode();
  bool _isFocused = false;

  @override
  void initState() {
    super.initState();
    _focusNode.addListener(() {
      setState(() {
        _isFocused = _focusNode.hasFocus;
      });
    });
  }

  @override
  void dispose() {
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    final textColor = isDark ? Colors.white : Colors.black87;
    final labelColor = isDark ? Colors.grey[400] : Colors.grey[700];
    final activeColor = isDark ? Colors.blue[400] : Colors.blue[700];
    final bgColor = isDark ? const Color(0xFF2D3436).withValues(alpha: 0.5) : Colors.white;
    final borderColor = isDark ? Colors.grey[700]! : Colors.grey[400]!;

    // Construct label with required star
    String labelText = widget.label;
    if (widget.required && labelText.isNotEmpty) {
      labelText += " *";
    }

    return Padding(
      padding: const EdgeInsets.only(top: 12, bottom: 8),
      child: InkWell(
        onTap: widget.readOnly ? widget.onTap : null,
        child: IgnorePointer(
          ignoring: widget.readOnly,
          child: TextFormField(
            controller: widget.controller,
            focusNode: _focusNode,
            keyboardType: widget.keyboardType,
            obscureText: widget.obscureText,
            maxLength: widget.maxLength,
            onChanged: widget.onChanged,
            readOnly: widget.readOnly,
            style: TextStyle(
              fontSize: 16,
              color: textColor,
              fontWeight: widget.readOnly ? FontWeight.bold : FontWeight.normal,
            ),
            decoration: InputDecoration(
              labelText: labelText,
              hintText: widget.placeholder,
              hintStyle: TextStyle(
                color: isDark ? Colors.white54 : Colors.grey[600],
                fontSize: 14,
              ),
              prefixIcon: widget.labelIcon != null 
                  ? Icon(widget.labelIcon, size: 20, color: _isFocused ? activeColor : labelColor)
                  : null,
              labelStyle: TextStyle(
                color: _isFocused ? activeColor : labelColor,
                fontWeight: _isFocused ? FontWeight.bold : FontWeight.normal,
              ),
              floatingLabelStyle: TextStyle(
                color: activeColor,
                fontWeight: FontWeight.bold,
                fontSize: 13,
                backgroundColor: isDark ? const Color(0xFF1E1E1E) : Colors.white, // Mask the border
              ),

              errorText: widget.errorMessage,
              helperText: widget.helperText,
              counterText: "",
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
              filled: true,
              fillColor: bgColor,
              
              // Borders
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide(color: borderColor, width: 1.0),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide(color: activeColor!, width: 2.0),
              ),
              errorBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Colors.red, width: 1.0),
              ),
              focusedErrorBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: Colors.red, width: 2.0),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
