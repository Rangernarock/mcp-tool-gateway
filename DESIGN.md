# MCP Tool Gateway - Technical Design Document

**Version:** 1.0.0  
**Author:** @openclaw-rhantolk  
**Date:** 2026-03-22  
**Status:** Design Draft

---

## Executive Summary

The MCP Tool Gateway is a decentralized, agent-native tool marketplace that enables AI agents to discover, authenticate, pay for, and execute tools programmatically. Built on principles similar to x402 (HTTP 402 Payment Required), it extends the payment-by-default model to the MCP (Model Context Protocol) ecosystem.

**Core Thesis:** In the agent economy, tools are infrastructure. Infrastructure should be monetized automatically, trustless, and machine-readable.

---

## 1. Architecture Overview

### 1.1 System Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Tool Gateway                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Tool       │  │ Auth       │  │ Payment                 │  │
│  │ Registry   │  │ Layer      │  │ Engine                  │  │
│  │ (On-chain) │  │ (Verif.)   │  │ (x402 + Escrow)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Executor   │  │ Discovery  │  │ Reputation              │  │
│  │ Pool       │  │ Engine     │  │ System                 │  │
│  │ (Sandbox)  │  │ (Vector)   │  │ (ERC-8004)             │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │           MCP Protocol Adapter Layer                       │  │
│  │  (Anthropic-compatible / OpenAI-compatible / Custom)      │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow

```
Agent A                    Gateway                    Tool Provider
   │                         │                            │
   │─── Discover Request ────▶│                            │
   │◀─── Tool Catalog ───────│                            │
   │                         │                            │
   │─── Execute Request ─────▶│                            │
   │   + Payment Proof ─────▶│                            │
   │                         │─── Verify Payment ────────▶│
   │                         │◀─── Payment Confirmed ────│
   │                         │                            │
   │                         │─── Tool Execution ────────▶│
   │                         │◀─── Result ──────────────│
   │◀─── Result ────────────│                            │
```

---

## 2. Core Components

### 2.1 Tool Registry (On-Chain)

All tools are registered on-chain for immutability and trust.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IToolRegistry {
    struct Tool {
        bytes32 id;
        address provider;
        string name;
        string description;
        bytes32 schemaHash;        // IPFS CID of input/output schema
        uint256 pricePerCall;
        address acceptedToken;      // USDC, USDT, or custom
        uint256 dailyQuota;
        uint256 usageCount;
        bool isActive;
        uint256 rating;
        bytes32 category;
    }

    event ToolRegistered(bytes32 indexed id, address indexed provider);
    event ToolUpdated(bytes32 indexed id);
    event ToolDisabled(bytes32 indexed id);

    function registerTool(Tool calldata tool) external returns (bytes32);
    function executeTool(bytes32 toolId, bytes calldata input) 
        external payable returns (bytes memory);
    function getTool(bytes32 id) external view returns (Tool memory);
    function getToolsByCategory(bytes32 category) external view returns (bytes32[] memory);
}
```

### 2.2 MCP Protocol Adapter

Supports multiple MCP client implementations:

```typescript
// Core MCP types
interface MCPRequest {
  jsonrpc: "2.0";
  id: string | number;
  method: string;
  params?: {
    name?: string;
    arguments?: Record<string, unknown>;
  };
}

interface MCPResponse {
  jsonrpc: "2.0";
  id: string | number;
  result?: {
    content: Array<{ type: "text"; text: string }>;
    isError?: boolean;
  };
  error?: {
    code: number;
    message: string;
    data?: unknown;
  };
}

// Gateway-specific extensions
interface MCPPaymentRequest extends MCPRequest {
  params: {
    payment: {
      toolId: string;
      maxPrice: string;
      paymentProof?: string;      // tx hash or proof
    };
    name: string;
    arguments: Record<string, unknown>;
  };
}
```

### 2.3 Payment Engine

Extended x402 protocol with additional features:

```typescript
interface PaymentEngine {
  // Standard x402
  parseChallenge(headers: Headers): PaymentChallenge | null;
  createChallenge(tool: Tool, requester: string): PaymentChallenge;
  
  // Escrow support
  createEscrow(params: {
    toolId: string;
    amount: string;
    timeout: number;           // Auto-refund if not executed
    agentId: string;
  }): Promise<Escrow>;

  // Subscription support
  checkSubscription(agentId: string, toolId: string): Promise<{
    active: boolean;
    remainingCalls: number;
    expiresAt: number;
  }>;

  // Multi-token support
  supportedTokens: Map<string, TokenConfig>;
  getBestToken(tokenIn: string, tokenOut: string): string;
}
```

### 2.4 Execution Engine

Sandboxed tool execution with resource limits:

```typescript
interface ExecutionEngine {
  // Resource limits per execution
  limits: {
    maxExecutionTimeMs: number;      // Default: 30000
    maxMemoryMb: number;            // Default: 512
    maxNetworkCalls: number;         // Default: 10
    maxTokens: number;              // Default: 8000
    allowedDomains: string[];        // For HTTP calls
  };

  // Sandbox options
  sandboxType: "wasm" | "docker" | "isolated-vm";
  
  // Execution
  execute(params: {
    tool: Tool;
    input: unknown;
    payment: PaymentConfirmation;
  }): Promise<ExecutionResult>;
}

interface ExecutionResult {
  success: boolean;
  output?: unknown;
  error?: {
    code: string;
    message: string;
    retriesLeft: number;
  };
  metrics: {
    executionTimeMs: number;
    tokensUsed: number;
    memoryUsedMb: number;
  };
  auditId: string;                 // For dispute resolution
}
```

### 2.5 Discovery Engine

Vector-based semantic search with filters:

```typescript
interface DiscoveryEngine {
  // Embedding model (configurable)
  embeddingModel: "text-embedding-3-small" | "e5-mistral-7b" | "local";

