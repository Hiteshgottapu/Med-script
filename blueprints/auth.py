"""
MedScript Authentication & User Profile Blueprint
"""

import logging
from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, session, jsonify, flash, g
from services.auth import supabase, get_db_client, verify_supabase_token, login_required

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if 'user' in session and session.get('user', {}).get('uid'):
            return redirect(url_for('main.index'))
        return render_template('login.html')

    if request.is_json:
        data = request.json or {}
        supabase_token = data.get('supabase_token')
        if not supabase_token:
            return jsonify({'success': False, 'message': 'Missing token'}), 400

        decoded_token = verify_supabase_token(supabase_token)
        if decoded_token:
            session.clear()
            uid = decoded_token.get('sub')
            email = decoded_token.get('email')

            session['user'] = {
                'email': email,
                'uid': uid,
                'token': supabase_token,
                'supabase_token': supabase_token
            }

            try:
                if supabase:
                    profile_resp = supabase.table('profiles').select('*').eq('id', uid).execute()
                    if profile_resp.data:
                        profile = profile_resp.data[0]
                        session['profile'] = {
                            'name': profile.get('name', ''),
                            'email': email,
                            'phone': profile.get('phone', '')
                        }
                    else:
                        session['profile'] = {'name': '', 'email': email, 'phone': ''}
                else:
                    session['profile'] = {'name': '', 'email': email, 'phone': ''}
            except Exception as e:
                logging.error(f"Error fetching profile: {e}")
                session['profile'] = {'name': '', 'email': email, 'phone': ''}

            session.modified = True
            return jsonify({'success': True, 'redirect': url_for('main.index')})

        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    return jsonify({'success': False, 'message': 'Invalid request format'}), 400


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')

    if request.is_json:
        data = request.json or {}
        supabase_token = data.get('supabase_token') or data.get('firebase_token')
        if not supabase_token:
            return jsonify({'success': False, 'message': 'Missing token'}), 400

        decoded_token = verify_supabase_token(supabase_token)
        if decoded_token:
            session.clear()
            uid = decoded_token.get('sub')
            email = decoded_token.get('email')

            session['user'] = {
                'email': email,
                'uid': uid,
                'token': supabase_token,
                'supabase_token': supabase_token
            }

            name = data.get('name', '')
            phone = data.get('phone', '')

            try:
                db_client = get_db_client()
                if db_client:
                    db_client.table('profiles').upsert({
                        'id': uid,
                        'name': name,
                        'phone': phone,
                        'updated_at': datetime.now().isoformat()
                    }).execute()
            except Exception as e:
                logging.error(f"Error creating profile in Supabase: {e}")

            session['profile'] = {'name': name, 'email': email, 'phone': phone}
            session.modified = True
            return jsonify({'success': True, 'redirect': url_for('main.index')})

        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    return jsonify({'success': False, 'message': 'Invalid request format'}), 400


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot-password.html')

    email = request.form.get('email')
    if not email:
        flash("Please enter your email address.", "danger")
        return render_template('forgot-password.html')

    try:
        if supabase:
            supabase.auth.reset_password_for_email(email)
        flash("Password reset instructions sent to your email.", "info")
    except Exception as e:
        logging.error(f"Error requesting password reset: {e}")
        flash("Password reset instructions sent to your email.", "info")

    return render_template('forgot-password.html')


