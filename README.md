## Mistral-on-AWS 

![mistral-aws](/notebooks/imgs/mistralaws.png)

A collection of notebooks and samples to get started with Mistral models on AWS.
Open a PR if you would like to contribute! :twisted_rightwards_arrows:

## What's New :star::star:

### New Model Launches on Amazon Bedrock

#### Mistral Large 3 (675B)
Mistral's flagship frontier model is now available on Amazon Bedrock! A sparse Mixture-of-Experts architecture with **41B active parameters** out of **675B total**, delivering frontier-level multimodal performance under the Apache 2.0 license.

- [Mistral Large 3 Capabilities Guide](Mistral%20Large%203/Mistral_Large_3_Capabilities.ipynb) - Text generation, multilingual (40+ languages), vision, and complex reasoning

| Specification | Details |
|--------------|----------|
| Model ID | `mistral.mistral-large-3-675b-instruct` |
| Architecture | Sparse MoE (41B active / 675B total) |
| Multimodal | Yes (Text + Vision) |
| License | Apache 2.0 |

#### Ministral Models (3B, 8B, 14B)
Compact yet powerful models optimized for edge deployment and cost-efficient inference, now available on Amazon Bedrock!

- [Ministral Capabilities Guide](Ministral/Ministral_Capabilities.ipynb) - Model comparison, text generation, reasoning, code, JSON output, and vision

| Model | Model ID | Best For |
|-------|----------|----------|
| **Ministral 3B** | `mistral.ministral-3-3b-instruct` | Edge devices, ultra-low latency |
| **Ministral 8B** | `mistral.ministral-3-8b-instruct` | Balanced performance/efficiency |
| **Ministral 14B** | `mistral.ministral-3-14b-instruct` | Complex reasoning, code generation |

#### Building AI Agents with Strands
Learn how to build production-ready AI agent systems using the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) with Mistral models on Bedrock.

- [Strands Agents with Mistral](Ministral/Strands_Agents_Mistral.ipynb) - Multi-agent orchestration, streaming, hooks, session persistence, and expert panels

---

### Model Capabilities & Use Cases

#### Pixtral
- [Comprehensive Capabilities Guide](Pixtral-samples/Pixtral_capabilities.ipynb)
- Deployment Options:
  - [SageMaker Real-time Inference](Deployment/SageMaker/Pixtral-12b-LMI-SageMaker-realtime-inference.ipynb)
  - [Bedrock Marketplace Integration](Deployment/Bedrock%20Marketplace/Deploy-Pixtral12B-from-Bedrock-Marketplace.ipynb)

#### Mistral Models
- **Large 3**: [Frontier Multimodal Model Guide](Mistral%20Large%203/Mistral_Large_3_Capabilities.ipynb) - 675B MoE with vision
- **Small 3**: [Model Overview & Capabilities](Mistral%20Small%203/Mistral_small_3.ipynb)
- **NeMo**: [Comparative Analysis & Benchmarks](Mistral%20NeMo/NeMo_comparative_analysis.ipynb)
- **Ministral**: [3B, 8B, 14B Models Guide](Ministral/Ministral_Capabilities.ipynb) - Compact models for edge and cost-efficient deployment

> 💡 **Note**: All notebooks include detailed explanations, code samples, and best practices for implementation.



## Getting Started :electric_plug:

1. Please visit [Amazon Bedrock user guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) on how to enable model access.
2. The notebooks are executed from SageMaker studio with Data Science 3.0 image.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## Distributors

- AWS
- Mistral 

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
