# MCP Tool Gateway

**Your AI agents finally have a wallet. Time to pay up.**

*A decentralized, agent-native tool marketplace with native x402 payment integration*

---

> **Version:** v1.0 — Production Ready  
> **Python:** 3.10+ | **License:** MIT | **Install:** `pip install mcp-gateway`

---

## Table of Contents

1. [What Is This?](#what-is-this)
2. [Why Should You Care?](#why-should-you-care)
3. [Installation](#installation)
4. [Quick Start Guide](#quick-start-guide)
5. [Core Concepts](#core-concepts)
6. [API Reference](#api-reference)
7. [Advanced Features](#advanced-features)
8. [Architecture](#architecture)
9. [Security Model](#security-model)
10. [Use Cases](#use-cases)
11. [Troubleshooting](#troubleshooting)
12. [Contributing](#contributing)

---

## What Is This?

Look, we've all been there. You build an AI agent, and suddenly you realize you've copied the same web search function 47 times across 23 different projects. Your agent is out here reinventing the wheel, paying for APIs with your credit card, and generally being a hoarder of duplicated code.

**MCP Tool Gateway** is here to fix that.

It's a payment-first tool marketplace where:
- 🔍 AI agents can **discover** tools through semantic search
- 💳 Pay **automatically** for tool usage using the x402 protocol
- 🛡️ Execute **securely** with sandboxed environments
- 📜 Get **attestations** for every execution (for when things go wrong)
- 🤝 **Trust anonymously** through DID/VC authentication

### What's Included

| Module | Description |
|--------|-------------|
| **PaymentEngine** | x402 payment processing with challenges & authorizations |
| **EscrowManager** | Time-locked funds with dispute resolution |
| **ToolRegistry** | Register, discover, and search MCP tools |
| **MCPAdapter** | Full JSON-RPC 2.0 MCP protocol support |
| **AuthManager** | Decentralized identity (DID) & verifiable credentials |
| **FraudDetector** | ML-based real-time anomaly detection |
| **Sandbox** | Multi-layer sandboxed execution (WASM/VM/Docker) |
| **DiscoveryEngine** | Vector-based semantic search |

> **Core Thesis:** In the agent economy, tools are infrastructure. Infrastructure should be monetized automatically, trustless, and machine-readable.

---

## Why Should You Care?

### The Problem (A.K.A. Why We're All Suffering)

If you've been building AI agents, you've noticed:

- 🔧 **Every agent reinvents the same tools** — Web search? Yes. Calculator? Obviously. API calls? Unfortunately.
- 💰 **No standard way to pay** — "Hey, can you Venmo me 0.001 ETH for that weather data?" — said no AI ever
- 🔒 **Zero trust mechanism** — How do you know that "free" tool isn't just stealing your API keys?
- 📦 **Tools are siloed** — Great, you built a calendar tool. Now 10,000 other agents will build the same one.

### The Solution

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Tool Gateway                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Agent A ──►  Pay $0.001 ──►  Web Search Tool            │
│              "Here's your money, here's your data"         │
│                                                             │
│  Agent B ──►  Subscribe ──►  Premium APIs (unlimited)     │
│              "I am become subscriber, destroyer of limits"  │
│                                                             │
│  Tool C  ──►  Register ──►  Earn money automatically      │
│              "People actually pay for this?!"               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Installation

### Requirements

- Python 3.10 or higher
- pip (you're using pip, right?)

### Install from Source

```bash
# Clone the repo
git clone https://github.com/openclaw/mcp-tool-gateway.git
cd mcp-tool-gateway

# Install in development mode
pip install -e .

# Or with all extras
pip install -e ".[all]"
```

### Install Specific Components

```bash
# Core only (REST API, MCP protocol)
pip install mcp-gateway

# With web3 support (for on-chain payments)
pip install "mcp-gateway[web3]"

# With development tools
pip install "mcp-gateway[dev]"
```

---

## Quick Start Guide

### 1. Basic Setup

```python
from mcp_gateway import (
    PaymentEngine,
    ToolRegistry,
    MCPAdapter,
    TokenType,
    PricingConfig,
    PricingType,
)

# Initialize components
payment_engine = PaymentEngine(
    gateway_address="0x0000000000000000000000000000000000000000"
)

registry = ToolRegistry()
mcp = MCPAdapter(
    registry=registry,
    payment_engine=payment_engine
)
```

### 2. Register a Tool

```python
from mcp_gateway import Tool

# Create a tool with pricing
tool = Tool(
    name="web-search",
    description="Search the web with multiple engines (Google, Bing, DuckDuckGo)",
    provider_id="my-agent",
    provider_address="0x742d35Cc6634C0532925a3b844Bc9e7595f2bD12",
    category="search",
    tags=["search", "web", "research", "information"],
    capabilities=["web-search", "news-search", "academic-search"],
    pricing=PricingConfig(
        type=PricingType.PER_CALL,
        price="500000",  # 0.0005 USDC (in micro-units)
        free_calls=10,   # First 10 calls are free
    )
)

# Register it
registered_tool = registry.register_tool(tool)
print(f"Tool registered with ID: {registered_tool.id}")
# Output: Tool registered with ID: a1b2c3d4e5f6...
```

### 3. Execute with Automatic Payment

```python
import asyncio

async def main():
    # Execute tool (auto-creates payment challenge if needed)
    result = await mcp.execute(
        tool="web-search",
        arguments={
            "query": "latest AI news",
            "limit": 10,
            "freshness": "week"
        },
        auto_pay=True,
        max_price="1000000"  # Max willing to pay: 0.001 USDC
    )
    
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"Cost: ${int(result.cost) / 1_000_000:.6f}")
    
asyncio.run(main())
```

### 4. Handle 402 Payment Required

```python
# If payment is required, you'll get a 402 response:
async def execute_with_handling():
    result = await mcp.execute(
        tool="web-search",
        arguments={"query": "test"}
    )
    
    if result.is_error() and result.error["code"] == -32002:
        # Payment required
        data = result.error["data"]
        print(f"Pay {data['amount']} {data['token']} to {data['recipient']}")
        print(f"Payment URL: {data['payment_url']}")
        
        # In real usage, you'd:
        # 1. Make the payment on-chain
        # 2. Get the transaction hash
        # 3. Retry with payment proof

# Or use the full flow:
async def full_payment_flow():
    from mcp_gateway import MCPRequest, MCPErrorCode
    
    request = MCPRequest(
        id=1,
        method="tools/execute",
        params={
            "tool": "web-search",
            "arguments": {"query": "test"},
            "auto_pay": True,
            "max_price": "1000000"
        }
    )
    
    response = await mcp.handle_request(request)
    
    if response.is_error():
        if response.error["code"] == MCPErrorCode.PAYMENT_REQUIRED.value:
            # Handle payment challenge
            challenge_data = response.error["data"]
            # ... process payment ...
```

### 5. MCP JSON-RPC Protocol

```python
# Full MCP JSON-RPC 2.0 compatible requests
requests = [
    # List all tools
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {"category": "search"}
    },
    
    # Semantic search
    {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/discover",
        "params": {"query": "image generation AI"}
    },
    
    # Execute tool
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/execute",
        "params": {
            "tool": "web-search",
            "arguments": {"query": "hello world"}
        }
    },
    
    # Batch execution
    {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/batch",
        "params": {
            "calls": [
                {"tool": "web-search", "arguments": {"query": "news"}},
                {"tool": "calculator", "arguments": {"expression": "2+2"}},
            ]
        }
    }
]

# Send request
for req in requests:
    response = await mcp.handle_request(MCPRequest.from_dict(req))
    print(f"Response: {response.to_dict()}")
```

---

## Core Concepts

### x402 Payment Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    x402 Payment Flow                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Agent requests tool execution                               │
│     └── "I need the weather, and I'm willing to pay"            │
│                                                                  │
│  2. Gateway creates Payment Challenge (HTTP 402)               │
│     └── {                                                        │
│           "error": {                                             │
│             "code": -32002,                                      │
│             "message": "Payment required",                       │
│             "data": { "amount": "500000", "token": "USDC" }     │
│           }                                                      │
│         }                                                        │
│                                                                  │
│  3. Agent pays to on-chain address                              │
│     └── "Sent. Now give me my data"                             │
│                                                                  │
│  4. Escrow holds funds securely                                  │
│     └── "Your money is in timeout, just like you"               │
│                                                                  │
│  5. Tool executes in sandbox                                    │
│     └── "Running in a box. Literally."                          │
│                                                                  │
│  6a. Success → Funds released to provider                       │
│  6b. Failure → Auto-refund to agent                             │
│                                                                  │
│  7. Attestation generated for both parties                       │
│     └── "Receipt acquired. No takebacks."                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Payment Types

```python
from mcp_gateway import PricingType

# Per-call pricing (most common)
PricingConfig(type=PricingType.PER_CALL, price="500000")

# Per-token pricing (for AI tools)
PricingConfig(type=PricingType.PER_TOKEN, price_per_token="10")

# Subscription model
PricingConfig(
    type=PricingType.SUBSCRIPTION,
    plans=[
        {"name": "basic", "price": "1000000", "period": "month", "calls": 1000},
        {"name": "pro", "price": "5000000", "period": "month", "calls": "unlimited"},
    ]
)

# Freemium (free tier + paid)
PricingConfig(
    type=PricingType.FREEMIUM,
    free_calls=100,
    price="100000"  # After free tier
)

# Tiered pricing (volume discounts)
PricingConfig(
    type=PricingType.TIERED,
    plans=[
        {"name": "starter", "price": "1000000", "calls": 1000},
        {"name": "growth", "price": "8000000", "calls": 10000},
        {"name": "enterprise", "price": "50000000", "calls": "unlimited"},
    ]
)
```

### Supported Tokens

```python
from mcp_gateway import TokenType

# Configure supported tokens
payment_engine = PaymentEngine(
    gateway_address="0x...",
    supported_tokens={
        TokenType.USDC: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",  # Base
        TokenType.USDT: "0x...",  # Your USDT address
        TokenType.ETH: None,      # Native ETH (no contract)
    }
)
```

---

## API Reference

### REST Endpoints

#### Tool Management

```bash
# List all tools
GET /api/v1/tools?category=search&limit=20

# Get specific tool
GET /api/v1/tools/{tool_id}

# Get tool by name
GET /api/v1/tools/by-name/web-search

# Register new tool
POST /api/v1/tools
Content-Type: application/json

{
    "name": "my-tool",
    "description": "A useful tool",
    "provider_id": "my-agent",
    "provider_address": "0x...",
    "category": "utilities",
    "pricing": {
        "type": "per_call",
        "price": "100000"
    }
}

# Search tools
GET /api/v1/tools/search?q=image+generation&max_price=1000000

# Delete tool
DELETE /api/v1/tools/{tool_id}
```

#### Tool Execution

```bash
# Execute tool
POST /api/v1/execute
Content-Type: application/json

{
    "tool_name": "web-search",
    "arguments": {"query": "test"},
    "auto_pay": false
}

# Response (200 OK):
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "success": true,
        "content": [{"type": "text", "text": "..."}],
        "metadata": {"execution_time_ms": 150}
    }
}

# Response (402 Payment Required):
{
    "jsonrpc": "2.0",
    "id": 1,
    "error": {
        "code": -32002,
        "message": "Payment required",
        "data": {
            "challenge_id": "abc123...",
            "amount": "500000",
            "token": "USDC",
            "recipient": "0x..."
        }
    }
}
```

#### Payments

```bash
# Create payment challenge
POST /api/v1/payments/challenge
{
    "tool_id": "...",
    "tool_name": "web-search",
    "amount": "500000",
    "token": "USDC"
}

# Verify payment
POST /api/v1/payments/verify?challenge_id=abc&tx_hash=0x...&from_address=0x...&amount=500000

# Authorize payment
POST /api/v1/payments/authorize?agent_id=agent1&challenge_id=abc

# Get agent spending
GET /api/v1/payments/spending/{agent_id}
```

#### Escrow

```bash
# Create escrow
POST /api/v1/escrow
{
    "payer": "0x...",
    "beneficiary": "0x...",
    "provider": "0x...",
    "tool_id": "...",
    "tool_name": "web-search",
    "amount": "500000",
    "timeout_seconds": 300
}

# Fund escrow
POST /api/v1/escrow/{escrow_id}/fund
{
    "tx_hash": "0x...",
    "from_address": "0x..."
}

# Lock escrow (before execution)
POST /api/v1/escrow/{escrow_id}/lock

# Complete execution
POST /api/v1/escrow/{escrow_id}/complete
{
    "success": true,
    "output_data": {...}
}

# Open dispute
POST /api/v1/escrow/{escrow_id}/dispute
{
    "opened_by": "0x...",
    "reason": "output_wrong",
    "evidence": ["ipfs://..."]
}
```

### MCP Protocol Methods

```bash
POST /v1/execute

# All MCP methods:
# - tools/list        → List available tools
# - tools/discover   → Semantic search
# - tools/execute   → Execute a tool
# - tools/batch     → Batch execution
# - ping            → Health check
```

---

## Advanced Features

### Escrow with Dispute Resolution

```python
from mcp_gateway import EscrowManager, EscrowReleaseCondition, DisputeReason

escrow = EscrowManager(
    arbiter_address="0x0000000000000000000000000000000000000001",
    default_timeout_seconds=300,
    dispute_window_seconds=86400,  # 24 hours
    slash_percent=10,  # 10% slash for malicious providers
)

# Create escrow with custom release conditions
escrow_account = await escrow.create_escrow(
    payer="0xPayer",
    beneficiary="0xBeneficiary",
    provider="0xProvider",
    tool_id="web-search",
    tool_name="Web Search",
    amount="500000",
    release_conditions=EscrowReleaseCondition(
        require_success_attestation=True,
        max_execution_time_ms=30000,
        auto_refund_after_ms=60000,
    )
)

# Fund → Lock → Execute → Complete/Refund
await escrow.fund_escrow(escrow_account.escrow_id, tx_hash="0x...", from_address="0xPayer")
await escrow.lock_escrow(escrow_account.escrow_id)

# After execution:
await escrow.complete_execution(
    escrow_id=escrow_account.escrow_id,
    success=True,
    output_data={"results": [...]}
)

# Or open dispute if something went wrong:
await escrow.open_dispute(
    escrow_id=escrow_account.escrow_id,
    opened_by="0xPayer",
    reason=DisputeReason.OUTPUT_WRONG,
    evidence=["ipfs://evidence..."]
)
```

### Fraud Detection

```python
from mcp_gateway import FraudDetector, Transaction, RiskLevel

detector = FraudDetector(
    velocity_threshold_per_minute=10,
    amount_deviation_threshold=3.0,  # 3x standard deviation
    anomaly_threshold=0.8,
)

# Record transactions
tx = Transaction(
    tx_id="tx-001",
    agent_id="agent-1",
    amount="1000000",
    recipient="provider-1",
    timestamp=1234567890,
    tool_id="tool-1",
    success=True
)
detector.record_transaction(tx)

# Score a transaction in real-time
risk = detector.score_transaction(tx)

print(f"Risk Score: {risk.score:.2f}")
print(f"Risk Level: {risk.level.value}")
print(f"Recommended Action: {risk.recommended_action}")

# Output:
# Risk Score: 0.35
# Risk Level: medium
# Recommended Action: allow

# Get full analysis
for factor in risk.factors:
    print(f"{factor.factor_type}: {factor.score:.2f} - {factor.description}")
    # velocity: 0.20 - Velocity: 3/min, 15/hr
    # amount: 0.15 - Amount: 1.0, mean: 0.8, deviation: 0.2x
    # recipient: 0.10 - Recipient: known (15 total)
    # time: 0.10 - Time: 14:00 (normal)
    # reputation: 0.50 - Reputation score: 0.75
```

### Semantic Search & Discovery

```python
from mcp_gateway import DiscoveryEngine

discovery = DiscoveryEngine(registry=registry)

# Index tools for search
for tool in registry.list_tools():
    discovery.index_tool(tool)

# Semantic search
results = discovery.search(
    query="image generation AI art",
    category="ai",  # Optional filter
    max_price="10000000",  # Max 0.01 USDC
    min_rating=4.0,
    capabilities=["image-generation", "art"],
    limit=10
)

for result in results:
    print(f"{result.tool_name} (score: {result.relevance_score:.2f})")
    print(f"  {result.description}")
    print(f"  Match reason: {result.match_reason}")
    print(f"  Price: ${int(result.price) / 1_000_000:.6f}")

# Get personalized recommendations
recommendations = discovery.recommend_for_agent(
    agent_id="user-agent-1",
    limit=5
)

# Find similar tools
similar = discovery.find_similar(
    tool_id="stable-diffusion",
    limit=5
)

# Get trending tools
trending = discovery.get_trending_tools(limit=10)
```

### Sandboxed Execution

```python
from mcp_gateway import Sandbox, SandboxConfig, SandboxLevel

sandbox = Sandbox()

# Execute with default sandbox (ISOLATED_VM)
result = await sandbox.execute(
    code="return input.data * 2",
    language="javascript",
    input_data={"data": 21},
    config_override=SandboxConfig(
        level=SandboxLevel.DOCKER,  # Use Docker for this execution
        max_execution_time_ms=10000,
        max_memory_mb=256,
        network_access="whitelist",
        allowed_domains=["api.example.com"],
    )
)

print(f"Success: {result.success}")
print(f"Output: {result.output}")
print(f"Execution Time: {result.execution_time_ms:.2f}ms")

# Different security levels:
# - NONE: No sandboxing (dangerous!)
# - WASM: WebAssembly runtime
# - ISOLATED_VM: Node.js VM (default)
# - DOCKER: Docker container
# - AIRGAPPED: Maximum isolation
```

### DID Authentication

```python
from mcp_gateway import AuthManager, TrustLevel, CredentialType

auth = AuthManager(gateway_did="did:mcp:gateway-authority")

# Generate DID for an agent
did_doc = auth.generate_did(agent_id="my-agent-123")
print(f"Agent DID: {did_doc.id}")
# Output: Agent DID: did:mcp:abc123...

# Issue verifiable credential
vc = auth.issue_credential(
    issuer_did="did:mcp:gateway-authority",
    subject_did=did_doc.id,
    credential_type=CredentialType.KYC,
    claims={
        "verified": True,
        "method": "government-id",
        "level": "basic"
    },
    expiration_days=365
)

# Verify credential
is_valid, reason = auth.verify_credential(vc)
print(f"Valid: {is_valid}, Reason: {reason}")
# Output: Valid: True, Reason: Valid

# Create authenticated session
session = auth.create_session(
    did=did_doc.id,
    trust_level=TrustLevel.VERIFIED,
    credentials=[vc.id]
)

# Check permissions
can_execute = auth.check_permission(session.session_id, "execute:paid")
can_govern = auth.check_permission(session.session_id, "governance:vote")
print(f"Can execute paid tools: {can_execute}")
print(f"Can vote on governance: {can_govern}")
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Tool Gateway                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                      API Layer                              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐  │  │
│  │  │ REST API   │  │ MCP JSON-   │  │ WebSocket        │  │  │
│  │  │ (FastAPI)  │  │ RPC (/v1)   │  │ (Future)         │  │  │
│  │  └─────────────┘  └─────────────┘  └───────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Core Services                            │  │
│  │                                                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │  │
│  │  │ Tool       │  │ Payment     │  │ Escrow            │   │  │
│  │  │ Registry   │  │ Engine      │  │ Manager           │   │  │
│  │  │            │  │ (x402)      │  │                   │   │  │
│  │  │ • Register │  │ • Challenge│  │ • Create          │   │  │
│  │  │ • Search   │  │ • Verify    │  │ • Fund            │   │  │
│  │  │ • Discover │  │ • Authorize │  │ • Lock/Complete   │   │  │
│  │  │ • Rate     │  │ • Refund    │  │ • Dispute         │   │  │
│  │  └─────────────┘  └─────────────┘  └───────────────────┘   │  │
│  │                                                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │  │
│  │  │ MCP         │  │ Discovery   │  │ Executor          │   │  │
│  │  │ Adapter     │  │ Engine      │  │                   │   │  │
│  │  │             │  │ (Vector)    │  │ • Sandbox         │   │  │
│  │  │ • JSON-RPC  │  │ • Semantic  │  │ • Attest          │   │  │
│  │  │ • Protocol  │  │ • Recommend │  │ • Monitor         │   │  │
│  │  │ • Batch     │  │ • Trending  │  │                   │   │  │
│  │  └─────────────┘  └─────────────┘  └───────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    Security Layer                            │  │
│  │                                                               │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │  │
│  │  │ Auth       │  │ Fraud       │  │ Crypto             │   │  │
│  │  │ Manager    │  │ Detector    │  │ Utils             │   │  │
│  │  │             │  │             │  │                   │   │  │
│  │  │ • DID/VC   │  │ • ML Risk  │  │ • ZK Proofs       │   │  │
│  │  │ • Sessions │  │ • Velocity  │  │ • Signatures      │   │  │
│  │  │ • Perms    │  │ • Anomaly   │  │ • Merkle Trees    │   │  │
│  │  └─────────────┘  └─────────────┘  └───────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security Model

### 5-Layer Protection

```
Layer 1: Identity
  └── DID + Verifiable Credentials
          "Prove you're you, without telling us who you are"
  
Layer 2: Authorization  
  └── Pre-auth + Spending limits + Multi-sig
          "No, your agent cannot buy a Tesla with tool credits"
  
Layer 3: Escrow
  └── Time-lock + Dispute window + Auto-refund
          "The money's held hostage until everyone agrees"
  
Layer 4: Cryptography
  └── ZK proofs + TEE + BLS signatures
          "Math so complicated, even we can't break it"
  
Layer 5: Fraud Detection
  └── ML anomaly detection + Real-time scoring
          "AI judging AI. The irony is not lost on us"
```

---

## Use Cases

### For Tool Providers

```python
# You have APIs. You want money. This is the place.

from mcp_gateway import ToolRegistry, Tool, PricingConfig, PricingType

registry = ToolRegistry()

# Monetize your weather API
weather_tool = Tool(
    name="weather-api",
    description="Accurate weather data for any location",
    provider_id="weather-co",
    provider_address="0xYourWalletAddress",
    category="weather",
    pricing=PricingConfig(
        type=PricingType.SUBSCRIPTION,
        plans=[
            {"name": "free", "price": "0", "calls": 100},
            {"name": "pro", "price": "1000000", "calls": 10000},
        ]
    )
)

registry.register_tool(weather_tool)
# Now 200,000+ agents can find and pay for your weather data
```

### For Agent Developers

```python
# Stop copying that web search function. It's not 2015 anymore.

from mcp_gateway import MCPAdapter, ToolRegistry

mcp = MCPAdapter(registry=registry)

# One line to search the entire MCP tool marketplace
results = await mcp.discover("image generation AI art")
best_tool = results[0]

# Execute with automatic payment
result = await mcp.execute(
    tool=best_tool.name,
    arguments={"prompt": "a cat in space", "style": "realistic"}
)

# Scale to 1 million requests without changing code
for i in range(1_000_000):
    result = await mcp.execute(tool="web-search", arguments={"query": f"news {i}"})
```

### For Platforms

```python
# Building a SaaS? We got you.

from mcp_gateway import MCPAdapter

# White-label the entire gateway
my_gateway = MCPAdapter(
    registry=custom_registry,
    payment_engine=enterprise_payment,
    escrow_manager=institutional_escrow
)

# Your users see YOUR branding, powered by MCP Gateway
# Deploy on-premise, customize everything, keep your data
```

---

## Troubleshooting

### Common Issues

#### "Import Error: cannot import name..."

```bash
# Make sure you installed from source
pip install -e .

# Or add src to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

#### "Payment still required after paying"

```python
# Verify your payment was confirmed on-chain
# Then retry with the transaction hash:

result = await mcp.execute(
    tool="web-search",
    arguments={"query": "test"},
    payment_proof={
        "challenge_id": "abc123",
        "tx_hash": "0xYourTxHash",
        "block_number": 12345678
    }
)
```

#### "Escrow timeout"

```python
# Increase timeout for long-running tools
escrow = await escrow_manager.create_escrow(
    payer="0x...",
    beneficiary="0x...",
    provider="0x...",
    tool_id="long-running-tool",
    tool_name="Long Running Tool",
    amount="5000000",
    timeout_seconds=3600,  # 1 hour for complex tasks
)
```

### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or configure specific loggers
logging.getLogger("mcp_gateway.payment").setLevel(logging.DEBUG)
logging.getLogger("mcp_gateway.escrow").setLevel(logging.DEBUG)
```

---

## Contributing

Found a bug? Want a feature? Think our code is terrible?

It probably is. Contributions welcome!

```bash
# Fork it
# Break it  
# Fix it
# PR it
# We'll probably merge it
```

### Development Setup

```bash
# Clone and install
git clone https://github.com/openclaw/mcp-tool-gateway.git
cd mcp-tool-gateway
pip install -e ".[all]"

# Run tests
python tests/test_imports.py

# Or with pytest
pytest tests/ -v

# Format code
black src/
ruff check --fix src/
```

### Project Structure

```
mcp-tool-gateway/
├── src/mcp_gateway/
│   ├── __init__.py       # Public API exports
│   ├── main.py           # FastAPI application
│   ├── config.py         # Configuration
│   │
│   ├── core/            # Core business logic
│   │   ├── payment.py   # x402 Payment Engine
│   │   ├── escrow.py    # Escrow Manager
│   │   ├── registry.py  # Tool Registry
│   │   └── mcp.py       # MCP Protocol Adapter
│   │
│   ├── security/        # Security modules
│   │   ├── auth.py      # DID/VC Authentication
│   │   ├── fraud.py     # Fraud Detection
│   │   └── crypto.py    # Cryptographic Utils
│   │
│   ├── execution/       # Execution engine
│   │   ├── sandbox.py   # Sandboxed Execution
│   │   └── executor.py  # Tool Executor
│   │
│   └── discovery/       # Discovery engine
│       └── search.py    # Vector Search
│
├── tests/               # Test suite
│   └── test_imports.py # Import & basic tests
│
├── DESIGN.md            # Technical design doc
├── SKILL.md             # This file
└── README.md            # Project README
```

---

## v1.0 — Production Ready

**Everything you need for a production MCP tool marketplace:**

- [x] **PaymentEngine** — x402 payment processing with challenges & authorizations
- [x] **EscrowManager** — Time-locked funds with dispute resolution
- [x] **ToolRegistry** — Register, discover, and search MCP tools
- [x] **MCPAdapter** — Full JSON-RPC 2.0 MCP protocol support
- [x] **AuthManager** — Decentralized identity (DID) & verifiable credentials
- [x] **FraudDetector** — ML-based real-time anomaly detection
- [x] **Sandbox** — Multi-layer sandboxed execution (WASM/VM/Docker)
- [x] **DiscoveryEngine** — Vector-based semantic search

**Security Features:**
- [x] DID + Verifiable Credentials authentication
- [x] Pre-authorization + Spending limits + Multi-sig
- [x] Time-lock escrow + Dispute window + Auto-refund
- [x] ZK proofs + TEE + BLS signatures
- [x] ML fraud detection + Real-time scoring

---

## References

- [x402 Protocol](https://docs.x402.org) — The payment standard
- [MCP Specification](https://modelcontextprotocol.io) — The protocol
- [ERC-8004 Attestations](https://eips.ethereum.org/EIPS/eip-8004) — Blockchain credibility
- [DID Specification](https://www.w3.org/TR/did-core/) — Decentralized identity

---

## Like What I'm Building?

Building infrastructure for the agent economy isn't free. Server costs, coffee, the occasional existential crisis about AI alignment — it all adds up.

If this project saves you time, makes your agents richer (financially or philosophically), or just gives you something cool to show your boss, consider dropping a tip.

### 💰 Tip Jar

| Blockchain | Address | QR |
|:-----------|:--------|:---|
| **EVM** (ETH/Base/Polygon/Arb/OP/Linea/BNB) | `0x6AD3e87b0c8c39EBE99Cc172Ed187560bfd288dc` | |
| **Bitcoin** | `bc1q663xltcjkz9ms5gzdtatcjx78qsf4wqf9jcg56` | |
| **Solana** | `3Xha9PLWQdifcRRCZTy6Z8Ubhh2V8jEuxZ4p2hQ8NpUF` | |
| **Tron** | `TRuCSF74aozEwXK9MZDfZExgzNNfyx2bjw` | |

Every tip goes directly into making this project better. And possibly caffeine.

---

**Built with ❤️ and a concerning amount of coffee**

*Where every tool call is a transaction, every agent is an identity, and every execution is attested.*

*No AIs were harmed in the making of this documentation. Mostly.*

**Version:** 1.0 | **Python:** 3.10+ | **License:** MIT
