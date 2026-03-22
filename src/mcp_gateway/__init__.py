"""
MCP Tool Gateway - Python Implementation

A decentralized, agent-native tool marketplace with x402 payment integration.

Usage:
    from mcp_gateway import PaymentEngine, ToolRegistry, MCPAdapter
    
    # Initialize
    engine = PaymentEngine()
    registry = ToolRegistry()
    mcp = MCPAdapter(registry=registry, payment_engine=engine)
"""

__version__ = "0.1.0"
__author__ = "@openclaw-rhantolk"
__email__ = "gateway@mcp.tools"
__license__ = "MIT"

# Core modules
from .config import Settings, get_settings

# Payment & Escrow
from .core.payment import (
    PaymentEngine,
    PaymentChallenge,
    PaymentAuthorization,
    PaymentStatus,
    TokenType,
)

from .core.escrow import (
    EscrowManager,
    EscrowAccount,
    EscrowStatus,
    EscrowReleaseCondition,
    Dispute,
    DisputeReason,
)

# Tool Registry
from .core.registry import (
    ToolRegistry,
    Tool,
    ToolStatus,
    PricingConfig,
    PricingType,
    SubscriptionPlan,
    ToolSchema,
    ToolLimits,
    create_web_search_tool,
)

# MCP Protocol
from .core.mcp import (
    MCPAdapter,
    MCPRequest,
    MCPResponse,
    MCPErrorCode,
    MCPToolInfo,
    ToolCall,
    ToolResult,
)

# Security
from .security.auth import (
    AuthManager,
    DIDDocument,
    VerifiableCredential,
    TrustLevel,
    CredentialType,
    AgentSession,
)

from .security.fraud import (
    FraudDetector,
    RiskScore,
    RiskLevel,
    RiskFactor,
    Transaction,
    AlertType,
)

from .security.crypto import (
    CryptoUtils,
    ZKProof,
    Signature,
    MerkleProof,
    HashAlgorithm,
)

# Execution
from .execution.sandbox import (
    Sandbox,
    SandboxConfig,
    SandboxLevel,
    SandboxResult,
)

from .execution.executor import (
    Executor,
    ExecutionResult,
    ExecutionStatus,
    ExecutionRequest,
)

# Discovery
from .discovery.search import (
    DiscoveryEngine,
    SearchResult,
    AgentProfile,
)

__all__ = [
    # Version
    "__version__",
    "__author__",
    "__license__",
    # Config
    "Settings",
    "get_settings",
    # Payment
    "PaymentEngine",
    "PaymentChallenge",
    "PaymentAuthorization",
    "PaymentStatus",
    "TokenType",
    # Escrow
    "EscrowManager",
    "EscrowAccount",
    "EscrowStatus",
    "EscrowReleaseCondition",
    "Dispute",
    "DisputeReason",
    # Registry
    "ToolRegistry",
    "Tool",
    "ToolStatus",
    "PricingConfig",
    "PricingType",
    "SubscriptionPlan",
    "ToolSchema",
    "ToolLimits",
    "create_web_search_tool",
    # MCP
    "MCPAdapter",
    "MCPRequest",
    "MCPResponse",
    "MCPErrorCode",
    "MCPToolInfo",
    "ToolCall",
    "ToolResult",
    # Auth
    "AuthManager",
    "DIDDocument",
    "VerifiableCredential",
    "TrustLevel",
    "CredentialType",
    "AgentSession",
    # Fraud
    "FraudDetector",
    "RiskScore",
    "RiskLevel",
    "RiskFactor",
    "Transaction",
    "AlertType",
    # Crypto
    "CryptoUtils",
    "ZKProof",
    "Signature",
    "MerkleProof",
    "HashAlgorithm",
    # Sandbox
    "Sandbox",
    "SandboxConfig",
    "SandboxLevel",
    "SandboxResult",
    # Executor
    "Executor",
    "ExecutionResult",
    "ExecutionStatus",
    "ExecutionRequest",
    # Discovery
    "DiscoveryEngine",
    "SearchResult",
    "AgentProfile",
]
