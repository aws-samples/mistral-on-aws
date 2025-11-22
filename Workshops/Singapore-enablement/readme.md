# Mistral on AWS - Singapore Enablement Workshop

This workshop provides hands-on experience with Mistral AI models on AWS, covering OCR, agentic workflows, Bedrock integration, and fine-tuning.

## Workshop Structure

### Notebook 01a: Introduction to Mistral OCR (Workshop Studio)
**File:** `01a-intro-to-mistral-ocr-workshop.ipynb`

Learn how to use Mistral's OCR capabilities in a Workshop Studio environment with cross-account access to a pre-deployed OCR endpoint.

**Topics Covered:**
- Cross-account SageMaker endpoint access
- Document processing with Mistral OCR
- Image-to-text extraction
- Practical OCR use cases

**Prerequisites:**
- Workshop Studio account
- No additional setup required

---

### Notebook 01b: Introduction to Mistral OCR (Own Account)
**File:** `01b-intro-to-mistral-ocr-own-account.ipynb`

Deploy and use Mistral OCR in your own AWS account.

**Topics Covered:**
- Deploying Mistral OCR endpoint
- Document processing workflows
- Cost optimization strategies

**Prerequisites:**
- AWS account with SageMaker access
- Sufficient service quotas for GPU instances

---

### Notebook 02: Agentic Use Cases with Mistral
**File:** `02-Agentic-Use-Cases-Mistral.ipynb`

Build intelligent AI agents using Mistral models and the Strands framework.

**Topics Covered:**
- Agent architecture patterns
- Tool calling and function execution
- Multi-step reasoning workflows
- Practical agent implementations

**Prerequisites:**
- Completed Notebook 01
- Understanding of AI agent concepts

---

### Notebook 03: Mistral Models on Amazon Bedrock
**File:** `03-mistral-models-on-bedrock.ipynb`

Explore Mistral models available through Amazon Bedrock.

**Topics Covered:**
- Bedrock API integration
- Model comparison and selection
- Streaming responses
- Cost optimization

**Prerequisites:**
- Bedrock model access enabled
- IAM permissions for Bedrock

---

### Notebook 04: Fine-tuning Mistral on SageMaker
**File:** `04-mistral-finetuning-sagemaker.ipynb`

Learn how to fine-tune Mistral models using SageMaker Training Jobs.

**Topics Covered:**
- Dataset preparation for fine-tuning
- LoRA (Low-Rank Adaptation) configuration
- SageMaker training job setup
- Model deployment and testing

**Prerequisites:**
- Understanding of fine-tuning concepts
- SageMaker training job permissions
- GPU instance access (ml.g5.2xlarge or similar)

**Key Features:**
- No SageMaker Domain/Studio required
- Works within Workshop Studio constraints
- Uses efficient LoRA fine-tuning
- Simple training job approach

---

## ⚠️ Important: Workshop Studio Limitations

**If you're using AWS Workshop Studio**, please read [WORKSHOP_STUDIO_LIMITATIONS.md](WORKSHOP_STUDIO_LIMITATIONS.md) first!

**Key limitations:**
- ❌ Cannot request GPU quota increases (blocked by SCPs)
- ⚠️ Limited GPU instance availability (may be 0 quota)
- ⏰ Time-limited access (4-8 hours)
- 💡 **Solution:** Use available instances (ml.g5.xlarge, ml.g4dn.xlarge) or complete notebooks 01-03

**Quick fix for Notebook 04:**
```python
# Try these instance types in order:
selected_instance = instance_options[1]  # ml.g5.xlarge
# or
selected_instance = instance_options[3]  # ml.g4dn.xlarge
```

---

## Setup Instructions

### For Workshop Studio

1. Launch the CloudFormation stack using `ocr-workshop.yaml`
2. Wait for the SageMaker notebook instance to be created
3. Open JupyterLab from the SageMaker console
4. Navigate to `mistral-on-aws/Workshops/Singapore-enablement/`
5. Start with notebook 01a
6. **For Notebook 04:** See [QUOTA_SOLUTIONS.md](QUOTA_SOLUTIONS.md) if you get quota errors

### For Your Own AWS Account

1. Ensure you have the necessary IAM permissions (see `participant_iam_policy.json`)
2. Launch a SageMaker notebook instance or use SageMaker Studio
3. Clone this repository
4. Install required packages: `pip install -r requirements.txt`
5. Start with notebook 01b

---

## Required Permissions

The workshop requires the following AWS permissions:

- **SageMaker:** Create/describe/invoke endpoints, training jobs
- **Bedrock:** Invoke models, list foundation models
- **S3:** Read/write to SageMaker default bucket
- **IAM:** PassRole for SageMaker execution
- **CloudWatch:** Read logs
- **ECR:** Pull container images

See `participant_iam_policy.json` for the complete policy.

---

## Cost Considerations

**Estimated Costs (per hour):**
- SageMaker Notebook (ml.t3.xlarge): ~$0.23/hour
- SageMaker Endpoint (ml.g5.2xlarge): ~$1.52/hour
- Bedrock API calls: Pay per token
- Training Job (ml.g5.2xlarge): ~$1.52/hour

**Cost Optimization Tips:**
- Stop notebook instances when not in use
- Delete endpoints after testing
- Use Bedrock for inference when possible (no infrastructure costs)
- Monitor CloudWatch for usage patterns

---

## Troubleshooting

### Quick Fixes

**Issue:** PyArrow build error (CMake)
- **Solution:** `pip install --only-binary=:all: -r requirements.txt`

**Issue:** GPU quota exceeded (ResourceLimitExceeded)
- **Solution:** Try `ml.g5.xlarge` or `ml.g4dn.xlarge` instead
- See [INSTANCE_SELECTION_GUIDE.md](INSTANCE_SELECTION_GUIDE.md)

**Issue:** "Unable to assume role"
- **Solution:** Verify IAM permissions and trust relationships

**Issue:** "Model not found" in Bedrock
- **Solution:** Enable model access in Bedrock console

**Issue:** "Training job failed"
- **Solution:** Check CloudWatch logs for detailed error messages

### Comprehensive Guides

- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Complete troubleshooting guide
- **[INSTANCE_SELECTION_GUIDE.md](INSTANCE_SELECTION_GUIDE.md)** - GPU instance selection
- **[FACILITATOR_GUIDE.md](FACILITATOR_GUIDE.md)** - Workshop facilitation guide

---

## Additional Resources

- [Mistral AI Documentation](https://docs.mistral.ai/)
- [Amazon SageMaker Documentation](https://docs.aws.amazon.com/sagemaker/)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Mistral on AWS GitHub Repository](https://github.com/aws-samples/mistral-on-aws)

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review CloudWatch logs for detailed error messages
3. Consult the AWS documentation links
4. Open an issue on the GitHub repository

---

## License

This workshop is provided under the MIT-0 License. See the LICENSE file for details.
