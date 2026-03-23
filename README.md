# MCP Tool Gateway

A decentralized, agent-native tool marketplace with x402 payment integration.

**Status:** MVP Development  
**Author:** @openclaw-rhantolk

---

## Overview

MCP Tool Gateway enables AI agents to discover, authenticate, pay for, and execute tools programmatically. Built on principles similar to x402 (HTTP 402 Payment Required), it extends the payment-by-default model to the MCP (Model Context Protocol) ecosystem.

**Core Thesis:** In the agent economy, tools are infrastructure. Infrastructure should be monetized automatically, trustless, and machine-readable.

---

## Features

### Core
- **x402 Payment Engine** - HTTP 402 Payment Required pattern
- **Tool Registry** - Register, discover, and manage MCP tools
- **MCP Protocol Adapter** - JSON-RPC 2.0 compatible
- **Escrow Manager** - Secure fund holding with dispute resolution

### Security (v1.0 Enhanced)
- **DID Authentication** - Decentralized Identity
- **Verifiable Credentials** - Trust verification
- **Fraud Detection** - ML-based anomaly detection
- **Cryptographic Utilities** - ZK proofs, signatures, Merkle trees

### Execution
- **Multi-level Sandboxing** - WASM, VM, Docker, Air-gapped
- **Attestation System** - Cryptographic execution proof
- **Tool Composition** - Chain multiple tools

---

## Quick Start

### Installation

```bash
# Clone repository
cd mcp-tool-gateway

# Install dependencies
pip install -e .

# Or install from source
pip install poetry
poetry install
```

### Run Server

```bash
# Development
python -m mcp_gateway.main

# Or with uvicorn
uvicorn mcp_gateway.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Tests

```bash
pytest tests/
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Tool Gateway                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Tool       │  │ Auth       │  │ Payment                 │  │
│  │ Registry   │  │ Layer      │  │ Engine                  │  │
│  │            │  │ (DID/VC)   │  │ (x402 + Escrow)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Executor   │  │ Discovery  │  │ Security                │  │
│  │ Pool       │  │ Engine     │  │ (Fraud + Crypto)        │  │
│  │ (Sandbox)  │  │ (Vector)   │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### MCP Protocol
```
POST /v1/execute          # MCP JSON-RPC endpoint
```

### Tool Management
```
GET    /api/v1/tools       # List tools
POST   /api/v1/tools       # Register tool
GET    /api/v1/tools/{id}  # Get tool
DELETE /api/v1/tools/{id}  # Delete tool
GET    /api/v1/tools/search # Search tools
GET    /api/v1/categories  # Get categories
```

### Tool Execution
```
POST   /api/v1/execute     # Execute tool
```

### Payments
```
POST   /api/v1/payments/challenge  # Create payment challenge
POST   /api/v1/payments/verify     # Verify payment
POST   /api/v1/payments/authorize  # Authorize payment
GET    /api/v1/payments/spending/{agent_id} # Get spending
```

### Escrow
```
POST   /api/v1/escrow           # Create escrow
GET    /api/v1/escrow/{id}      # Get escrow
POST   /api/v1/escrow/{id}/fund    # Fund escrow
POST   /api/v1/escrow/{id}/lock    # Lock escrow
POST   /api/v1/escrow/{id}/complete # Complete execution
POST   /api/v1/escrow/{id}/dispute  # Open dispute
```

---

## Usage Examples

### Register a Tool

```python
import httpx

# Create tool
response = httpx.post("http://localhost:8000/api/v1/tools", json={
    "name": "web-search",
    "description": "Search the web",
    "provider_id": "my-agent",
    "provider_address": "0x1234...",
    "category": "search",
    "pricing": {
        "type": "per_call",
        "price": "500000"  # 0.0005 USDC
    }
})
tool = response.json()
```

### Execute Tool with Payment

```python
# Execute tool
response = httpx.post("http://localhost:8000/api/v1/execute", json={
    "tool_name": "web-search",
    "arguments": {"query": "latest AI news"},
    "auto_pay": True,
    "max_price": "1000000"
})

if response.status_code == 402:
    # Payment required
    challenge = response.json()["error"]["data"]
    print(f"Pay {challenge['amount']} USDC to {challenge['recipient']}")
else:
    result = response.json()
    print(result["result"])
```

### MCP JSON-RPC

```python
# MCP request
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/execute",
    "params": {
        "tool": "web-search",
        "arguments": {"query": "hello"}
    }
}

response = httpx.post("http://localhost:8000/v1/execute", json=request)
```

---

## Configuration

Create `.env` file:

```env
# App
DEBUG=true
HOST=0.0.0.0
PORT=8000

# Network
NETWORK=base-sepolia
RPC_URL=https://sepolia.base.org

# Payment
PAYMENT_TOKEN=USDC
PAYMENT_TOKEN_ADDRESS=0x036CbD53842c5426634e7929541eC2318f3dCF7e

# Security
HIGH_VALUE_THRESHOLD=100.0
MAX_DAILY_SPENT=1000.0

# Escrow
ESCROW_TIMEOUT=300
DISPUTE_WINDOW=86400
```

---

## Project Structure

```
mcp-tool-gateway/
├── src/mcp_gateway/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── config.py            # Configuration
│   ├── core/
│   │   ├── payment.py       # x402 Payment Engine
│   │   ├── escrow.py        # Escrow Manager
│   │   ├── registry.py      # Tool Registry
│   │   └── mcp.py           # MCP Protocol
│   ├── security/
│   │   ├── auth.py          # DID/VC Auth
│   │   ├── fraud.py         # Fraud Detection
│   │   └── crypto.py        # Cryptography
│   ├── execution/
│   │   ├── sandbox.py       # Sandboxing
│   │   └── executor.py      # Tool Executor
│   └── discovery/
│       └── search.py        # Vector Search
├── tests/
├── examples/
└── contracts/               # Smart contracts (future)
```

---

## Roadmap

### v0.1 (Current) - MVP
- [x] Core payment engine
- [x] Basic tool registry
- [x] Simple MCP adapter
- [x] In-memory escrow
- [x] Basic API

### v0.2 - Security
- [ ] DID/VC authentication
- [ ] Fraud detection integration
- [ ] Rate limiting

### v0.3 - Advanced Execution
- [ ] Sandbox integration
- [ ] Attestation system
- [ ] Tool composition

### v1.0 - Production
- [ ] On-chain registry
- [ ] Real payment integration
- [ ] Distributed execution

---

## References

- [x402 Protocol](https://docs.x402.org)
- [MCP Specification](https://modelcontextprotocol.io)
- [ERC-8004 Attestations](https://eips.ethereum.org/EIPS/eip-8004)

---
## License

MIT
