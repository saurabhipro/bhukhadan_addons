import 'package:flutter/material.dart';
import '../utils/colors.dart';

class CustomButton extends StatelessWidget {
  final String title;
  final VoidCallback? onPress;
  final bool isLoading;
  final bool filled;
  final Color? color;
  final Color? textColor;
  final String? leftIconPath;
  final String? rightIconPath;

  const CustomButton({
    super.key,
    required this.title,
    this.onPress,
    this.isLoading = false,
    this.filled = true,
    this.color,
    this.textColor,
    this.leftIconPath,
    this.rightIconPath,
  });

  @override
  Widget build(BuildContext context) {
    final bgColor = filled ? (color ?? AppColors.primary) : AppColors.white; // Defaulting to primary as per ButtonColors.blue map
    final txtColor = filled ? (Colors.white) : (textColor ?? AppColors.primary);
    final borderColor = color ?? AppColors.primary;

    return Container(
      margin: const EdgeInsets.only(top: 20),
      height: 60,
      width: double.infinity,
      child: ElevatedButton(
        onPressed: isLoading ? null : onPress,
        style: ElevatedButton.styleFrom(
          backgroundColor: bgColor,
          foregroundColor: txtColor,
          elevation: 0,
          side: BorderSide(color: borderColor, width: 1),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16),
        ),
        child: isLoading
            ? const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
              )
            : Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (leftIconPath != null) ...[
                    Image.asset(leftIconPath!, width: 20, height: 20),
                    const SizedBox(width: 10),
                  ],
                  Text(
                    title,
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w500,
                      color: txtColor,
                    ),
                  ),
                  if (rightIconPath != null) ...[
                    const SizedBox(width: 10),
                    Image.asset(rightIconPath!, width: 20, height: 20),
                  ],
                ],
              ),
      ),
    );
  }
}
