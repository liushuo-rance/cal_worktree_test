"""
AI 助手路由
提供对话页面和 SSE 流式响应
"""

import json
import sys
import os

from flask import Blueprint, render_template, request, session, jsonify, Response, stream_with_context

from web.utils import get_db

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from services.assistant_service import get_assistant_service

bp = Blueprint('assistant', __name__, url_prefix='/assistant')


@bp.route('/')
def index():
    """AI 助手页面"""
    messages = session.get('assistant_chat', [])
    return render_template('assistant.html', messages=messages)


@bp.route('/stream', methods=['POST'])
def stream():
    """SSE 流式对话接口"""
    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()

    if not user_message:
        def _error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': '消息不能为空'})}\n\n"
        return Response(_error_stream(), mimetype='text/event-stream')

    # 初始化 session 中的消息历史
    messages = session.get('assistant_chat', [])
    messages.append({'role': 'user', 'content': user_message})
    session['assistant_chat'] = messages
    session.modified = True
    from flask import current_app
    current_app.session_interface.save_session(
        current_app, session, current_app.response_class()
    )

    db_conn = get_db()
    service = get_assistant_service()

    def event_stream():
        nonlocal messages
        try:
            for event in service.chat_stream(messages, db_conn):
                event_type = event.get('type')

                # 如果返回了完整消息列表，更新 session 并显式保存
                if event_type == 'done' and 'messages' in event:
                    messages = event['messages']
                    session['assistant_chat'] = messages
                    session.modified = True
                    from flask import current_app
                    current_app.session_interface.save_session(
                        current_app, session, current_app.response_class()
                    )

                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'流式响应异常: {str(e)}'})}\n\n"
        finally:
            db_conn.close()

    return Response(stream_with_context(event_stream()), mimetype='text/event-stream')


@bp.route('/clear', methods=['POST'])
def clear():
    """清空对话历史"""
    session.pop('assistant_chat', None)
    session.modified = True
    from flask import current_app
    current_app.session_interface.save_session(
        current_app, session, current_app.response_class()
    )
    return jsonify({'success': True})
