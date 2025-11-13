resource "random_string" "random" {
  length  = 2
  special = false
  upper   = false

  # Add keepers to prevent recreation of this random string
  # This ensures the same random string is used across applies
  keepers = {
    # This value changes only when you want to force a new random string
    force_recreation = "v1"
  }
}

resource "aws_kms_key" "s3_key" {
  description             = "KMS key for S3 bucket encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow S3 service to use the key"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow CodePipeline role to use the key"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.AWSCodePipelineServiceRole.arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow Lambda role to use the key"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.lambda-role.arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "s3_key_alias" {
  name          = "alias/graviton-s3-key-${random_string.random.result}"
  target_key_id = aws_kms_key.s3_key.key_id
}

resource "aws_s3_bucket" "S3Bucket" {
  bucket        = "${var.bucket_name}-${random_string.random.result}"
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "S3Bucket_encryption" {
  bucket = aws_s3_bucket.S3Bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3_key.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "S3Bucket_pab" {
  bucket = aws_s3_bucket.S3Bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "S3Bucket_logging" {
  bucket = aws_s3_bucket.S3Bucket.id

  target_bucket = aws_s3_bucket.S3Bucket.id
  target_prefix = "log/"
}

resource "aws_s3_bucket_lifecycle_configuration" "S3Bucket_lifecycle" {
  bucket = aws_s3_bucket.S3Bucket.id

  rule {
    id     = "delete_old_objects"
    status = "Enabled"
    filter {
      prefix = "*"
    }
    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_versioning" "S3Bucket_versioning" {
  bucket = aws_s3_bucket.S3Bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# CodePipeline Artifact Store Bucket
resource "aws_s3_bucket" "codepipeline_artifacts" {
  bucket        = "codepipeline-artifacts-${data.aws_caller_identity.current.account_id}-${random_string.random.result}"
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "codepipeline_artifacts_encryption" {
  bucket = aws_s3_bucket.codepipeline_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.codepipeline_key.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "codepipeline_artifacts_pab" {
  bucket = aws_s3_bucket.codepipeline_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "codepipeline_artifacts_versioning" {
  bucket = aws_s3_bucket.codepipeline_artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_logging" "codepipeline_artifacts_logging" {
  bucket = aws_s3_bucket.codepipeline_artifacts.id

  target_bucket = aws_s3_bucket.codepipeline_artifacts.id
  target_prefix = "access-logs/"
}

resource "aws_s3_bucket_notification" "codepipeline_artifacts_notification" {
  bucket = aws_s3_bucket.codepipeline_artifacts.id

  eventbridge = true
}

resource "aws_s3_bucket_lifecycle_configuration" "codepipeline_artifacts_lifecycle" {
  bucket = aws_s3_bucket.codepipeline_artifacts.id

  rule {
    id     = "delete_old_artifacts"
    status = "Enabled"
    filter {
      prefix = "*"
    }
    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}
resource "aws_s3_object" "upload_scripts" {
  bucket = aws_s3_bucket.S3Bucket.id
  key    = "scripts/script.zip"
  source = data.archive_file.zip_validation_tool.output_path
  # Remove etag to avoid inconsistent plan errors
  # etag   = filemd5(data.archive_file.zip_validation_tool.output_path)

  # Add source_hash instead for content tracking without etag issues
  source_hash = data.archive_file.zip_validation_tool.output_base64sha256
}
resource "aws_s3_object" "s3_dependency" {
  bucket = aws_s3_bucket.S3Bucket.id
  key    = "dependency/"
}
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.S3Bucket.id

  # Send S3 events to SQS queue instead of directly to Lambda
  queue {
    queue_arn     = aws_sqs_queue.lambda_input_queue.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "dependency/"
    filter_suffix = ".json"
  }

  depends_on = [aws_sqs_queue_policy.lambda_input_queue_policy]
}

resource "aws_kms_key" "codepipeline_key" {
  description             = "KMS key for CodePipeline encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CodePipeline service to use the key"
        Effect = "Allow"
        Principal = {
          Service = "codepipeline.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow CodePipeline role to use the key"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.AWSCodePipelineServiceRole.arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "codepipeline_key_alias" {
  name          = "alias/graviton-codepipeline-key-${random_string.random.result}"
  target_key_id = aws_kms_key.codepipeline_key.key_id
}

resource "aws_kms_key" "codebuild_key" {
  description             = "KMS key for CodeBuild encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CodeBuild service to use the key"
        Effect = "Allow"
        Principal = {
          Service = "codebuild.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow CodeBuild role to use the key"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.CodeBuildRole.arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "codebuild_key_alias" {
  name          = "alias/graviton-codebuild-key-${random_string.random.result}"
  target_key_id = aws_kms_key.codebuild_key.key_id
}

resource "aws_codepipeline" "CodePipelinePipeline" {
  name          = "sbom-graviton-app-dependency-compatibility-${random_string.random.result}"
  role_arn      = aws_iam_role.AWSCodePipelineServiceRole.arn
  pipeline_type = "V2"

  # Define pipeline variables for V2
  variable {
    name          = "BUCKET_NAME"
    default_value = ""
    description   = "S3 bucket name containing the SBOM file"
  }

  variable {
    name          = "FILE_KEY"
    default_value = ""
    description   = "S3 object key for the SBOM file"
  }

  variable {
    name          = "PACKAGE_TYPES"
    default_value = ""
    description   = "Comma-separated list of package types to analyze"
  }
  variable {
    name          = "IS_APP"
    default_value = ""
    description   = "Checks needed app_only,docker_only,all"
  }
  variable {
    name          = "IS_DOCKER"
    default_value = ""
    description   = "Checks needed app_only,docker_only,all"
  }

  artifact_store {
    location = aws_s3_bucket.codepipeline_artifacts.bucket
    type     = "S3"

    encryption_key {
      id   = aws_kms_key.codepipeline_key.arn
      type = "KMS"
    }
  }

  stage {
    name = "Source"
    action {
      name     = "Source"
      category = "Source"
      owner    = "AWS"
      configuration = {
        S3Bucket    = aws_s3_bucket.S3Bucket.id
        S3ObjectKey = "scripts/script.zip"
      }
      provider = "S3"
      version  = "1"
      output_artifacts = [
        "SourceArtifact"
      ]
      run_order = 1
    }
  }
  stage {
    name = "BuildAmazonLinux"
    before_entry {
      condition {
        result = "SKIP"
        rule {
          name = "AppCheck"
          rule_type_id {
            category = "Rule"
            owner    = "AWS"
            provider = "VariableCheck"
            version  = "1"
          }
          configuration = {
            Operator = "EQ"
            Value    = "true"
            Variable = "#{variables.IS_APP}"
          }
        }
      }
    }
    action {
      name     = "Build"
      category = "Build"
      owner    = "AWS"
      configuration = {
        EnvironmentVariables = jsonencode([
          {
            name  = "BUCKET_NAME"
            value = "#{variables.BUCKET_NAME}"
            type  = "PLAINTEXT"
          },
          {
            name  = "FILE_KEY"
            value = "#{variables.FILE_KEY}"
            type  = "PLAINTEXT"
          },
          {
            name  = "PACKAGE_TYPE"
            value = "#{variables.PACKAGE_TYPES}"
            type  = "PLAINTEXT"
          },
          {
            name  = "IS_DOCKER"
            value = "#{variables.IS_DOCKER}"
            type  = "PLAINTEXT"
          },
          {
            name  = "IS_APP"
            value = "#{variables.IS_APP}"
            type  = "PLAINTEXT"
          }
        ])
        ProjectName = aws_codebuild_project.CodebuildProject.name
      }
      input_artifacts = [
        "SourceArtifact"
      ]
      provider = "CodeBuild"
      version  = "1"
      output_artifacts = [
        "BuildArtifact-App"
      ]
      run_order = 1
    }
  }
  stage {
    name = "BuildDocker"
    before_entry {
      condition {
        result = "SKIP"
        rule {
          name = "DockerCheck"
          rule_type_id {
            category = "Rule"
            owner    = "AWS"
            provider = "VariableCheck"
            version  = "1"
          }
          configuration = {
            Operator = "EQ"
            Value    = "true"
            Variable = "#{variables.IS_DOCKER}"
          }
        }
      }
    }
    action {
      name     = "BuildDocker"
      category = "Build"
      owner    = "AWS"
      configuration = {
        EnvironmentVariables = jsonencode([
          {
            name  = "BUCKET_NAME"
            value = "#{variables.BUCKET_NAME}"
            type  = "PLAINTEXT"
          },
          {
            name  = "FILE_KEY"
            value = "#{variables.FILE_KEY}"
            type  = "PLAINTEXT"
          },
          {
            name  = "PACKAGE_TYPE"
            value = "#{variables.PACKAGE_TYPES}"
            type  = "PLAINTEXT"
          },
          {
            name  = "IS_DOCKER"
            value = "#{variables.IS_DOCKER}"
            type  = "PLAINTEXT"
          },
          {
            name  = "IS_APP"
            value = "#{variables.IS_APP}"
            type  = "PLAINTEXT"
          }
        ])
        ProjectName = aws_codebuild_project.CodebuildProjectDocker.name
      }
      input_artifacts = [
        "SourceArtifact"
      ]
      provider = "CodeBuild"
      version  = "1"
      output_artifacts = [
        "BuildArtifact-Docker"
      ]
      run_order = 1
    }
  }
}
resource "aws_codebuild_project" "CodebuildProjectDocker" {
  name           = "graviton-app-dependency-compatibility-build-docker-${random_string.random.result}"
  description    = "Code build "
  build_timeout  = 5
  service_role   = aws_iam_role.CodeBuildRole.arn
  encryption_key = aws_kms_key.codebuild_key.arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "public.ecr.aws/ubuntu/ubuntu:22.04"
    type                        = "ARM_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"

    # Environment variables will be passed from CodePipeline
    # No need to define them here as they'll be overridden
  }


  logs_config {
    cloudwatch_logs {
      group_name = "graviton-app-dependency-compatibility-build-docker-${random_string.random.result}"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "buildspec-docker.yml"
  }
}

resource "aws_codebuild_project" "CodebuildProject" {
  name           = "graviton-app-dependency-compatibility-tool-build-${random_string.random.result}"
  description    = "Code build "
  build_timeout  = 5
  service_role   = aws_iam_role.CodeBuildRole.arn
  encryption_key = aws_kms_key.codebuild_key.arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/amazonlinux2-aarch64-standard:3.0"
    type                        = "ARM_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"

    # Environment variables will be passed from CodePipeline
    # No need to define them here as they'll be overridden
  }

  logs_config {
    cloudwatch_logs {
      group_name = "codebuild/graviton-app-dependency-compatibility-tool-build-${random_string.random.result}"
    }
  }

  source {
    type = "CODEPIPELINE"
  }
}


resource "aws_codedeploy_app" "CodeDeployApplication" {
  name             = "GravitonSampleDeploy-${random_string.random.result}"
  compute_platform = "Server"
}



resource "aws_kms_key" "lambda_key" {
  description             = "KMS key for Lambda encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Lambda service to use the key"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow Lambda role to use the key"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.lambda-role.arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}

# KMS key for SQS encryption
resource "aws_kms_key" "sqs_key" {
  description             = "KMS key for SQS queue encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow SQS service to use the key"
        Effect = "Allow"
        Principal = {
          Service = "sqs.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow Lambda role to use the key for SQS"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.lambda-role.arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow S3 service to use the key for SQS notifications"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "sqs_key_alias" {
  name          = "alias/graviton-sqs-key-${random_string.random.result}"
  target_key_id = aws_kms_key.sqs_key.key_id
}

resource "aws_kms_alias" "lambda_key_alias" {
  name          = "alias/graviton-lambda-key-${random_string.random.result}"
  target_key_id = aws_kms_key.lambda_key.key_id
}

# Input queue for Lambda processing
resource "aws_sqs_queue" "lambda_input_queue" {
  name                       = "graviton-lambda-input-${random_string.random.result}"
  visibility_timeout_seconds = 240    # 4x Lambda timeout (40s * 6)
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20     # Long polling for cost optimization

  # Redrive policy to DLQ after 3 attempts
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.lambda_dlq.arn
    maxReceiveCount     = 3
  })

  kms_master_key_id = aws_kms_key.sqs_key.arn

  tags = {
    Environment = "production"
    Application = "sbom-graviton-compatibility-tool"
    Purpose     = "Lambda Input Queue"
  }
}

# SQS queue policy to allow S3 to send messages
resource "aws_sqs_queue_policy" "lambda_input_queue_policy" {
  queue_url = aws_sqs_queue.lambda_input_queue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.lambda_input_queue.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_s3_bucket.S3Bucket.arn
          }
        }
      }
    ]
  })
}

# Dead Letter Queue
resource "aws_sqs_queue" "lambda_dlq" {
  name                       = "graviton-lambda-dlq-${random_string.random.result}"
  message_retention_seconds  = 1209600 # 14 days - maximum retention
  visibility_timeout_seconds = 300     # 5 minutes for processing
  kms_master_key_id          = aws_kms_key.sqs_key.arn

  # Enable long polling to reduce costs
  receive_wait_time_seconds = 20

  tags = {
    Environment = "production"
    Application = "sbom-graviton-compatibility-tool"
    Purpose     = "Lambda Dead Letter Queue"
  }
}


resource "aws_lambda_function" "LambdaFunction" {
  description = "Lambda function to trigger CodePipeline on S3 events"
  environment {
    variables = {
      CODEBUILD_PROJECT = aws_codebuild_project.CodebuildProject.name
      CODEPIPELINE_NAME = aws_codepipeline.CodePipelinePipeline.name
    }
  }
  function_name = "sbom-graviton-build-trigger-${random_string.random.result}"
  handler       = "lambda_function.lambda_handler"
  architectures = [
    "x86_64"
  ]
  filename    = "${path.module}/functions/packaged/trigger.zip"
  memory_size = 128
  role        = aws_iam_role.lambda-role.arn
  runtime     = "python3.13"
  timeout     = 40
  kms_key_arn = aws_kms_key.lambda_key.arn
  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }

  tracing_config {
    mode = "Active"
  }
  layers = [
    "arn:aws:lambda:${data.aws_region.current.id}:336392948345:layer:AWSSDKPandas-Python313:1"
  ]
  
  reserved_concurrent_executions = 100
  
  tags = {
    Environment = "production"
    Application = "sbom-graviton-compatibility-tool"
  }
}
resource "aws_kms_key" "cloudwatch_key" {
  description             = "KMS key for CloudWatch logs encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch Logs for Lambda"
        Effect = "Allow"
        Principal = {
          Service = "logs.${data.aws_region.current.id}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/sbom-graviton-build-trigger-${random_string.random.result}"
          }
        }
      },
      {
        Sid    = "Allow CloudWatch Logs for CodeBuild"
        Effect = "Allow"
        Principal = {
          Service = "logs.${data.aws_region.current.id}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:log-group:/codebuild/sbom-graviton-build-trigger-${random_string.random.result}"
          }
        }
      },
      {
        Sid    = "Allow Lambda role to use the key for CloudWatch"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.lambda-role.arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "cloudwatch_key_alias" {
  name          = "alias/graviton-cloudwatch-key-${random_string.random.result}"
  target_key_id = aws_kms_key.cloudwatch_key.key_id
}

resource "aws_cloudwatch_log_group" "lambda_log_group" {
  name              = "/aws/lambda/sbom-graviton-build-trigger-${random_string.random.result}"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.cloudwatch_key.arn

  tags = {
    Environment = "production"
    Application = "sbom-graviton-compatibility-tool"
  }
}

resource "aws_cloudwatch_log_group" "codebuild_log_group" {
  name              = "/codebuild/sbom-graviton-build-trigger-${random_string.random.result}"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.cloudwatch_key.arn

  tags = {
    Environment = "production"
    Application = "sbom-graviton-compatibility-tool"
  }
}

# Lambda event source mapping from SQS
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.lambda_input_queue.arn
  function_name    = aws_lambda_function.LambdaFunction.arn
  batch_size       = 1 # Process one message at a time

  # Enable partial batch failure handling
  function_response_types = ["ReportBatchItemFailures"]

  # Scale configuration
  scaling_config {
    maximum_concurrency = 10 # Max concurrent Lambda executions
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_custom_policy,
    aws_sqs_queue.lambda_input_queue
  ]
}

# Keep Lambda permission for backward compatibility (if needed)
resource "aws_lambda_permission" "allow_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.LambdaFunction.arn
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.S3Bucket.arn
}
