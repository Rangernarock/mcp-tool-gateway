
# MCP Tool Gateway

**Your AI agents finally have a wallet. Time to pay up.**

A decentralized, agent-native tool marketplace with native x402 payment integration.

## What Is This?

MCP Tool Gateway is a payment-first tool marketplace where AI agents can discover, pay for, and execute tools automatically using the x402 protocol.

## Features

- PaymentEngine - x402 payment processing
- EscrowManager - Time-locked funds with dispute resolution
- ToolRegistry - Register, discover, and search MCP tools
- MCPAdapter - Full JSON-RPC 2.0 support
- AuthManager - DID + Verifiable Credentials
- FraudDetector - ML-based anomaly detection
- Sandbox - WASM/VM/Docker execution
- DiscoveryEngine - Vector-based semantic search

## Quick Start

```python
pip install mcp-gateway

from mcp_gateway import PaymentEngine, ToolRegistry, MCPAdapter

payment_engine = PaymentEngine()
registry = ToolRegistry()
mcp = MCPAdapter(registry=registry, payment_engine=payment_engine)
```

## Security

- DID + Verifiable Credentials authentication
- Pre-authorization + Spending limits + Multi-sig
- Time-lock escrow + Dispute window + Auto-refund
- ZK proofs + TEE + BLS signatures
- ML fraud detection + Real-time scoring

## v1.0 - Production Ready

All features implemented and tested.

## License

MIT
