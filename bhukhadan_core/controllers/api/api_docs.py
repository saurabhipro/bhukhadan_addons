from odoo import http
from odoo.http import request, Response
import json

class ApiDocsController(http.Controller):

    @http.route('/bhuarjan/api/docs', type='http', auth='user')
    def api_docs(self, **kwargs):
        # Only allow administrators (base.group_system)
        if not request.env.user.has_group('base.group_system'):
             return request.not_found()
        
        swagger_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>BhuKhadan API Documentation</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" />
    <style>
        body { margin: 0; padding: 0; }
    </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js" crossorigin></script>
<script>
    window.onload = () => {
    window.ui = SwaggerUIBundle({
        url: '/bhuarjan/api/openapi.json',
        dom_id: '#swagger-ui',
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout",
    });
    };
</script>
</body>
</html>
        """
        return swagger_html

    @http.route('/bhuarjan/api/openapi.json', type='http', auth='user', cors='*')
    def openapi_spec(self, **kwargs):
        if not request.env.user.has_group('base.group_system'):
             return request.not_found()

        # Construct basic spec
        # Use relative URL to allow flexibility (works with HTTP/HTTPS automatically)
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "BhuKhadan REST API",
                "description": "API documentation for BhuKhadan Mobile App integration. You can test endpoints directly here.",
                "version": "1.0.0"
            },
            "servers": [
                {"url": "/"} 
            ],
            "components": {
                "securitySchemes": {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT"
                    }
                }
            },
            "paths": {
                # Authentication
                "/api/auth/request_otp": {
                    "post": {
                        "tags": ["Authentication"],
                        "summary": "Request OTP",
                        "description": "Request an OTP for a mobile number.",
                         "requestBody": {
                             "required": True,
                             "content": {
                                 "application/json": {
                                     "schema": {
                                         "type": "object",
                                         "required": ["mobile"],
                                         "properties": {
                                             "mobile": {"type": "string", "example": "9990649990"}
                                         }
                                     }
                                 }
                             }
                         },
                        "responses": {
                             "200": {"description": "OTP Generated/Sent"},
                             "400": {"description": "Bad Request"},
                             "500": {"description": "Server Error"}
                        }
                    }
                },
                "/api/auth/login": {
                     "post": {
                         "tags": ["Authentication"],
                         "summary": "Login with OTP",
                         "description": "Validate OTP and get JWT token.",
                         "requestBody": {
                             "required": True,
                             "content": {
                                 "application/json": {
                                     "schema": {
                                         "type": "object",
                                         "required": ["mobile", "otp_input"],
                                         "properties": {
                                             "mobile": {"type": "string", "example": "9990649990"},
                                             "otp_input": {"type": "string", "example": "1234"}
                                         }
                                     }
                                 }
                             }
                         },
                         "responses": {
                             "200": {"description": "Successful Login, returns Token"},
                             "400": {"description": "Invalid OTP"}
                         }
                     }
                },

                # User Data
                "/api/bhuarjan/user/projects": {
                    "get": {
                        "tags": ["User Data"],
                        "summary": "Get User Projects",
                        "description": "Get departments, projects, and villages mapped to a specific user.",
                        "security": [{"bearerAuth": []}],
                        "parameters": [
                            {"name": "user_id", "in": "query", "required": True, "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "List of user projects structure"}
                        }
                    }
                },
                "/api/bhuarjan/users": {
                    "get": {
                        "tags": ["User Data"],
                        "summary": "Get All Users",
                        "security": [{"bearerAuth": []}],
                        "parameters": [
                            {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                            {"name": "offset", "in": "query", "schema": {"type": "integer"}},
                            {"name": "role", "in": "query", "schema": {"type": "string"}}
                        ],
                        "responses": {
                            "200": {"description": "List of users"}
                        }
                    }
                },
                 "/api/bhuarjan/users/autocomplete": {
                    "get": {
                        "tags": ["User Data"],
                        "summary": "Autocomplete Users",
                        "security": [{"bearerAuth": []}],
                        "parameters": [
                            {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
                            {"name": "limit", "in": "query", "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "List of matching users"}
                        }
                    }
                },

                # Master Data
                "/api/bhuarjan/departments": {
                    "get": {
                        "tags": ["Master Data"],
                        "summary": "Get All Departments",
                        "responses": {
                            "200": {"description": "List of departments"}
                        }
                    }
                },
                "/api/bhuarjan/departments/{department_id}/projects": {
                    "get": {
                        "tags": ["Master Data"],
                        "summary": "Get Department Projects",
                        "parameters": [
                            {"name": "department_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                            {"name": "user_id", "in": "query", "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "List of projects in department"}
                        }
                    }
                },

                "/api/bhuarjan/land-types": {
                    "get": {
                        "tags": ["Master Data"],
                        "summary": "Get Land Types",
                        "responses": {
                            "200": {"description": "List of land types"}
                        }
                    }
                },
                "/api/bhuarjan/trees": {
                    "get": {
                        "tags": ["Master Data"],
                        "summary": "Get Trees",
                        "parameters": [
                            {"name": "type", "in": "query", "schema": {"type": "string", "enum": ["fruit_bearing", "non_fruit_bearing"]}},
                            {"name": "name", "in": "query", "schema": {"type": "string"}},
                            {"name": "development_stage", "in": "query", "schema": {"type": "string"}},
                            {"name": "girth_cm", "in": "query", "schema": {"type": "number"}}
                        ],
                        "responses": {
                            "200": {"description": "List of trees with optional rates"}
                        }
                    }
                },

                # Survey Management
                "/api/bhuarjan/survey": {
                    "post": {
                        "tags": ["Survey Management"],
                        "summary": "Create Survey",
                        "security": [{"bearerAuth": []}],
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "project_id": {"type": "integer"},
                                            "village_id": {"type": "integer"},
                                            "department_id": {"type": "integer"},
                                            "tehsil_id": {"type": "integer"},
                                            "survey_type": {"type": "string", "enum": ["rural", "urban"]},
                                            "khasra_number": {"type": "string"},
                                            "total_area": {"type": "number"},
                                            "acquired_area": {"type": "number"},
                                            "landowner_ids": {"type": "array", "items": {"type": "integer"}},
                                            "tree_lines": {
                                                "type": "array", 
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "tree_master_id": {"type": "integer"},
                                                        "tree_name": {"type": "string"},
                                                        "development_stage": {"type": "string", "enum": ["undeveloped", "semi_developed", "fully_developed"]},
                                                        "girth_cm": {"type": "number", "description": "Circumference in cm (optional, > 0)"},
                                                        "quantity": {"type": "integer"}
                                                    }
                                                }
                                            },
                                            "photos": {"type": "array", "items": {"type": "object"}}
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {
                            "201": {"description": "Survey Created"},
                            "400": {"description": "Validation Error"}
                        }
                    }
                },
                "/api/bhuarjan/survey/{survey_id}": {
                    "get": {
                        "tags": ["Survey Management"],
                        "summary": "Get Survey Details",
                        "security": [{"bearerAuth": []}],
                        "parameters": [
                            {"name": "survey_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "Survey details"}
                        }
                    }
                },
                "/api/bhuarjan/surveys": {
                     "get": {
                        "tags": ["Survey Management"],
                        "summary": "List Surveys",
                        "security": [{"bearerAuth": []}],
                        "parameters": [
                             {"name": "project_id", "in": "query", "schema": {"type": "integer"}},
                             {"name": "village_id", "in": "query", "schema": {"type": "integer"}},
                             {"name": "state", "in": "query", "schema": {"type": "string"}},
                             {"name": "survey_type", "in": "query", "schema": {"type": "string", "enum": ["rural", "urban"]}}
                        ],
                        "responses": {
                            "200": {"description": "List of surveys"}
                        }
                     }
                },
                "/api/bhuarjan/photo/{photo_id}": {
                    "delete": {
                        "tags": ["Survey Management"],
                        "summary": "Delete Survey Photo",
                        "security": [{"bearerAuth": []}],
                        "parameters": [
                            {"name": "photo_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "Photo deleted"}
                        }
                    }
                },

                # File Upload
                "/api/bhuarjan/s3/presigned-urls": {
                    "post": {
                        "tags": ["File Upload"],
                        "summary": "Generate S3 Presigned URLs",
                        "requestBody": {
                             "required": True,
                             "content": {
                                 "application/json": {
                                     "schema": {
                                         "type": "object",
                                         "required": ["survey_id", "file_names"],
                                         "properties": {
                                             "survey_id": {"type": "integer"},
                                             "file_names": {"type": "array", "items": {"type": "string"}}
                                         }
                                     }
                                 }
                             }
                        },
                        "responses": {
                            "200": {"description": "Presigned URLs generated"}
                        }
                    }
                },
                "/api/bhuarjan/survey/images": {
                    "get": {
                        "tags": ["File Upload"],
                        "summary": "Get Survey Images",
                        "parameters": [
                            {"name": "survey_id", "in": "query", "required": True, "schema": {"type": "integer"}},
                            {"name": "photo_type_id", "in": "query", "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "List of images"}
                        }
                    }
                },

                # Exports
                 "/api/bhuarjan/form10/download": {
                    "get": {
                        "tags": ["Exports"],
                        "summary": "Download Form 10 PDF",
                        "parameters": [
                            {"name": "village_id", "in": "query", "required": True, "schema": {"type": "integer"}},
                            {"name": "project_id", "in": "query", "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "PDF File"}
                        }
                    }
                },
                 "/api/bhuarjan/form10/excel/download": {
                    "get": {
                        "tags": ["Exports"],
                        "summary": "Download Form 10 Excel",
                        "parameters": [
                            {"name": "village_id", "in": "query", "required": True, "schema": {"type": "integer"}},
                            {"name": "project_id", "in": "query", "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "Excel File"}
                        }
                    }
                }
            }
        }
        return request.make_response(json.dumps(spec), headers=[('Content-Type', 'application/json')])
