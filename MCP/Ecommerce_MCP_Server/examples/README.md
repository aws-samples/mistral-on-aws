# E-Commerce MCP Server - Examples

Python examples for integrating with the E-Commerce MCP Server using Strands agents and other frameworks.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your LLM API key (choose one)
export ANTHROPIC_API_KEY=your-key    # For Claude
export OPENAI_API_KEY=your-key       # For GPT
export AWS_PROFILE=your-profile      # For Bedrock

# Run the demo
python strands_agent_example.py
```

## Examples

### 1. `strands_agent_example.py` - Comprehensive Example

Full-featured example with:
- MCP authentication helper class
- Complete MCP client wrapper
- Strands agent with all 5 tools
- Interactive chat mode
- Direct client demo (no Strands required)

```bash
# Run interactive mode
python strands_agent_example.py chat

# Run direct client demo
python strands_agent_example.py demo
```

### 2. `strands_mcp_integration.py` - Integration Patterns

Shows three different integration approaches:
- **Option 1:** Native MCP client (async)
- **Option 2:** Custom tool definitions (recommended)
- **Option 3:** AWS Bedrock integration

```bash
# Run demo mode
python strands_mcp_integration.py

# Run interactive mode
python strands_mcp_integration.py interactive
```

## MCP Server Configuration

Default endpoint: `http://localhost:8000` (set MCP_SERVER_URL for remote server)

Override with environment variables:
```bash
export MCP_SERVER_URL=http://your-server:8000
export DEMO_EMAIL=demo1@example.com
export DEMO_PASSWORD=Demo123!
```

## Available Tools

| Tool | Auth | Description |
|------|------|-------------|
| `search_products` | No | Search by query, category, price range |
| `order_product` | Yes | Place orders |
| `write_product_review` | Yes | Submit reviews |
| `get_order_history` | Yes | View past orders |
| `initiate_return` | Yes | Process returns |

## Example Conversations

```
User: Search for laptops under $1500
Assistant: I found 2 laptops:
1. Rodriguez Laptop Classic - $989.26 (prod-e9075764)
2. Riggs Laptop Standard - $1138.15 (prod-7f453c75)

User: Order the first one
Assistant: Order placed successfully!
- Order ID: ord-abc123
- Total: $989.26
- Estimated delivery: 3 days

User: Write a 5-star review
Assistant: Review submitted!
- Review ID: rev-xyz789
- Rating: 5 stars
```

## Troubleshooting

### "Server unreachable"
```bash
# Test connection
curl http://localhost:8000/health
```

### "Authentication failed"
```bash
# Test login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo1@example.com", "password": "Demo123!"}'
```

### "Strands not installed"
```bash
pip install strands-agents strands-agents-tools
```

## Related Documentation

- [USER_GUIDE.md](../USER_GUIDE.md) - Full deployment guide
- [QUICK_START.md](../QUICK_START.md) - Quick start guide
- [Strands Documentation](https://docs.strands.dev) - Strands framework docs
