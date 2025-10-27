import boto3
import json
import uuid
import os
from botocore.exceptions import ClientError, BotoCoreError
from config import Config


class BedrockAgentService:
    def __init__(self):
        self.agent_client = boto3.client(
            'bedrock-agent-runtime',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION
        )
        
        # Configuración de tu agente específico
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
                    completion += chunk['bytes'].decode('utf-8')
                
                elif 'citation' in event:
                    citation = event['citation']
                    citations.append({
                        'generated_response_part': citation.get('generatedResponsePart', {}).get('text', ''),
                        'retrieved_references': citation.get('retrievedReferences', [])
                    })
            
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
            
            spanish_query = f"Responde en español: {query}"
            
            if not retrieval_config:
                retrieval_config = {
                    'vectorSearchConfiguration': {
                        'numberOfResults': 5,
                        'overrideSearchType': 'SEMANTIC'  # or 'SEMANTIC'
                    }
                }
            
            response = self.agent_client.retrieve_and_generate(
                input={
                    'text': prompt
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
            agent_client = boto3.client(
                'bedrock-agent',
                aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
                region_name=Config.AWS_REGION
            )
            
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

# Agente especializado que usa tu agente personalizado
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
        # Primero intentar con el agente completo
        result = self.agent_service.invoke_agent(user_message, session_id)
        
        # Si falla, intentar con RetrieveAndGenerate directo
        if not result['success'] and self.agent_service.knowledge_base_id:
            result = self.agent_service.retrieve_and_generate(user_message)
        
        return result
    
    def get_agent_status(self):
        """Verificar estado del agente"""
        return self.agent_service.get_agent_info()