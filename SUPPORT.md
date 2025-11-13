# Support

Thank you for using the SBOM Graviton App Dependency Compatibility Tool! This document provides information on how to get help and support.

## Getting Help

### Documentation
Start with our comprehensive documentation:
- **[README.md](README.md)**: Complete setup and usage guide
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Development and contribution guidelines
- **[CHANGELOG.md](CHANGELOG.md)**: Version history and release notes
- **[SECURITY.md](SECURITY.md)**: Security policies and best practices

### Common Issues and Solutions

#### Deployment Issues

**Terraform deployment fails**
- Verify AWS credentials and permissions
- Check service quotas in your AWS account
- Ensure unique S3 bucket names
- Review CloudTrail logs for detailed error information

**CodePipeline variables not updating**
- Ensure CodePipeline V2 variables are properly declared
- Check Lambda function environment variables
- Verify IAM permissions for CodePipeline execution

**SBOM upload not triggering analysis**
- Check S3 event configuration
- Verify Lambda function permissions
- Ensure SBOM file is in JSON format
- Check CloudWatch logs for Lambda execution errors

#### Analysis Issues

**Missing dependencies in analysis**
- Verify SBOM generation includes all package types
- Check that SBOM contains expected components
- Ensure AWS Inspector SBOM Generator is configured correctly
- Review buildspec.yml for package type detection logic

**Files not uploading to S3**
- Check CodeBuild IAM permissions for S3 access
- Verify S3 bucket exists and is accessible
- Review buildspec.yml file paths and upload commands
- Check CloudWatch logs for upload errors

**Maven analysis fails**
- Ensure Maven is properly installed in CodeBuild
- Check internet connectivity for dependency downloads
- Verify pom.xml generation from SBOM
- Review Java compatibility analyzer logs

#### Performance Issues

**Analysis takes too long**
- Increase CodeBuild timeout settings
- Optimize dependency analysis scripts
- Consider parallel processing for large SBOM files
- Monitor CodeBuild resource utilization

**High AWS costs**
- Review S3 lifecycle policies
- Optimize Lambda memory allocation
- Monitor CodeBuild usage patterns
- Implement cost alerts and budgets

### Self-Service Resources

#### AWS Documentation
- [AWS Inspector SBOM Generator User Guide](https://docs.aws.amazon.com/inspector/latest/user/sbom-generator.html)
- [AWS Graviton Technical Guide](https://github.com/aws/aws-graviton-getting-started)
- [AWS CodeBuild User Guide](https://docs.aws.amazon.com/codebuild/latest/userguide/)
- [AWS CodePipeline User Guide](https://docs.aws.amazon.com/codepipeline/latest/userguide/)

#### Community Resources
- [AWS Graviton Community](https://github.com/aws/aws-graviton-getting-started/discussions)
- [CycloneDX Community](https://cyclonedx.org/community/)
- [SPDX Working Group](https://spdx.dev/participate/)

#### Troubleshooting Tools
- **CloudWatch Logs**: Monitor Lambda and CodeBuild execution
- **CloudTrail**: Track API calls and resource access
- **AWS X-Ray**: Trace request flows (if enabled)
- **AWS Config**: Monitor configuration changes

## Getting Support

### GitHub Issues
For bugs, feature requests, and general questions:
1. **Search existing issues** to see if your question has been answered
2. **Create a new issue** with detailed information:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (AWS region, Terraform version, etc.)
   - Relevant logs or error messages

### GitHub Discussions
For questions, ideas, and community discussions:
- **Q&A**: Ask questions and get help from the community
- **Ideas**: Suggest new features or improvements
- **Show and Tell**: Share your use cases and success stories
- **General**: General discussions about the project

### Professional Support

#### AWS Support
For AWS service-related issues:
- **AWS Support Plans**: Use your existing AWS Support plan
- **AWS Forums**: Community support for AWS services
- **AWS Documentation**: Comprehensive service documentation
- **AWS Training**: Official AWS training and certification

#### Consulting Services
For implementation assistance and custom development:
- Contact us at [consulting@example.com](mailto:consulting@example.com)
- Professional services for large-scale deployments
- Custom feature development and integration
- Training and workshops for your team

## Response Times

### Community Support (GitHub Issues/Discussions)
- **Bug Reports**: We aim to respond within 3-5 business days
- **Feature Requests**: Initial response within 1 week
- **Questions**: Community members typically respond within 24-48 hours
- **Security Issues**: See [SECURITY.md](SECURITY.md) for security-specific response times

### Professional Support
- **Critical Issues**: 4-hour response time during business hours
- **High Priority**: 1 business day response time
- **Medium Priority**: 3 business days response time
- **Low Priority**: 1 week response time

## What We Need

When requesting support, please provide:

### Environment Information
- AWS region and account ID (if relevant)
- Terraform version
- Python version
- Operating system
- Browser (for web-based issues)

### Problem Details
- Clear description of the issue
- Steps to reproduce the problem
- Expected behavior vs actual behavior
- Error messages or logs
- Screenshots (if applicable)

### Configuration Information
- Terraform configuration (sanitized)
- SBOM file structure (sample)
- Environment variables
- IAM policies (if relevant)

### Logs and Diagnostics
- CloudWatch logs (Lambda, CodeBuild)
- Terraform plan/apply output
- Error messages from CLI tools
- Network connectivity information

## Contributing to Support

### Help Others
- Answer questions in GitHub Discussions
- Share your experiences and solutions
- Contribute to documentation improvements
- Report bugs and suggest enhancements

### Improve Documentation
- Fix typos and unclear instructions
- Add examples and use cases
- Create troubleshooting guides
- Translate documentation

### Code Contributions
- Fix bugs and implement features
- Improve error handling and logging
- Add tests and validation
- Optimize performance

## Support Channels Summary

| Channel | Best For | Response Time |
|---------|----------|---------------|
| GitHub Issues | Bug reports, feature requests | 3-5 business days |
| GitHub Discussions | Questions, community help | 24-48 hours |
| Documentation | Self-service troubleshooting | Immediate |
| AWS Support | AWS service issues | Per your support plan |
| Professional Support | Custom development, consulting | 4 hours - 1 week |

## Feedback

We value your feedback! Help us improve by:
- Rating our documentation and support
- Suggesting improvements to this support guide
- Sharing your use cases and success stories
- Participating in user surveys and feedback sessions

Contact us at [feedback@example.com](mailto:feedback@example.com) with your thoughts and suggestions.

---
