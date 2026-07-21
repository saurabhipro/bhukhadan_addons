import 'package:flutter/material.dart';

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

// Simple global state// Parameters passed from Home to List
String? globalSurveyFilter;

// Notifier to tell SurveyList to refresh when params change in Home
final ValueNotifier<int> globalSelectionChanged = ValueNotifier(0);
