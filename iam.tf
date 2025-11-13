resource "aws_iam_role" "AWSCodePipelineServiceRole" {
  path = "/service-role/"
  name = "AWSCodePipelineServiceRole-graviton-${random_string.random.result}"
  assume_role_policy = jsonencode(
    {
      "Version" : "2012-10-17",
      "Statement" : [
        {
          "Effect" : "Allow",
          "Principal" : {
            "Service" : "codepipeline.amazonaws.com"
          },
          "Action" : "sts:AssumeRole"
        }
      ]
    }
  )
  max_session_duration = 3600
  tags                 = {}
}

# Attach CodePipeline policy using separate resource
resource "aws_iam_role_policy_attachment" "codepipeline_custom_policy" {
  role       = aws_iam_role.AWSCodePipelineServiceRole.name
  policy_arn = aws_iam_policy.AWSCodePipelineServiceRole-policy.arn
}
resource "aws_iam_policy" "AWSCodePipelineServiceRole-policy" {
  name = "AWSCodePipelineServiceRole-policy-${random_string.random.result}"

  policy = jsonencode({
    "Statement" : [
      {
        "Action" : [
          "iam:PassRole"
        ],
        "Resource" : "*",
        "Effect" : "Allow",
        "Condition" : {
          "StringEqualsIfExists" : {
            "iam:PassedToService" : [
              "cloudformation.amazonaws.com",
              "elasticbeanstalk.amazonaws.com",
              "ec2.amazonaws.com",
              "ecs-tasks.amazonaws.com"
            ]
          }
        }
      },
      {
        "Action" : [
          "codecommit:CancelUploadArchive",
          "codecommit:GetBranch",
          "codecommit:GetCommit",
          "codecommit:GetRepository",
          "codecommit:GetUploadArchiveStatus",
          "codecommit:UploadArchive"
        ],
        "Resource" : "arn:aws:codecommit:*:${data.aws_caller_identity.current.account_id}:*",
        "Effect" : "Allow"
      },
      {
        "Action" : [
          "codedeploy:CreateDeployment",
          "codedeploy:GetApplication",
          "codedeploy:GetApplicationRevision",
          "codedeploy:GetDeployment",
          "codedeploy:GetDeploymentConfig",
          "codedeploy:RegisterApplicationRevision",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEventspermissions"
        ],
        "Resource" : "*",
        "Effect" : "Allow"
      },
      {
        "Action" : [
          "codestar-connections:UseConnection"
        ],
        "Resource" : "arn:aws:codestar-connections:*:${data.aws_caller_identity.current.account_id}:*",
        "Effect" : "Allow"
      },
      {
        "Action" : [
          "s3:*"
        ],
        "Resource" : [
          "arn:aws:s3:::codepipeline-*",
          "arn:aws:s3:::codepipeline-*/*",
          "${aws_s3_bucket.S3Bucket.arn}",
          "${aws_s3_bucket.S3Bucket.arn}/*",
          "${aws_s3_bucket.codepipeline_artifacts.arn}",
          "${aws_s3_bucket.codepipeline_artifacts.arn}/*",
          "*"
        ],
        "Effect" : "Allow"
      },
      {
        "Action" : [
          "lambda:InvokeFunction"
        ],
        "Resource" : "arn:aws:lambda:*:${data.aws_caller_identity.current.account_id}:function:*",
        "Effect" : "Allow"
      },
      {
        "Action" : [
          "opsworks:CreateDeployment",
          "opsworks:DescribeApps",
          "opsworks:DescribeCommands",
          "opsworks:DescribeDeployments",
          "opsworks:DescribeInstances",
          "opsworks:DescribeStacks",
          "opsworks:UpdateApp",
          "opsworks:UpdateStack"
        ],
        "Resource" : "*",
        "Effect" : "Allow"
      },
      {
        "Action" : [
          "cloudformation:CreateStack",
          "cloudformation:DeleteStack",
          "cloudformation:DescribeStacks",
          "cloudformation:UpdateStack",
          "cloudformation:CreateChangeSet",
          "cloudformation:DeleteChangeSet",
          "cloudformation:DescribeChangeSet",
          "cloudformation:ExecuteChangeSet",
          "cloudformation:SetStackPolicy",
          "cloudformation:ValidateTemplate"
        ],
        "Resource" : "*",
        "Effect" : "Allow"
      },
      {
        "Action" : [
          "codebuild:BatchGetBuilds",
          "codebuild:StartBuild",
          "codebuild:BatchGetBuildBatches",
          "codebuild:StartBuildBatch"
        ],
        "Resource" : "arn:aws:codebuild:*:${data.aws_caller_identity.current.account_id}:project/*",
        "Effect" : "Allow"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "devicefarm:ListProjects",
          "devicefarm:ListDevicePools",
          "devicefarm:GetRun",
          "devicefarm:GetUpload",
          "devicefarm:CreateUpload",
          "devicefarm:ScheduleRun"
        ],
        "Resource" : "*"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "servicecatalog:ListProvisioningArtifacts",
          "servicecatalog:CreateProvisioningArtifact",
          "servicecatalog:DescribeProvisioningArtifact",
          "servicecatalog:DeleteProvisioningArtifact",
          "servicecatalog:UpdateProduct"
        ],
        "Resource" : "*"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "cloudformation:ValidateTemplate"
        ],
        "Resource" : "*"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "ecr:DescribeImages"
        ],
        "Resource" : "*"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "states:DescribeExecution",
          "states:DescribeStateMachine",
          "states:StartExecution"
        ],
        "Resource" : "*"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "appconfig:StartDeployment",
          "appconfig:StopDeployment",
          "appconfig:GetDeployment"
        ],
        "Resource" : "*"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "codepipeline:StartPipelineExecution"
        ],
        "Resource" : "arn:aws:codepipeline:*:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ],
        "Resource" : [
          "${aws_kms_key.codepipeline_key.arn}",
          "${aws_kms_key.s3_key.arn}",
          "${aws_kms_key.codebuild_key.arn}",
          "arn:aws:kms:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:key/*"
        ]
      }
    ],
    "Version" : "2012-10-17"
  })
}

