lines = open('lib/src/screens/survey_details_screen.dart', 'r', encoding='utf-8').readlines()

# 1. Replace lines 571-607 (0-indexed: 570-606) - the SUBMITTED badge container
# Add survey type badge BEFORE the submitted badge, on the same row
# The row starts at line 559 (0-indexed 558) with mainAxisAlignment: spaceBetween
# We'll change the right side to have both badges in a Row

old_right_side = ''.join(lines[570:607])  # lines 571-607

new_right_side = (
    '                         Row(\r\n'
    '                           mainAxisSize: MainAxisSize.min,\r\n'
    '                           children: [\r\n'
    '                             // Survey Type badge\r\n'
    '                             Container(\r\n'
    '                               padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),\r\n'
    '                               decoration: BoxDecoration(\r\n'
    "                                 color: (s['survey_type'] == 'rural')\r\n"
    '                                     ? Colors.green.withOpacity(0.12)\r\n'
    '                                     : Colors.grey.withOpacity(0.12),\r\n'
    '                                 borderRadius: BorderRadius.circular(20),\r\n'
    '                                 border: Border.all(\r\n'
    "                                   color: (s['survey_type'] == 'rural') ? Colors.green : Colors.grey,\r\n"
    '                                   width: 1.2,\r\n'
    '                                 ),\r\n'
    '                               ),\r\n'
    '                               child: Text(\r\n'
    "                                 (s['survey_type'] == 'rural') ? '\u0917\u094d\u0930\u093e\u092e\u0940\u0923' : '\u0936\u0939\u0930\u0940',\r\n"
    '                                 style: TextStyle(\r\n'
    '                                   fontSize: 11,\r\n'
    '                                   fontWeight: FontWeight.bold,\r\n'
    "                                   color: (s['survey_type'] == 'rural') ? Colors.green : Colors.grey[600],\r\n"
    '                                 ),\r\n'
    '                               ),\r\n'
    '                             ),\r\n'
    '                             const SizedBox(width: 6),\r\n'
    '                             // Status badge\r\n'
    '                             Container(\r\n'
    '                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),\r\n'
    '                                decoration: BoxDecoration(\r\n'
    "                                   color: (s['state']?.toString().toLowerCase() == 'approved') \r\n"
    '                                       ? Colors.green.withOpacity(0.1) \r\n'
    "                                       : (s['state']?.toString().toLowerCase() == 'rejected' ? Colors.red.withOpacity(0.1) : Colors.orange.withOpacity(0.1)),\r\n"
    '                                   borderRadius: BorderRadius.circular(20),\r\n'
    '                                   border: Border.all(\r\n'
    "                                     color: (s['state']?.toString().toLowerCase() == 'approved') \r\n"
    '                                       ? Colors.green \r\n'
    "                                       : (s['state']?.toString().toLowerCase() == 'rejected' ? Colors.red : Colors.orange),\r\n"
    '                                     width: 1\r\n'
    '                                   )\r\n'
    '                                ),\r\n'
    '                                child: Row(\r\n'
    '                                   children: [\r\n'
    '                                     Icon(\r\n'
    "                                       (s['state']?.toString().toLowerCase() == 'approved') ? Icons.check_circle : Icons.info,\r\n"
    '                                       size: 14,\r\n'
    "                                       color: (s['state']?.toString().toLowerCase() == 'approved') \r\n"
    '                                         ? Colors.green \r\n'
    "                                         : (s['state']?.toString().toLowerCase() == 'rejected' ? Colors.red : Colors.orange),\r\n"
    '                                     ),\r\n'
    '                                     const SizedBox(width: 4),\r\n'
    '                                     Text(\r\n'
    "                                       s['state']?.toString().toUpperCase() ?? 'N/A',\r\n"
    '                                       style: TextStyle(\r\n'
    '                                          fontSize: 11,\r\n'
    '                                          fontWeight: FontWeight.bold,\r\n'
    "                                          color: (s['state']?.toString().toLowerCase() == 'approved') \r\n"
    '                                             ? Colors.green \r\n'
    "                                             : (s['state']?.toString().toLowerCase() == 'rejected' ? Colors.red : Colors.orange),\r\n"
    '                                       ),\r\n'
    '                                     ),\r\n'
    '                                   ],\r\n'
    '                                ),\r\n'
    '                             ),\r\n'
    '                           ],\r\n'
    '                         )\r\n'
)

lines[570:607] = [new_right_side]

# 2. Now remove Row 4 (survey type badge section) - lines 675-709 (0-indexed: 674-708)
# After the above replacement, line numbers shift. Let's reload and find the marker.
open('lib/src/screens/survey_details_screen.dart', 'w', encoding='utf-8').writelines(lines)
print('Step 1 done, lines now:', len(lines))

# Reload and remove Row 4
lines2 = open('lib/src/screens/survey_details_screen.dart', 'r', encoding='utf-8').readlines()
# Find "Row 4: Survey Type badge"
start_idx = None
end_idx = None
for i, line in enumerate(lines2):
    if '// Row 4: Survey Type badge' in line:
        start_idx = i - 2  # include the SizedBox(height: 12) before it
        break

if start_idx is not None:
    # Find the closing ) of the Row - look for the line with just ")" after the badge
    for j in range(start_idx + 1, len(lines2)):
        stripped = lines2[j].strip()
        if stripped == ')' and j > start_idx + 5:
            end_idx = j + 1
            break

    if end_idx:
        print(f'Removing lines {start_idx+1} to {end_idx}')
        lines2 = lines2[:start_idx] + lines2[end_idx:]
        open('lib/src/screens/survey_details_screen.dart', 'w', encoding='utf-8').writelines(lines2)
        print('Step 2 done, final lines:', len(lines2))
    else:
        print('Could not find end of Row 4')
else:
    print('Could not find Row 4 marker')
