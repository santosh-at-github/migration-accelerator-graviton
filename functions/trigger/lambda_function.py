import json
import logging
import os
import time
from typing import Dict, List, Set, Tuple, Any

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

# Import error handler
try:
    from error_handler import handle_error, ErrorContext, ErrorClassifier
except ImportError:
    # Fallback if error_handler not available
    handle_error = None
    ErrorContext = None
    ErrorClassifier = None

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Package type mappings for better maintainability
PACKAGE_MAPPINGS = {
    'pkg:pypi/': 'pip',
    'pkg:maven/': 'maven',
    'pkg:npm/': 'npm',
    'pkg:nuget/': 'nuget'
}

# Configure boto3 clients with retry strategy
retry_config = Config(
    retries={
        'max_attempts': 3,
        'mode': 'adaptive'  # Adaptive retry mode for better handling
    },
    connect_timeout=5,
    read_timeout=30
)

# Initialize boto3 clients outside handler for connection reuse
s3_client = boto3.client('s3', config=retry_config)
codepipeline_client = boto3.client('codepipeline', config=retry_config)
cloudwatch = boto3.client('cloudwatch', config=retry_config)


def extract_s3_info(event: Dict[str, Any]) -> Tuple[str, str]:
    """
    Extract S3 bucket and key from Lambda event.
    Handles both direct S3 events and SQS-wrapped S3 events.
    """
    try:
        record = event['Records'][0]
        
        # Check if this is an SQS event wrapping an S3 event
        if 'eventSource' in record and record['eventSource'] == 'aws:sqs':
            # Parse the S3 event from SQS message body
            s3_event = json.loads(record['body'])
            s3_record = s3_event['Records'][0]
            bucket = s3_record['s3']['bucket']['name']
            key = s3_record['s3']['object']['key']
        else:
            # Direct S3 event
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
        
        # URL decode the key (S3 keys are URL encoded in events)
        from urllib.parse import unquote_plus
        key = unquote_plus(key)
        
        return bucket, key
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"Failed to extract S3 info from event: {e}", extra={'event': event})
        raise ValueError(f"Invalid S3 event structure: {e}")


def get_sbom_content(bucket: str, key: str) -> Dict[str, Any]:
    """Download and parse SBOM file from S3."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            raise FileNotFoundError(f"SBOM file not found: s3://{bucket}/{key}")
        elif error_code == 'NoSuchBucket':
            raise FileNotFoundError(f"S3 bucket not found: {bucket}")
        else:
            raise RuntimeError(f"S3 error ({error_code}): {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in SBOM file: {e}")
    except UnicodeDecodeError as e:
        raise ValueError(f"Unable to decode SBOM file content: {e}")


def analyze_components(components: List[Dict[str, Any]]) -> Tuple[Set[str], bool, bool]:
    """Analyze SBOM components to determine package types and flags."""
    package_set = set()
    is_app = False
    is_docker = False
    
    for component in components:
        purl = component.get('purl', '')
        if not purl:
            continue
            
        # Check for application packages
        for prefix, package_type in PACKAGE_MAPPINGS.items():
            if purl.startswith(prefix):
                package_set.add(package_type)
                is_app = True
                break
        
        # Check for Docker packages
        if purl.startswith('pkg:docker/'):
            is_docker = True
    
    return package_set, is_app, is_docker


def start_pipeline(pipeline_name: str, bucket: str, key: str, 
                  package_types: str, is_app: bool, is_docker: bool) -> Dict[str, Any]:
    """Start CodePipeline execution with the analyzed parameters."""
    try:
        variables = [
            {'name': 'BUCKET_NAME', 'value': bucket},
            {'name': 'FILE_KEY', 'value': key},
            {'name': 'PACKAGE_TYPES', 'value': package_types},
            {'name': 'IS_APP', 'value': str(is_app).lower()},
            {'name': 'IS_DOCKER', 'value': str(is_docker).lower()}
        ]
        
        response = codepipeline_client.start_pipeline_execution(
            name=pipeline_name,
            variables=variables
        )
        
        logger.info(f"Pipeline started successfully: {response['pipelineExecutionId']}")
        return response
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'PipelineNotFoundException':
            raise ValueError(f"CodePipeline not found: {pipeline_name}")
        else:
            raise RuntimeError(f"CodePipeline error ({error_code}): {e}")


def start_pipeline_with_retry(pipeline_name: str, bucket: str, key: str,
                              package_types: str, is_app: bool, 
                              is_docker: bool, max_retries: int = 2) -> Dict[str, Any]:
    """
    Start pipeline with exponential backoff retry for transient failures.
    """
    for attempt in range(max_retries + 1):
        try:
            return start_pipeline(pipeline_name, bucket, key, 
                                package_types, is_app, is_docker)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            # Don't retry permanent errors
            if error_code in ['PipelineNotFoundException', 'ValidationException', 'AccessDeniedException']:
                logger.error(f"Permanent error, not retrying: {error_code}")
                raise
            
            # Retry transient errors with backoff
            if attempt < max_retries:
                wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                logger.warning(f"Pipeline start failed (attempt {attempt + 1}/{max_retries + 1}), "
                             f"retrying in {wait_time}s: {error_code}")
                time.sleep(wait_time)
            else:
                logger.error(f"Pipeline start failed after {max_retries + 1} attempts")
                raise


def publish_metric(metric_name: str, value: float, unit: str = 'Count', 
                  dimensions: Dict[str, str] = None):
    """
    Publish custom CloudWatch metrics for monitoring.
    """
    try:
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit
        }
        
        if dimensions:
            metric_data['Dimensions'] = [
                {'Name': k, 'Value': v} for k, v in dimensions.items()
            ]
        
        cloudwatch.put_metric_data(
            Namespace='GravitonTool/Lambda',
            MetricData=[metric_data]
        )
    except Exception as e:
        # Don't fail the Lambda if metrics fail
        logger.warning(f"Failed to publish metric {metric_name}: {e}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler to process SBOM files and trigger CodePipeline.
    Enhanced with error handling and SQS batch support.
    
    Args:
        event: Lambda event containing S3 or SQS trigger information
        context: Lambda context object
        
    Returns:
        Dict containing execution status and details
    """
    try:
        # Log request context
        logger.info(f"Lambda invoked", extra={
            'request_id': context.aws_request_id,
            'function_name': context.function_name,
            'remaining_time_ms': context.get_remaining_time_in_millis()
        })
        
        # Handle SQS batch events
        if 'Records' in event and event['Records']:
            first_record = event['Records'][0]
            if 'eventSource' in first_record and first_record['eventSource'] == 'aws:sqs':
                return process_sqs_batch(event, context)
        
        # Handle direct S3 events (legacy)
        return process_s3_event(event, context)
        
    except Exception as e:
        # Use error handler if available
        if handle_error:
            return handle_error(e, event, context)
        else:
            logger.error(f"Lambda execution failed: {str(e)}", exc_info=True)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': str(e),
                    'message': 'Lambda execution failed'
                })
            }


