"""
Escrow Manager - Secure fund management for tool execution.

Implements time-locked escrow with automatic refunds and dispute resolution.
"""

import hashlib
import time
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List, Tuple
from enum import Enum
from decimal import Decimal
import asyncio


class EscrowStatus(str, Enum):
    """Escrow status enumeration."""
    PENDING = "pending"           # Created, not funded
    FUNDED = "funded"             # Funds received
    LOCKED = "locked"             # Execution in progress
    COMPLETED = "completed"       # Successfully executed
    REFUNDED = "refunded"         # Refunded to payer
    DISPUTED = "disputed"         # Under dispute resolution
    EXPIRED = "expired"          # Timed out
    PARTIAL = "partial"           # Partial execution, partial refund


class DisputeReason(str, Enum):
    """Reasons for opening a dispute."""
    OUTPUT_WRONG = "output_wrong"
    TIMEOUT = "timeout"
    OVERCHARGE = "overcharge"
    TOOL_MALICIOUS = "tool_malicious"
    OTHER = "other"


@dataclass
class EscrowReleaseCondition:
    """Conditions for releasing escrow funds."""
    require_success_attestation: bool = True
    max_execution_time_ms: int = 30000
    auto_refund_after_ms: int = 60000
    require_provider_signature: bool = True


@dataclass
class Dispute:
    """Dispute record for escrow."""
    dispute_id: str
    escrow_id: str
    
    # Who opened
    opened_by: str
    reason: DisputeReason
    
    # Evidence (IPFS CIDs)
    evidence: List[str] = field(default_factory=list)
    
    # Status
    status: str = "open"  # open, under_review, resolved
    resolution: Optional[str] = None
    payer_amount: Optional[str] = None  # Amount to refund payer
    beneficiary_amount: Optional[str] = None  # Amount to pay beneficiary
    
    # Timestamps
    opened_at: int = field(default_factory=lambda: int(time.time()))
    resolved_at: Optional[int] = None
    
    # Arbiter
    assigned_arbiter: Optional[str] = None
    arbiter_notes: Optional[str] = None


@dataclass
class EscrowAccount:
    """
    Escrow account for a tool execution.
    
    Holds funds securely until:
    1. Tool executes successfully -> funds released to provider
    2. Tool fails or times out -> funds refunded to payer
    3. Dispute opened -> funds held until resolution
    """
    # Escrow identifier
    escrow_id: str
    
    # Parties
    payer: str                    # Agent paying for execution
    beneficiary: str              # Tool provider receiving payment
    provider: str                 # Provider's address (can differ from beneficiary)
    
    # Funds
    amount: str                   # Amount held in escrow
    token: str = "USDC"           # Token type
    
    # Tool
    tool_id: str
    tool_name: str
    input_hash: str               # Hash of input for verification
    output_hash: Optional[str] = None  # Hash of output (set after execution)
    
    # Status
    status: EscrowStatus = EscrowStatus.PENDING
    
    # Release conditions
    release_conditions: EscrowReleaseCondition = field(
        default_factory=EscrowReleaseCondition
    )
    
    # Execution tracking
    execution_attestation_id: Optional[str] = None
    execution_started_at: Optional[int] = None
    execution_completed_at: Optional[int] = None
    
    # Refund tracking
    released_amount: Optional[str] = None
    refunded_amount: Optional[str] = None
    
    # Timestamps
    created_at: int = field(default_factory=lambda: int(time.time()))
    funded_at: Optional[int] = None
    locked_at: Optional[int] = None
    expires_at: int = field(
        default_factory=lambda: int(time.time()) + 300  # 5 min default
    )
    
    # Dispute
    dispute: Optional[Dispute] = None
    
    # History (for auditing)
    history: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        return d
    
    @property
    def is_expired(self) -> bool:
        """Check if escrow has expired."""
        return int(time.time()) > self.expires_at
    
    @property
    def can_be_refunded(self) -> bool:
        """Check if funds can be refunded."""
        return self.status in [
            EscrowStatus.FUNDED,
            EscrowStatus.EXPIRED
        ] and self.dispute is None
    
    @property
    def can_be_released(self) -> bool:
        """Check if funds can be released to beneficiary."""
        return (
            self.status == EscrowStatus.LOCKED and
            self.execution_completed_at is not None
        )
    
    def add_history(self, event: str, details: Dict = None) -> None:
        """Add an event to history."""
        entry = {
            "event": event,
            "timestamp": int(time.time()),
            "details": details or {}
        }
        self.history.append(entry)


