lines = open('lib/src/screens/create_survey_screen.dart', 'r', encoding='utf-8').readlines()
# Line 782: label for Survey Type
lines[781] = '                          label: "\u0938\u0930\u094d\u0935\u0947 \u0915\u093e \u092a\u094d\u0930\u0915\u093e\u0930",\r\n'
# Line 785: Rural option
lines[784] = '                             CustomRadioOption(label: "\u0917\u094d\u0930\u093e\u092e\u0940\u0923", value: "rural", icon: Icons.landscape),\r\n'
# Line 786: Urban option
lines[785] = '                             CustomRadioOption(label: "\u0936\u0939\u0930\u0940", value: "urban", icon: Icons.location_city),\r\n'
open('lib/src/screens/create_survey_screen.dart', 'w', encoding='utf-8').writelines(lines)
print('Done')
