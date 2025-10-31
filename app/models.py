import boto3
from flask_login import UserMixin
from botocore.exceptions import ClientError
import uuid
from datetime import datetime
from config import Config

class User(UserMixin):
    def __init__(self, user_id, email, password, role='user', created_at=None):
        self.id = user_id
        self.email = email
        self.password = password
        self.role = role
        self.created_at = created_at or datetime.utcnow().isoformat()

    def to_dict(self):
        return {
            'user_id': self.id,
            'email': self.email,
            'password': self.password,
            'role': self.role,
            'created_at': self.created_at
        }

    @staticmethod
    def from_dict(data):
        return User(
            user_id=data.get('user_id'),
            email=data.get('email'),
            password=data.get('password'),
            role=data.get('role', 'user'),
            created_at=data.get('created_at')
        )

class DynamoDB:
    def __init__(self):
        self.table_name = 'users'
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION
        )
        self.table = self.dynamodb.Table(self.table_name)
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        try:
            # Intentar describir la tabla para ver si existe
            self.table.table_status
            print(f"Tabla DynamoDB '{self.table_name}' existe y está accesible")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"Creando tabla DynamoDB '{self.table_name}'...")
                self._create_table()
            else:
                raise e

#Tablas y gestion de usuarios

    def _create_table(self):
        try:
            table = self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {
                        'AttributeName': 'user_id',
                        'KeyType': 'HASH'
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'user_id',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'email',
                        'AttributeType': 'S'
                    }
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'email-index',
                        'KeySchema': [
                            {
                                'AttributeName': 'email',
                                'KeyType': 'HASH'
                            }
                        ],
                        'Projection': {
                            'ProjectionType': 'ALL'
                        },
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            table.wait_until_exists()
            print(f"Tabla '{self.table_name}' creada exitosamente")
        except ClientError as e:
            print(f"Error creando tabla: {e}")
            raise e

    def create_user(self, user):
        user_data = user.to_dict()
        try:
            self.table.put_item(
                Item=user_data,
                ConditionExpression='attribute_not_exists(email)'
            )
            print(f"Usuario {user.email} creado exitosamente")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                print(f"Usuario {user.email} ya existe")
                return False
            print(f"Error creando usuario: {e}")
            return False

    def get_user_by_email(self, email):
        try:
            response = self.table.query(
                IndexName='email-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('email').eq(email)
            )
            if response['Items']:
                print(f"Usuario {email} encontrado")
                return User.from_dict(response['Items'][0])
            print(f"Usuario {email} no encontrado")
            return None
        except ClientError as e:
            print(f"Error buscando usuario por email: {e}")
            return None

    def get_user_by_id(self, user_id):
        try:
            response = self.table.get_item(Key={'user_id': user_id})
            if 'Item' in response:
                return User.from_dict(response['Item'])
            return None
        except ClientError as e:
            print(f"Error buscando usuario por ID: {e}")
            return None

    def list_users(self):
        try:
            response = self.table.scan()
            return [User.from_dict(item) for item in response.get('Items', [])]
        except ClientError as e:
            print(f"Error listando usuarios: {e}")
            return []

