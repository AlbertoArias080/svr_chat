import boto3
import uuid
from botocore.exceptions import ClientError, NoCredentialsError
from config import Config
import os

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

    def ensure_bucket_exists(self):
        """Verificar que el bucket S3 existe, si no crearlo"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"✅ Bucket S3 '{self.bucket_name}' existe y está accesible")
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
                    print(f"✅ Bucket S3 '{self.bucket_name}' creado exitosamente")
                except ClientError as create_error:
                    print(f"❌ Error creando bucket S3: {create_error}")
            else:
                print(f"❌ Error accediendo a bucket S3: {e}")

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