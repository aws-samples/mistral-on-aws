# Singapore Enablement Workshop

## Overview

This workshop provides hands-on experience with Mistral models on AWS, covering advanced topics including optical character recognition (OCR), single-agent security analysis, and sophisticated multi-agent workflow orchestration using the Strands Agents framework.

## Notebooks

### 1. Agentic Use Cases with Mistral (`Agentic_Use_Cases_Mistral.ipynb`)

Learn to build intelligent security analysis systems using **Strands Agents** framework with Mistral's **Pixtral Large** model on Amazon Bedrock.

**Part 1: Single-Agent Security Analysis**
- Analyze CloudWatch logs for security incidents
- Review AWS SecurityHub compliance findings
- Detect performance anomalies in metrics data
- Correlate events across multiple data sources
- Provide actionable remediation recommendations

**Part 2: Multi-Agent Workflow Orchestration**
- **Triage Agent**: Routes investigations to appropriate specialists
- **Log Analysis Agent**: Focuses on CloudWatch security events
- **Compliance Agent**: Reviews SecurityHub findings
- **Metrics Agent**: Detects performance anomalies
- **Remediation Agent**: Synthesizes findings into action plans

**Key Capabilities:**
- Tool functions with `@tool` decorator for agent-callable Python functions
- Sequential orchestration with agents building upon each other's findings
- Conditional routing based on investigation type (log_analysis, compliance_review, metrics_analysis, full_audit)
- State management tracking findings across multiple agent executions
- Synthesis combining insights from all specialists

### 2. Mistral OCR (`Mistral_OCR.ipynb`)

Demonstrates Optical Character Recognition using Mistral OCR model (mistral-ocr-2505) on Amazon SageMaker.

**Features:**
- Extract text from scanned documents, receipts, and forms
- Process handwritten notes and whiteboard images
- Handle multi-page PDF documents
- Multi-language support (French, Arabic, and more)
- Structured markdown output with embedded images

**Use Cases:**
- Document digitization and processing
- Invoice batch processing with structured data extraction
- Handwriting recognition from whiteboards and notes
- Document understanding pipelines combining OCR with LLMs (Mistral Small 3.0)

## Setup

### Prerequisites
- AWS account with Amazon Bedrock access
- Python 3.8+
- Jupyter Notebook or JupyterLab

### Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Configure AWS credentials:

```bash
aws configure
```

3. Ensure you have access to the following models in Amazon Bedrock:
   - `us.mistral.pixtral-large-2502-v1:0` (for Agentic use cases)
   - Mistral OCR model deployment on SageMaker (for OCR notebook)

## Requirements

Core dependencies:
- `boto3>=1.26.0` - AWS SDK for Python
- `sagemaker>=2.150.0` - Amazon SageMaker Python SDK
- `pandas>=1.5.0` - Data manipulation and analysis
- `numpy>=1.24.0` - Numerical computing
- `strands-agents>=0.1.6` - Strands Agents framework for multi-agent orchestration
- `ipython>=8.0.0` - Interactive Python shell and Jupyter support

See `requirements.txt` for the complete list.

## Usage

Open the notebooks in Jupyter or JupyterLab:

```bash
jupyter notebook
```

Then navigate to:
- `Agentic_Use_Cases_Mistral.ipynb` for multi-agent security workflows
- `Mistral_OCR.ipynb` for OCR demonstrations

Follow the step-by-step instructions in each notebook to explore the capabilities of Mistral models on AWS.

## Additional Resources

- `NOTEBOOK_REVIEW.md` - Comprehensive review of the Agentic Use Cases notebook structure and data flow
- `images/` - Sample images for OCR processing (invoices, whiteboards, documents)
- `docs/` - Additional documentation files
