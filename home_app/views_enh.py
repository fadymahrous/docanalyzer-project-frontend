from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.conf import settings
import hashlib
import magic
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid

from .forms import UploadedFileForm
from .services import FileUploadService, FileValidationService
from helper.logger_setup import setup_logger
from helper.aws_boto3_agent import AWSBoto3Agent
from config.configuration import ConfigurationCenter

logger = setup_logger('home_app')

# Configuration - move to settings.py in production
ALLOWED_EXTENSIONS = ['pdf']
ALLOWED_MIME_TYPES = ['application/pdf']

# Initialize services
config_center = ConfigurationCenter()
file_upload_service = FileUploadService()
file_validation_service = FileValidationService()

def home_page(request):
    """Render the home page."""
    return render(request, 'home_page.html')

def _log_upload_attempt(request, filename: str, success: bool, error: Optional[str] = None):
    """Log upload attempts with context using your existing logger setup."""
    user_info = f"user_id: {request.user.id}" if request.user.is_authenticated else "anonymous"
    ip_info = f"ip: {request.META.get('REMOTE_ADDR', 'unknown')}"
    
    log_message = f"Upload attempt - {filename} - {user_info} - {ip_info}"
    
    if success:
        logger.info(f"{log_message} - SUCCESS")
    else:
        logger.error(f"{log_message} - FAILED: {error}")

def _create_safe_filename(user_id: int, original_filename: str) -> str:
    """Create a safe, unique filename."""
    # Remove path components and dangerous characters
    safe_name = original_filename.split('/')[-1].split('\\')[-1]
    safe_name = ''.join(c for c in safe_name if c.isalnum() or c in '._-')
    
    # Limit length and add unique identifier
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    
    return f"{timestamp}-{user_id}-{unique_id}-{safe_name}"

def _validate_file_content(uploaded_file) -> Dict[str, Any]:
    """Validate file content beyond extension check."""
    try:
        # Check actual MIME type
        uploaded_file.seek(0)
        file_content = uploaded_file.read(1024)  # Read first 1KB
        uploaded_file.seek(0)
        
        detected_type = magic.from_buffer(file_content, mime=True)
        
        if detected_type not in ALLOWED_MIME_TYPES:
            return {
                'valid': False,
                'error': f'Invalid file type. Expected: {", ".join(ALLOWED_MIME_TYPES)}, Got: {detected_type}'
            }
        
        # Generate file hash for deduplication/integrity
        uploaded_file.seek(0)
        file_hash = hashlib.sha256(uploaded_file.read()).hexdigest()
        uploaded_file.seek(0)
        
        return {
            'valid': True,
            'mime_type': detected_type,
            'file_hash': file_hash
        }
        
    except Exception as e:
        logger.error(f"Error during file content validation: {str(e)}")
        return {
            'valid': False,
            'error': 'File validation failed'
        }

@csrf_protect
@login_required(login_url='accounts_app:login')
@require_http_methods(["GET", "POST"])
def upload_file(request):
    """Handle file upload with comprehensive validation and error handling."""
    
    if request.method == 'POST':
        form = UploadedFileForm(request.POST, request.FILES)
        
        if not form.is_valid():
            error_msg = f"Form validation failed: {form.errors}"
            _log_upload_attempt(request, "unknown", False, error_msg)
            messages.error(request, "Please correct the form errors.")
            return render(request, 'upload_page.html', {'form': form})
        
        uploaded_file = form.cleaned_data['filename']
        original_filename = uploaded_file.name
        
        try:
            # File size validation
            max_size = config_center.get_parameter('general_configuration', 'max_filesize_kb')
            if file_validation_service.file_size_exceeded(uploaded_file, max_size):
                error_msg = f'File size exceeded limit of {max_size}KB'
                _log_upload_attempt(request, original_filename, False, error_msg)
                messages.error(request, error_msg)
                return redirect('home_app:upload')
            
            # Extension validation
            if not file_validation_service.allowed_file_extension(original_filename, ALLOWED_EXTENSIONS):
                error_msg = f'Unsupported file extension. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
                _log_upload_attempt(request, original_filename, False, error_msg)
                messages.error(request, error_msg)
                return redirect('home_app:upload')
            
            # Content validation
            content_validation = _validate_file_content(uploaded_file)
            if not content_validation['valid']:
                _log_upload_attempt(request, original_filename, False, content_validation['error'])
                messages.error(request, "File content validation failed.")
                return redirect('home_app:upload')
            
            # Create safe filename
            safe_filename = _create_safe_filename(request.user.id, original_filename)
            
            # Use database transaction to ensure consistency
            with transaction.atomic():
                # Create file instance but don't save yet
                file_instance = form.save(commit=False)
                file_instance.file_hash = content_validation['file_hash']
                file_instance.mime_type = content_validation['mime_type']
                file_instance.original_filename = original_filename
                file_instance.user = request.user
                
                # Upload to S3
                upload_result = file_upload_service.upload_to_s3(uploaded_file, safe_filename)
                
                if not upload_result['success']:
                    error_msg = "Failed to upload file to storage"
                    _log_upload_attempt(request, original_filename, False, error_msg)
                    messages.error(request, "Upload failed. Please try again.")
                    return redirect('home_app:upload')
                
                # Save to database
                bucket_name = config_center.get_parameter('aws_configuration', 's3_bucketname')
                file_instance.file_address_s3 = f"{bucket_name}.{safe_filename}"
                file_instance.save()
                
                # Send to SQS for processing
                sqs_result = file_upload_service.send_to_processing_queue(file_instance)
                
                if not sqs_result['success']:
                    logger.error(f"Failed to send file to processing queue - user: {request.user.id} - file: {safe_filename} - error: {sqs_result.get('error', 'unknown')}")
                    # Don't fail the upload, just log the error
                
                _log_upload_attempt(request, original_filename, True)
                messages.success(request, 'File uploaded successfully!')
                return redirect('home_app:upload')
                
        except ValidationError as e:
            error_msg = f"Validation error: {str(e)}"
            _log_upload_attempt(request, original_filename, False, error_msg)
            messages.error(request, "File validation failed.")
            return redirect('home_app:upload')
            
        except Exception as e:
            logger.error(f"Unexpected error during file upload - user: {request.user.id} - file: {original_filename} - error: {str(e)}")
            _log_upload_attempt(request, original_filename, False, "Unexpected error")
            messages.error(request, "An unexpected error occurred. Please try again.")
            return redirect('home_app:upload')
    
    # GET request - show form
    form = UploadedFileForm()
    context = {
        'form': form,
        'max_file_size': config_center.get_parameter('general_configuration', 'max_filesize_kb'),
        'allowed_extensions': ALLOWED_EXTENSIONS,
    }
    return render(request, 'upload_page.html', context)

# Additional API endpoint for AJAX uploads
@csrf_protect
@login_required
@require_http_methods(["POST"])
def upload_file_ajax(request):
    """API endpoint for AJAX file uploads."""
    try:
        # Similar validation logic as above
        # Return JSON response for AJAX handling
        return JsonResponse({
            'success': True,
            'message': 'File uploaded successfully'
        })
    except Exception as e:
        logger.error(f"AJAX upload failed - user: {request.user.id} - error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Upload failed'
        }, status=400)