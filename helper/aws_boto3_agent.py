import io
import boto3
from botocore.config import Config

from botocore.exceptions import ClientError
from typing import Dict, Optional, Tuple
from json import dumps, loads, JSONDecodeError

from helper.logger_setup import setup_logger
from config.configuration import ConfigurationCenter

logger = setup_logger("helper")

# -------------------------
# S3 responsibilities only
# -------------------------
class S3Agent:
    def __init__(self, boto3_config:Config, bucket_name: str,region:str=None) -> None:
        self.bucket_name = bucket_name
        if region is None:
            logger.error("config.region_missing")
            raise ValueError("AWS region missing.")
        self.region = region
        try:
            self.s3 = boto3.client("s3", config=boto3_config)
        except Exception as e:
            logger.exception("s3.client_create_failed region=%s", self.region)
            raise RuntimeError("Failed to create S3 client.") from e

    def _ensure_bucket_exists(self, bucket_name: Optional[str] = None) -> bool:
        bucket = bucket_name or self.bucket_name

        try:
            self.s3.head_bucket(Bucket=bucket)
            logger.info("s3.bucket_exists bucket=%s", bucket)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchBucket"):
                logger.info("s3.bucket_missing_creating bucket=%s region=%s", bucket, self.region)
                try:
                    params = {"Bucket": bucket}
                    # Create with region when not us-east-1
                    if self.region != "us-east-1":
                        params["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
                    self.s3.create_bucket(**params)
                    logger.info("s3.bucket_created bucket=%s region=%s", bucket, self.region)
                    return True
                except Exception as ce:
                    logger.exception("s3.bucket_create_failed bucket=%s region=%s", bucket, self.region)
                    return False
            elif code in ("403", "AccessDenied"):
                logger.error("s3.bucket_access_denied bucket=%s", bucket)
                return False
            elif code in ("301", "PermanentRedirect"):
                logger.error("s3.bucket_wrong_region bucket=%s expected_region=%s", bucket, self.region)
                return False
            else:
                logger.exception("s3.bucket_head_error bucket=%s", bucket)
                return False
        except Exception:
            logger.exception("s3.bucket_head_unexpected bucket=%s", bucket)
            return False

    # keep interface: upload_fileobj_to_s3(file_obj, object_name, bucket=None) -> bool
    def upload_fileobj_to_s3(self, file_obj, object_name: str, bucket: Optional[str] = None) -> bool:
        bucket = bucket or self.bucket_name
        if not self._ensure_bucket_exists(bucket):
            logger.error("s3.upload_abort_bucket_unavailable bucket=%s key=%s", bucket, object_name)
            return False
        try:
            file_obj.seek(0)
            file_like = io.BytesIO(file_obj.read())
            self.s3.upload_fileobj(file_like, bucket, object_name)
            logger.info("s3.upload_ok bucket=%s key=%s", bucket, object_name)
            file_obj.seek(0)
            return True
        except Exception:
            logger.exception("s3.upload_failed bucket=%s key=%s", bucket, object_name)
            return False

    def delete_fileobj_from_s3(self, file_key,bucket: Optional[str] = None) -> bool:
        bucket = bucket or self.bucket_name
        if not self._ensure_bucket_exists(bucket):
            logger.error(f"Cannot proceed with deletion - bucket {bucket} is not available")
            return False
        try:
            self.s3.delete_object(Bucket=bucket, Key =file_key)
            logger.info(f"Successfully deleted {file_key} from {bucket}")
            return True
        except Exception as e:
            logger.error(f"Error deleted {file_key} from {bucket} on S3: {e}")
            return False

    # keep interface: get_object_from_s3(object_name, bucket=None) -> Optional[bytes]
    def get_object_from_s3(self, object_name: str, bucket: Optional[str] = None) -> Optional[bytes]:
        bucket = bucket or self.bucket_name
        if not self._ensure_bucket_exists(bucket):
            logger.error("s3.get_abort_bucket_unavailable bucket=%s key=%s", bucket, object_name)
            return None

        try:
            resp = self.s3.get_object(Bucket=bucket, Key=object_name)
            blob = resp["Body"].read()
            logger.info("s3.get_ok bucket=%s key=%s size=%s", bucket, object_name, len(blob))
            return blob
        except self.s3.exceptions.NoSuchKey:
            logger.error("s3.get_no_such_key bucket=%s key=%s", bucket, object_name)
            return None
        except Exception:
            logger.exception("s3.get_failed bucket=%s key=%s", bucket, object_name)
            return None


# --------------------------
# SQS responsibilities only
# --------------------------
class SQSAgent:
    def __init__(self, boto3_config:Config, queue_name: str,region:str=None) -> None:
        self.queue_name = queue_name
        if region is None:
            logger.error("config.region_missing")
            raise ValueError("AWS region missing.")
        self.region = region

        try:
            self.sqs = boto3.client("sqs", config=boto3_config)
        except Exception:
            logger.exception("sqs.client_create_failed region=%s", self.region)
            raise RuntimeError("Failed to create SQS client.")

        self.queue_url = self._resolve_queue_url()
        if not self.queue_url:
            logger.error("sqs.queue_url_resolve_failed queue_name=%s", self.queue_name)
            raise RuntimeError("Cannot resolve SQS queue URL.")

    def _create_queue(self) -> Optional[str]:
        try:
            resp = self.sqs.create_queue(
                QueueName=self.queue_name,
                tags={"source": "Created_by_Boto3_Agent"},
            )
            url = resp.get("QueueUrl")
            if url:
                logger.info("sqs.queue_created queue_name=%s url=%s", self.queue_name, url)
                return url
        except Exception:
            logger.exception("sqs.queue_create_failed queue_name=%s", self.queue_name)
        return None

    def _resolve_queue_url(self) -> Optional[str]:
        try:
            resp = self.sqs.get_queue_url(QueueName=self.queue_name)
            url = resp.get("QueueUrl")
            logger.info("sqs.queue_url_resolved queue_name=%s url=%s", self.queue_name, url)
            return url
        except self.sqs.exceptions.QueueDoesNotExist:
            logger.warning("sqs.queue_missing_creating queue_name=%s", self.queue_name)
            return self._create_queue()
        except Exception:
            logger.exception("sqs.get_queue_url_failed queue_name=%s", self.queue_name)
            return None

    # keep interface: send_sqs_message(message_content: Dict) -> Optional[str]
    def send_sqs_message(self, message_content: Dict) -> Optional[str]:
        try:
            body = dumps(message_content, ensure_ascii=False, separators=(",", ":"))
            resp = self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=body,
                DelaySeconds=3,
            )
            message_id = resp.get("MessageId")
            if message_id:
                logger.info("sqs.send_ok queue_url=%s message_id=%s", self.queue_url, message_id)
                return message_id
            logger.error("sqs.send_missing_message_id queue_url=%s", self.queue_url)
            return None
        except Exception:
            logger.exception("sqs.send_failed queue_url=%s", self.queue_url)
            return None

    # keep interface: receive_sqs_message() -> Tuple[Optional[str], Optional[Dict]]
    def receive_sqs_message(self) -> Tuple[Optional[str], Optional[Dict]]:
        try:
            resp = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=1,
                VisibilityTimeout=30,
            )
            messages = resp.get("Messages", [])

            if not messages:
                logger.info("sqs.receive_empty queue_url=%s", self.queue_url)
                return None, None

            msg = messages[0]
            receipt = msg.get("ReceiptHandle")
            body_raw = msg.get("Body")

            if not receipt or body_raw is None:
                logger.error("sqs.receive_missing_fields queue_url=%s", self.queue_url)
                return None, None

            try:
                body = loads(body_raw)
            except (TypeError, JSONDecodeError):
                logger.exception("sqs.receive_json_decode_failed queue_url=%s body_preview=%s", self.queue_url, str(body_raw)[:200])
                # Return receipt so the caller can delete/skip if desired
                return receipt, None

            logger.info("sqs.receive_ok queue_url=%s", self.queue_url)
            return receipt, body

        except Exception:
            logger.exception("sqs.receive_failed queue_url=%s", self.queue_url)
            return None, None

    # keep interface: delete_sqs_message(receipt: str) -> bool
    def delete_sqs_message(self, receipt: str) -> bool:
        try:
            resp = self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)
            status = resp.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 200:
                logger.info("sqs.delete_ok queue_url=%s", self.queue_url)
                return True
            logger.error("sqs.delete_unexpected_status queue_url=%s status=%s", self.queue_url, status)
            return False
        except Exception:
            logger.exception("sqs.delete_failed queue_url=%s", self.queue_url)
            return False



