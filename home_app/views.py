from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from datetime import datetime, timezone
import uuid

from .forms import UploadedFileForm,lebenslaufMetadataForm
from helper.logger_setup import setup_logger
from helper.aws_boto3_agent import AWSBoto3Agent
from .services import Local_Supporter
from config.configuration import ConfigurationCenter
from django.shortcuts import get_object_or_404

from .models import LebenslaufMetadata, UploadedFile

logger = setup_logger('home_app')

# Consider moving these to settings.py or lazy-loading them inside the view.
ALLOWED_EXTENSIONS = {'pdf'}
_minicenter = ConfigurationCenter()
MAX_FILE_SIZE_KB = int(_minicenter.get_parameter('general_configuration', 'max_filesize_kb') or 0)
BUCKET_NAME = _minicenter.get_parameter('aws_configuration', 's3_bucketname') or ''
_boto3_agent = AWSBoto3Agent()

def home_page(request):
    return render(request, 'home_page.html')

def _exit_error(request, msg):
    messages.error(request, msg)
    return redirect('home_app:upload')

def _exit_success(request, msg):
    messages.success(request, msg)
    return redirect('home_app:upload')

@login_required(login_url='accounts_app:login')
def upload_file(request):
    if request.method == 'POST':
        form = UploadedFileForm(request.POST, request.FILES)
        if not form.is_valid():
            logger.warning("Upload form invalid for user %s: %s", request.user.id, form.errors)
            return _exit_error(request, 'Invalid input. Please check the form and try again.')

        uploaded_django_file = form.cleaned_data['filelocation']  # a Django InMemoryUploadedFile / TemporaryUploadedFile

        # Size check (bytes vs KB)
        max_bytes = MAX_FILE_SIZE_KB * 1024
        if max_bytes and uploaded_django_file.size > max_bytes:
            return _exit_error(request, f'File size exceeded {MAX_FILE_SIZE_KB} KB.')

        # Extension check (case-insensitive)
        if not Local_Supporter.allowed_file_extention(uploaded_django_file.name, ALLOWED_EXTENSIONS):
            return _exit_error(request, f'Unsupported file extension. Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}')

        # Optional: simple MIME/content-type check (server-provided; not foolproof)
        if not uploaded_django_file.content_type or 'pdf' not in uploaded_django_file.content_type.lower():
            logger.info("Content-Type check failed: %s", uploaded_django_file.content_type)
            return _exit_error(request, 'Unsupported file type. Only PDF is allowed.')

        # Build a safe, unique S3 key
        now_part = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        filename=f"{now_part}-{uuid.uuid4().hex}-{uploaded_django_file.name}"
        file_key = f"uploads/user-{request.user.id}/{filename}"

        # Upload to S3 first (so DB doesn’t point to missing objects if upload fails)
        try:
            uploaded = _boto3_agent.upload_fileobj_to_s3(uploaded_django_file, file_key)  # assume this uses BUCKET_NAME internally or accepts bucket separately
        except Exception as e:
            logger.exception("S3 upload error for user %s, key %s: %s", request.user.id, file_key, e)
            return _exit_error(request, 'Internal error during upload.')

        if not uploaded:
            logger.error("S3 upload returned falsy for user %s, key %s", request.user.id, file_key)
            return _exit_error(request, 'Internal error during upload.')

        # Persist + SQS (atomic transaction for DB; decide policy if SQS fails)
        try:
            with transaction.atomic():
                instance = form.save(commit=False)
                # Store bucket & key separately; don’t mash them with a dot
                instance.file_address_key = file_key
                instance.save()

                payload = Local_Supporter.clean_dict_for_sqs(instance)
                msg_id = _boto3_agent.send_sqs_message(payload)
                if not msg_id:
                    # Decide whether to fail or just log. Here we fail so the user can retry.
                    logger.error("SQS send failed for user %s; payload=%s", request.user.id, payload)
                    raise RuntimeError("SQS send failed")
        except Exception as e:
            logger.exception("DB/SQS failure after S3 upload for user %s, key %s: %s", request.user.id, file_key, e)
            # RollBack the S3 upload if DB/SQS fails
            if not _boto3_agent.delete_fileobj_from_s3(file_key=file_key):
                logger.error("Failed to delete S3 object %s after DB/SQS failure for user %s, This is Incosistency Red flag", file_key, request.user.id)
            return _exit_error(request, 'Internal error finalizing upload.')

        return _exit_success(request, 'File uploaded successfully.')

    # GET
    form = UploadedFileForm()
    return render(request, 'upload_page.html', {'form': form})

@login_required(login_url='accounts_app:login')
def my_documents(request):
    if request.method=="POST":
        if request.POST.get('action') == 'delete':
            try:
                # Get the file key from the POST data
                file_key = request.POST.get('file_key')
                if not file_key:
                    messages.error(request, 'File key is missing.')
                    logger.error("Delete action called without file_key for user %s", request.user.id)
                    return redirect('home_app:mydocuments')

                # Fetch the UploadedFile instance
                instance = get_object_or_404(UploadedFile, file_address_key=file_key, user=request.user)
                
                # Delete the S3 object first
                if not _boto3_agent.delete_fileobj_from_s3(file_key=file_key):
                    messages.error(request, 'Failed to delete the document from S3.')
                    return redirect('home_app:mydocuments')
                instance.delete()
            except Exception as e:
                logger.exception("Error deleting document for user %s, file_key %s: %s", request.user.id, file_key, e)
                messages.error(request, 'An error occurred while deleting the document.')
                return redirect('home_app:mydocuments')
            messages.success(request, 'Document deleted successfully.')
        return redirect('home_app:mydocuments')
    documents = LebenslaufMetadata.objects.filter(user=request.user).order_by('-file_key')
    return render(request, 'my_documents.html', {'documents': documents})

@login_required(login_url='accounts_app:login')
def editdocument(request, file_key_passed):
    try:
        instance_to_edit= get_object_or_404(LebenslaufMetadata, user=request.user, file_key=file_key_passed)
    except LebenslaufMetadata.DoesNotExist:
        messages.error(request, 'Document not found or you do not have permission to edit it.')
        logger.error("Edit action called with invalid file_key %s for user %s", file_key_passed, request.user.id)
        return redirect('home_app:mydocuments')

    if request.method == 'POST':
        form = lebenslaufMetadataForm(request.POST,instance=instance_to_edit)
        if form.is_valid():
            instance_to_edit = form.save(commit=True)
            return redirect('home_app:mydocuments')
        else:
            logger.warning("Edit form invalid for user %s, file_key %s: %s", request.user.id, file_key_passed, form.errors)
            messages.error(request, 'Invalid input. Please check the form and try again.')
            return render(request, 'edit_document.html', {'form': form, 'file_key_passed': file_key_passed})
    form= lebenslaufMetadataForm(instance=instance_to_edit)
    return render(request, 'edit_document.html', {'form': form, 'file_key_passed': file_key_passed})