@auth_bp.route('/profile', methods=['GET', 'POST'])
@auth_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def profile():
    try:
        user_uid = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')
        if not user_uid:
            return redirect(url_for('auth.login'))

        profile_data = {}
        client = get_db_client()
        if client:
            try:
                profile_resp = client.table('profiles').select('*').eq('id', user_uid).execute()
                if profile_resp.data:
                    profile_data = profile_resp.data[0]
                else:
                    profile_data = session.get('profile', {})
                    profile_data['email'] = g.user.get('email', '') if hasattr(g, 'user') else ''
            except Exception as e:
                logging.error(f"Error getting user data: {e}")
                profile_data = session.get('profile', {})
        else:
            profile_data = session.get('profile', {})

        if request.method == 'POST':
            data = request.get_json() if request.is_json else request.form.to_dict()
            street = data.get('street', '').strip()
            city = data.get('city', '').strip()
            state = data.get('state', '').strip()
            zipcode = data.get('zipcode', '').strip()
            country = data.get('country', '').strip()
            address_str = data.get('address') or f"{street} {city} {state} {zipcode} {country}".strip()

            update_data = {
                'name': data.get('name', ''),
                'phone': data.get('phone', ''),
                'photo_url': data.get('photo_url', ''),
                'dob': data.get('dob', '') or None,
                'gender': data.get('gender', ''),
                'address': address_str,
                'height': float(data.get('height')) if data.get('height') else None,
                'weight': float(data.get('weight')) if data.get('weight') else None,
                'blood_group': data.get('blood_group', ''),
                'smoking': data.get('smoking', ''),
                'allergies': data.get('allergies', ''),
                'chronic_conditions': data.get('medical_conditions') or data.get('chronic_conditions', ''),
                'current_medications': data.get('current_medications') or data.get('medication_reminder', ''),
                'updated_at': datetime.now().isoformat()
            }
            update_data = {k: v for k, v in update_data.items() if v is not None}

            if client:
                try:
                    client.table('profiles').upsert({'id': user_uid, **update_data}).execute()
                except Exception as e:
                    logging.warning(f"Upsert failed, trying update: {e}")
                    try:
                        client.table('profiles').update(update_data).eq('id', user_uid).execute()
                    except Exception as err:
                        logging.error(f"Update failed: {err}")

            profile_data.update(update_data)
            session['profile'] = profile_data
            session.modified = True
            flash("Settings updated successfully!", "success")

            if request.is_json:
                return jsonify({'success': True, 'profile': profile_data, 'message': 'Settings saved successfully'})
            return redirect(url_for('auth.profile'))

        return render_template('settings.html', profile=profile_data)

    except Exception as e:
        logging.error(f"Profile/Settings error: {e}")
        return redirect(url_for('auth.login'))


@auth_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    return profile()


@auth_bp.route('/update_password', methods=['POST'])
@login_required
def update_password():
    try:
        user_uid = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')
        data = request.get_json() if request.is_json else request.form.to_dict()
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')

        if not new_password or len(new_password) < 6:
            msg = 'Password must be at least 6 characters'
            if request.is_json: return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'danger')
            return redirect(url_for('auth.profile'))

        if new_password != confirm_password:
            msg = 'Passwords do not match'
            if request.is_json: return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'danger')
            return redirect(url_for('auth.profile'))

        if supabase:
            try:
                supabase.auth.admin.update_user_by_id(user_uid, {'password': new_password})
            except Exception as e:
                logging.error(f"Supabase admin password update: {e}")

        flash('Password updated successfully!', 'success')
        if request.is_json:
            return jsonify({'success': True, 'message': 'Password updated successfully'})
        return redirect(url_for('auth.profile'))
    except Exception as e:
        logging.error(f"Update password error: {e}")
        return redirect(url_for('auth.profile'))


@auth_bp.route('/export_data', methods=['GET'])
@login_required
def export_data():
    user_uid = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')
    data = {
        "user_id": user_uid,
        "profile": session.get('profile', {}),
        "exported_at": datetime.now().isoformat()
    }
    return jsonify(data)


@auth_bp.route('/delete-account', methods=['GET', 'POST'])
@login_required
def delete_account():
    session.clear()
    flash("Your account and associated session data have been cleared.", "info")
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))


@auth_bp.route('/check-session')
def check_session():
    user = session.get('user')
    if user and user.get('uid'):
        return jsonify({'logged_in': True, 'email': user.get('email')})
    return jsonify({'logged_in': False}), 200


@auth_bp.route('/auth/action', methods=['GET'])
def handle_auth_action():
    return render_template('login.html')


@auth_bp.route('/firebase.js')
def serve_firebase_js():
    return ('console.log("Firebase compatibility stub loaded");', 200, {'Content-Type': 'application/javascript'})
