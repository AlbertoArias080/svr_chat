import boto3
import json
import uuid
import os
import logging
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config as BotoCoreConfig
from config import Config

logger = logging.getLogger(__name__)


class BedrockAgentService:
    def __init__(self):
        
        self.agent_client = boto3.client(
            'bedrock-agent-runtime',
            config=BotoCoreConfig(
                read_timeout=120,
                connect_timeout=10,
                retries={'max_attempts': 2}
            )
        )
        
        # Configuración del agente específico
        self.agent_id = os.environ.get('BEDROCK_AGENT_ID')
        self.agent_alias_id = os.environ.get('BEDROCK_AGENT_ALIAS_ID') or 'TSTALIASID'
        self.knowledge_base_id = os.environ.get('BEDROCK_KNOWLEDGE_BASE_ID')
        
        if not self.agent_id:
            raise ValueError("BEDROCK_AGENT_ID must be set in environment variables")

    def invoke_agent(self, prompt, session_id=None):
        """
        Invocar tu agente personalizado de Bedrock con Knowledge Base
        """
        try:
            if not session_id:
                session_id = str(uuid.uuid4())
            
            # Invocar el agente
            response = self.agent_client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=prompt
            )
            
            # Procesar la respuesta stream
            completion = ""
            citations = []

            for event in response['completion']:
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        completion += chunk['bytes'].decode('utf-8')
                    # Las citas vienen dentro del chunk, no como evento separado
                    if 'attribution' in chunk:
                        for citation in chunk['attribution'].get('citations', []):
                            citations.append({
                                'generated_response_part': citation.get('generatedResponsePart', {}).get('textResponsePart', {}).get('text', ''),
                                'retrieved_references': citation.get('retrievedReferences', [])
                            })

                elif 'returnControl' in event:
                    # El agente solicitó ejecutar un action group
                    rc = event['returnControl']
                    invocation_id = rc.get('invocationId', '')
                    inputs = rc.get('invocationInputs', [])
                    logger.warning(f"Agent returnControl — invocationId={invocation_id}, inputs={inputs}")
                    return {
                        'success': False,
                        'error': 'El agente requiere ejecutar una acción que no está configurada en la aplicación. Contacta al administrador.'
                    }

                elif 'trace' in event:
                    pass  # Solo diagnóstico, no afecta la respuesta

                elif 'internalServerException' in event:
                    msg = event['internalServerException'].get('message', 'Error interno')
                    logger.error(f"Bedrock internalServerException: {msg}")
                    return {'success': False, 'error': f'Error interno de Bedrock: {msg}'}

                elif 'throttlingException' in event:
                    logger.warning("Bedrock throttlingException")
                    return {'success': False, 'error': 'Límite de solicitudes alcanzado. Intenta en unos segundos.'}

                elif 'validationException' in event:
                    msg = event['validationException'].get('message', 'Error de validación')
                    return {'success': False, 'error': f'Error de validación: {msg}'}

                else:
                    logger.debug(f"Evento desconocido del agente: {list(event.keys())}")

            logger.info(f"Agente respondió — sesión={session_id}, chars={len(completion)}, citas={len(citations)}")

            if not completion:
                logger.warning(f"El agente devolvió una respuesta vacía — sesión={session_id}")
                return {'success': False, 'error': 'El agente no generó una respuesta. Intenta de nuevo.'}

            return {
                'success': True,
                'response': completion.strip(),
                'session_id': session_id,
                'citations': citations,
                'has_citations': len(citations) > 0
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                return {'success': False, 'error': 'Acceso denegado al agente Bedrock. Verifica los permisos IAM.'}
            elif error_code == 'ResourceNotFoundException':
                return {'success': False, 'error': f'Agente {self.agent_id} no encontrado.'}
            else:
                return {'success': False, 'error': f'Error del agente Bedrock: {str(e)}'}
                
        except BotoCoreError as e:
            return {'success': False, 'error': f'Error de conexión AWS: {str(e)}'}
            
        except Exception as e:
            return {'success': False, 'error': f'Error inesperado: {str(e)}'}

    def retrieve_and_generate(self, query, prompt, retrieval_config=None):
        """
        Usar RetrieveAndGenerate directamente con la Knowledge Base
        """
        try:
            
            if not retrieval_config:
                retrieval_config = {
                    'vectorSearchConfiguration': {
                        'numberOfResults': 5,
                        'overrideSearchType': 'SEMANTIC'
                    }
                }

            spanish_prompt = f"Por favor responde siempre en español. {prompt}"

            response = self.agent_client.retrieve_and_generate(
                input={
                    'text': spanish_prompt
                },
                retrieveAndGenerateConfiguration={
                    'type': 'KNOWLEDGE_BASE',
                    'knowledgeBaseConfiguration': {
                        'knowledgeBaseId': self.knowledge_base_id,
                        'modelArn': f'arn:aws:bedrock:{Config.AWS_REGION}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0',
                        'retrievalConfiguration': retrieval_config
                    }
                }
            )
            
            citations = []
            for citation in response.get('citations', []):
                citations.append({
                    'retrieved_references': citation.get('retrievedReferences', [])
                })
            
            return {
                'success': True,
                'response': response['output']['text'],
                'citations': citations,
                'has_citations': len(citations) > 0
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Error en RetrieveAndGenerate: {str(e)}'}
        
    def clean_response(self, text):
        """Limpia completamente la respuesta de caracteres escape"""
        if not text:
            return ""
        
        # Cadena de limpieza progresiva
        cleaned = text
        
        # Primero: eliminar todas las barras invertidas de escape
        while '\\\\n' in cleaned:
            cleaned = cleaned.replace('\\\\n', '\n')
        
        while '\\n' in cleaned:
            cleaned = cleaned.replace('\\n', '\n')
        
        # Limpiar espacios múltiples y caracteres extraños
        cleaned = ' '.join(cleaned.split())
        
        # Convertir saltos de línea en <br> para HTML
        cleaned = cleaned.replace('\n', '<br>')
        
        return cleaned.strip()

    def get_agent_info(self):
        """
        Obtener información sobre el agente configurado
        """
        try:
            
            agent_client = boto3.client('bedrock-agent')
            
            response = agent_client.get_agent(agentId=self.agent_id)
            agent_alias = agent_client.get_agent_alias(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id
            )
            
            return {
                'success': True,
                'agent_name': response['agent']['agentName'],
                'agent_status': response['agent']['agentStatus'],
                'agent_alias': agent_alias['agentAlias']['agentAliasName'],
                'knowledge_base_id': response['agent'].get('knowledgeBases', [{}])[0].get('knowledgeBaseId', 'N/A')
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Error obteniendo info del agente: {str(e)}'}

# Agente especializado que usa el agente personalizado
class BMCCustomAgent:
    def __init__(self):
        self.agent_service = BedrockAgentService()
        self.system_context = """
        Eres un agente especializado para BMC (Bolsa Mercantil de Colombia) 
        que tiene acceso a una Knowledge Base con documentación específica de procesos disciplinarios.
        
        Usa la información de la Knowledge Base para proporcionar respuestas 
        precisas y actualizadas sobre:
        - Funcionalidades del sistema BMC
        - Procedimientos y manuales
        - Configuraciones específicas
        - Documentación técnica
        
        Da respuestas en español
        
        Cuando cites información de la Knowledge Base, menciona que estás 
        usando la documentación oficial del sistema.
        """
    
    def process_message(self, user_message, session_id=None):
        """
        Procesar mensaje usando tu agente personalizado con Knowledge Base
        """
        prompt = (
            "Responde SIEMPRE en español. "
            "Basa tu respuesta en la información de los documentos de la Knowledge Base. "
            "Si después de consultar los documentos no encuentras información relevante, indícalo brevemente. "
            "No inventes datos como números, fechas o nombres que no estén en los documentos. "
            f"Pregunta: {user_message}"
        )
        result = self.agent_service.invoke_agent(prompt, session_id)
        
        # Si falla, intentar con RetrieveAndGenerate directo
        #if not result['success'] and self.agent_service.knowledge_base_id:
        #    result = self.agent_service.retrieve_and_generate(user_message)
        
        return result
    
    def get_agent_status(self):
        """Verificar estado del agente"""
        return self.agent_service.get_agent_info()