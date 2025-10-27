from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
import uuid
from datetime import datetime

from app.models import DynamoDB, ChatMessage
from app.services.bedrock_agent_service import BMCCustomAgent

chat_bp = Blueprint('chat', __name__)
db = DynamoDB()
bmc_custom_agent = BMCCustomAgent()

@chat_bp.route('/chat')
@login_required
def chat_ui():
    """Página principal del chat con agente personalizado"""
    chat_history = db.get_user_chat_history(current_user.id)
    
    # Obtener información del agente para mostrar
    agent_info = bmc_custom_agent.get_agent_status()
    
    return render_template('user/chat.html', 
                         chat_history=chat_history,
                         agent_info=agent_info)

@chat_bp.route('/api/chat/send', methods=['POST'])
@login_required
def send_message():
    """API para enviar mensaje al agente personalizado"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'success': False, 'error': 'El mensaje no puede estar vacío'})
        
        # Usar session_id único por usuario para mantener contexto
        session_id = f"user_{current_user.id}"
        
        # Guardar mensaje del usuario
        user_msg = ChatMessage(
            message_id=str(uuid.uuid4()),
            user_id=current_user.id,
            role='user',
            content=user_message
        )
        db.save_chat_message(user_msg)
        
        # Obtener respuesta del agente personalizado
        agent_response = bmc_custom_agent.process_message(user_message, session_id)
        
        if agent_response['success']:
            # Preparar respuesta con citaciones si existen
            response_text = agent_response['response']
            if agent_response.get('has_citations'):
                response_text += "*Basado en la documentación del sistema*"
            
            # Guardar respuesta del agente
            assistant_msg = ChatMessage(
                message_id=str(uuid.uuid4()),
                user_id=current_user.id,
                role='assistant',
                content=response_text,
                model_used="Bedrock Agent"
            )
            db.save_chat_message(assistant_msg)
            
            return jsonify({
                'success': True,
                'response': response_text,
                'message_id': assistant_msg.message_id,
                'timestamp': assistant_msg.timestamp,
                'has_citations': agent_response.get('has_citations', False),
                'citations_count': len(agent_response.get('citations', []))
            })
        else:
            # En caso de error, proporcionar respuesta de fallback
            error_msg = ChatMessage(
                message_id=str(uuid.uuid4()),
                user_id=current_user.id,
                role='assistant',
                content=f"⚠️ Lo siento, hubo un error: {agent_response['error']}. Por favor, intenta de nuevo."
            )
            db.save_chat_message(error_msg)
            
            return jsonify({
                'success': False,
                'error': agent_response['error']
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error procesando mensaje: {str(e)}'})

@chat_bp.route('/api/chat/agent-info', methods=['GET'])
@login_required
def get_agent_info():
    """API para obtener información del agente"""
    try:
        agent_info = bmc_custom_agent.get_agent_status()
        return jsonify(agent_info)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@chat_bp.route('/api/chat/history', methods=['GET'])
@login_required
def get_chat_history():
    """API para obtener historial de chat"""
    try:
        chat_history = db.get_user_chat_history(current_user.id)
        history_data = [
            {
                'id': msg.message_id,
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp,
                'is_user': msg.role == 'user'
            }
            for msg in chat_history
        ]
        return jsonify({'success': True, 'history': history_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@chat_bp.route('/api/chat/clear', methods=['POST'])
@login_required
def clear_chat_history():
    """API para limpiar historial de chat"""
    try:
        if db.clear_user_chat_history(current_user.id):
            return jsonify({'success': True, 'message': 'Historial limpiado'})
        else:
            return jsonify({'success': False, 'error': 'Error limpiando historial'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})