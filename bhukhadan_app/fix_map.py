lines = open('lib/src/screens/create_survey_screen.dart', 'r', encoding='utf-8').readlines()
for i, line in enumerate(lines):
    if 'userAgentPackageName' in line and 'com.example.app' in line:
        lines[i] = "                                                   userAgentPackageName: 'com.example.bhuarjan',\r\n"
        print(f'Fixed line {i+1}')
        break
open('lib/src/screens/create_survey_screen.dart', 'w', encoding='utf-8').writelines(lines)
print('Done')
