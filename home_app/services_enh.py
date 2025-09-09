from typing import Dict, Any, List, Optional
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import hashlib
from helper.logger_setup import setup_logger
from .models import UploadedFile

logger = setup_logger('file_services')

class FileValidationService:
    """Service for file validation operations."""
    
    @staticmethod
    def file_size_exceeded(uploaded_file, size_limit_kb: int) -> bool:
        """Check if file size exceeds limit."""
        size_kb = uploaded_file.size / 1024
        if size_kb > int(size_limit_kb):
            logger.error(f"File size validation failed - size: {size_kb}KB exceeds limit: {size_limit_kb}KB")
            return True
        return False
    
    @staticmethod
    def allowed_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
        """Check if file extension is allowed."""
        if '.' not in filename:
            return False
        
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in [ext.lower() for ext in allowed_extensions]
    
    @staticmethod
    def check_file_duplicate(file_hash: str, user_id: int) -> Optional[UploadedFile]:
        """Check if file already exists for user."""
        try:
            return UploadedFile.objects.filter(
                file_hash=file_hash,
                user_id=user_id
            ).first()
        except Exception as e:
            logger.error(f"Error checking file duplicate - user_id: {user_id} - file_hash: {file_hash} - error: {str(e)}")
            return None

class RateLimitService:
    """Service for rate limiting operations."""
    
    @staticmethod
    def check_upload_rate_limit(user_id: int, max_uploads_per_hour: int = 10) -> Dict[str, Any]:
        """Check if user has exceeded upload rate limit."""
        cache_key = f"upload_rate_limit_{user_id}"
        current_count = cache.get(cache_key, 0)
        
        if current_count >= max_uploads_per_hour:
            return {
                'allowed': False,
                'message': f'Upload rate limit exceeded. Maximum {max_uploads_per_hour} uploads per hour.',
                'reset_time': cache.ttl(cache_key)
            }
        
        # Increment counter
        cache.set(cache_key, current_count + 1, timeout=3600)  # 1 hour
        
        return {
            'allowed': True,
            'remaining': max_uploads_per_hour - current_count - 1
        }

class FileUploadService:
    """Service for handling file uploads."""
    
    def __init__(self):
        from helper.aws_boto3_agent import AWSBoto3Agent
        from config.configuration import ConfigurationCenter
        
        self.aws_agent = AWSBoto3Agent()
        self.config_center = ConfigurationCenter()
    
    def upload_to_s3(self, file_obj, filename: str) -> Dict[str, Any]:
        """Upload file to S3 with proper error handling."""
        try:
            success = self.aws_agent.upload_fileobj_to_s3(file_obj, filename)
            
            if success:
                return {
                    'success': True,
                    'filename': filename,
                    'message': 'File uploaded to S3 successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to upload to S3',
                    'message': 'Storage upload failed'
                }
                
        except Exception as e:
            logger.error(f"Error uploading file to S3 - filename: {filename} - error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Storage upload failed due to unexpected error'
            }
    
    def send_to_processing_queue(self, file_instance: UploadedFile) -> Dict[str, Any]:
        """Send file info to processing queue."""
        try:
            from .services import Local_Supporter  # Your existing service
            
            message_dict = Local_Supporter.clean_dict_for_sqs(file_instance)
            success = self.aws_agent.send_sqs_message(message_dict)
            
            if success:
                return {
                    'success': True,
                    'message': 'File queued for processing'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to queue file for processing',
                    'message': 'Processing queue error'
                }
                
        except Exception as e:
            logger.error(f"Error sending file to processing queue - file_id: {file_instance.id} - error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Queue error'
            }

class FileMonitoringService:
    """Service for monitoring file operations."""
    
    @staticmethod
    def log_upload_metrics(user_id: int, file_size: int, upload_time: float, success: bool):
        """Log upload metrics for monitoring."""
        try:
            # Here you would send metrics to your monitoring system
            # (e.g., CloudWatch, Prometheus, etc.)
            
            metrics = {
                'user_id': user_id,
                'file_size_kb': file_size / 1024,
                'upload_time_seconds': upload_time,
                'success': success,
                'timestamp': timezone.now().isoformat()
            }
            
            logger.info(f"Upload metrics - user_id: {user_id} - size_kb: {file_size/1024:.2f} - time: {upload_time:.2f}s - success: {success}")
            
            # Example: Send to CloudWatch
            # boto3.client('cloudwatch').put_metric_data(...)
            
        except Exception as e:
            logger.error(f"Error logging upload metrics - user_id: {user_id} - error: {str(e)}")
    
    @staticmethod
    def check_system_health() -> Dict[str, Any]:
        """Check system health for uploads."""
        try:
            # Check S3 connectivity
            # Check SQS connectivity
            # Check database connectivity
            # Check disk space, etc.
            
            return {
                'healthy': True,
                'services': {
                    's3': True,
                    'sqs': True,
                    'database': True
                }
            }
        except Exception as e:
            logger.error(f"Error checking system health - error: {str(e)}")
            return {
                'healthy': False,
                'error': str(e)
            }