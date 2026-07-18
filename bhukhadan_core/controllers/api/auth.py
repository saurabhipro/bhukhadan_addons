from .main import *

from datetime import timezone
import logging

_logger = logging.getLogger(__name__)

SECRET_KEY = 'secret'

class JWTAuthController(http.Controller):

    def _find_user_by_mobile(self, mobile):
        """Find a user by primary mobile OR any of their additional mobile numbers."""
        env = request.env
        # 1. Check primary mobile
        user = env['res.users'].sudo().search([('mobile', '=', mobile)], limit=1)
        if user:
            return user
        # 2. Check additional mobile numbers
        extra = env['bhu.user.mobile'].sudo().search([
            ('mobile', '=', mobile),
            ('active', '=', True),
        ], limit=1)
        if extra:
            return extra.user_id
        return env['res.users'].sudo().browse()  # empty recordset

    @http.route('/api/auth/request_otp', type='http', auth='none', methods=['POST'], csrf=False)

    def request_otp(self, **kwargs):
        try:
            data = json.loads(request.httprequest.data or "{}")
            mobile = data.get('mobile')
            if not mobile:
                return Response(json.dumps({'error': 'Mobile number is missing'}), status=400, content_type='application/json')

            user = self._find_user_by_mobile(mobile)
            if not user:            
                return Response(json.dumps({'error': "User Not Register"}), status=400, content_type='application/json')

            existing_otp = request.env['mobile.otp'].sudo().search([('mobile', '=', mobile)])
            if existing_otp:
                existing_otp.unlink()

            # Check if static OTP is enabled in any active settings master
            settings_master = request.env['bhuarjan.settings.master'].sudo().search([
                ('active', '=', True)
            ], limit=1)

            # Determine if we should use static OTP behavior (skip SMS)
            use_static_otp_behavior = False
            otp_to_return = None

            # 1. Check Global Static OTP Setting
            if settings_master and settings_master.enable_static_otp:
                otp_code = str(settings_master.static_otp_value or '1234')
                use_static_otp_behavior = True
                otp_to_return = otp_code
                _logger.info(f"Using Global Static OTP: {otp_code} for mobile: {mobile}")
            
            # 2. Check for Patwari Role (Auto-Detect Logic)
            # If user is a Patwari, we generate an OTP but return it in the response (skipping SMS)
            # so the app can auto-detect/auto-fill it for easy login.
            elif user.bhuarjan_role in request.env['res.users'].BHUKHADAN_PATWARI_ROLES:
                otp_code = str(random.randint(1000, 9999))
                use_static_otp_behavior = True # We treat it like static in terms of "return in response, skip SMS"
                otp_to_return = otp_code
                _logger.info(f"Generated Auto-Login OTP for Patwari: {otp_code}")

            # 3. Default: Generate Random OTP for SMS
            else:
                otp_code = str(random.randint(1000, 9999))
                # Do NOT set use_static_otp_behavior or otp_to_return

            expire_time = datetime.datetime.now(timezone.utc) + datetime.timedelta(minutes=5)
            # Convert to naive datetime (Odoo Datetime fields expect naive datetimes)
            expire_time_naive = expire_time.replace(tzinfo=None)

            request.env['mobile.otp'].sudo().create({
                'mobile': mobile,
                'user_id': user.id,
                'otp': otp_code,
                'expire_date': expire_time_naive,
            })

            # If we decided to skip SMS (Global Static OR Patwari Auto-Login)
            if use_static_otp_behavior:
                return Response(
                    json.dumps({
                        'message': 'OTP generated successfully',
                        'details': otp_to_return, # Return OTP for auto-fill
                        'auto_fill': True,       # Flag for app to know it can auto-fill
                        'role': user.bhuarjan_role or 'user'
                    }),
                    status=200,
                    content_type='application/json'
                )

            # Send SMS for normal users (Non-Patwari, and Global Static is OFF)
            try:
                # Check if OTP API URL is configured in settings
                if settings_master and settings_master.otp_api_url:
                    api_url = settings_master.otp_api_url
                    
                    # Prepare message
                    message_template = settings_master.otp_message_template or 'OTP to Login in Survey APP {otp} Redmelon Pvt Ltd.'
                    message = message_template.replace('{otp}', otp_code)
                    
                    # Append Android App Hash if configured
                    if settings_master.android_app_hash:
                        message = f"{message} {settings_master.android_app_hash}"
                    
                    # Prepare parameters
                    params = {
                        'ApiKey': settings_master.otp_api_key or '',
                        'ClientId': settings_master.otp_client_id or '',
                        'senderid': settings_master.otp_sender_id or '',
                        'message': message,
                        'MobileNumbers': mobile,
                        'msgtype': 'TXT',
                        'response': 'Y',
                        'dlttempid': settings_master.otp_dlt_template_id or ''
                    }
                    
                    _logger.info(f"Sending OTP to {mobile} via configured API")
                    
                    # Verify we have a sender ID before sending
                    if not settings_master.otp_sender_id:
                        _logger.error("OTP Sender ID is missing in configuration")
                        return Response(json.dumps({'error': 'SMS Configuration Error: Sender ID is missing'}), status=500, content_type='application/json')

                    response = requests.get(api_url, params=params)
                else:
                    # Settings not configured
                    _logger.error("OTP Settings (API URL) not configured in BhuKhadan Settings.")
                    return Response(json.dumps({'error': 'OTP Service Not Configured', 'details': 'Please contact administrator to configure OTP settings'}), status=500, content_type='application/json')
                
                print("\n\n response.status_code - ", response.status_code)
                
                if response.status_code == 200:
                    # Check for API-level errors in JSON if possible
                    try:
                        resp_json = response.json()
                        if resp_json.get('ErrorCode') and resp_json.get('ErrorCode') != 0:
                             _logger.error(f"SMS API Error: {resp_json}")
                             return Response(json.dumps({'error': 'SMS Gateway Error', 'details': resp_json.get('ErrorDescription')}), status=400, content_type='application/json')
                    except:
                        pass # Not JSON or parse error, assume success if 200 OK

                    return Response(json.dumps({'message': 'OTP sent successfully'}), status=200, content_type='application/json')
                else:
                    return Response(json.dumps({'error': 'Failed to send OTP via SMS API', 'details': response.text}), status=400, content_type='application/json')

            except Exception as sms_error:
                _logger.error(f"Error sending SMS: {str(sms_error)}", exc_info=True)
                return Response(json.dumps({'error': 'Error sending SMS', 'details': str(sms_error)}), status=400, content_type='application/json')

        except json.JSONDecodeError as e:
            _logger.error(f"JSON decode error in request_otp: {str(e)}", exc_info=True)
            return Response(json.dumps({'error': 'Invalid JSON in request body', 'details': str(e)}), status=400, content_type='application/json')
        except Exception as e:
            _logger.error(f"Error in request_otp: {str(e)}", exc_info=True)
            return Response(json.dumps({'error': 'Internal server error', 'details': str(e)}), status=500, content_type='application/json')
               
    @http.route('/api/auth/register', type='http', auth='public', methods=['POST'], csrf=False)

    def create_user(self, **kwargs):
        try:
            # Parse incoming JSON data
            data = json.loads(request.httprequest.data or "{}")

            # Validate that required fields are present in the request data
            required_fields = ['name', 'mobile', 'login', 'password']
            for field in required_fields:
                if field not in data:
                    return Response(
                        json.dumps({'error': f'{field} is required'}),
                        status=400,
                        content_type='application/json'
                    )

            # Extract user details from the request
            name = data.get('name')
            mobile = data.get('mobile')
            login = data.get('login')
            password = data.get('password')

            # Check if the login already exists (limit=1 ensures only 1 user is returned)
            existing_user = request.env['res.users'].sudo().search([('login', '=', login)], limit=1)
            if existing_user:
                return Response(
                    json.dumps({'error': f'User with login {login} already exists'}),
                    status=400,
                    content_type='application/json'
                )

            # Check if the mobile number already exists (limit=1 ensures only 1 user is returned)
            existing_mobile_user = request.env['res.users'].sudo().search([('mobile', '=', mobile)], limit=1)
            if existing_mobile_user:
                return Response(
                    json.dumps({'error': f'User with mobile {mobile} already exists'}),
                    status=400,
                    content_type='application/json'
                )

            # Create the new user
            user_vals = {
                'name': name,
                'mobile': mobile,
                'login': login,
                'password': password,
                'active': True,
                'company_id': 1,  # Set the default company if needed
                'company_ids': [(4, 1)],  # Link the user to the company with ID 1
                'groups_id': [(6, 0, [request.env.ref('base.group_user').id, request.env.ref('jwt_mobile_auth.surveyor_group_ddn').id])],  # Assigning the user to the basic user group
            }

            # Create the user
            user = request.env['res.users'].sudo().create(user_vals)
            # Return a success response with user details
            return Response(
                json.dumps({
                    'message': 'User created successfully',
                    'user_id': user.id,
                    'name': user.name,
                    'mobile': user.mobile,
                    'login': user.login,
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            # Handle any unexpected errors
            return Response(
                json.dumps({'error': str(e)}),
                status=400,
                content_type='application/json'
            )

    @http.route('/api/auth/login', type='http', auth='none', methods=['POST'], csrf=False)

    def login(self, **kwargs):
        try:
            data = json.loads(request.httprequest.data or "{}")
            mobile = data.get('mobile')
            otp_input = data.get('otp_input')
            if not mobile or not otp_input:
                return Response(json.dumps({'error': 'Mobile number or OTP is missing'}), status=400, content_type='application/json')
            
            user_obj = None
            otp_record = None

            # Check Global Static OTP Setting for Bypass
            settings_master = request.env['bhuarjan.settings.master'].sudo().search([('active', '=', True)], limit=1)
            
            bypass_otp_check = False
            if settings_master and settings_master.enable_static_otp:
                static_val = str(settings_master.static_otp_value or '1234')
                if otp_input == static_val:
                     # Static OTP Matched! Find user by mobile directly (primary OR additional).
                     user_obj = self._find_user_by_mobile(mobile)
                     if not user_obj:
                         return Response(json.dumps({'error': 'User not found for this mobile'}), status=400, content_type='application/json')
                     bypass_otp_check = True
            
            if not bypass_otp_check:
                otp_record = request.env['mobile.otp'].sudo().search([
                    ('mobile', '=', mobile),
                    ('otp', '=', otp_input)
                ], limit=1)
                if not otp_record:
                    return Response(json.dumps({'error': 'Invalid OTP'}), status=400, content_type='application/json')

                expire_date = otp_record.expire_date
                # Odoo returns naive datetime, convert current time to naive UTC for comparison
                if expire_date:
                    current_time_naive = datetime.datetime.now(timezone.utc).replace(tzinfo=None)
                    if current_time_naive > expire_date:
                        otp_record.unlink()
                        return Response(json.dumps({'error': 'OTP expired'}), status=400, content_type='application/json')
                
                user_obj = otp_record.user_id

            user_id = user_obj.id
            
            # Check if user is active
            if not user_obj.active:
                if otp_record:
                    otp_record.unlink()
                return Response(
                    json.dumps({
                        'error': 'User account is inactive. Please contact Administrator.',
                        'user_name': user_obj.name or '',
                        'login': user_obj.login or ''
                    }),
                    status=403,
                    content_type='application/json'
                )
            
            if otp_record:
                otp_record.unlink()

            # Delete old JWT tokens for the same user before creating a new one
            old_tokens = request.env['jwt.token'].sudo().search([('user_id', '=', user_id)])
            if old_tokens:
                old_tokens.unlink()

            payload = {
                'user_id': user_id,
                'exp': datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=24)
            }
            token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

            # Create new JWT token with channel information
            request.env['jwt.token'].sudo().create({
                'user_id': user_id,
                'token': token,
                'channel_type': 'mobile',
            })

            # Get user's groups/roles
            user_groups = user_obj.groups_id
            roles = []
            for group in user_groups:
                roles.append({
                    'id': group.id,
                    'name': group.name,
                    'category_id': group.category_id.name if group.category_id else None
                })

            # Prepare response with user details
            response_data = {
                'user_id': user_id,
                'user_name': user_obj.name or '',
                'login': user_obj.login or '',
                'mobile': user_obj.mobile or '',
                'roles': roles,
                'token': token
            }

            return Response(json.dumps(response_data), status=200, content_type='application/json')

        except json.JSONDecodeError as e:
            _logger.error(f"JSON decode error in login: {str(e)}", exc_info=True)
            return Response(json.dumps({'error': 'Invalid JSON in request body', 'details': str(e)}), status=400, content_type='application/json')
        except Exception as e:
            _logger.error(f"Error in login: {str(e)}", exc_info=True)
            return Response(json.dumps({'error': 'Internal server error', 'details': str(e)}), status=500, content_type='application/json')

    @http.route('/api/get_contacts', type='json', auth='none', methods=['POST'], csrf=False)
    def get_contacts(self, **kwargs):
        try:
            user_id = check_permission(request.httprequest.headers.get('Authorization'))
            if user_id :
                contacts = request.env['res.partner'].sudo().search([])
                contact_data = []
                for contact in contacts:
                    contact_data.append({
                        'name': contact.name,
                        'phone': contact.phone,
                        'email': contact.email,
                        'company': contact.company_id.name if contact.company_id else ''
                    })

                return {'contacts': contact_data}

        except jwt.ExpiredSignatureError:
            raise AccessError('JWT token has expired')
        except jwt.InvalidTokenError:
            raise AccessError('Invalid JWT token')
    