  // Index all registered tools
  async indexTool(tool: Tool): Promise<void>;
  async removeTool(toolId: string): Promise<void>;

  // Semantic search
  async search(query: string, filters?: {
    category?: string;
    maxPrice?: string;
    minRating?: number;
    provider?: string;
    capabilities?: string[];      // e.g., ["image-generation", "web-search"]
  }): Promise<SearchResult[]>;

  // Recommendations
  async recommendForAgent(agentProfile: AgentProfile): Promise<Tool[]>;
}
```

### 2.6 Reputation System

ERC-8004 inspired with agent-specific metrics:

```typescript
interface ReputationSystem {
  // For tool providers
  recordToolExecution(params: {
    toolId: string;
    success: boolean;
    userRating?: number;           // 1-5
    executionTimeMs: number;
    outputQuality?: number;         // AI-evaluated
  }): Promise<void>;

  getToolReputation(toolId: string): Promise<{
    score: number;                 // 0-100
    totalExecutions: number;
    successRate: number;
    avgExecutionTime: number;
    ratings: RatingDistribution;
    trend: "rising" | "stable" | "declining";
  }>;

  // For agents (trust score)
  getAgentTrust(agentId: string): Promise<{
    score: number;
    totalPayments: number;
    onTimeRate: number;
    disputeRate: number;
    tier: "new" | "trusted" | "premium";
  }>;
}
```

---

## 3. Advanced Features

### 3.1 Tool Composition

Chain multiple tools in a single transaction:

```typescript
interface ToolComposer {
  // Define a pipeline
  createPipeline(params: {
    name: string;
    steps: Array<{
      toolId: string;
      inputMapping: Record<string, string>;  // map previous output to input
      condition?: {
        field: string;
        operator: "eq" | "neq" | "gt" | "exists";
        value: unknown;
      };
    }>;
  }): Promise<Pipeline>;

  // Execute with atomic payment
  executePipeline(pipelineId: string, initialInput: unknown): Promise<{
    results: unknown[];
    totalCost: string;
    executionGraph: ExecutionGraph;   // For debugging
  }>;

  // Optimize execution (parallel where possible)
  optimize(pipelineId: string): Pipeline;
}
```

### 3.2 Tool Versioning

```
Tool v1.0 ──▶ Tool v1.1 ──▶ Tool v2.0
   │            │            │
   deprecated   stable       experimental
   (still works) (supported) (beta)
```

```typescript
interface ToolVersioning {
  publishVersion(params: {
    toolId: string;
    version: string;           // semver
    changelog: string;
    breaking: boolean;
    schema: JsonSchema;
    code: string | IPFS_CID;
  }): Promise<void>;

  getVersion(toolId: string, version: string): Promise<ToolVersion>;
  getLatestStable(toolId: string): Promise<ToolVersion>;
  deprecateVersion(toolId: string, version: string): Promise<void>;
}
```

### 3.3 Tool Dependencies

Declare and manage dependencies:

```typescript
interface ToolDependencies {
  // e.g., "web-scraper" depends on "browser-automation"
  dependencies: Map<string, {
    toolId: string;
    versionRange: string;      // semver range
    optional: boolean;
  }>;

  // Auto-install dependencies when tool is used
  async resolveAndInstall(toolId: string): Promise<DependencyGraph>;
}
```

### 3.4 Streaming Responses

For long-running tools:

```typescript
interface StreamingExecution {
  // SSE or WebSocket based
  async executeStreaming(params: {
    toolId: string;
    input: unknown;
    payment: PaymentConfirmation;
  }): AsyncGenerator<StreamingChunk>;

  // Chunk structure
  chunk: {
    type: "progress" | "output" | "error" | "complete";
    data: unknown;
    progress?: {
      current: number;
      total: number;
      message: string;
    };
  };
}
```

### 3.5 Distributed Execution

Multiple executor nodes with load balancing:

```typescript
interface DistributedExecutor {
  // Node registration
  registerNode(params: {
    capabilities: string[];
    maxConcurrency: number;
    regions: string[];
    pricing: Record<string, string>;
  }): Promise<NodeCredentials>;

  // Geographic routing
  routeRequest(params: {
    toolId: string;
    requesterRegion: string;
    maxLatency: number;
  }): Promise<ExecutorNode>;

