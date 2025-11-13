output "s3_bucket_name" {
  description = "The name of the S3 bucket created for SBOM uploads"
  value       = aws_s3_bucket.S3Bucket.id
}

output "lambda_function_name" {
  description = "The name of the Lambda function that processes SBOM uploads"
  value       = aws_lambda_function.LambdaFunction.function_name
}

output "codepipeline_name" {
  description = "The name of the CodePipeline that orchestrates the analysis workflow"
  value       = aws_codepipeline.CodePipelinePipeline.name
}

output "codebuild_project_name" {
  description = "The name of the CodeBuild project that performs the dependency analysis"
  value       = aws_codebuild_project.CodebuildProject.name
}

output "dependency_upload_path" {
  description = "The S3 path where SBOM files should be uploaded"
  value       = "s3://${aws_s3_bucket.S3Bucket.id}/dependency/"
}

output "reports_path" {
  description = "The S3 path where analysis reports will be stored"
  value       = "s3://${aws_s3_bucket.S3Bucket.id}/reports/"
}

output "codepipeline_artifacts_bucket" {
  description = "The name of the S3 bucket used for CodePipeline artifacts"
  value       = aws_s3_bucket.codepipeline_artifacts.id
}

output "lambda_dlq_name" {
  description = "The name of the Lambda Dead Letter Queue"
  value       = aws_sqs_queue.lambda_dlq.name
}

output "lambda_input_queue_url" {
  description = "The URL of the Lambda input queue"
  value       = aws_sqs_queue.lambda_input_queue.url
}

output "lambda_input_queue_name" {
  description = "The name of the Lambda input queue"
  value       = aws_sqs_queue.lambda_input_queue.name
}

output "lambda_dlq_url" {
  description = "The URL of the Lambda Dead Letter Queue for monitoring failed invocations"
  value       = aws_sqs_queue.lambda_dlq.url
}

output "lambda_dlq_arn" {
  description = "The ARN of the Lambda Dead Letter Queue"
  value       = aws_sqs_queue.lambda_dlq.arn
}
