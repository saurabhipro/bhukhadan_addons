class PickerUser {
  final String id;
  final String name;
  final String? fatherName;
  final String? spouseName;
  final String? districtId;
  final String? tehsilId;
  final String? villageId;
  final String? ownerAddress;
  final String? aadharNumber;
  final String? panNumber;
  final String? bankName;
  final String? accountNumber;
  final String? ifscCode;
  final String? accountHolderName;
  final String? phone;

  PickerUser({
    required this.id,
    required this.name,
    this.fatherName,
    this.spouseName,
    this.districtId,
    this.tehsilId,
    this.villageId,
    this.ownerAddress,
    this.aadharNumber,
    this.panNumber,
    this.bankName,
    this.accountNumber,
    this.ifscCode,
    this.accountHolderName,
    this.phone,
  });

  factory PickerUser.fromJson(Map<String, dynamic> json) {
    return PickerUser(
      id: json['id']?.toString() ?? json['landowner_id']?.toString() ?? json['landowner_master_id']?.toString() ?? '',
      name: json['name'] ?? '',
      fatherName: json['father_name'],
      spouseName: json['spouse_name'],
      districtId: json['district_id']?.toString(),
      tehsilId: json['tehsil_id']?.toString(),
      villageId: json['village_id']?.toString(),
      ownerAddress: json['owner_address'],
      aadharNumber: json['aadhar_number'],
      panNumber: json['pan_number'],
      bankName: json['bank_name'],
      accountNumber: json['account_number'],
      ifscCode: json['ifsc_code'],
      accountHolderName: json['account_holder_name'],
      phone: json['phone'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'father_name': fatherName,
      'spouse_name': spouseName,
      'district_id': districtId,
      'tehsil_id': tehsilId,
      'village_id': villageId,
      'owner_address': ownerAddress,
      'aadhar_number': aadharNumber,
      'pan_number': panNumber,
      'bank_name': bankName,
      'account_number': accountNumber,
      'ifsc_code': ifscCode,
      'account_holder_name': accountHolderName,
    };
  }
}
