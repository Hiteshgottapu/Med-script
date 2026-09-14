"""
MedScript AI Clinical Chatbot Blueprint
"""

import time
import logging
from datetime import datetime
from flask import Blueprint, request, render_template, session, jsonify, g
from services.auth import login_required
from services.chat import chatbot_service

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/chatbot')
@login_required
def chatbot():
    text = request.args.get('text', '')
    user_id = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')
    chat_history = chatbot_service.get_user_chat_history(user_id)
    return render_template('chatbot.html', initial_text=text, chat_history=chat_history)


@chat_bp.route("/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    history = data.get("history", [])
    conv_id = data.get("conversation_id")
    user_id = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')

    if not user_message:
        return jsonify({
            "success": False,
            "error": "Please enter a message.",
            "response": "Please enter a message."
        }), 400

    reply = chatbot_service.generate_response(user_message, history=history)
    timestamp_iso = datetime.now().isoformat()
    timestamp_display = datetime.now().strftime("%I:%M %p")

    # 1. Save to Supabase
    chatbot_service.save_chat_to_supabase(user_id, user_message, reply)

    # 2. Update session thread
    try:
        if 'chat_conversations' not in session:
            session['chat_conversations'] = []

        convs = session['chat_conversations']
        active_conv = None

        if conv_id:
            for c in convs:
                if c.get('id') == conv_id:
                    active_conv = c
                    break

        if not active_conv:
            conv_id = f"conv_{int(time.time() * 1000)}"
            active_conv = {
                'id': conv_id,
                'title': user_message[:50] + ('...' if len(user_message) > 50 else ''),
                'created_at': timestamp_iso,
                'updated_at': timestamp_iso,
                'messages': []
            }
            convs.insert(0, active_conv)
        else:
            active_conv['updated_at'] = timestamp_iso
            convs.remove(active_conv)
            convs.insert(0, active_conv)

        active_conv['messages'].append({
            'role': 'user',
            'content': user_message,
            'timestamp': timestamp_display
        })
        active_conv['messages'].append({
            'role': 'assistant',
            'content': reply,
            'timestamp': timestamp_display
        })

        session['chat_conversations'] = convs[:20]
        session.modified = True
    except Exception as e:
        logging.error(f"Error managing session conversation: {e}")

    return jsonify({
        "success": True,
        "response": reply,
        "message": reply,
        "timestamp": timestamp_display,
        "timestamp_iso": timestamp_iso,
        "conversation_id": conv_id,
        "user_message": user_message
    })


@chat_bp.route('/api/chat/history', methods=['GET'])
@login_required
def get_chat_history_api():
    user_id = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')
    session_convs = session.get('chat_conversations', [])
    raw_chats = chatbot_service.get_user_chat_history(user_id)

    return jsonify({
        'success': True,
        'conversations': session_convs,
        'raw_history': raw_chats
    })


@chat_bp.route('/api/chat/clear', methods=['POST'])
@login_required
def clear_chat_history():
    user_id = g.user.get('sub') if hasattr(g, 'user') and isinstance(g.user, dict) else session.get('user', {}).get('uid')
    chatbot_service.clear_user_chat_history(user_id)
    session['chat_conversations'] = []
    session.modified = True
    return jsonify({'success': True, 'message': 'Chat history cleared successfully.'})