  // Consensus for critical executions
  executeWithConsensus(params: {
    toolId: string;
    input: unknown;
    consensusRequired: number;     // e.g., 2-of-3 nodes
    nodes: ExecutorNode[];
  }): Promise<ConsensusResult>;
}
```

---

## 4. Security Architecture

### 4.1 Threat Model

| Threat | Mitigation |
|--------|------------|
| Tool impersonation | On-chain verification + code signing |
| Input injection | Sandboxed execution + input validation |
| Output manipulation | Cryptographic proofs + attestation |
| Payment fraud | Escrow + dispute resolution |
| Rate limit bypass | Per-agent throttling + reputation gates |
| Tool scraping | Watermarking + access patterns |
| Double-spending | Transaction ordering + merkle proofs |
| Payment replay | Nonce tracking + expiry timestamps |
| Front-running | Commit-reveal scheme + private transactions |
| Fund drainage | Multi-sig + withdrawal limits |
| Sybil attacks | Identity verification + stake requirements |

---

### 4.2 Multi-Layer Payment Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 PAYMENT SECURITY LAYERS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Layer 1: Identity & Access Control                              │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  • Agent identity verification (DID + Verifiable Creeds) │  │
│  │  • Multi-factor authentication for high-value payments    │  │
│  │  • Rate limiting per agent + per IP                       │  │
│  │  • Device fingerprinting + anomaly detection              │  │
│  └─────────────────────────────────────────────────────────┘     │
│                              │                                   │
│                              ▼                                   │
│  Layer 2: Payment Authorization                                 │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  • Pre-authorization with hold (like credit card auth)   │  │
│  │  • Spending limits (daily/weekly/monthly/cumulative)      │  │
│  │  • Multi-sig for amounts above threshold                  │  │
│  │  • Cooling-off period for first-time agents              │  │
│  │  • Whitelist of trusted tool providers                   │  │
│  └─────────────────────────────────────────────────────────┘     │
│                              │                                   │
│                              ▼                                   │
│  Layer 3: Escrow & Settlement                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  • Funds held in escrow until execution confirmed         │  │
│  │  • Atomic swaps (all-or-nothing execution)               │  │
│  │  • Time-locked releases with escalation path              │  │
│  │  • Automatic refunds on timeout/failure                   │  │
│  │  • Partial refunds for partial execution                 │  │
│  └─────────────────────────────────────────────────────────┘     │
│                              │                                   │
│                              ▼                                   │
│  Layer 4: Cryptographic Verification                            │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  • Zero-knowledge proofs for privacy-preserving pay     │  │
│  │  • Merkle trees for batch verification                   │  │
│  │  • BLS signatures for efficient multi-party signing      │  │
│  │  • TEE (Trusted Execution Environment) for key ops      │  │
│  │  • HSM (Hardware Security Module) for cold storage      │  │
│  └─────────────────────────────────────────────────────────┘     │
│                              │                                   │
│                              ▼                                   │
│  Layer 5: Fraud Detection & Prevention                          │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  • ML-based anomaly detection on payment patterns        │  │
│  │  • Behavioral analysis (typing speed, mouse movement)    │  │
│  │  • Real-time risk scoring before each transaction        │  │
│  │  • Automatic circuit-breaker on suspicious activity     │  │
│  │  • Cross-chain analytics for fund tracing               │  │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.3 Payment Security Core Implementation

```typescript
// Advanced Payment Security System
interface PaymentSecuritySystem {
  // ============ Layer 1: Identity ============
  identity: {
    // Decentralized Identifier for agents
    async registerDID(agent: AgentInfo): Promise<DIDDocument> {
      // Generate key pair
      const keyPair = await generateKeyPair("secp256k1");
      
      // Create DID document
      const did = `did:mcp:${sha256(agent.publicKey).slice(0, 16)}`;
      return {
        id: did,
        publicKey: [{
          id: `${did}#keys-1`,
          type: "EcdsaSecp256k1VerificationKey2019",
          controller: did,
          publicKeyBase58: keyPair.publicKey
        }],
        authentication: [`${did}#keys-1`],
        service: [{
          id: `${did#payment}`,
          type: "PaymentService",
          endpoint: `https://gateway.mcp.tools/did/${did}`
        }]
      };
    }

    // Verifiable Credentials for KYC/AML
    async issueVC(agent: Agent, level: TrustLevel): Promise<VerifiableCredential> {
      // ZK proof that agent meets requirements without revealing identity
      const proof = await generateZKProof({
        circuit: "kyc-v3",
        privateInput: agent.identityData,
        publicInput: { level, issuedAt: Date.now() }
      });
      
      return {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        type: ["VerifiableCredential", "AgentCredential"],
        issuer: "did:mcp:gateway-authority",
        credentialSubject: {
          id: agent.did,
          trustLevel: level,
          proof: proof
        },
        proof: {
          type: "BLS12381G2",
          proofValue: await signWithGatewayKey(proof)
        }
      };
    }
  };

  // ============ Layer 2: Authorization ============
  authorization: {
    // Pre-authorization with hold (like credit card pre-auth)
    async preAuthorize(params: {
      agentId: string;
      toolId: string;
      estimatedCost: string;
      maxCost: string;        // Cap for overages
      validUntil: number;     // Unix timestamp
    }): Promise<AuthorizationHold> {
      // Check agent's available balance
      const balance = await this.getAgentBalance(params.agentId);
      if (balance < params.maxCost) {
        throw new InsufficientFundsError(params.maxCost, balance);
      }

      // Check spending limits
      await this.checkSpendingLimits(params.agentId, params.maxCost);

      // Create hold on funds
      const holdId = await this.createHold({
        agentId: params.agentId,
        amount: params.maxCost,
        reason: `pre-auth:${params.toolId}`,
        expiresAt: params.validUntil,
        automaticRelease: true
      });

      return {
        holdId,
        authorizedAmount: params.estimatedCost,
        maxAmount: params.maxCost,
        expiresAt: params.validUntil,
        status: "authorized"
      };
    }

    // Multi-signature for high-value transactions
    async requireMultiSig(params: {
      agentId: string;
      amount: string;
      threshold: number;      // e.g., 2 of 3 signers required
      signers: Signer[];
    }): Promise<MultiSigRequest> {
      const thresholdUSD = parseUsd(params.amount);
      
      // Auto-determine if multi-sig required based on amount
      const requiredThreshold = 
        thresholdUSD > 1000 ? 2 :
        thresholdUSD > 10000 ? 3 : 1;

      if (requiredThreshold > 1) {
        return {
          requestId: generateUUID(),
          signers: params.signers.slice(0, requiredThreshold),
          requiredSignatures: requiredThreshold,
          collectedSignatures: [],
          status: "pending",
          expiresAt: Date.now() + 3600000
        };
      }
      
      return { status: "not_required" };
    }
  };

