import jwt
import datetime
import random
import logging
import requests  # Import requests to send API call
from odoo import http
from odoo.http import request, Response
from odoo import models, fields
import json
import random

_logger = logging.getLogger(__name__)

import jwt

from odoo.exceptions import AccessError, UserError


from functools import wraps

def check_permission(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            raise AccessError('Authorization header is missing or invalid')

        token = auth_header[7:]

        try:
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            user_id = decoded_token['user_id']
            user = request.env['res.users'].sudo().search([('id', '=', user_id)])
            if not user:
                raise AccessError('User not found')
            request.user = user  # Optionally store for later use
        except jwt.ExpiredSignatureError:
            raise AccessError('JWT token has expired')
        except jwt.InvalidTokenError:
            raise AccessError('Invalid JWT token')
        except Exception as e:
            raise AccessError(str(e))

        return func(*args, **kwargs)
    return wrapper





