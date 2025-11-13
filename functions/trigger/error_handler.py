"""
Enhanced error handling for Lambda functions with error classification
and comprehensive context capture for debugging.
"""

from enum import Enum
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger()


class ErrorType(Enum):
    """Classification of error types for retry strategy"""
    TRANSIENT = "transient"  # Retry with backoff
    PERMANENT = "permanent"  # Send to DLQ immediately
    THROTTLING = "throttling"  # Retry with longer delay
    VALIDATION = "validation"  # Don't retry, log and skip


class ErrorClassifier:
    """Classify errors to determine retry strategy"""
    
    TRANSIENT_ERRORS = {
        'ServiceUnavailable',
        'RequestTimeout',
        'InternalError',
        'TooManyRequestsException',
        'ProvisionedThroughputExceededException',
        'RequestLimitExceeded'
    }
    
    THROTTLING_ERRORS = {
        'ThrottlingException',
        'TooManyRequestsException',
        'ProvisionedThroughputExceededException',
        'RequestLimitExceeded',
        'SlowDown'
    }
    
    PERMANENT_ERRORS = {
        'NoSuchKey',
        'NoSuchBucket',
        'AccessDenied',
        'InvalidParameterValue',
        'ResourceNotFoundException',
        'PipelineNotFoundException'
    }
    
    @classmethod
    def classify(cls, error: Exception) -> ErrorType:
        """Classify error type based on exception"""
        error_name = type(error).__name__
        
        # Check for AWS error codes
        if hasattr(error, 'response'):
            error_code = error.response.get('Error', {}).get('Code', '')
            
            if error_code in cls.PERMANENT_ERRORS:
                return ErrorType.PERMANENT
            elif error_code in cls.THROTTLING_ERRORS:
                return ErrorType.THROTTLING
            elif error_code in cls.TRANSIENT_ERRORS:
                return ErrorType.TRANSIENT
        
        # Check for validation errors
        if isinstance(error, (ValueError, KeyError, json.JSONDecodeError)):
            return ErrorType.VALIDATION
        
        # Check for file not found
        if isinstance(error, FileNotFoundError):
            return ErrorType.PERMANENT
        
        # Default to transient for unknown errors
        return ErrorType.TRANSIENT


class ErrorContext:
    """Capture comprehensive error context for debugging"""
    
    def __init__(self, error: Exception, event: Dict[str, Any], 
                 context: Any, additional_info: Optional[Dict] = None):
        self.error = error
        self.event = event
        self.context = context
        self.additional_info = additional_info or {}
        self.error_type = ErrorClassifier.classify(error)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error context to dictionary for logging/DLQ"""
        error_dict = {
            'error': {
                'type': type(self.error).__name__,
                'message': str(self.error),
                'classification': self.error_type.value
            },
            'lambda': {
                'request_id': self.context.aws_request_id,
                'function_name': self.context.function_name,
                'memory_limit': self.context.memory_limit_in_mb,
                'remaining_time_ms': self.context.get_remaining_time_in_millis()
            },
            'event': self._sanitize_event(self.event),
            'additional_info': self.additional_info,
            'should_retry': self.error_type in [ErrorType.TRANSIENT, ErrorType.THROTTLING]
        }
        
        # Add AWS error details if available
        if hasattr(self.error, 'response'):
            error_dict['error']['aws_error_code'] = self.error.response.get('Error', {}).get('Code')
            error_dict['error']['aws_error_message'] = self.error.response.get('Error', {}).get('Message')
        
        return error_dict
    
    def _sanitize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from event for logging"""
        # Create a copy to avoid modifying original
        sanitized = event.copy()
        
        # Remove large payloads if present
        if 'body' in sanitized and len(str(sanitized['body'])) > 1000:
            sanitized['body'] = str(sanitized['body'])[:1000] + '... (truncated)'
        
        return sanitized
    
    def log(self):
        """Log error with full context"""
        logger.error(
            f"Lambda execution failed: {self.error_type.value} error - {str(self.error)}",
            extra={'error_context': self.to_dict()}
        )


def handle_error(error: Exception, event: Dict[str, Any], 
                context: Any, **kwargs) -> Dict[str, Any]:
    """
    Centralized error handling with classification and context
    
    Returns appropriate response based on error type
    """
    error_ctx = ErrorContext(error, event, context, kwargs)
    error_ctx.log()
    
    # For SQS batch processing, return failure info
    if 'Records' in event and len(event['Records']) > 0:
        record = event['Records'][0]
        if 'messageId' in record:  # SQS event
            # Only report failure if it's retryable
            if error_ctx.error_type in [ErrorType.TRANSIENT, ErrorType.THROTTLING]:
                return {
                    'batchItemFailures': [
                        {'itemIdentifier': record['messageId']}
                    ]
                }
            else:
                # Don't retry permanent/validation errors
                logger.info(f"Skipping retry for {error_ctx.error_type.value} error")
                return {'batchItemFailures': []}
    
    # For direct invocation, return error response
    if error_ctx.error_type == ErrorType.PERMANENT:
        # Don't retry permanent errors
        logger.error("Permanent error detected, not retrying")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': str(error),
                'classification': error_ctx.error_type.value,
                'message': 'Permanent error - will not retry'
            })
        }
    
    # Raise exception to trigger retry for transient errors
    raise error