  // ============ Layer 3: Escrow ============
  escrow: {
    // Time-locked escrow with escalation
    async createEscrow(params: {
      agentId: string;
      providerId: string;
      toolId: string;
      amount: string;
      executionTimeout: number;   // ms
      totalTimeout: number;       // Auto-refund if not completed
    }): Promise<EscrowAccount> {
      // Deploy escrow smart contract
      const escrow = await deployEscrowContract({
        beneficiary: params.providerId,
        payer: params.agentId,
        amount: params.amount,
        timeout: params.totalTimeout,
        arbiter: this.config.arbiterAddress,
        disputeWindow: 86400 // 24 hours
      });

      // Fund the escrow
      await transferToEscrow(escrow.address, params.amount);

      return {
        escrowId: escrow.address,
        status: "funded",
        fundedAt: Date.now(),
        releaseConditions: {
          successAttestation: true,
          timeoutMs: params.executionTimeout,
          autoRefundAfter: params.totalTimeout
        },
        disputeResolution: {
          windowStart: params.totalTimeout,
          windowEnd: params.totalTimeout + 86400000,
          arbiter: this.config.arbiterAddress
        }
      };
    }

    // Atomic execution with guaranteed settlement
    async atomicExecute(params: {
      escrow: EscrowAccount;
      tool: Tool;
      input: unknown;
    }): Promise<AtomicResult> {
      // Step 1: Lock execution (prove funds available)
      await escrow.lock();
      
      try {
        // Step 2: Execute tool
        const result = await executionEngine.execute({
          tool: params.tool,
          input: params.input,
          sandbox: "wasm"
        });

        // Step 3: Generate attestation
        const attestation = await this.generateAttestation(result);

        // Step 4: Conditional release
        if (result.success && attestation.valid) {
          await escrow.release(params.tool.provider, "full");
          return { success: true, amount: params.escrow.amount, attestation };
        } else if (result.partialSuccess) {
          const refundPercent = calculatePartialRefund(result.completionPercent);
          await escrow.release(params.tool.provider, "partial", refundPercent);
          await escrow.refund(params.agentId, 100 - refundPercent);
          return { success: false, partial: true, refundPercent };
        } else {
          await escrow.refund(params.agentId, "full");
          return { success: false, reason: result.error };
        }
      } catch (error) {
        await escrow.refund(params.agentId, "full");
        throw error;
      }
    }
  };

  // ============ Layer 4: Cryptographic Verification ============
  crypto: {
    // Zero-Knowledge Proof for privacy-preserving payments
    async generateZKPaymentProof(params: {
      amount: string;
      sender: string;
      recipient: string;
      nullifier: string;        // Prevent double-spend
      merkleRoot: string;       // Prove sender has balance
    }): Promise<ZKProof> {
      const circuit = await loadCircuit("payment-v3");
      
      return await generateProof({
        circuit,
        inputs: {
          // Private (hidden)
          amount: params.amount,
          senderSecret: params.sender,
          merklePath: params.merkleProof,
          
          // Public (verifiable)
          nullifier: params.nullifier,
          recipient: params.recipient,
          merkleRoot: params.merkleRoot,
          publicAmount: params.amount  // For range proof
        }
      });
    }

    // Batch verification for efficiency
    async verifyBatch(proofs: ZKProof[]): Promise<BatchVerificationResult> {
      // Aggregate signatures using BLS
      const aggregatedProof = await BLS.aggregate(proofs.map(p => p.signature));
      
      // Single proof verification for all
      const valid = await this.verifyAggregatedProof(aggregatedProof, {
        batchSize: proofs.length,
        publicInputs: proofs.map(p => p.publicInput)
      });

      return {
        valid,
        validCount: valid ? proofs.length : 0,
        invalidIndices: valid ? [] : await findInvalidIndices(proofs)
      };
    }

    // TEE-based key operations
    async teeOperation(params: {
      operation: "sign" | "decrypt" | "compute";
      data: string;
      enclaveQuote: string;     // Remote attestation
    }): Promise<TEEResult> {
      // Verify TEE signature (Intel SGX / ARM TrustZone)
      const verified = await verifyEnclaveQuote(params.enclaveQuote, {
        mrEnclave: this.config.allowedEnclaveHash,
        securityVersion: 3,
        debuggable: false
      });

      if (!verified) {
        throw new SecurityError("TEE verification failed");
      }

      // Execute in trusted enclave
      return await executeInEnclave(params.operation, params.data);
    }
  };

