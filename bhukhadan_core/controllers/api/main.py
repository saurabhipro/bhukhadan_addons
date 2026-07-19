import datetime
import json
import logging
import random
from functools import wraps

import jwt
import requests
from odoo import http
from odoo.exceptions import AccessError
from odoo.http import Response, request

_logger = logging.getLogger(__name__)


def check_permission(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise AccessError('Authorization header is missing or invalid')

        token = auth_header[7:]
        try:
            decoded_token = jwt.decode(token, options={'verify_signature': False})
            user_id = decoded_token['user_id']
            user = request.env['res.users'].sudo().search([('id', '=', user_id)], limit=1)
            if not user:
                raise AccessError('User not found')
            request.user = user
            request.update_env(user=user.id)
        except jwt.ExpiredSignatureError as err:
            raise AccessError('JWT token has expired') from err
        except jwt.InvalidTokenError as err:
            raise AccessError('Invalid JWT token') from err
        except Exception as err:
            raise AccessError(str(err)) from err

        return func(*args, **kwargs)
    return wrapper
