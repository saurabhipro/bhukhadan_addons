import 'package:flutter/material.dart';
import 'storage.dart';

// Keys
const String LANGUAGE_CODE_KEY = 'language_code';

class Localization {
  static final ValueNotifier<Locale> currentLocale = ValueNotifier(const Locale('en', 'US'));

  static const Map<String, Map<String, String>> _localizedValues = {
    'en': {
      'app_title': 'BhuKhadan',
      'survey_form': 'Survey Form',
      'new_survey': 'New Survey',
      'edit_survey': 'Edit Survey',
      
      // Headers
      'project_info': 'Project Information',
      'location_info': 'Location Information',
      'land_info': 'Land Information',
      'tree_info': 'Tree Information',
      'house_info': 'House Information',
      'infrastructure': 'Infrastructure',
      
      // Fields
      'department': 'Department',
      'project': 'Project',
      'village': 'Village',
      'district': 'District',
      'tehsil': 'Tehsil',
      
      'affected_khasra': 'Affected Khasra Number',
      'total_area': 'Total Area (Hectares)',
      'acquired_area': 'Area to be Acquired (Hectares)',
      'landowners': 'Landowners',
      'select_landowners': 'Select Landowners',
      'diverted_land': 'Diverted Land',
      'diverted_land_area': 'Diverted Land Area (Hectares)',
      'land_type': 'Land Type',
      'irrigation_type': 'Irrigation Type',
      
      'add_trees_q': 'Do you want to add trees?',
      'tree_name': 'Tree Name',
      'dev_stage': 'Development Stage',
      'num_trees': 'Number of Trees',
      'add_tree': 'Add Tree',
      
      'has_house': 'Has House?',
      'house_type': 'House Type',
      'house_area': 'House Area (Sq. Ft.)',
      'has_shed': 'Has Shed?',
      'shed_area': 'Shed Area (Sq. Ft.)',
      
      'has_well': 'Has Well?',
      'well_type': 'Well Type',
      'well_count': 'Well Count',
      'has_tubewell': 'Has Tubewell/Submersible Pump?',
      'tubewell_count': 'Tubewell Count',
      'has_pond': 'Has Pond?',
      
      'remarks': 'Remarks',
      
      // Home Screen
      'dashboard_stats': 'Dashboard Statistics',
      'total_surveys': 'Total',
      'approved': 'Approved',
      'rejected': 'Rejected',
      'pending': 'Pending',
      'select_dept_label': 'Department',
      'select_project_label': 'Project',
      'select_area_label': 'Area',
      'select_village_label': 'Village',
      'select_dept_hint': 'Select Department',
      'select_project_hint': 'Select Project',
      'select_area_hint': 'Select Area',
      'select_village_hint': 'Select Village',
      'msg_select_village': 'Select Area then Village to view statistics',
      'msg_no_areas': 'No areas linked to this project',
      'area': 'Area',
      'document_checklist': 'Document Checklist',
      'mb_decl_date': 'Owner Declaration Date',
      'mb_decl_no_claim': 'No claim pending declaration',
      'mb_decl_docs': 'Required documents received',
      'mb_decl_gps': 'GPS photo/video captured',
      
      // Actions / Common
      'yes': 'Yes',
      'no': 'No',
      'submit_survey': 'Submit Survey',
      'update_survey': 'Update',
      'cancel': 'Cancel',
      'confirm': 'Confirm',
      'success': 'Success',
      'error': 'Error',
      'required_field': 'Required',
      'enter_valid_number': 'Enter valid number',
      'search_placeholder': 'Search...',
    },
    'hi': {
      'app_title': 'भू-खदान',
      'survey_form': 'सर्वेक्षण फॉर्म',
      'new_survey': 'नया सर्वेक्षण',
      'edit_survey': 'सर्वेक्षण संपादित करें',

      // Headers
      'project_info': 'परियोजना की जानकारी',
      'location_info': 'स्थान की जानकारी',
      'land_info': 'भूमि की जानकारी',
      'tree_info': 'वृक्ष की जानकारी',
      'house_info': 'मकान की जानकारी',
      'infrastructure': 'बुनियादी सुविधाएं',

      // Fields
      'department': 'विभाग',
      'project': 'परियोजना',
      'village': 'ग्राम',
      'district': 'जिला',
      'tehsil': 'तहसील',

      'affected_khasra': 'प्रभावित खसरा नंबर',
      'total_area': 'कुल रकबा (हेक्टेयर)',
      'acquired_area': 'अर्जन हेतु प्रस्तावित रकबा (हेक्टेयर)',
      'landowners': 'भूमिस्वामी',
      'select_landowners': 'भूमिस्वामी चुनें',
      'diverted_land': 'व्यपवर्तित भूमि',
      'diverted_land_area': 'व्यपवर्तित भूमि का क्षेत्रफल (हेक्टेयर)',
      'land_type': 'भूमि का प्रकार',
      'irrigation_type': 'सिंचाई प्रकार',

      'add_trees_q': 'क्या आप वृक्ष जोड़ना चाहते हैं?',
      'tree_name': 'वृक्ष का नाम',
      'dev_stage': 'विकास स्तर',
      'num_trees': 'वृक्षों की संख्या',
      'add_tree': 'वृक्ष जोड़ें',

      'has_house': 'क्या मकान है?',
      'house_type': 'मकान का प्रकार',
      'house_area': 'मकान का क्षेत्रफल (वर्ग फुट)',
      'has_shed': 'क्या शेड है?',
      'shed_area': 'शेड का क्षेत्रफल (वर्ग फुट)',

      'has_well': 'क्या कुआं है?',
      'well_type': 'कुएं का प्रकार',
      'well_count': 'कुओं की संख्या',
      'has_tubewell': 'क्या ट्यूबवेल/सबमर्सिबल पम्प है?',
      'tubewell_count': 'ट्यूबवेल/सबमर्सिबल पम्प की संख्या',
      'has_pond': 'क्या तालाब है?',

      'remarks': 'टिप्पणी',

      // Home Screen
      'dashboard_stats': 'डैशबोर्ड आँकड़े',
      'total_surveys': 'कुल',
      'approved': 'स्वीकृत',
      'rejected': 'अस्वीकृत',
      'pending': 'लंबित',
      'select_dept_label': 'विभाग',
      'select_project_label': 'परियोजना',
      'select_area_label': 'क्षेत्र',
      'select_village_label': 'ग्राम',
      'select_dept_hint': 'विभाग चुनें',
      'select_project_hint': 'परियोजना चुनें',
      'select_area_hint': 'क्षेत्र चुनें',
      'select_village_hint': 'ग्राम चुनें',
      'msg_select_village': 'आँकड़े देखने के लिए क्षेत्र फिर ग्राम चुनें',
      'msg_no_areas': 'इस परियोजना से कोई क्षेत्र जुड़ा नहीं है',
      'area': 'क्षेत्र',
      'document_checklist': 'दस्तावेज़ चेकलिस्ट',
      'mb_decl_date': 'मालिक घोषणा तिथि',
      'mb_decl_no_claim': 'कोई दावा लंबित नहीं',
      'mb_decl_docs': 'आवश्यक दस्तावेज प्राप्त',
      'mb_decl_gps': 'GPS फोटो/वीडियो ली गई',

      // Actions / Common
      'yes': 'हाँ',
      'no': 'नहीं',
      'submit_survey': 'सर्वेक्षण सबमिट करें',
      'update_survey': 'सर्वेक्षण अपडेट करें',
      'cancel': 'रद्द करें',
      'confirm': 'पुष्टि करें',
      'success': 'सफल',
      'error': 'त्रुटि',
      'required_field': 'आवश्यक है',
      'enter_valid_number': 'मान्य संख्या दर्ज करें',
      
      // Picker
      'search_placeholder': 'खोजें...',
    },
  };

  static String t(String key) {
    String lang = currentLocale.value.languageCode;
    return _localizedValues[lang]?[key] ?? _localizedValues['en']?[key] ?? key;
  }

  static Future<void> loadLanguage() async {
    String? code = await getAsyncItem(LANGUAGE_CODE_KEY);
    if (code != null) {
      currentLocale.value = Locale(code);
    }
  }

  static Future<void> changeLanguage(String code) async {
    currentLocale.value = Locale(code);
    await setAsyncItem(LANGUAGE_CODE_KEY, code);
  }
}