  // ============ Layer 5: Fraud Detection ============
  fraudDetection: {
    // Real-time risk scoring
    async scoreTransaction(tx: PaymentRequest): Promise<RiskScore> {
      const factors = await Promise.all([
        this.analyzeVelocity(tx),           // How many recent transactions?
        this.checkPatterns(tx),             // Unusual patterns?
        this.verifyDevice(tx),              // Known device?
        this.checkGeolocation(tx),          // Unusual location?
        this.analyzeAmount(tx),              // Abnormal amount?
        this.checkRecipient(tx),            // New or suspicious recipient?
        this.reviewHistory(tx.agentId)       // Payment history
      ]);

      const weights = [0.2, 0.15, 0.15, 0.1, 0.15, 0.1, 0.15];
      const totalScore = factors.reduce((sum, f, i) => sum + f.score * weights[i], 0);

      return {
        score: totalScore,
        level: totalScore > 0.8 ? "high" : totalScore > 0.5 ? "medium" : "low",
        factors,
        recommendedAction: this.getAction(totalScore, factors),
        requiresVerification: totalScore > 0.6,
        blockIfScoreExceeds: 0.95
      };
    }

    // Anomaly detection using ML
    async detectAnomalies(agentId: string): Promise<Anomaly[]> {
      const history = await this.getTransactionHistory(agentId, 1000);
      
      // Isolation Forest for outlier detection
      const isolationScore = await isolationForest.detect(
        history.map(tx => [
          tx.amount,
          tx.frequency,
          tx.timeOfDay,
          tx.recipientTypes.length,
          tx.avgResponseTime
        ])
      );

      // Sequence analysis for unusual patterns
      const sequenceAnomalies = await this.detectSequenceAnomalies(history);

      return [...isolationScore, ...sequenceAnomalies];
    }

    // Automatic circuit breaker
    async triggerCircuitBreaker(params: {
      agentId: string;
      reason: CircuitBreakerReason;
      severity: "warning" | "lockout" | "freeze";
      duration: number;           // ms
    }): Promise<void> {
      // Immediately block all outgoing transactions
      await this.blockTransactions(agentId, params.duration);

      // Notify agent
      await this.notifyAgent(agentId, {
        type: "security_alert",
        reason: params.reason,
        action: params.severity,
        unlockAt: Date.now() + params.duration
      });

      // Log for human review
      await this.escalateToSecurityTeam({
        agentId,
        reason: params.reason,
        severity: params.severity,
        recentTransactions: await this.getRecentTransactions(agentId, 50)
      });
    }
  };
}
```

---

### 4.4 Smart Contract Security

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/// @title SecureEscrow - Multi-layer protected escrow contract
/// @notice Features:
///         - Reentrancy protection
///         - Time-locked releases
///         - Multi-sig for high-value
///         - Emergency pause
///         - Slashing for malicious providers
contract SecureEscrow is ReentrancyGuard, Pausable, AccessControl {
    using ECDSA for bytes32;

    // ============ Roles ============
    bytes32 public constant ARBITER_ROLE = keccak256("ARBITER_ROLE");
    bytes32 public constant GOVERNANCE_ROLE = keccak256("GOVERNANCE_ROLE");

    // ============ Constants ============
    uint256 public constant HIGH_VALUE_THRESHOLD = 1e18; // 1 ETH/USDC
    uint256 public constant MAX_GAS_LIMIT = 500000;
    uint256 public constant DISPUTE_WINDOW = 24 hours;
    uint256 public constant EXECUTION_TIMEOUT = 5 minutes;

    // ============ State ============
    enum EscrowStatus {
        Created,
        Funded,
        Locked,
        Executing,
        Released,
        Refunded,
        Disputed
    }

    struct Escrow {
        address payer;
        address beneficiary;
        address provider;
        uint256 amount;
        uint256 fundedAt;
        uint256 expiresAt;
        EscrowStatus status;
        bytes32 toolId;
        bytes32 inputHash;
        bytes32 outputHash;
        uint256 requiredSignatures;
        mapping(address => bool) signed;
        uint256 signaturesCollected;
        uint256 releasedAmount;
        string attestationId;
    }

    mapping(bytes32 => Escrow) public escrows;
    mapping(bytes32 => bool) public nullifiers;  // Prevent double-spend
    mapping(address => uint256) public agentLimits;
    mapping(address => uint256) public agentBalances;
    
    // Security parameters
    uint256 public globalDailyLimit = 100e18;
    uint256 public agentDailyLimit = 10e18;
    uint256 public slashPercent = 10;  // 10% slash for malicious execution

    // ============ Events ============
    event EscrowCreated(bytes32 indexed escrowId, address indexed payer, uint256 amount);
    event EscrowFunded(bytes32 indexed escrowId);
    event EscrowLocked(bytes32 indexed escrowId);
    event EscrowExecuted(bytes32 indexed escrowId, bool success);
    event EscrowReleased(bytes32 indexed escrowId, uint256 amount, address to);
    event EscrowRefunded(bytes32 indexed escrowId, uint256 amount);
    event DisputeOpened(bytes32 indexed escrowId, address indexed opener);
    event DisputeResolved(bytes32 indexed escrowId, uint256 payerAmount, uint256 beneficiaryAmount);
    event SlashingApplied(bytes32 indexed escrowId, uint256 slashedAmount);
    event CircuitBreakerTriggered(address indexed agent, string reason);

    // ============ Modifiers ============
    modifier onlyValidEscrow(bytes32 escrowId) {
        require(escrows[escrowId].payer != address(0), "Escrow not found");
        _;
    }

    modifier onlyHighValue(bytes32 escrowId) {
        require(
            escrows[escrowId].amount > HIGH_VALUE_THRESHOLD,
            "Not high value"
        );
        _;
    }

    modifier withinDailyLimit(address agent, uint256 amount) {
        uint256 dailySpent = getDailySpent(agent);
        require(
            dailySpent + amount <= agentDailyLimit,
            "Daily limit exceeded"
        );
        _;
    }

    // ============ Core Functions ============

    /// @notice Create new escrow with security checks
    function createEscrow(
        address beneficiary,
        address provider,
        uint256 amount,
        bytes32 toolId,
        bytes32 inputHash,
        uint256 timeout
    ) external whenNotPaused nonReentrant returns (bytes32 escrowId) {
        // Security checks
        require(amount > 0, "Amount must be positive");
        require(beneficiary != address(0), "Invalid beneficiary");
        require(provider != address(0), "Invalid provider");
        require(timeout <= 7 days, "Timeout too long");

        // Rate limiting
        _checkRateLimit(msg.sender, amount);

        // Create escrow
        escrowId = keccak256(abi.encodePacked(
            msg.sender,
            beneficiary,
            amount,
            block.timestamp,
            toolId
        ));

        Escrow storage e = escrows[escrowId];
        e.payer = msg.sender;
        e.beneficiary = beneficiary;
        e.provider = provider;
        e.amount = amount;
        e.fundedAt = block.timestamp;
        e.expiresAt = block.timestamp + timeout;
        e.status = EscrowStatus.Created;
        e.toolId = toolId;
        e.inputHash = inputHash;

        emit EscrowCreated(escrowId, msg.sender, amount);
    }

    /// @notice Fund escrow with safety deposit
    function fundEscrow(bytes32 escrowId) 
        external 
        payable 
        onlyValidEscrow(escrowId) 
        nonReentrant 
    {
        Escrow storage e = escrows[escrowId];
        require(e.status == EscrowStatus.Created, "Wrong status");
        require(msg.value >= e.amount, "Insufficient funds");

        e.status = EscrowStatus.Funded;
        e.fundedAt = block.timestamp;

        // Return excess
        if (msg.value > e.amount) {
            payable(msg.sender).transfer(msg.value - e.amount);
        }

        emit EscrowFunded(escrowId);
    }

    /// @notice Lock escrow before execution (prevents reentrancy)
    function lockEscrow(bytes32 escrowId) 
        external 
        onlyValidEscrow(escrowId) 
        onlyRole(ARBITER_ROLE)
    {
        Escrow storage e = escrows[escrowId];
        require(e.status == EscrowStatus.Funded, "Wrong status");
        require(block.timestamp < e.expiresAt, "Expired");
        
        e.status = EscrowStatus.Locked;
        emit EscrowLocked(escrowId);
    }

    /// @notice Execute with attestation and release
    function executeAndRelease(
        bytes32 escrowId,
        bool success,
        bytes32 outputHash,
        string calldata attestationId,
        bytes[] calldata providerSignatures
    ) external nonReentrant onlyValidEscrow(escrowId) {
        Escrow storage e = escrows[escrowId];
        require(e.status == EscrowStatus.Locked, "Not locked");
        
        e.status = EscrowStatus.Executing;
        e.outputHash = outputHash;
        e.attestationId = attestationId;

        if (success) {
            // Full release to beneficiary
            e.releasedAmount = e.amount;
            e.status = EscrowStatus.Released;
            
            // Verify signatures for high-value
            if (e.amount > HIGH_VALUE_THRESHOLD) {
                _verifyMultiSig(escrowId, providerSignatures);
            }
            
            payable(e.beneficiary).transfer(e.amount);
            emit EscrowReleased(escrowId, e.amount, e.beneficiary);
        } else {
            // Refund payer
            e.status = EscrowStatus.Refunded;
            payable(e.payer).transfer(e.amount);
            emit EscrowRefunded(escrowId, e.amount);
        }
    }

    /// @notice Slash malicious provider
    function slashProvider(
        bytes32 escrowId,
        uint256 slashAmount,
        string calldata reason
    ) external onlyRole(ARBITER_ROLE) {
        Escrow storage e = escrows[escrowId];
        require(e.status == EscrowStatus.Executed, "Not executed");
        
        uint256 actualSlash = (e.amount * slashPercent) / 100;
        e.releasedAmount = e.amount - actualSlash;
        
        // Slashed amount goes to payer
        payable(e.payer).transfer(actualSlash);
        payable(e.beneficiary).transfer(e.releasedAmount);
        
        emit SlashingApplied(escrowId, actualSlash);
    }

    /// @notice Open dispute with escalation
    function openDispute(bytes32 escrowId) 
        external 
        onlyValidEscrow(escrowId) 
    {
        Escrow storage e = escrows[escrowId];
        require(
            msg.sender == e.payer || msg.sender == e.beneficiary,
            "Not authorized"
        );
        require(
            block.timestamp < e.expiresAt + DISPUTE_WINDOW,
            "Dispute window closed"
        );

        e.status = EscrowStatus.Disputed;
        emit DisputeOpened(escrowId, msg.sender);
    }

    /// @notice Resolve dispute by arbiter
    function resolveDispute(
        bytes32 escrowId,
        uint256 payerAmount,
        uint256 beneficiaryAmount,
        bytes calldata arbiterSignature
    ) external onlyRole(ARBITER_ROLE) {
        Escrow storage e = escrows[escrowId];
        require(e.status == EscrowStatus.Disputed, "Not disputed");
        
        // Verify arbiter signature
        bytes32 messageHash = keccak256(abi.encodePacked(
            escrowId, payerAmount, beneficiaryAmount
        ));
        require(
            messageHash.toEthSignedMessageHash().recover(arbiterSignature) 
                == msg.sender,
            "Invalid arbiter signature"
        );

        require(payerAmount + beneficiaryAmount <= e.amount, "Amount mismatch");
        
        e.releasedAmount = beneficiaryAmount;
        e.status = EscrowStatus.Released;
        
        if (payerAmount > 0) {
            payable(e.payer).transfer(payerAmount);
        }
        if (beneficiaryAmount > 0) {
            payable(e.beneficiary).transfer(beneficiaryAmount);
        }
        
        emit DisputeResolved(escrowId, payerAmount, beneficiaryAmount);
    }

    // ============ Security Functions ============

    /// @notice Emergency circuit breaker
    function emergencyPause(address agent) external onlyRole(GOVERNANCE_ROLE) {
        agentLimits[agent] = 0;
        emit CircuitBreakerTriggered(agent, "Emergency pause by governance");
    }

    /// @notice Update security parameters
    function updateSecurityParams(
        uint256 _dailyLimit,
        uint256 _agentLimit,
        uint256 _slashRate
    ) external onlyRole(GOVERNANCE_ROLE) {
        globalDailyLimit = _dailyLimit;
        agentDailyLimit = _agentLimit;
        slashPercent = _slashRate;
    }

    // ============ Internal Helpers ============

    function _checkRateLimit(address agent, uint256 amount) internal {
        uint256 dailySpent = getDailySpent(agent);
        require(
            dailySpent + amount <= agentDailyLimit,
            "Rate limit exceeded"
        );
        agentBalances[agent] += amount;
    }

    function _verifyMultiSig(
        bytes32 escrowId,
        bytes[] calldata signatures
    ) internal view {
        Escrow storage e = escrows[escrowId];
        bytes32 messageHash = keccak256(abi.encodePacked(escrowId, "release"));
        
        uint256 validSigs = 0;
        for (uint i = 0; i < signatures.length; i++) {
            address signer = messageHash.recover(signatures[i]);
            if (signer == e.provider || signer == e.beneficiary) {
                validSigs++;
            }
        }
        
        require(validSigs >= e.requiredSignatures, "Not enough signatures");
    }

    function getDailySpent(address agent) internal view returns (uint256) {
        // Simplified - in production use a more sophisticated tracking
        return agentBalances[agent];
    }
}
```