class EscrowManager:
    """
    Manages escrow accounts for secure tool execution payments.
    
    Features:
    - Time-locked escrow
    - Automatic refunds on timeout
    - Dispute resolution with arbiter
    - Partial refunds for partial execution
    - Multi-signature support for high-value
    """
    
    def __init__(
        self,
        arbiter_address: str = "0x0000000000000000000000000000000000000001",
        default_timeout_seconds: int = 300,
        dispute_window_seconds: int = 86400,
        slash_percent: int = 10,
    ):
        self.arbiter_address = arbiter_address
        self.default_timeout = default_timeout_seconds
        self.dispute_window = dispute_window_seconds
        self.slash_percent = slash_percent
        
        # In-memory storage for MVP
        self._escrows: Dict[str, EscrowAccount] = {}
        self._disputes: Dict[str, Dispute] = {}
        
        # Background task for expiration checking
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start background tasks (e.g., expiration checker)."""
        self._cleanup_task = asyncio.create_task(self._expiration_checker())
    
    async def stop(self) -> None:
        """Stop background tasks."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _expiration_checker(self) -> None:
        """Background task to auto-refund expired escrows."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._process_expired_escrows()
            except asyncio.CancelledError:
                break
            except Exception:
                pass  # Log in production
    
    async def _process_expired_escrows(self) -> None:
        """Process all expired escrows."""
        now = int(time.time())
        for escrow_id, escrow in list(self._escrows.items()):
            if escrow.status == EscrowStatus.FUNDED and now > escrow.expires_at:
                await self._auto_expire(escrow)
            elif escrow.status == EscrowStatus.LOCKED:
                # Check if execution timed out
                max_time = escrow.release_conditions.auto_refund_after_ms / 1000
                if escrow.execution_started_at:
                    elapsed = now - escrow.execution_started_at
                    if elapsed > max_time and escrow.execution_completed_at is None:
                        await self._auto_refund_timeout(escrow)
    
    async def _auto_expire(self, escrow: EscrowAccount) -> None:
        """Automatically expire an escrow."""
        escrow.status = EscrowStatus.EXPIRED
        escrow.refunded_amount = escrow.amount
        escrow.add_history("auto_expired", {"reason": "timeout"})
        # Refund would happen via on-chain tx in production
    
    async def _auto_refund_timeout(self, escrow: EscrowAccount) -> None:
        """Auto-refund on execution timeout."""
        escrow.status = EscrowStatus.REFUNDED
        escrow.refunded_amount = escrow.amount
        escrow.add_history("auto_refund", {"reason": "timeout"})
    
    async def create_escrow(
        self,
        payer: str,
        beneficiary: str,
        provider: str,
        tool_id: str,
        tool_name: str,
        amount: str,
        token: str = "USDC",
        input_data: Optional[Dict] = None,
        timeout_seconds: Optional[int] = None,
        release_conditions: Optional[EscrowReleaseCondition] = None,
    ) -> EscrowAccount:
        """
        Create a new escrow account.
        
        Args:
            payer: Address paying for execution
            beneficiary: Address receiving payment
            provider: Actual tool provider
            tool_id: Tool being executed
            tool_name: Human-readable tool name
            amount: Amount to hold
            token: Token type
            input_data: Input data (for hash verification)
            timeout_seconds: Timeout before auto-refund
            release_conditions: Custom release conditions
            
        Returns:
            Created EscrowAccount
        """
        # Generate escrow ID
        escrow_id = self._generate_escrow_id(payer, beneficiary, tool_id, amount)
        
        # Create input hash
        input_hash = ""
        if input_data:
            input_json = json.dumps(input_data, sort_keys=True)
            input_hash = hashlib.sha256(input_json.encode()).hexdigest()
        
        # Default release conditions
        if release_conditions is None:
            release_conditions = EscrowReleaseCondition(
                require_success_attestation=True,
                max_execution_time_ms=30000,
                auto_refund_after_ms=60000,
            )
        
        # Create escrow
        escrow = EscrowAccount(
            escrow_id=escrow_id,
            payer=payer,
            beneficiary=beneficiary,
            provider=provider,
            amount=amount,
            token=token,
            tool_id=tool_id,
            tool_name=tool_name,
            input_hash=input_hash,
            release_conditions=release_conditions,
            expires_at=int(time.time()) + (timeout_seconds or self.default_timeout),
        )
        
        escrow.add_history("created", {
            "payer": payer,
            "beneficiary": beneficiary,
            "amount": amount,
        })
        
        self._escrows[escrow_id] = escrow
        
        return escrow
    
    async def fund_escrow(
        self,
        escrow_id: str,
        tx_hash: str,
        from_address: str,
    ) -> Tuple[bool, str]:
        """
        Mark escrow as funded (funds received).
        
        Args:
            escrow_id: Escrow to fund
            tx_hash: Transaction hash of the deposit
            from_address: Address that sent the funds
            
        Returns:
            Tuple of (success, message)
        """
        escrow = self._escrows.get(escrow_id)
        if not escrow:
            return False, "Escrow not found"
        
        if escrow.status != EscrowStatus.PENDING:
            return False, f"Escrow not pending: {escrow.status}"
        
        if from_address.lower() != escrow.payer.lower():
            return False, "Funds not from payer"
        
        escrow.status = EscrowStatus.FUNDED
        escrow.funded_at = int(time.time())
        escrow.add_history("funded", {"tx_hash": tx_hash})
        
        return True, "Escrow funded successfully"
    
    async def lock_escrow(self, escrow_id: str) -> Tuple[bool, str]:
        """
        Lock escrow for execution (prevents refund during execution).
        
        Args:
            escrow_id: Escrow to lock
            
        Returns:
            Tuple of (success, message)
        """
        escrow = self._escrows.get(escrow_id)
        if not escrow:
            return False, "Escrow not found"
        
        if escrow.status != EscrowStatus.FUNDED:
            return False, f"Escrow not funded: {escrow.status}"
        
        escrow.status = EscrowStatus.LOCKED
        escrow.locked_at = int(time.time())
        escrow.execution_started_at = int(time.time())
        escrow.add_history("locked", {"message": "Execution started"})
        
        return True, "Escrow locked for execution"
    
    async def complete_execution(
        self,
        escrow_id: str,
        success: bool,
        output_data: Optional[Dict] = None,
        attestation_id: Optional[str] = None,
        partial_refund_percent: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Mark execution as completed and handle fund distribution.
        
        Args:
            escrow_id: Escrow to complete
            success: Whether execution was successful
            output_data: Output data (for hash verification)
            attestation_id: Execution attestation ID
            partial_refund_percent: For partial execution, % to refund
            
        Returns:
            Tuple of (success, message)
        """
        escrow = self._escrows.get(escrow_id)
        if not escrow:
            return False, "Escrow not found"
        
        if escrow.status != EscrowStatus.LOCKED:
            return False, f"Escrow not locked: {escrow.status}"
        
        # Update output hash
        if output_data:
            output_json = json.dumps(output_data, sort_keys=True)
            escrow.output_hash = hashlib.sha256(output_json.encode()).hexdigest()
        
        escrow.execution_completed_at = int(time.time())
        
        if success:
            # Full release to beneficiary
            escrow.status = EscrowStatus.COMPLETED
            escrow.released_amount = escrow.amount
            escrow.execution_attestation_id = attestation_id
            escrow.add_history("completed", {
                "released_to": escrow.beneficiary,
                "amount": escrow.amount,
            })
            return True, f"Escrow completed, {escrow.amount} released to {escrow.beneficiary}"
        
        elif partial_refund_percent is not None:
            # Partial execution - split funds
            escrow.status = EscrowStatus.PARTIAL
            refund_amount = str(
                float(escrow.amount) * partial_refund_percent / 100
            )
            release_amount = str(float(escrow.amount) - float(refund_amount))
            
            escrow.refunded_amount = refund_amount
            escrow.released_amount = release_amount
            escrow.add_history("partial", {
                "refunded_to": escrow.payer,
                "refund_amount": refund_amount,
                "released_to": escrow.beneficiary,
                "release_amount": release_amount,
            })
            return True, f"Partial: {refund_amount} refunded, {release_amount} released"
        
        else:
            # Full refund
            escrow.status = EscrowStatus.REFUNDED
            escrow.refunded_amount = escrow.amount
            escrow.add_history("refunded", {
                "refunded_to": escrow.payer,
                "amount": escrow.amount,
            })
            return True, f"Escrow refunded, {escrow.amount} returned to {escrow.payer}"
    
    async def open_dispute(
        self,
        escrow_id: str,
        opened_by: str,
        reason: DisputeReason,
        evidence: Optional[List[str]] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Open a dispute for an escrow.
        
        Args:
            escrow_id: Escrow to dispute
            opened_by: Address opening dispute
            reason: Reason for dispute
            evidence: IPFS CIDs of evidence
            
        Returns:
            Tuple of (success, message, dispute_id)
        """
        escrow = self._escrows.get(escrow_id)
        if not escrow:
            return False, "Escrow not found", None
        
        # Verify opener is authorized
        if opened_by.lower() not in [escrow.payer.lower(), escrow.beneficiary.lower()]:
            return False, "Not authorized to open dispute", None
        
        # Check dispute window
        if escrow.execution_completed_at:
            window_end = escrow.execution_completed_at + self.dispute_window
            if int(time.time()) > window_end:
                return False, "Dispute window closed", None
        
        # Check escrow status
        if escrow.dispute is not None:
            return False, "Dispute already open", None
        
        # Create dispute
        dispute_id = self._generate_dispute_id(escrow_id, opened_by)
        dispute = Dispute(
            dispute_id=dispute_id,
            escrow_id=escrow_id,
            opened_by=opened_by,
            reason=reason,
            evidence=evidence or [],
            assigned_arbiter=self.arbiter_address,
        )
        
        escrow.dispute = dispute
        escrow.status = EscrowStatus.DISPUTED
        escrow.add_history("dispute_opened", {
            "dispute_id": dispute_id,
            "reason": reason.value,
        })
        
        self._disputes[dispute_id] = dispute
        
        return True, f"Dispute opened: {dispute_id}", dispute_id
    
    async def resolve_dispute(
        self,
        dispute_id: str,
        arbiter_address: str,
        payer_amount: str,
        beneficiary_amount: str,
        arbiter_notes: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Resolve a dispute.
        
        Args:
            dispute_id: Dispute to resolve
            arbiter_address: Arbiter making the decision
            payer_amount: Amount to refund payer
            beneficiary_amount: Amount to pay beneficiary
            arbiter_notes: Arbiter's notes
            
        Returns:
            Tuple of (success, message)
        """
        if arbiter_address.lower() != self.arbiter_address.lower():
            return False, "Not authorized to resolve dispute"
        
        dispute = self._disputes.get(dispute_id)
        if not dispute:
            return False, "Dispute not found"
        
        escrow = self._escrows.get(dispute.escrow_id)
        if not escrow:
            return False, "Escrow not found"
        
        # Validate amounts
        total = float(payer_amount) + float(beneficiary_amount)
        if total > float(escrow.amount):
            return False, "Amounts exceed escrow balance"
        
        # Resolve dispute
        dispute.status = "resolved"
        dispute.resolved_at = int(time.time())
        dispute.payer_amount = payer_amount
        dispute.beneficiary_amount = beneficiary_amount
        dispute.arbiter_notes = arbiter_notes
        
        escrow.refunded_amount = payer_amount
        escrow.released_amount = beneficiary_amount
        escrow.status = EscrowStatus.COMPLETED  # or REFUNDED if 100% refund
        if float(payer_amount) == float(escrow.amount):
            escrow.status = EscrowStatus.REFUNDED
        
        escrow.add_history("dispute_resolved", {
            "payer_amount": payer_amount,
            "beneficiary_amount": beneficiary_amount,
            "arbiter": arbiter_address,
        })
        
        return True, f"Dispute resolved: {payer_amount} to payer, {beneficiary_amount} to beneficiary"
    
    async def get_escrow(self, escrow_id: str) -> Optional[EscrowAccount]:
        """Get an escrow by ID."""
        return self._escrows.get(escrow_id)
    
    async def get_dispute(self, dispute_id: str) -> Optional[Dispute]:
        """Get a dispute by ID."""
        return self._disputes.get(dispute_id)
    
    async def get_escrows_by_payer(self, payer: str) -> List[EscrowAccount]:
        """Get all escrows for a payer."""
        return [
            e for e in self._escrows.values()
            if e.payer.lower() == payer.lower()
        ]
    
    async def get_escrows_by_beneficiary(self, beneficiary: str) -> List[EscrowAccount]:
        """Get all escrows for a beneficiary."""
        return [
            e for e in self._escrows.values()
            if e.beneficiary.lower() == beneficiary.lower()
        ]
    
    async def get_active_disputes(self) -> List[Dispute]:
        """Get all open disputes."""
        return [d for d in self._disputes.values() if d.status == "open"]
    
    def _generate_escrow_id(
        self,
        payer: str,
        beneficiary: str,
        tool_id: str,
        amount: str,
    ) -> str:
        """Generate a unique escrow ID."""
        data = f"{payer}:{beneficiary}:{tool_id}:{amount}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    def _generate_dispute_id(self, escrow_id: str, opener: str) -> str:
        """Generate a unique dispute ID."""
        data = f"{escrow_id}:{opener}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    def get_stats(self) -> Dict:
        """Get escrow statistics."""
        total = len(self._escrows)
        by_status = {}
        for escrow in self._escrows.values():
            status = escrow.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        total_disputes = len(self._disputes)
        open_disputes = len([d for d in self._disputes.values() if d.status == "open"])
        
        return {
            "total_escrows": total,
            "by_status": by_status,
            "total_disputes": total_disputes,
            "open_disputes": open_disputes,
        }
