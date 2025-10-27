from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
import uuid
from werkzeug.utils import secure_filename

from app.models import DynamoDB, Document
from app.forms import DocumentUploadForm
from app.services.s3_service import S3Service

admin_bp = Blueprint('admin', __name__)
db = DynamoDB()
s3_service = S3Service()

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash('No tienes permisos para acceder a esta página', 'danger')
        return redirect(url_for('main.home'))
    
    users = db.list_users()
    documents = db.get_all_documents()
    
    return render_template('admin/dashboard.html', users=users, documents=documents)

@admin_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_ui():
    if current_user.role != 'admin':
        flash('No tienes permisos para acceder a esta página', 'danger')
        return redirect(url_for('main.home'))
    
    form = DocumentUploadForm()
    
    if form.validate_on_submit():
        try:
            file = form.document.data
            description = form.description.data
            category = form.category.data
            
            # Subir archivo a S3
            upload_result = s3_service.upload_file(
                file=file,
                folder=category,
                user_id=current_user.id
            )
            
            if upload_result['success']:
                # Guardar metadata en DynamoDB
                document = Document(
                    document_id=str(uuid.uuid4()),
                    filename=upload_result['filename'],
                    original_filename=upload_result['original_filename'],
                    s3_key=upload_result['s3_key'],
                    file_url=upload_result['file_url'],
                    file_size=upload_result['file_size'],
                    file_type=file.content_type,
                    user_id=current_user.id,
                    description=description,
                    category=category
                )
                
                if db.save_document(document):
                    flash(f'✅ Documento "{upload_result["original_filename"]}" subido exitosamente', 'success')
                    return redirect(url_for('admin.upload_ui'))
                else:
                    flash('❌ Error guardando metadata del documento', 'danger')
            else:
                flash(f'❌ Error subiendo archivo: {upload_result["error"]}', 'danger')
                
        except Exception as e:
            flash(f'❌ Error inesperado: {str(e)}', 'danger')
    
    # Obtener documentos del usuario actual
    documents = db.get_user_documents(current_user.id)
    
    return render_template('admin/upload.html', form=form, documents=documents)

@admin_bp.route('/users')
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash('No tienes permisos para acceder a esta página', 'danger')
        return redirect(url_for('main.home'))
    
    users = db.list_users()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/documents')
@login_required
def manage_documents():
    if current_user.role != 'admin':
        flash('No tienes permisos para acceder a esta página', 'danger')
        return redirect(url_for('main.home'))
    
    documents = db.get_all_documents()
    return render_template('admin/documents.html', documents=documents)

@admin_bp.route('/delete-document/<document_id>', methods=['POST'])
@login_required
def delete_document(document_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        # Obtener documento para tener la key de S3
        documents_table = db.dynamodb.Table('documents')
        response = documents_table.get_item(Key={'document_id': document_id})
        
        if 'Item' not in response:
            return jsonify({'success': False, 'error': 'Documento no encontrado'}), 404
        
        document_data = response['Item']
        s3_key = document_data['s3_key']
        
        # Eliminar de S3
        s3_result = s3_service.delete_file(s3_key)
        if not s3_result['success']:
            return jsonify({'success': False, 'error': s3_result['error']}), 500
        
        # Eliminar de DynamoDB
        if db.delete_document(document_id):
            return jsonify({'success': True, 'message': 'Documento eliminado'})
        else:
            return jsonify({'success': False, 'error': 'Error eliminando de la base de datos'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500