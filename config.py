import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # AWS Credentials
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION') or 'us-east-1'
    
    # S3 Configuration
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME') or 'bmc-documents'
    S3_UPLOAD_FOLDER = 'uploads'
    
    # Bedrock Agent Configuration
    BEDROCK_AGENT_ID = os.environ.get('BEDROCK_AGENT_ID')
    BEDROCK_AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID') or 'TSTALIASID'
    BEDROCK_KNOWLEDGE_BASE_ID = os.environ.get('BEDROCK_KNOWLEDGE_BASE_ID')
    
    # Validar credenciales
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        raise ValueError("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in environment variables")