resource "aws_iam_role" "CodeBuildRole" {
  path = "/service-role/"
  name = "codebuild-graviton-service-role-${random_string.random.result}"
  assume_role_policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Principal" : {
          "Service" : "codebuild.amazonaws.com"
        },
        "Action" : "sts:AssumeRole"
      }
    ]
  })
  max_session_duration = 3600
  tags                 = {}
}

# Attach CodeBuild policies using separate resources
resource "aws_iam_role_policy_attachment" "codebuild_custom_policy" {
  role       = aws_iam_role.CodeBuildRole.name
  policy_arn = aws_iam_policy.CodeBuildRole-policy.arn
}

resource "aws_iam_role_policy_attachment" "codebuild_s3_access" {
  role       = aws_iam_role.CodeBuildRole.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "codebuild_logs_access" {
  role       = aws_iam_role.CodeBuildRole.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}
resource "aws_iam_policy" "CodeBuildRole-policy" {
  name = "GravitonCodeBuildRole-policy-${random_string.random.result}"
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Resource" : [
          "arn:aws:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:log-group:/aws/codebuild/sbom-graviton-app-dependency-compatibility-${random_string.random.result}",
          "arn:aws:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:log-group:/aws/codebuild/sbom-graviton-app-dependency-compatibility-${random_string.random.result}:*"
        ],
        "Action" : [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
      },
      {
        "Effect" : "Allow",
        "Resource" : [
          "${aws_s3_bucket.codepipeline_artifacts.arn}",
          "${aws_s3_bucket.codepipeline_artifacts.arn}/*"
        ],
        "Action" : [
          "s3:PutObject",
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:GetBucketAcl",
          "s3:GetBucketLocation"
        ]
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "codebuild:CreateReportGroup",
          "codebuild:CreateReport",
          "codebuild:UpdateReport",
          "codebuild:BatchPutTestCases",
          "codebuild:BatchPutCodeCoverages"
        ],
        "Resource" : [
          "arn:aws:codebuild:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:report-group/Graviton-*"
        ]
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ],
        "Resource" : [
          "${aws_kms_key.codebuild_key.arn}",
          "${aws_kms_key.s3_key.arn}",
          aws_kms_key.codepipeline_key.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role" "lambda-role" {
  path = "/service-role/"
  name = "graviton-build-lambda-trigger-role-${random_string.random.result}"
  assume_role_policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Principal" : {
          "Service" : "lambda.amazonaws.com"
        },
        "Action" : "sts:AssumeRole"
      }
    ]
  })
  max_session_duration = 3600
  tags                 = {}
}

# Attach policies using separate resources instead of deprecated managed_policy_arns
resource "aws_iam_role_policy_attachment" "lambda_custom_policy" {
  role       = aws_iam_role.lambda-role.name
  policy_arn = aws_iam_policy.build-trigger-lambda-policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda-role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "build-trigger-lambda-policy" {
  name = "graviton-build-lambda-trigger-policy-${random_string.random.result}"
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Action" : [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        "Resource" : [
          "arn:aws:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:*"
        ]
      },
      {
        "Sid" : "SQSInputQueueAccess",
        "Effect" : "Allow",
        "Action" : [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ],
        "Resource" : [
          "arn:aws:sqs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:graviton-lambda-input-*"
        ]
      },
      {
        "Sid" : "SQSDLQAccess",
        "Effect" : "Allow",
        "Action" : [
          "sqs:SendMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ],
        "Resource" : [
          "arn:aws:sqs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:graviton-lambda-dlq-*"
        ]
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "codebuild:StartBuild",
          "codebuild:BatchGetBuilds"
        ],
        "Resource" : [
          "arn:aws:codebuild:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:project/*"
        ]
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "codepipeline:StartPipelineExecution",
          "codepipeline:GetPipelineState"
        ],
        "Resource" : [
          "arn:aws:codepipeline:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:*"
        ]
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "s3:GetObject",
          "s3:PutObject"
        ],
        "Resource" : [
          "${aws_s3_bucket.S3Bucket.arn}/*"
        ]
      },
      {
        "Sid" : "CloudWatchMetrics",
        "Effect" : "Allow",
        "Action" : [
          "cloudwatch:PutMetricData"
        ],
        "Resource" : "*",
        "Condition" : {
          "StringEquals" : {
            "cloudwatch:namespace" : "GravitonTool/Lambda"
          }
        }
      },
      {
        "Effect" : "Allow",
        "Action" : [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ],
        "Resource" : [
          "${aws_kms_key.lambda_key.arn}",
          "${aws_kms_key.sqs_key.arn}",
          "${aws_kms_key.cloudwatch_key.arn}",
          "${aws_kms_key.s3_key.arn}"
        ]
      }
    ]
  })
}
