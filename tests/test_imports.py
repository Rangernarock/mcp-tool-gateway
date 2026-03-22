"""
Basic import tests for MCP Tool Gateway.

Run: python -m pytest tests/test_imports.py -v
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_config_imports():
    """Test config module imports."""
    from mcp_gateway.config import Settings, get_settings
    assert Settings is not None
    assert get_settings is not None
    print("✓ config imports OK")


def test_payment_imports():
    """Test payment module imports."""
    from mcp_gateway.core.payment import (
        PaymentEngine, 
        PaymentChallenge, 
        PaymentStatus,
        TokenType,
        PaymentAuthorization
    )
    assert PaymentEngine is not None
    assert PaymentChallenge is not None
    assert PaymentStatus is not None
    assert TokenType is not None
    print("✓ payment imports OK")


def test_escrow_imports():
    """Test escrow module imports."""
    from mcp_gateway.core.escrow import (
        EscrowManager,
        EscrowAccount,
        EscrowStatus,
        DisputeReason,
        Dispute,
        EscrowReleaseCondition
    )
    assert EscrowManager is not None
    assert EscrowAccount is not None
    assert EscrowStatus is not None
    print("✓ escrow imports OK")


def test_registry_imports():
    """Test registry module imports."""
    from mcp_gateway.core.registry import (
        ToolRegistry,
        Tool,
        ToolStatus,
        PricingConfig,
        PricingType,
        ToolSchema,
        ToolLimits
    )
    assert ToolRegistry is not None
    assert Tool is not None
    assert PricingConfig is not None
    print("✓ registry imports OK")


def test_mcp_imports():
    """Test MCP module imports."""
    from mcp_gateway.core.mcp import (
        MCPAdapter,
        MCPRequest,
        MCPResponse,
        MCPErrorCode,
        MCPToolInfo,
        ToolCall,
        ToolResult
    )
    assert MCPAdapter is not None
    assert MCPRequest is not None
    assert MCPResponse is not None
    print("✓ mcp imports OK")


def test_security_imports():
    """Test security module imports."""
    from mcp_gateway.security.auth import (
        AuthManager,
        DIDDocument,
        VerifiableCredential,
        TrustLevel,
        CredentialType
    )
    from mcp_gateway.security.fraud import (
        FraudDetector,
        RiskScore,
        RiskLevel,
        Transaction,
        AlertType
    )
    from mcp_gateway.security.crypto import (
        CryptoUtils,
        ZKProof,
        Signature,
        MerkleProof,
        HashAlgorithm
    )
    assert AuthManager is not None
    assert FraudDetector is not None
    assert CryptoUtils is not None
    print("✓ security imports OK")


def test_execution_imports():
    """Test execution module imports."""
    from mcp_gateway.execution.sandbox import (
        Sandbox,
        SandboxConfig,
        SandboxLevel,
        SandboxResult
    )
    from mcp_gateway.execution.executor import (
        Executor,
        ExecutionResult,
        ExecutionStatus,
        ExecutionRequest
    )
    assert Sandbox is not None
    assert Executor is not None
    print("✓ execution imports OK")


def test_discovery_imports():
    """Test discovery module imports."""
    from mcp_gateway.discovery.search import (
        DiscoveryEngine,
        SearchResult,
        AgentProfile
    )
    assert DiscoveryEngine is not None
    assert SearchResult is not None
    print("✓ discovery imports OK")


def test_basic_payment_engine():
    """Test basic PaymentEngine functionality."""
    from mcp_gateway.core.payment import PaymentEngine, TokenType
    
    engine = PaymentEngine()
    
    # Create a challenge
    challenge = engine.create_challenge(
        tool_id="test-tool",
        tool_name="Test Tool",
        amount="1000000",
        token=TokenType.USDC
    )
    
    assert challenge is not None
    assert challenge.tool_id == "test-tool"
    assert challenge.amount == "1000000"
    assert not challenge.is_expired
    print("✓ payment engine basic test OK")


def test_basic_registry():
    """Test basic ToolRegistry functionality."""
    from mcp_gateway.core.registry import ToolRegistry, Tool, PricingConfig, PricingType
    
    registry = ToolRegistry()
    
    # Create a tool
    tool = Tool(
        id="test-id",
        name="test-tool",
        description="A test tool",
        provider_id="test-provider",
        provider_address="0x1234567890123456789012345678901234567890",
        pricing=PricingConfig(type=PricingType.PER_CALL, price="1000000")
    )
    
    # Register
    registered = registry.register_tool(tool)
    assert registered.id == tool.id
    
    # Get
    retrieved = registry.get_tool(tool.id)
    assert retrieved is not None
    assert retrieved.name == "test-tool"
    print("✓ registry basic test OK")


def test_basic_mcp():
    """Test basic MCP functionality."""
    from mcp_gateway.core.mcp import MCPRequest, MCPResponse, MCPErrorCode
    
    # Create request
    request = MCPRequest(
        id=1,
        method="tools/list",
        params={}
    )
    
    assert request.jsonrpc == "2.0"
    assert request.method == "tools/list"
    
    # Create success response
    response = MCPResponse.success(request.id, {"tools": []})
    assert not response.is_error()
    
    # Create error response
    error_response = MCPResponse.error(
        request.id,
        MCPErrorCode.PAYMENT_REQUIRED,
        "Payment required"
    )
    assert error_response.is_error()
    print("✓ mcp basic test OK")


def test_basic_crypto():
    """Test basic crypto functionality."""
    from mcp_gateway.security.crypto import CryptoUtils, HashAlgorithm
    
    crypto = CryptoUtils()
    
    # Test hashing
    hash_result = crypto.sha256("test data")
    assert len(hash_result) == 64  # SHA-256 produces 64 hex characters
    
    # Test HMAC
    hmac_result = crypto.generate_hmac("test message")
    assert len(hmac_result) == 64
    
    # Test nonce generation
    nonce = crypto.generate_nonce()
    assert len(nonce) == 64  # 32 bytes = 64 hex chars
    
    print("✓ crypto basic test OK")


def test_basic_fraud():
    """Test basic fraud detection."""
    from mcp_gateway.security.fraud import FraudDetector, Transaction, RiskLevel
    
    detector = FraudDetector()
    
    # Create a transaction
    tx = Transaction(
        tx_id="test-tx-1",
        agent_id="agent-1",
        amount="1000000",
        recipient="provider-1",
        timestamp=1234567890,
        tool_id="tool-1",
        success=True
    )
    
    # Record transaction
    detector.record_transaction(tx)
    
    # Score transaction
    score = detector.score_transaction(tx)
    assert score is not None
    assert score.score >= 0 and score.score <= 1
    assert score.level in RiskLevel
    
    print("✓ fraud detection basic test OK")


if __name__ == "__main__":
    print("\n" + "="*50)
    print("Running MCP Tool Gateway Import Tests")
    print("="*50 + "\n")
    
    test_config_imports()
    test_payment_imports()
    test_escrow_imports()
    test_registry_imports()
    test_mcp_imports()
    test_security_imports()
    test_execution_imports()
    test_discovery_imports()
    
    print("\n" + "-"*50)
    print("Basic Functionality Tests")
    print("-"*50 + "\n")
    
    test_basic_payment_engine()
    test_basic_registry()
    test_basic_mcp()
    test_basic_crypto()
    test_basic_fraud()
    
    print("\n" + "="*50)
    print("All tests passed! ✓")
    print("="*50 + "\n")
