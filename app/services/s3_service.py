import boto3
import uuid
from botocore.exceptions import ClientError, NoCredentialsError
from config import Config
import os
import time

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION
        )
        self.bucket_name = Config.S3_BUCKET_NAME
        self.ensure_bucket_exists()
        
        self.bedrock_agent_client = boto3.client(
            'bedrock-agent',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION
        )
        
        self.knowledge_base_id = os.environ.get('BEDROCK_KNOWLEDGE_BASE_ID')
        self.ensure_bucket_exists()

    def ensure_bucket_exists(self):
        """Verificar que el bucket S3 existe, si no crearlo"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"Bucket S3 '{self.bucket_name}' existe y está accesible")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket no existe, crearlo
                try:
                    if Config.AWS_REGION == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': Config.AWS_REGION}
                        )
                    print(f"Bucket S3 '{self.bucket_name}' creado exitosamente")
                except ClientError as create_error:
                    print(f"Error creando bucket S3: {create_error}")
            else:
                print(f"Error accediendo a bucket S3: {e}")

    def upload_file(self, file, folder=None, user_id=None):
        """Subir archivo a S3"""
        try:
            # Generar nombre único para el archivo
            file_extension = os.path.splitext(file.filename)[1].lower()
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # Construir la ruta en S3
            s3_path_parts = [Config.S3_UPLOAD_FOLDER]
            if folder:
                s3_path_parts.append(folder)
            if user_id:
                s3_path_parts.append(user_id)
            s3_path_parts.append(unique_filename)
            
            s3_key = "/".join(s3_path_parts)
            
            # Subir archivo
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': file.content_type,
                    'Metadata': {
                        'original_filename': file.filename
                    }
                }
            )
            
            # Generar URL del archivo
            file_url = f"https://{self.bucket_name}.s3.{Config.AWS_REGION}.amazonaws.com/{s3_key}"
            
            print("Archivo subido - La Lambda sincronizará automáticamente la KB")
            time.sleep(2)
            return {
                'success': True,
                's3_key': s3_key,
                'file_url': file_url,
                'filename': unique_filename,
                'original_filename': file.filename,
                'file_size': file.content_length
            }
            
        except NoCredentialsError:
            return {'success': False, 'error': 'Credenciales AWS no configuradas'}
        except ClientError as e:
            return {'success': False, 'error': f"Error de S3: {e}"}
        except Exception as e:
            return {'success': False, 'error': f"Error subiendo archivo: {e}"}

    def delete_file(self, s3_key):
        """Eliminar archivo de S3"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            print("Archivo eliminado - La Lambda sincronizará automáticamente la KB")
            time.sleep(2)
            return {'success': True}
        except ClientError as e:
            return {'success': False, 'error': f"Error eliminando archivo: {e}"}

    def list_files(self, prefix=None):
        """Listar archivos en S3"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix or Config.S3_UPLOAD_FOLDER
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'url': f"https://{self.bucket_name}.s3.{Config.AWS_REGION}.amazonaws.com/{obj['Key']}"
                    })
            
            return {'success': True, 'files': files}
        except ClientError as e:
            return {'success': False, 'error': f"Error listando archivos: {e}"}

    def get_file_url(self, s3_key, expires_in=3600):
        """Generar URL firmada temporal para el archivo"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            return None

    def get_sync_status(self):
        """Obtener solo el último estado de sincronización - Versión corregida"""
        try:
            if not self.knowledge_base_id:
                return {'success': False, 'error': 'Knowledge Base ID no configurado'}
            
            print(f"🔍 Consultando último sync status para KB: {self.knowledge_base_id}")
            
            # Primero obtener todos los data sources
            try:
                data_sources_response = self.bedrock_agent_client.list_data_sources(
                    knowledgeBaseId=self.knowledge_base_id
                )
                data_sources = data_sources_response.get('dataSourceSummaries', [])
                print(f"Data sources encontrados: {len(data_sources)}")
                
            except Exception as ds_error:
                print(f"Error obteniendo data sources: {ds_error}")
                return {'success': False, 'error': f"No se pudieron obtener los data sources: {str(ds_error)}"}
            
            if not data_sources:
                return {
                    'success': True,
                    'last_sync_job': None,
                    'message': 'No hay data sources configurados',
                    'data_sources_count': 0
                }
            
            latest_job = None
            
            # Para cada data source, obtener sus jobs de ingestión
            for data_source in data_sources:
                data_source_id = data_source.get('dataSourceId')
                data_source_name = data_source.get('name', 'N/A')
                data_source_status = data_source.get('status', 'UNKNOWN')
                
                print(f"🔍 Revisando data source: {data_source_name} (Status: {data_source_status})")
                
                if not data_source_id:
                    print(f"Data source sin ID, saltando...")
                    continue
                
                try:
                    # Obtener jobs de ingestión para este data source
                    jobs_response = self.bedrock_agent_client.list_ingestion_jobs(
                        knowledgeBaseId=self.knowledge_base_id,
                        dataSourceId=data_source_id,
                        maxResults=10  # Obtenemos varios para encontrar el más reciente
                    )
                    
                    jobs = jobs_response.get('ingestionJobSummaries', [])
                    print(f"Jobs encontrados para {data_source_name}: {len(jobs)}")
                    
                    for job in jobs:
                        job_status = job.get('status', 'UNKNOWN')
                        started_at = job.get('startedAt')
                        
                        print(f"  - Job {job.get('ingestionJobId', 'N/A')}: {job_status}")
                        
                        # Solo considerar jobs completados o en progreso
                        if job_status in ['COMPLETE', 'IN_PROGRESS', 'STARTING']:
                            job_info = {
                                'job_id': job.get('ingestionJobId', 'N/A'),
                                'status': job_status,
                                'data_source_id': data_source_id,
                                'data_source_name': data_source_name,
                                'started_at': started_at,
                                'last_modified_at': job.get('lastModifiedAt', 'N/A'),
                                'started_at_iso': started_at.isoformat() if started_at else 'N/A'
                            }
                            
                            # Comparar objetos datetime, no strings
                            if latest_job is None:
                                latest_job = job_info
                            elif started_at and latest_job.get('started_at'):
                                # Ambos son objetos datetime, podemos comparar
                                if started_at > latest_job['started_at']:
                                    latest_job = job_info
                            # Si latest_job no tiene started_at válido, usar el nuevo
                            elif started_at and not latest_job.get('started_at'):
                                latest_job = job_info
                            
                except Exception as ds_error:
                    print(f"⚠️ Error obteniendo jobs para {data_source_name}: {ds_error}")
                    continue
            
            if latest_job:
                # Formatear las fechas para la respuesta final
                if latest_job.get('started_at'):
                    latest_job['started_at'] = latest_job['started_at'].isoformat()
                if latest_job.get('last_modified_at') and hasattr(latest_job['last_modified_at'], 'isoformat'):
                    latest_job['last_modified_at'] = latest_job['last_modified_at'].isoformat()
                
                print(f"Último job encontrado: {latest_job['job_id']} - {latest_job['status']}")
                return {
                    'success': True,
                    'last_sync_job': latest_job,
                    'data_sources_count': len(data_sources),
                    'message': 'Última sincronización encontrada'
                }
            else:
                print("No se encontraron jobs de sincronización recientes")
                return {
                    'success': True,
                    'last_sync_job': None,
                    'data_sources_count': len(data_sources),
                    'message': 'No hay trabajos de sincronización recientes'
                }
                
        except Exception as e:
            error_msg = f"Error obteniendo último estado de sync: {str(e)}"
            print(f" {error_msg}")
            return {'success': False, 'error': error_msg}
    
    
    def get_data_source_info(self):
        """Obtener información del data source - Versión segura"""
        try:
            if not self.knowledge_base_id:
                return {'success': False, 'error': 'Knowledge Base ID no configurado'}
            
            response = self.bedrock_agent_client.list_data_sources(
                knowledgeBaseId=self.knowledge_base_id
            )
            
            data_sources = []
            
            for data_source in response['dataSourceSummaries']:
                # Información básica con valores por defecto seguros
                ds_info = {
                    'data_source_id': data_source.get('dataSourceId', 'N/A'),
                    'name': data_source.get('name', 'Sin nombre'),
                    'status': data_source.get('status', 'UNKNOWN'),
                    'description': data_source.get('description', 'Sin descripción'),
                    'type': 'Desconocido',
                    'bucket_name': 'No disponible'
                }
                
                # Configuración de forma segura
                ds_config = data_source.get('dataSourceConfiguration', {})
                
                # Verificar si es S3
                if ds_config.get('type') == 'S3':
                    ds_info['type'] = 'S3'
                    s3_config = ds_config.get('s3Configuration', {})
                    ds_info['bucket_name'] = s3_config.get('bucketName', 'No especificado')
                    ds_info['inclusion_prefixes'] = s3_config.get('inclusionPrefixes', [])
                
                # Información de ingestión segura
                ingestion_summary = data_source.get('ingestionSummary', {})
                ds_info['last_ingestion_status'] = ingestion_summary.get('lastIngestionStatus', 'No sincronizado')
                
                last_ingestion_time = ingestion_summary.get('lastIngestionTime')
                if last_ingestion_time and hasattr(last_ingestion_time, 'strftime'):
                    ds_info['last_ingestion_time'] = last_ingestion_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    ds_info['last_ingestion_time'] = 'Nunca'
                
                data_sources.append(ds_info)
            
            return {
                'success': True,
                'data_sources': data_sources,
                'total_sources': len(data_sources)
            }
            
        except Exception as e:
            return {'success': False, 'error': f"Error obteniendo data sources: {str(e)}"}