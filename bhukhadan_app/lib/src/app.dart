import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'navigation/app_navigation.dart';
import 'utils/globals.dart';
import 'utils/theme_provider.dart';
import 'screens/survey_details_screen.dart';

class BhuarjanApp extends StatelessWidget {
  const BhuarjanApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => ThemeProvider(),
      child: Consumer<ThemeProvider>(
        builder: (context, themeProvider, _) {
          return MaterialApp(
            title: 'BhuKhadan',
            theme: ThemeProvider.lightTheme,
            darkTheme: ThemeProvider.darkTheme,
            themeMode: themeProvider.themeMode,
            navigatorKey: navigatorKey,
            home: const AppNavigation(),
            debugShowCheckedModeBanner: false,
            onGenerateRoute: (settings) {
              if (settings.name == '/survey-details') {
                final args = settings.arguments;
                int selectedId;
                List<int> allIds = [];

                if (args is Map) {
                   selectedId = int.parse(args['id'].toString());
                   if (args['allIds'] != null) {
                      allIds = (args['allIds'] as List).map((e) => int.parse(e.toString())).toList();
                   }
                } else {
                   selectedId = args is int ? args : int.parse(args.toString());
                }
                
                if (allIds.isEmpty) allIds = [selectedId];

                return MaterialPageRoute(
                  builder: (context) => SurveyDetailsScreen(
                     surveyId: selectedId,
                     allSurveyIds: allIds
                  ),
                );
              }
              return null;
            },
          );
        },
      ),
    );
  }
}
