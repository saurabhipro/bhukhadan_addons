lines = open('lib/src/screens/survey_details_screen.dart', 'r', encoding='utf-8').readlines()
new_block = [
    '                    // Row 4: Survey Type badge\r\n',
    '                    Row(\r\n',
    '                       children: [\r\n',
    '                          Icon(Icons.landscape, size: 16, color: Colors.grey[600]),\r\n',
    '                          const SizedBox(width: 8),\r\n',
    '                          Text(\r\n',
    "                            '\u0938\u0930\u094d\u0935\u0947 \u0915\u093e \u092a\u094d\u0930\u0915\u093e\u0930: ',\r\n",
    '                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: isDark ? Colors.grey[400] : Colors.grey[700]),\r\n',
    '                          ),\r\n',
    '                          Container(\r\n',
    '                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),\r\n',
    '                            decoration: BoxDecoration(\r\n',
    "                              color: (s['survey_type'] == 'rural')\r\n",
    '                                  ? Colors.green.withOpacity(0.15)\r\n',
    '                                  : Colors.grey.withOpacity(0.15),\r\n',
    '                              borderRadius: BorderRadius.circular(20),\r\n',
    '                              border: Border.all(\r\n',
    "                                color: (s['survey_type'] == 'rural') ? Colors.green : Colors.grey,\r\n",
    '                                width: 1.2,\r\n',
    '                              ),\r\n',
    '                            ),\r\n',
    '                            child: Text(\r\n',
    "                              (s['survey_type'] == 'rural') ? '\u0917\u094d\u0930\u093e\u092e\u0940\u0923' : '\u0936\u0939\u0930\u0940',\r\n",
    '                              style: TextStyle(\r\n',
    '                                fontSize: 13,\r\n',
    '                                fontWeight: FontWeight.bold,\r\n',
    "                                color: (s['survey_type'] == 'rural') ? Colors.green : Colors.grey[600],\r\n",
    '                              ),\r\n',
    '                            ),\r\n',
    '                          ),\r\n',
    '                       ],\r\n',
    '                    )\r\n',
]
# lines are 1-indexed, replace lines 678-700 (indices 677-699)
result = lines[:677] + new_block + lines[700:]
open('lib/src/screens/survey_details_screen.dart', 'w', encoding='utf-8').writelines(result)
print('Done, total lines:', len(result))