def process_sqs_batch(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process SQS batch with partial failure handling.
    Returns failed message IDs for automatic retry.
    """
    batch_item_failures = []
    successful = 0
    
    logger.info(f"Processing SQS batch with {len(event['Records'])} messages")
    
    for record in event['Records']:
        message_id = record.get('messageId', 'unknown')
        
        try:
            # Extract S3 event from SQS message
            message_body = json.loads(record['body'])
            
            # Handle S3 test events
            if 'Event' in message_body and message_body['Event'] == 's3:TestEvent':
                logger.info(f"Skipping S3 test event: {message_id}")
                successful += 1
                continue
            
            # Process the S3 event
            result = process_s3_event(message_body, context)
            
            logger.info(f"Successfully processed message: {message_id}")
            successful += 1
            
            # Publish success metric
            publish_metric('MessageProcessed', 1, 'Count')
            
        except Exception as e:
            logger.error(f"Failed to process message {message_id}: {str(e)}")
            
            # Classify error to determine if we should retry
            if ErrorClassifier:
                error_type = ErrorClassifier.classify(e)
                
                if error_type.value in ['permanent', 'validation']:
                    # Don't retry permanent/validation errors
                    logger.error(f"Permanent error, skipping message: {message_id}")
                    publish_metric('MessageSkipped', 1, 'Count', {'ErrorType': error_type.value})
                    continue
            
            # Add to batch failures for retry
            batch_item_failures.append({
                'itemIdentifier': message_id
            })
            
            # Publish failure metric
            publish_metric('MessageFailed', 1, 'Count')
    
    logger.info(f"Batch processing complete: {successful} successful, {len(batch_item_failures)} failed")
    
    # Return batch failures for Lambda to retry
    return {
        'batchItemFailures': batch_item_failures
    }


def process_s3_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Core S3 event processing logic.
    Handles both direct S3 events and S3 events from SQS.
    """
    # Extract environment variables
    pipeline_name = os.environ.get('CODEPIPELINE_NAME')
    if not pipeline_name:
        raise ValueError("CODEPIPELINE_NAME environment variable not set")
    
    # Extract S3 information from event
    bucket, key = extract_s3_info(event)
    logger.info(f"Processing SBOM file: s3://{bucket}/{key}", extra={
        'bucket': bucket,
        'key': key,
        'pipeline': pipeline_name
    })
    
    # Download and parse SBOM file
    sbom_data = get_sbom_content(bucket, key)
    components = sbom_data.get('components', [])
    
    if not components:
        logger.warning("No components found in SBOM file", extra={
            'bucket': bucket,
            'key': key
        })
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'No components found in SBOM file',
                'bucket': bucket,
                'key': key
            })
        }
    
    # Analyze components
    package_set, is_app, is_docker = analyze_components(components)
    package_types = ",".join(sorted(package_set)) if package_set else "none"
    
    logger.info(f"Analysis results - Package types: {package_types}, "
               f"Is App: {is_app}, Is Docker: {is_docker}", extra={
        'package_types': package_types,
        'is_app': is_app,
        'is_docker': is_docker,
        'component_count': len(components)
    })
    
    # Start pipeline execution with retry logic
    pipeline_response = start_pipeline_with_retry(
        pipeline_name, bucket, key, package_types, is_app, is_docker
    )
    
    # Publish success metric
    publish_metric('PipelineStarted', 1, 'Count')
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Pipeline started successfully',
            'pipelineExecutionId': pipeline_response['pipelineExecutionId'],
            'bucket': bucket,
            'key': key,
            'packageTypes': package_types,
            'isApp': is_app,
            'isDocker': is_docker
        })
    }