# --------------------------
# Bedrock responsibilities
# --------------------------
class BedrockAgent:
    def __init__(self, boto3_config:Config, provider: str = None,region:str=None) -> None:
        if region is None:
            logger.error("config.region_missing")
            raise ValueError("AWS region missing.")
        self.region = region

        try:
            self.bedrock = boto3.client("bedrock", config=boto3_config)
            self.bedrock_runtime = boto3.client("bedrock-runtime", config=boto3_config)
        except Exception:
            logger.exception("bedrock.client_create_failed region=%s", self.region)
            raise RuntimeError("Failed to create Bedrock clients.")

        # Load available models
        try:
            resp = self.bedrock.list_foundation_models()
            summaries = resp.get("modelSummaries", []) or []
            active_models = [m for m in summaries if (m.get("modelLifecycle") or {}).get("status") == "ACTIVE"]
        except Exception as e:
            logger.exception("bedrock.list_models_failed region=%s", self.region)
            raise RuntimeError("Failed to list foundation models.") from e

        providers = {m.get("providerName") for m in active_models if m.get("providerName")}
        if not providers:
            logger.error("bedrock.no_active_providers_found region=%s", self.region)
            raise RuntimeError("No active providers available in Bedrock.")

        # Resolve provider
        if not provider:
            cfg = ConfigurationCenter()
            provider = cfg.get_parameter("aws_configuration", "model_provider")

        if not provider:
            logger.error("bedrock.no_provider_passed_or_configured")
            raise ValueError("Model provider must be configured or passed explicitly.")

        if provider not in providers:
            logger.error("bedrock.invalid_provider provider=%s valid=%s", provider, providers)
            raise ValueError(f"Invalid provider '{provider}', valid: {providers}")

        self.provider = provider

        # Pick latest model deterministically (max lexicographically)
        provider_models = [m.get('modelArn') for m in active_models if m.get("providerName") == provider]
        if not provider_models:
            logger.error("bedrock.no_models_for_provider provider=%s", provider)
            raise RuntimeError(f"No active models found for provider {provider}")

        resp = self.bedrock.list_inference_profiles()
        mapper={sub_arns.get('modelArn'):line.get('inferenceProfileArn') for line in resp.get('inferenceProfileSummaries') for sub_arns in line.get('models')}


        self.model_id = mapper[provider_models[-1]]
        logger.info("bedrock.model_selected provider=%s model_id=%s", provider, self.model_id)

    # keep interface: ask(user_message) -> str
    def ask(self, user_message: str, *, max_tokens: int = 2000, temperature: float = 0.3) -> str:
        conversation = [{"role": "user", "content": [{"text": user_message}]}]
        try:
            resp = self.bedrock_runtime.converse(
                modelId=self.model_id,
                messages=conversation,
                inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
            )
        except ClientError:
            logger.exception("bedrock.invoke_failed model_id=%s", self.model_id)
            raise
        except Exception:
            logger.exception("bedrock.invoke_unexpected_error model_id=%s", self.model_id)
            raise

        # Parse response safely
        output = (resp.get("output") or {}).get("message") or {}
        content = output.get("content") or []

        response_text, reasoning_text = "", ""
        for item in content:
            if "text" in item and isinstance(item["text"], str):
                response_text += item["text"]
            elif "reasoningContent" in item:
                rc = item.get("reasoningContent") or {}
                rt = (rc.get("reasoningText") or {}).get("text")
                if isinstance(rt, str):
                    reasoning_text += rt

        logger.info("bedrock.response_received model_id=%s response_len=%s", self.model_id, len(response_text))
        return response_text



