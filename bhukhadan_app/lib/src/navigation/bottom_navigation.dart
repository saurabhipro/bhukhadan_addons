import 'package:flutter/material.dart';
import '../constants/assets.dart';
import 'form10_wrapper.dart';
import 'package:provider/provider.dart';
import '../utils/theme_provider.dart';
import '../utils/colors.dart';
import '../screens/home_screen.dart';
import '../screens/survey_list_screen.dart';
import '../screens/profile_screen.dart';
import '../screens/create_survey_screen.dart';

class BottomNavigation extends StatefulWidget {
  const BottomNavigation({super.key});

  @override
  State<BottomNavigation> createState() => _BottomNavigationState();
}

class _BottomNavigationState extends State<BottomNavigation> {
  int _currentIndex = 0;
  
  List<Widget> get _pages => [
    HomeScreen(onSwitchTab: _onTabTapped), 
    const SurveyListScreen(), 
    const SizedBox(), // Placeholder for FAB
    const Form10Wrapper(), 
    const ProfileScreen(), 
  ];

  void _onTabTapped(int index) {
    if (index == 2) {
       return; // Handled by FAB
    }
    setState(() {
      _currentIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final themeProvider = Provider.of<ThemeProvider>(context);
    final isDark = themeProvider.isDarkMode;
    final navBg = isDark ? AppColors.darkInputBg : Colors.white;

    return Scaffold(
      extendBody: false,
      backgroundColor: isDark ? const Color(0xFF1F1F1F) : Colors.white,
      body: SafeArea(
        bottom: false,
        child: IndexedStack(
          index: _currentIndex,
          children: [
            HomeScreen(onSwitchTab: _onTabTapped), 
            SurveyListScreen(isActive: _currentIndex == 1), 
            const SizedBox(), // Placeholder for FAB
            const Form10Wrapper(), 
            const ProfileScreen(), 
          ],
        ),
      ),
      floatingActionButton: Container(
        height: 70,
        width: 70,
        decoration: BoxDecoration(
          color: navBg,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: isDark ? Colors.black.withValues(alpha: 0.4) : Colors.black.withValues(alpha: 0.1),
              blurRadius: 8,
              offset: const Offset(0, 4),
            )
          ]
        ),
        child: Padding(
          padding: const EdgeInsets.all(3),
          child: FloatingActionButton(
            heroTag: "bottom_nav_fab",
            onPressed: () {
              Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CreateSurveyScreen()));
            },
            elevation: 0,
            backgroundColor: Colors.transparent,
            shape: const CircleBorder(),
            child: Image.asset(
              AppAssets.icNavFloat,
              fit: BoxFit.contain,
            ),
          ),
        ),
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
      bottomNavigationBar: BottomAppBar(
        color: navBg,
        elevation: 10,
        notchMargin: 10,
        padding: EdgeInsets.zero,
        height: 70,
        shape: const CircularNotchedRectangle(),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            // Left Side Items
            Expanded(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _buildNavItem(AppAssets.icHomeN, "Home", 0),
                  _buildNavItem(AppAssets.icSurveyN, "Surveys", 1),
                ],
              ),
            ),
            
            // Spacer for FAB
            const SizedBox(width: 70),

            // Right Side Items
            Expanded(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                   _buildNavItem(AppAssets.icForm10N, "Form 10", 3),
                   _buildNavItem(AppAssets.icUserN, "Profile", 4),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNavItem(String assetPath, String label, int index) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isSelected = _currentIndex == index;
    final activeColor = isDark ? Colors.blue[300]! : const Color(0xFF104E8B);
    final inactiveColor = isDark ? Colors.grey[400]! : Colors.grey.shade600;

    // Use Material Design icons
    IconData getIcon() {
      switch (index) {
        case 0: return Icons.home_rounded;
        case 1: return Icons.assignment_rounded;
        case 3: return Icons.description_rounded;
        case 4: return Icons.person_rounded;
        default: return Icons.circle;
      }
    }

    return Expanded(
      child: GestureDetector(
        onTap: () => _onTabTapped(index),
        behavior: HitTestBehavior.opaque,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              getIcon(),
              size: 24,
              color: isSelected ? activeColor : inactiveColor,
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? activeColor : inactiveColor,
                fontSize: 11,
                fontWeight: isSelected ? FontWeight.w900 : FontWeight.w600,
              ),
            ),
            const SizedBox(height: 4),
            // Active indicator bar
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              height: 3,
              width: isSelected ? 20 : 0,
              decoration: BoxDecoration(
                color: activeColor,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
