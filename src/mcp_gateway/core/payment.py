"""
x402 Payment Engine - Core payment processing for MCP Tool Gateway.

Implements the HTTP 402 Payment Required pattern for tool execution payments.
"""

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple, Union
from enum import Enum
from decimal import Decimal


class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class TokenType(str, Enum):
    """Supported payment tokens."""
    USDC = "USDC"
    USDT = "USDT"
    ETH = "ETH"
    WETH = "WETH"


@dataclass
class PaymentChallenge:
    """
    HTTP 402 Payment Challenge response.
    
    When a tool requires payment, the gateway returns this challenge
    with payment instructions. The client must pay and include proof.
    """
    # Challenge identifier
    challenge_id: str
    
    # Payment details
    amount: str  # Amount in smallest unit (e.g., wei for ETH, micro for USDC)
    token: TokenType
    token_address: Optional[str] = None
    
    # Payment destination
    recipient_address: str  # Where to send payment
    
    # Challenge metadata
    created_at: int = field(default_factory=lambda: int(time.time()))
    expires_at: int = field(default_factory=lambda: int(time.time()) + 300)  # 5 min
    max_usage: int = 1  # Can only be used once by default
    
    # Tool information
    tool_id: str = ""
    tool_name: str = ""
    
    # Payment URL for easy payment
    payment_url: str = ""
    
    # Metadata
    description: str = ""
    metadata: Dict = field(default_factory=dict)
    
    def to_headers(self) -> Dict[str, str]:
        """Convert challenge to HTTP headers (for x402 compliance)."""
        return {
            "X-Payment-Required": "402",
            "X-Payment-Challenge-ID": self.challenge_id,
            "X-Payment-Amount": self.amount,
            "X-Payment-Token": self.token.value,
            "X-Payment-Recipient": self.recipient_address,
            "X-Payment-Expires": str(self.expires_at),
        }
    
    def to_response_body(self) -> Dict:
        """Convert challenge to API response body."""
        return {
            "error": {
                "code": -32002,
                "message": "Payment required",
                "data": {
                    "challenge_id": self.challenge_id,
                    "amount": self.amount,
                    "token": self.token.value,
                    "token_address": self.token_address,
                    "recipient": self.recipient_address,
                    "payment_url": self.payment_url,
                    "expires_at": self.expires_at,
                    "tool_id": self.tool_id,
                    "tool_name": self.tool_name,
                    "description": self.description,
                }
            }
        }
    
    @property
    def is_expired(self) -> bool:
        """Check if the challenge has expired."""
        return int(time.time()) > self.expires_at
    
    def verify_nonce(self, nonce: str) -> bool:
        """Verify the payment nonce (prevents replay attacks)."""
        expected = hashlib.sha256(
            f"{self.challenge_id}:{self.recipient_address}".encode()
        ).hexdigest()
        return secrets.compare_digest(nonce, expected)


@dataclass
class PaymentAuthorization:
    """
    Payment authorization record.
    Tracks authorized payments and their status.
    """
    # Authorization ID
    auth_id: str
    
    # User who authorized
    agent_id: str
    
    # Challenge reference
    challenge_id: str
    
    # Amount authorized
    amount: str
    token: TokenType
    
    # Status
    status: PaymentStatus = PaymentStatus.PENDING
    
    # Usage tracking
    used_count: int = 0
    max_usage: int = 1
    
    # Timestamps
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    expires_at: int = field(default_factory=lambda: int(time.time()) + 3600)  # 1 hour
    
    # Payment reference (for on-chain)
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    
    # Receipt
    receipt_url: Optional[str] = None