# ------------------------------------------------
# Facade keeping your original public interface
# ------------------------------------------------

class AWSBoto3Agent:
    def __init__(self) -> None:
        cfg = ConfigurationCenter()
        self.region = cfg.get_parameter("aws_configuration", "region")
        if not self.region:
            logger.error("config.region_missing from ConfigurationCenter please double check config.ini for details.")
            raise RuntimeError("AWS region missing, check logs for details.")
        
        self.boto3_my_config = Config(
            region_name = self.region,
            signature_version = 'v4',
            retries = {
                'max_attempts': 3,
                'mode': 'standard'
            },
            connect_timeout=5,
            read_timeout=10
        )

        bucket = cfg.get_parameter("aws_configuration", "s3_bucketname")
        if not bucket:
            logger.error("config.s3_bucket_missing")
            raise RuntimeError("s3_bucketname missing.")
        self.bucket_name = bucket

        queue = cfg.get_parameter("aws_configuration", "sqs_queue_name")
        if not queue:
            logger.error("config.sqs_queue_missing")
            raise RuntimeError("sqs_queue_name missing.")
        self.queue_name = queue

        provider = cfg.get_parameter("aws_configuration", "model_provider")

        # Compose agents
        self._s3 = S3Agent(boto3_config=self.boto3_my_config, bucket_name=self.bucket_name,region=self.region)
        self._sqs = SQSAgent(boto3_config=self.boto3_my_config, queue_name=self.queue_name,region=self.region)
        self._bedrock = BedrockAgent(boto3_config=self.boto3_my_config, provider=provider,region=self.region)

    # S3 passthrough
    def upload_fileobj_to_s3(self, file_obj, object_name, bucket=None):
        return self._s3.upload_fileobj_to_s3(file_obj, object_name, bucket)

    def get_object_from_s3(self, object_name, bucket=None):
        return self._s3.get_object_from_s3(object_name, bucket)
    
    def delete_fileobj_from_s3(self, file_key, bucket=None):
        return self._s3.delete_fileobj_from_s3(file_key, bucket)

    # SQS passthrough
    def send_sqs_message(self, message_content: Dict):
        return self._sqs.send_sqs_message(message_content)

    def receive_sqs_message(self):
        return self._sqs.receive_sqs_message()

    def delete_sqs_message(self, receipt: str):
        return self._sqs.delete_sqs_message(receipt)

    # Bedrock passthrough
    def ask(self, user_message: str):
        return self._bedrock.ask(user_message)
