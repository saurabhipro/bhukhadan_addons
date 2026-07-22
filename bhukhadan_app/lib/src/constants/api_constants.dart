class ApiEndpoints {
  // Base
  static const String baseUrl = "https://bhuarjan.com/api";

  // Auth
  static const String requestOtp = '/auth/request_otp';
  static const String login = '/auth/login';

  // Master Data (Project → Area → Village)
  // GET /bhukhadan/projects?department_id=
  static const String projects = '/bhukhadan/projects';
  // GET /bhukhadan/areas?project_id=
  static const String areas = '/bhukhadan/areas';
  // GET /bhukhadan/villages?project_id=&area_id=
  static const String villages = '/bhukhadan/villages';

  // Legacy nested projects (kept for profile/fallback if still available)
  static const String userProjects = '/bhukhadan/projects';

  // Dashboard
  static const String dashboardVillage = '/bhukhadan/dashboard/village';

  // Surveys (list + CRUD share /bhukhadan/survey)
  // GET /bhukhadan/survey?village_id=&q=
  // POST /bhukhadan/survey
  // GET /bhukhadan/survey/$id
  // PATCH /bhukhadan/survey/$id
  static const String surveys = '/bhukhadan/survey';
  static const String survey = '/bhukhadan/survey';

  // Master Data
  static const String trees = '/bhukhadan/trees';
  static const String landTypes = '/bhukhadan/land-types';
  static const String landowners = '/bhukhadan/landowners';
  static const String landowner = '/bhukhadan/landowner';

  // Photos
  static const String presignedUrls = '/bhukhadan/s3/presigned-urls';
  static const String surveyImages = '/bhukhadan/survey/images';
  static const String photoUpload = '/bhukhadan/survey/photos';
  static const String deletePhoto = '/bhukhadan/photo';

  // PDF
  static const String generatePdf = '/bhukhadan/pdf/generate';

  // Screenshot audit
  // POST /bhukhadan/audit/screenshot
  static const String screenshotAudit = '/bhukhadan/audit/screenshot';
}