class PaymentEngine:
    """
    Core payment engine implementing x402 pattern.
    
    Handles:
    - Challenge generation
    - Payment authorization
    - Payment verification
    - Refund processing
    """
    
    def __init__(
        self,
        gateway_address: str = "0x0000000000000000000000000000000000000000",
        supported_tokens: Optional[Dict[TokenType, str]] = None,
    ):
        self.gateway_address = gateway_address
        self.supported_tokens = supported_tokens or {
            TokenType.USDC: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",  # Base Sepolia
            TokenType.ETH: None,  # Native ETH
        }
        
        # In-memory storage for MVP
        self._challenges: Dict[str, PaymentChallenge] = {}
        self._authorizations: Dict[str, PaymentAuthorization] = {}
        self._nonces: Dict[str, int] = {}  # nonce -> count (for replay prevention)
        
        # Rate limiting
        self._agent_spending: Dict[str, List[Tuple[int, Decimal]]] = {}  # agent_id -> [(timestamp, amount), ...]
        self._daily_limit = Decimal("1000.0")  # Default daily limit
    
    def create_challenge(
        self,
        tool_id: str,
        tool_name: str,
        amount: str,
        token: TokenType = TokenType.USDC,
        recipient_address: Optional[str] = None,
        max_usage: int = 1,
        timeout_seconds: int = 300,
    ) -> PaymentChallenge:
        """
        Create a new payment challenge.
        
        Args:
            tool_id: Unique identifier for the tool
            tool_name: Human-readable tool name
            amount: Amount to pay (in smallest unit)
            token: Token to pay with
            recipient_address: Where payment goes (defaults to gateway address)
            max_usage: How many times this challenge can be used
            timeout_seconds: Challenge validity period
            
        Returns:
            PaymentChallenge object with payment instructions
        """
        # Generate unique challenge ID
        challenge_id = self._generate_challenge_id(tool_id, amount)
        
        # Determine recipient
        recipient = recipient_address or self.gateway_address
        
        # Create challenge
        challenge = PaymentChallenge(
            challenge_id=challenge_id,
            amount=amount,
            token=token,
            token_address=self.supported_tokens.get(token),
            recipient_address=recipient,
            created_at=int(time.time()),
            expires_at=int(time.time()) + timeout_seconds,
            max_usage=max_usage,
            tool_id=tool_id,
            tool_name=tool_name,
            payment_url=self._build_payment_url(challenge_id, amount, token, recipient),
            description=f"Payment for {tool_name}",
        )
        
        # Store challenge
        self._challenges[challenge_id] = challenge
        
        return challenge
    
    def verify_payment(
        self,
        challenge_id: str,
        tx_hash: str,
        from_address: str,
        amount: str,
        block_number: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a payment against a challenge.
        
        In MVP, this is a simplified in-memory verification.
        In production, this would verify on-chain transactions.
        
        Args:
            challenge_id: The challenge ID to verify against
            tx_hash: Transaction hash of the payment
            from_address: Address that made the payment
            amount: Amount that was paid
            block_number: Block number (for on-chain verification)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get challenge
        challenge = self._challenges.get(challenge_id)
        if not challenge:
            return False, "Challenge not found"
        
        # Check expiration
        if challenge.is_expired:
            return False, "Challenge expired"
        
        # Check nonce (prevent replay)
        if tx_hash in self._nonces:
            return False, "Payment already used"
        
        # Verify amount
        if Decimal(amount) < Decimal(challenge.amount):
            return False, f"Insufficient payment: required {challenge.amount}, got {amount}"
        
        # Verify recipient
        # In production: verify on-chain that funds went to correct address
        # For MVP: trust the tx_hash provided
        
        # Mark nonce as used
        self._nonces[tx_hash] = int(time.time())
        
        return True, None
    
    def authorize_payment(
        self,
        agent_id: str,
        challenge_id: str,
        tx_hash: Optional[str] = None,
        block_number: Optional[int] = None,
    ) -> Optional[PaymentAuthorization]:
        """
        Create an authorization record after successful payment.
        
        Args:
            agent_id: The agent making the payment
            challenge_id: The challenge that was paid
            tx_hash: Payment transaction hash
            block_number: Block number of the payment
            
        Returns:
            PaymentAuthorization if successful, None otherwise
        """
        challenge = self._challenges.get(challenge_id)
        if not challenge:
            return None
        
        # Check rate limits
        if not self._check_rate_limit(agent_id, Decimal(challenge.amount)):
            return None
        
        # Create authorization
        auth_id = self._generate_auth_id(agent_id, challenge_id)
        auth = PaymentAuthorization(
            auth_id=auth_id,
            agent_id=agent_id,
            challenge_id=challenge_id,
            amount=challenge.amount,
            token=challenge.token,
            status=PaymentStatus.AUTHORIZED,
            used_count=0,
            max_usage=challenge.max_usage,
            tx_hash=tx_hash,
            block_number=block_number,
        )
        
        self._authorizations[auth_id] = auth
        
        # Update spending
        self._record_spending(agent_id, Decimal(challenge.amount))
        
        return auth
    
    def use_authorization(self, auth_id: str) -> Tuple[bool, Optional[str]]:
        """
        Use an authorization (decrement usage counter).
        
        Args:
            auth_id: Authorization ID to use
            
        Returns:
            Tuple of (success, error_message)
        """
        auth = self._authorizations.get(auth_id)
        if not auth:
            return False, "Authorization not found"
        
        if auth.status != PaymentStatus.AUTHORIZED:
            return False, f"Authorization not active: {auth.status}"
        
        if auth.used_count >= auth.max_usage:
            return False, "Authorization fully used"
        
        if int(time.time()) > auth.expires_at:
            auth.status = PaymentStatus.EXPIRED
            return False, "Authorization expired"
        
        auth.used_count += 1
        auth.updated_at = int(time.time())
        
        if auth.used_count >= auth.max_usage:
            auth.status = PaymentStatus.CAPTURED
        
        return True, None
    
    def refund_payment(self, auth_id: str) -> bool:
        """
        Refund a payment (marks authorization as refunded).
        
        Args:
            auth_id: Authorization ID to refund
            
        Returns:
            True if successful
        """
        auth = self._authorizations.get(auth_id)
        if not auth:
            return False
        
        if auth.status == PaymentStatus.REFUNDED:
            return False
        
        auth.status = PaymentStatus.REFUNDED
        auth.updated_at = int(time.time())
        
        return True
    
    def get_authorization(self, auth_id: str) -> Optional[PaymentAuthorization]:
        """Get an authorization by ID."""
        return self._authorizations.get(auth_id)
    
    def get_challenge(self, challenge_id: str) -> Optional[PaymentChallenge]:
        """Get a challenge by ID."""
        return self._challenges.get(challenge_id)
    
    def _check_rate_limit(self, agent_id: str, amount: Decimal) -> bool:
        """Check if agent is within rate limits."""
        now = int(time.time())
        day_ago = now - 86400
        
        # Get agent's spending history
        spending = self._agent_spending.get(agent_id, [])
        
        # Filter to last 24 hours
        spending = [(ts, amt) for ts, amt in spending if ts > day_ago]
        
        # Calculate total
        total = sum(amt for _, amt in spending)
        
        return total + amount <= self._daily_limit
    
    def _record_spending(self, agent_id: str, amount: Decimal) -> None:
        """Record agent spending for rate limiting."""
        now = int(time.time())
        if agent_id not in self._agent_spending:
            self._agent_spending[agent_id] = []
        self._agent_spending[agent_id].append((now, amount))
    
    def _generate_challenge_id(self, tool_id: str, amount: str) -> str:
        """Generate a unique challenge ID."""
        data = f"{tool_id}:{amount}:{time.time()}:{secrets.token_hex(8)}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    def _generate_auth_id(self, agent_id: str, challenge_id: str) -> str:
        """Generate a unique authorization ID."""
        data = f"{agent_id}:{challenge_id}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    def _build_payment_url(
        self,
        challenge_id: str,
        amount: str,
        token: TokenType,
        recipient: str,
    ) -> str:
        """Build a payment URL for easy payment."""
        # In production, this would be a proper payment link
        return f"pay://mcp-gateway/{challenge_id}?amount={amount}&token={token.value}&to={recipient}"
    
    def get_agent_spending(self, agent_id: str) -> Dict:
        """Get spending summary for an agent."""
        now = int(time.time())
        day_ago = now - 86400
        
        spending = self._agent_spending.get(agent_id, [])
        recent = [(ts, amt) for ts, amt in spending if ts > day_ago]
        total = sum(amt for _, amt in recent)
        
        return {
            "agent_id": agent_id,
            "total_24h": str(total),
            "limit": str(self._daily_limit),
            "remaining": str(self._daily_limit - total),
            "transaction_count_24h": len(recent),
        }
