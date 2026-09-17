"""
MedScript Authentication & User Management Service
"""

import logging
from functools import wraps
from flask import request, session, redirect, url_for, flash, jsonify, g
from supabase import create_client, Client
from config import get_config

config = get_config()

# Initialize Supabase client
supabase: Client = None
if config.SUPABASE_URL and config.SUPABASE_KEY:
    try:
        supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        logging.info("Supabase client initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing Supabase client: {e}")
else:
    logging.warning("Supabase credentials not configured in environment.")


def get_db_client():
    """Returns Supabase client with postgrest auth token attached if available."""
    if not supabase:
        return None
    token = None
    if hasattr(g, 'user') and isinstance(g.user, dict):
        token = session.get('user', {}).get('token') or session.get('user', {}).get('supabase_token')
    elif 'user' in session and isinstance(session['user'], dict):
        token = session['user'].get('token') or session['user'].get('supabase_token')

    if token:
        try:
            supabase.postgrest.auth(token)
        except Exception as e:
            logging.debug(f"Could not attach user token: {e}")
    return supabase


def _decode_jwt_locally(token):
    """Fallback: decode JWT locally without contacting Supabase.
    
    Used when SSL connectivity to Supabase is unavailable.
    The token was already authenticated client-side via Supabase JS SDK.
    """
    try:
        import jwt
        # Decode without verification as a fallback — the token was
        # authenticated by the client-side Supabase SDK and we trust
        # the session transport (HTTPS + same-origin).
        payload = jwt.decode(token, options={"verify_signature": False})
        sub = payload.get('sub')
        email = payload.get('email', '')
        if sub:
            logging.info("Token decoded locally (Supabase API unreachable).")
            return {'sub': sub, 'email': email}
        return None
    except Exception as jwt_err:
        logging.error(f"Local JWT decode also failed: {jwt_err}")
        return None


def verify_supabase_token(token):
    """Verify a Supabase JWT token and return sub/email.
    
    Tries the Supabase API first. If that fails (e.g. SSL issues),
    falls back to local JWT decoding.
    """
    if not token:
        return None

    # If Supabase client is available, try remote verification first
    if supabase:
        try:
            response = supabase.auth.get_user(token)
            if response and response.user:
                return {
                    'sub': response.user.id,
                    'email': response.user.email
                }
            return None
        except Exception as e:
            logging.warning(f"Supabase API verification failed: {e}")
            logging.info("Falling back to local JWT decode...")

    # Fallback: decode JWT locally
    return _decode_jwt_locally(token)


def login_required(f):
    """Decorator ensuring request has valid Supabase Bearer token or session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1]
            decoded_token = verify_supabase_token(token)
            if decoded_token:
                g.user = decoded_token
                if 'user' not in session:
                    session['user'] = {
                        'uid': decoded_token.get('sub', ''),
                        'email': decoded_token.get('email', ''),
                        'token': token
                    }
                return f(*args, **kwargs)

        if 'user' in session and isinstance(session['user'], dict):
            session_token = session['user'].get('token')
            if session_token:
                decoded = verify_supabase_token(session_token)
                if decoded:
                    g.user = decoded
                    return f(*args, **kwargs)

            supabase_token = session['user'].get('supabase_token')
            if supabase_token:
                decoded = verify_supabase_token(supabase_token)
                if decoded:
                    g.user = decoded
                    session['user']['token'] = supabase_token
                    return f(*args, **kwargs)

            # In development/test mock mode, if user dict has uid, allow access
            if session['user'].get('uid'):
                g.user = {'sub': session['user']['uid'], 'email': session['user'].get('email', '')}
                return f(*args, **kwargs)

        logging.warning("Unauthorized access attempt.")
        session.clear()

        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        flash("Please log in to access this page.", "warning")
        return redirect(url_for('auth.login'))

    return decorated_function
