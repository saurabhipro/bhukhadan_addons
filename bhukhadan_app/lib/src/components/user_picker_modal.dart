import 'package:flutter/material.dart';
import '../utils/colors.dart';
import '../components/text_input_field.dart';
import '../components/custom_button.dart';
import '../models/picker_user.dart';

class UserPickerModal extends StatefulWidget {
  final List<PickerUser> users;
  final List<String> selectedUserIds; // Changed from Set to List for simplicity in params
  final String districtId;
  final String tehsilId;
  final String villageId;
  final Function(List<PickerUser>) onConfirmSelection;
  final Future<PickerUser> Function(Map<String, dynamic>) onSaveNewUser;
  final Future<PickerUser> Function(String, Map<String, dynamic>)? onUpdateUser;

  const UserPickerModal({
    super.key,
    required this.users,
    required this.selectedUserIds,
    required this.districtId,
    required this.tehsilId,
    required this.villageId,
    required this.onConfirmSelection,
    required this.onSaveNewUser,
    this.onUpdateUser,
  });

  @override
  State<UserPickerModal> createState() => _UserPickerModalState();
}

class _UserPickerModalState extends State<UserPickerModal> {
  bool _isAdding = false;
  String? _editingUserId;
  late List<String> _selectedIds;
  String _searchQuery = "";
  
  // Form State
  final _nameController = TextEditingController();
  final _fatherNameController = TextEditingController();
  final _spouseNameController = TextEditingController();
  final _addressController = TextEditingController();
  final _bankNameController = TextEditingController();
  final _accountNumberController = TextEditingController();
  final _ifscController = TextEditingController();
  final _accountHolderController = TextEditingController();

  String _nameType = 'father'; // 'father' or 'spouse'
  bool _isLoading = false;
  Map<String, String> _errors = {};

  @override
  void initState() {
    super.initState();
    _selectedIds = List.from(widget.selectedUserIds);
  }

  void _resetForm() {
    _nameController.clear();
    _fatherNameController.clear();
    _spouseNameController.clear();
    _addressController.clear();
    _bankNameController.clear();
    _accountNumberController.clear();
    _ifscController.clear();
    _accountHolderController.clear();
    _nameType = 'father';
    _editingUserId = null;
    _errors = {};
  }

  void _populateForm(PickerUser user) {
    _nameController.text = user.name;
    _fatherNameController.text = user.fatherName ?? "";
    _spouseNameController.text = user.spouseName ?? "";
    _nameType = (user.fatherName != null && user.fatherName!.isNotEmpty) ? 'father' : 'spouse';
    _addressController.text = user.ownerAddress ?? "";
    _bankNameController.text = user.bankName ?? "";
    _accountNumberController.text = user.accountNumber ?? "";
    _ifscController.text = user.ifscCode ?? "";
    _accountHolderController.text = user.accountHolderName ?? "";
    _editingUserId = user.id;
  }