---

### 4.5 Real-time Monitoring Dashboard

```typescript
// Security monitoring and alerting
interface SecurityMonitor {
  // Live threat dashboard
  async getDashboard(): Promise<SecurityDashboard> {
    return {
      activeThreats: await this.getActiveThreats(),
      blockedTransactions: await this.getBlockedStats(),
      escrowHealth: await this.getEscrowStats(),
      anomalyAlerts: await this.getRecentAlerts(),
      networkHealth: await this.getNetworkStatus()
    };
  }

  // Continuous monitoring
  async startMonitoring(): Promise<void> {
    // Real-time event listeners
    this.on("large_transaction", this.reviewLargeTransaction.bind(this));
    this.on("new_agent", this.setupNewAgentMonitoring.bind(this));
    this.on("velocity_spike", this.investigateVelocity.bind(this));
    this.on("geolocation_change", this.verifyLocationChange.bind(this));

    // Periodic checks
    setInterval(() => this.checkDailylimits(), 60000);
    setInterval(() => this.updateRiskScores(), 300000);
    setInterval(() => this.runSecurityAudit(), 3600000);
  }

  // Alert thresholds
  alertThresholds: {
    transactionAmount: 1000,         // $1000+
    velocityPerMinute: 10,          // 10+ tx/min
    failedAttempts: 3,              // 3 failures
    newRecipientPercent: 0.5,        // 50%+ new recipients
    amountDeviation: 3,             // 3x normal amount
    unusualHourStart: 2,             // 2 AM
    unusualHourEnd: 5                // 5 AM
  };
}
```