#Tablas y gestion de documentos

    def create_documents_table(self):
        """Crear tabla para documentos si no existe"""
        try:
            table = self.dynamodb.create_table(
                TableName='documents',
                KeySchema=[
                    {
                        'AttributeName': 'document_id',
                        'KeyType': 'HASH'
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'document_id',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'user_id',
                        'AttributeType': 'S'
                    }
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'user-id-index',
                        'KeySchema': [
                            {
                                'AttributeName': 'user_id',
                                'KeyType': 'HASH'
                            }
                        ],
                        'Projection': {
                            'ProjectionType': 'ALL'
                        },
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            table.wait_until_exists()
            print("Tabla 'documents' creada exitosamente")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                print("Tabla 'documents' ya existe")
            else:
                print(f"Error creando tabla documents: {e}")

    def save_document(self, document):
        """Guardar documento en DynamoDB"""
        try:
            self.dynamodb.Table('documents').put_item(Item=document.to_dict())
            return True
        except ClientError as e:
            print(f"Error guardando documento: {e}")
            return False

    def get_user_documents(self, user_id):
        """Obtener documentos de un usuario"""
        try:
            response = self.dynamodb.Table('documents').query(
                IndexName='user-id-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id)
            )
            return [Document.from_dict(item) for item in response.get('Items', [])]
        except ClientError as e:
            print(f"Error obteniendo documentos: {e}")
            return []

    def get_all_documents(self):
        """Obtener todos los documentos (para admin)"""
        try:
            response = self.dynamodb.Table('documents').scan()
            return [Document.from_dict(item) for item in response.get('Items', [])]
        except ClientError as e:
            print(f"Error obteniendo todos los documentos: {e}")
            return []

    def delete_document(self, document_id):
        """Eliminar documento de DynamoDB"""
        try:
            self.dynamodb.Table('documents').delete_item(Key={'document_id': document_id})
            return True
        except ClientError as e:
            print(f"Error eliminando documento: {e}")
            return False

#Tablas y gestion de chat

    def create_chat_table(self):
        """Crear tabla para historial de chat si no existe"""
        try:
            table = self.dynamodb.create_table(
                TableName='chat_messages',
                KeySchema=[
                    {
                        'AttributeName': 'message_id',
                        'KeyType': 'HASH'
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'message_id',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'user_id',
                        'AttributeType': 'S'
                    }
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'user-id-index',
                        'KeySchema': [
                            {
                                'AttributeName': 'user_id',
                                'KeyType': 'HASH'
                            }
                        ],
                        'Projection': {
                            'ProjectionType': 'ALL'
                        },
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            table.wait_until_exists()
            print("Tabla 'chat_messages' creada exitosamente")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                print("Tabla 'chat_messages' ya existe")
            else:
                print(f"Error creando tabla chat_messages: {e}")

    def save_chat_message(self, message):
        """Guardar mensaje de chat en DynamoDB"""
        try:
            self.dynamodb.Table('chat_messages').put_item(Item=message.to_dict())
            return True
        except ClientError as e:
            print(f"Error guardando mensaje de chat: {e}")
            return False

    def get_user_chat_history(self, user_id, limit=50):
        """Obtener historial de chat de un usuario"""
        try:
            response = self.dynamodb.Table('chat_messages').query(
                IndexName='user-id-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id),
                Limit=limit,
                ScanIndexForward=False  # Orden descendente (más recientes primero)
            )
            messages = [ChatMessage.from_dict(item) for item in response.get('Items', [])]
            # Ordenar por timestamp (más antiguo primero para conversación)
            messages.sort(key=lambda x: x.timestamp)
            return messages
        except ClientError as e:
            print(f"Error obteniendo historial de chat: {e}")
            return []

    def clear_user_chat_history(self, user_id):
        """Eliminar historial de chat de un usuario"""
        try:
            messages = self.get_user_chat_history(user_id)
            with self.dynamodb.Table('chat_messages').batch_writer() as batch:
                for message in messages:
                    batch.delete_item(Key={'message_id': message.message_id})
            return True
        except ClientError as e:
            print(f"Error eliminando historial de chat: {e}")
            return False
        
class Document:
    def __init__(self, document_id, filename, original_filename, s3_key, file_url, 
                 file_size, file_type, user_id, description=None, category=None, 
                 created_at=None):
        self.document_id = document_id
        self.filename = filename
        self.original_filename = original_filename
        self.s3_key = s3_key
        self.file_url = file_url
        self.file_size = file_size
        self.file_type = file_type
        self.user_id = user_id
        self.description = description
        self.category = category
        self.created_at = created_at or datetime.utcnow().isoformat()

    def to_dict(self):
        return {
            'document_id': self.document_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            's3_key': self.s3_key,
            'file_url': self.file_url,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'user_id': self.user_id,
            'description': self.description,
            'category': self.category,
            'created_at': self.created_at
        }

    @staticmethod
    def from_dict(data):
        return Document(
            document_id=data.get('document_id'),
            filename=data.get('filename'),
            original_filename=data.get('original_filename'),
            s3_key=data.get('s3_key'),
            file_url=data.get('file_url'),
            file_size=data.get('file_size'),
            file_type=data.get('file_type'),
            user_id=data.get('user_id'),
            description=data.get('description'),
            category=data.get('category'),
            created_at=data.get('created_at')
        )

class ChatMessage:
    def __init__(self, message_id, user_id, role, content, timestamp=None, model_used=None):
        self.message_id = message_id
        self.user_id = user_id
        self.role = role  # 'user' or 'assistant'
        self.content = content
        self.timestamp = timestamp or datetime.utcnow().isoformat()
        self.model_used = model_used

    def to_dict(self):
        return {
            'message_id': self.message_id,
            'user_id': self.user_id,
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp,
            'model_used': self.model_used
        }

    @staticmethod
    def from_dict(data):
        return ChatMessage(
            message_id=data.get('message_id'),
            user_id=data.get('user_id'),
            role=data.get('role'),
            content=data.get('content'),
            timestamp=data.get('timestamp'),
            model_used=data.get('model_used')
        )