  Future<void> _handleSave() async {
    setState(() => _errors = {});
    
    if (_nameController.text.trim().isEmpty) {
      setState(() => _errors['name'] = "Name is required");
      return;
    }
    if (_nameType == 'father' && _fatherNameController.text.trim().isEmpty) {
       setState(() => _errors['fatherName'] = "Father's name is required");
       return;
    }
    if (_nameType == 'spouse' && _spouseNameController.text.trim().isEmpty) {
       setState(() => _errors['spouseName'] = "Husband's name is required");
       return;
    }
    if (_addressController.text.trim().isEmpty) {
       setState(() => _errors['address'] = "Address is required");
       return;
    }

    setState(() => _isLoading = true);
    
    debugPrint("Creating landowner with IDs:");
    debugPrint("  District ID: ${widget.districtId}");
    debugPrint("  Tehsil ID: ${widget.tehsilId}");
    debugPrint("  Village ID: ${widget.villageId}");
    
    try {
      final userData = {
        'name': _nameController.text.trim(),
        'owner_address': _addressController.text.trim(),
        'father_name': _nameType == 'father' ? _fatherNameController.text.trim() : '',
        'spouse_name': _nameType == 'spouse' ? _spouseNameController.text.trim() : '',
        'bank_name': _bankNameController.text.trim(),
        'account_number': _accountNumberController.text.trim(),
        'ifsc_code': _ifscController.text.trim().toUpperCase(),
        'account_holder_name': _accountHolderController.text.trim(),
        if (widget.districtId.isNotEmpty) 'district_id': widget.districtId,
        if (widget.tehsilId.isNotEmpty) 'tehsil_id': widget.tehsilId,
        if (widget.villageId.isNotEmpty) 'village_id': widget.villageId,
      };
      
      debugPrint("Full userData being sent: $userData");

      if (_editingUserId != null && widget.onUpdateUser != null) {
         await widget.onUpdateUser!(_editingUserId!, userData);
      } else {
         final newUser = await widget.onSaveNewUser(userData);
         _selectedIds.add(newUser.id);
      }
      
      _resetForm();
      setState(() => _isAdding = false);
      
    } catch (e) {
      debugPrint("Error saving user: $e");
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
      backgroundColor: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        padding: const EdgeInsets.all(16),
        constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.9),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  _isAdding 
                    ? (_editingUserId != null ? "Edit Landowner" : "Add Landowner")
                    : "Select Landowner",
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.h1),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () {
                     if (_isAdding) {
                       _resetForm();
                       setState(() => _isAdding = false);
                     } else {
                       Navigator.of(context).pop();
                     }
                  },
                )
              ],
            ),
            
            Expanded(
              child: _isAdding ? _buildForm() : _buildList(),
            )
          ],
        ),
      ),
    );
  }

  Widget _buildList() {
    final filteredUsers = widget.users.where((u) => 
       u.name.toLowerCase().contains(_searchQuery.toLowerCase())
    ).toList();

    return Column(
      children: [
        // Search Bar
        Container(
          height: 48,
          decoration: BoxDecoration(
            color: Colors.grey.shade100,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.grey.shade300),
          ),
          child: TextField(
             onChanged: (val) => setState(() => _searchQuery = val),
             decoration: const InputDecoration(
               hintText: "Search landowner...",
               prefixIcon: Icon(Icons.search, color: Colors.grey),
               border: InputBorder.none,
               contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
             ),
          ),
        ),
        const SizedBox(height: 16),
        
        // List
        Expanded(
          child: filteredUsers.isEmpty 
             ? Column(
                 mainAxisAlignment: MainAxisAlignment.center,
                 children: [
                   Icon(Icons.person_off_outlined, size: 48, color: Colors.grey.shade300),
                   const SizedBox(height: 8),
                   Text("No landowners found", style: TextStyle(color: Colors.grey.shade500)),
                 ],
               )
             : ListView.builder(
                 itemCount: filteredUsers.length,
                 itemBuilder: (context, index) {
                    final user = filteredUsers[index];
                    final isSelected = _selectedIds.contains(user.id);
                    return InkWell(
                      onTap: () {
                         setState(() {
                            if (isSelected) {
                               _selectedIds.remove(user.id);
                            } else {
                               _selectedIds.add(user.id);
                            }
                         });
                      },
                      child: Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                        decoration: BoxDecoration(
                          color: isSelected ? const Color(0xFF104E8B).withValues(alpha: 0.05) : Colors.white,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: isSelected ? const Color(0xFF104E8B) : Colors.grey.shade200,
                            width: 1.5
                          ),
                          boxShadow: [
                            if (!isSelected)
                             BoxShadow(color: Colors.black.withValues(alpha: 0.03), blurRadius: 4, offset: const Offset(0, 2))
                          ]
                        ),
                        child: Row(
                          children: [
                            // Avatar
                            Container(
                              width: 44, height: 44,
                              decoration: BoxDecoration(
                                color: isSelected ? const Color(0xFF104E8B).withValues(alpha: 0.1) : Colors.grey.shade100,
                                shape: BoxShape.circle,
                              ),
                              child: Icon(Icons.person, color: isSelected ? const Color(0xFF104E8B) : Colors.grey, size: 24),
                            ),
                            const SizedBox(width: 12),
                            
                            // Info
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(user.name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Color(0xFF2D3436))),
                                  const SizedBox(height: 2),
                                  Text(
                                    user.fatherName != null ? 'Father: ${user.fatherName}' : 'Husband: ${user.spouseName}',
                                    style: TextStyle(fontSize: 13, color: Colors.grey.shade600),
                                  ),
                                ],
                              ),
                            ),
                            
                            // Actions
                            Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  icon: const Icon(Icons.edit_outlined, size: 20, color: Color(0xFF104E8B)),
                                  constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                                  padding: EdgeInsets.zero,
                                  onPressed: () {
                                     _populateForm(user);
                                     setState(() => _isAdding = true);
                                  },
                                ),
                                const SizedBox(width: 4),
                                Container(
                                  width: 24, height: 24,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: isSelected ? const Color(0xFF104E8B) : Colors.transparent,
                                    border: Border.all(
                                      color: isSelected ? const Color(0xFF104E8B) : Colors.grey.shade400,
                                      width: 2
                                    )
                                  ),
                                  child: isSelected 
                                     ? const Icon(Icons.check, size: 16, color: Colors.white)
                                     : null,
                                )
                              ],
                            )
                          ],
                        ),
                      ),
                    );
                 },
             ),
        ),
        const SizedBox(height: 16),
        // Action Buttons with Brand Color
        Row(
          children: [
            Expanded(
              child: CustomButton(
                title: "Create New", // Shortened text
                color: const Color(0xFF104E8B), 
                filled: false, 
                onPress: () => setState(() => _isAdding = true)
              )
            ),
            const SizedBox(width: 12),
            Expanded(
              child: CustomButton(
                title: "Done", 
                color: const Color(0xFF104E8B), 
                onPress: () {
                   final selectedUsers = widget.users.where((u) => _selectedIds.contains(u.id)).toList();
                   widget.onConfirmSelection(selectedUsers);
                   Navigator.of(context).pop();
                }
              )
            ),
          ],
        )
      ],
    );
  }

  Widget _buildForm() {
    return SingleChildScrollView(
      child: Column(
        children: [
          TextInputField(label: "Name", required: true, controller: _nameController, errorMessage: _errors['name']),
          
          const SizedBox(height: 16),
          Row(
            children: [
              const Text("Select *", style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(width: 16),
              Expanded(
                child: RadioListTile(
                   title: const Text("Father's Name", style: TextStyle(fontSize: 14)),
                   value: 'father',
                   groupValue: _nameType,
                   contentPadding: EdgeInsets.zero,
                   onChanged: (val) => setState(() => _nameType = val.toString()),
                ),
              ),
              Expanded(
                child: RadioListTile(
                   title: const Text("Husband's Name", style: TextStyle(fontSize: 14)),
                   value: 'spouse',
                   groupValue: _nameType,
                   contentPadding: EdgeInsets.zero,
                   onChanged: (val) => setState(() => _nameType = val.toString()),
                ),
              ),
            ],
          ),
          
          if (_nameType == 'father')
             TextInputField(label: "Father's Name", required: true, controller: _fatherNameController, errorMessage: _errors['fatherName']),
          if (_nameType == 'spouse')
             TextInputField(label: "Husband's Name", required: true, controller: _spouseNameController, errorMessage: _errors['spouseName']),
             
          TextInputField(label: "Address", required: true, controller: _addressController, errorMessage: _errors['address']),
          
          TextInputField(label: "Bank Name", controller: _bankNameController),
          TextInputField(label: "Account Number", controller: _accountNumberController, keyboardType: TextInputType.number),
          TextInputField(label: "IFSC Code", controller: _ifscController, maxLength: 11),
          TextInputField(label: "Account Holder Name", controller: _accountHolderController),
          
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(child: CustomButton(title: "Cancel", filled: false, onPress: () {
                 _resetForm();
                 setState(() => _isAdding = false);
              })),
              const SizedBox(width: 10),
              Expanded(child: CustomButton(title: "Save", isLoading: _isLoading, onPress: _handleSave)),
            ],
          )
        ],
      ),
    );
  }
}