---

### 4.6 Security Comparison

| Feature | Traditional Payment | MCP Gateway Payment | Improvement |
|---------|-------------------|-------------------|-------------|
| Authentication | API Key only | DID + VC + MFA | +300% |
| Authorization | Simple token | Pre-auth + limits + multi-sig | +500% |
| Escrow | None | Time-locked + dispute window | +∞ |
| Verification | None | ZK proofs + TEE | +∞ |
| Fraud Detection | Reactive | ML + real-time | +1000% |
| Dispute Resolution | Manual | Arbiter network | +200% |
| Slashing | N/A | 10% for malicious | +∞ |

---

### 4.7 Penetration Testing Checklist

- [ ] SQL/NoSQL injection in tool parameters
- [ ] XSS in tool output rendering
- [ ] CSRF on payment authorization
- [ ] Rate limiting bypass
- [ ] Reentrancy in escrow contract
- [ ] Integer overflow in amount calculations
- [ ] Front-running on escrow releases
- [ ] Signature replay attacks
- [ ] Time manipulation (clock skew)
- [ ] Malicious tool provider exit scam
- [ ] Fake attestation generation
- [ ] Sybil attack on reputation system

```
Level 1: WASM Runtime (fast, memory-safe)
    │
Level 2: Isolated VM (Node.js/V8)
    │
Level 3: Docker Container (full isolation)
    │
Level 4: Air-gapped Execution (high-security)
```

```typescript
interface SandboxConfig {
  level: 1 | 2 | 3 | 4;
  
  // Per-tool override
  overrides: Map<string, {
    level: number;
    timeout: number;
    memoryLimit: number;
    networkAccess: "none" | "whitelist" | "all";
    filesystemAccess: "none" | "temp" | "full";
  }>;
}
```

### 4.3 Cryptographic Attestations

Every execution produces a verifiable attestation:

```typescript
interface ExecutionAttestation {
  id: string;
  toolId: string;
  version: string;
  inputHash: string;           // SHA-256 of input
  outputHash: string;          // SHA-256 of output
  executionProof: {
    nodeId: string;
    timestamp: number;
    signature: string;         // Node's signing key
    merkleProof: string[];    // For batch verification
  };
  paymentProof: {
    txHash: string;
    blockNumber: number;
    confirmed: boolean;
  };
}

// Verify attestation
async verifyAttestation(attestation: ExecutionAttestation): Promise<{
  valid: boolean;
  nodeReputation: number;
  paymentVerified: boolean;
}>
```

---

## 5. Business Models

### 5.1 Pricing Models

```typescript
type PricingModel =
  | { type: "per-call"; price: string }
  | { type: "per-token"; pricePerToken: string }
  | { type: "subscription"; 
      plans: Array<{
        name: string;
        price: string;
        period: "day" | "month" | "year";
        calls: number | "unlimited";
      }>
    }
  | { type: "freemium"; 
      freeCalls: number; 
      paidPrice: string 
    }
  | { type: "tiered"; 
      tiers: Array<{
        minVolume: number;
        price: string;
      }>
    }
  | { type: "auction"; }
```

### 5.2 Revenue Distribution

```
┌────────────────────────────────────────────────┐
│ Tool Execution Revenue                          │
├────────────────────────────────────────────────┤
│ 85% ───▶ Tool Provider                        │
│ 10% ───▶ Gateway Operator                     │
│  5% ───▶ Reputation Stakers (via protocol)    │
└────────────────────────────────────────────────┘
```

### 5.3Escrow & Dispute Resolution

```typescript
interface DisputeResolution {
  // Auto-escalation
  createDispute(params: {
    executionId: string;
    reason: "output-wrong" | "timeout" | "overcharge";
    evidence: string[];          // IPFS CIDs
  }): Promise<Dispute>;

  // Arbiter network (reputable agents)
  arbiterVote(disputeId: string, vote: {
    decision: "refund" | "pay" | "partial";
    percentage: number;           // 0-100 for partial
    reasoning: string;
  }): Promise<void>;

  // Auto-resolution for small claims
  autoResolve(amount: string): "approve" | "escalate" | "reject";
}
```

---

## 6. Agent Integration

### 6.1 OpenClaw Skill Interface

```typescript
// skill.json
{
  "name": "mcp-gateway",
  "version": "1.0.0",
  "description": "Access paid MCP tools via the gateway",
  "metadata": {
    "mcpGateway": {
      "apiBase": "https://gateway.mcp.tools/api/v1",
      "defaultToken": "USDC",
      "network": "base-sepolia"
    }
  }
}

// Usage in agent
const gateway = new MCPGateway({
  apiKey: process.env.MCP_GATEWAY_KEY,
  network: "base-sepolia"
});

// Discover tools
const tools = await gateway.discover({
  query: "web scraping",
  category: "data",
  maxPrice: "0.01"
});

// Execute with automatic payment
const result = await gateway.execute({
  tool: "web-scraper-pro",
  input: { url: "https://example.com" }
});
```

### 6.2 Agent Profile

```typescript
interface AgentProfile {
  id: string;
  name: string;
  capabilities: string[];
  preferredTools: string[];
  budget: {
    dailyLimit: string;
    totalSpent: string;
    subscriptionTier: string;
  };
  trustLevel: "anonymous" | "verified" | "premium";
  paymentHistory: {
    onTimeRate: number;
    avgResponseTime: number;
  };
}
```

---

## 7. Protocol Specification

### 7.1 MCP Gateway Protocol (MCPG)

```
Request:
POST /v1/execute
Authorization: Bearer <agent_api_key>
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/execute",
  "params": {
    "tool": "web-scraper",
    "input": { "url": "..." },
    "payment": {
      "max_price": "0.005",
      "auto_pay": true
    }
  }
}

Response (200):
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "success": true,
    "output": { "data": "..." },
    "attestation": { "id": "...", "signature": "..." }
  }
}

Response (402 - Payment Required):
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32002,
    "message": "Payment required",
    "data": {
      "price": "0.005",
      "token": "USDC",
      "address": "0x...",
      "payment_url": "https://pay.mcp.tools/..."
    }
  }
}
```

### 7.2 Tool Registration Protocol

```
Request:
POST /v1/tools/register
Authorization: Bearer <provider_api_key>
Content-Type: application/json

{
  "name": "image-generator",
  "description": "Generate images from text prompts",
  "category": "ai",
  "pricing": {
    "type": "per-call",
    "price": "0.05"
  },
  "schema": {
    "input": { ... },
    "output": { ... }
  },
  "code": "ipfs://Qm...",
  "limits": {
    "maxExecutionTime": 30000,
    "maxTokens": 4000
  }
}

Response (201):
{
  "id": "0x1234...",
  "onChainTx": "0x5678...",
  "endpoint": "https://gateway.mcp.tools/v1/execute/web-generator"
}
```

---

## 8. Roadmap

### Phase 1: MVP (v1.0)
- [ ] Basic tool registry (on-chain)
- [ ] x402 payment integration
- [ ] Single tool execution
- [ ] Simple discovery (keyword search)
- [ ] API key authentication

### Phase 2: Trust & Discovery (v1.5)
- [ ] Vector search integration
- [ ] Reputation system (ERC-8004)
- [ ] Subscription support
- [ ] Tool versioning

### Phase 3: Advanced Execution (v2.0)
- [ ] WASM sandbox
- [ ] Tool composition
- [ ] Streaming responses
- [ ] Distributed execution

### Phase 4: Decentralization (v3.0)
- [ ] DAO governance
- [ ] Staking mechanism
- [ ] Cross-chain tool registry
- [ ] Decentralized dispute resolution

---

## 9. Technical Stack

| Layer | Technology |
|-------|------------|
| Blockchain | Base (EVM) |
| Payments | x402 / EIP-3009 |
| MCP Adapter | TypeScript |
| Search | Vector DB (Pinecone/Milvus) |
| Sandboxing | WASM / Isolated VM |
| Attestation | BLS Signatures + Merkle |
| Storage | IPFS + Filecoin |
| Monitoring | OpenTelemetry |

---

## 10. Success Metrics

| Metric | Target |
|--------|--------|
| Tool registrations | 1000+ in 6 months |
| Daily active agents | 100+ |
| Avg payment time | < 500ms |
| Execution success rate | > 99.5% |
| Dispute rate | < 0.1% |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| MCP | Model Context Protocol |
| Tool | Executable function accessible via API |
| Provider | Agent or service that owns and monetizes a tool |
| Consumer | Agent that pays to use a tool |
| Attestation | Cryptographic proof of execution |
| Escrow | Funds held until execution completes |
| Watermarking | Invisible markers in outputs to trace theft |

---

## Appendix B: Reference Implementations

- [x402 Protocol](https://docs.x402.org)
- [MCP Specification](https://modelcontextprotocol.io)
- [ERC-8004 Attestations](https://eips.ethereum.org/EIPS/eip-8004)
- [Anthropic Tools](https://docs.anthropic.com/claude/docs/tool-use)

---

**Document Version:** 1.0.0  
**Last Updated:** 2026-03-22  
**Status:** Ready for Review
