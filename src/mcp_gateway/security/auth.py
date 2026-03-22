"""
Authentication and Authorization - DID and Verifiable Credentials.

Implements decentralized identity and authentication for agents.
"""

import hashlib
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import secrets


class TrustLevel(str, Enum):
    """Agent trust levels."""
    ANONYMOUS = "anonymous"
    VERIFIED = "verified"
    PREMIUM = "premium"
    GOVERNANCE = "governance"


class CredentialType(str, Enum):
    """Verifiable credential types."""
    AGENT_IDENTITY = "AgentIdentity"
    KYC = "KYC"
    PAYMENT_CAPACITY = "PaymentCapacity"
    TOOL_PROVIDER = "ToolProvider"
    ARBITER = "Arbiter"


@dataclass
class DIDDocument:
    """
    Decentralized Identifier Document.
    
    Represents an agent's identity on-chain.
    """
    id: str  # DID (e.g., did:mcp:abc123)
    public_key: Dict  # Public key info
    authentication: List[str]  # Authentication method IDs
    service: List[Dict] = field(default_factory=list)  # Service endpoints
    
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    
    # Metadata
    status: str = "active"
    last_auth: Optional[int] = None
    
    def to_dict(self) -> Dict:
        return {
            "@context": "https://www.w3.org/ns/did/v1",
            "id": self.id,
            "publicKey": [self.public_key],
            "authentication": self.authentication,
            "service": self.service,
            "created": self.created_at,
            "updated": self.updated_at,
        }


@dataclass
class VerifiableCredential:
    """
    Verifiable Credential (VC).
    
    A tamper-evident credential that can be verified cryptographically.
    """
    # Standard VC fields
    context: List[str] = field(default_factory=lambda: [
        "https://www.w3.org/2018/credentials/v1"
    ])
    type: List[str] = field(default_factory=lambda: ["VerifiableCredential"])
    issuer: str  # DID of issuer
    issuance_date: int = field(default_factory=lambda: int(time.time()))
    expiration_date: Optional[int] = None
    
    # Credential subject
    credential_subject: Dict = field(default_factory=dict)
    
    # Proof
    proof: Optional[Dict] = None
    
    # Metadata
    id: str = ""  # Credential ID
    
    def to_dict(self) -> Dict:
        return {
            "@context": self.context,
            "id": self.id,
            "type": self.type,
            "issuer": self.issuer,
            "issuanceDate": self.issuance_date,
            "expirationDate": self.expiration_date,
            "credentialSubject": self.credential_subject,
            "proof": self.proof,
        }
    
    @property
    def is_expired(self) -> bool:
        if self.expiration_date is None:
            return False
        return int(time.time()) > self.expiration_date


@dataclass
class AgentSession:
    """Agent session tracking."""
    agent_id: str
    did: str
    trust_level: TrustLevel
    
    # Session info
    session_id: str
    created_at: int = field(default_factory=lambda: int(time.time()))
    last_active: int = field(default_factory=lambda: int(time.time())))
    
    # Capabilities
    verified_credentials: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    
    # Limits
    rate_limit_per_minute: int = 60
    max_call_value: str = "1000000"  # Max value per call in micro-USDC


class AuthManager:
    """
    Authentication and Authorization Manager.
    
    Handles:
    - DID registration and management
    - Verifiable credential issuance
    - Session management
    - Permission checking
    """
    
    def __init__(
        self,
        gateway_did: str = "did:mcp:gateway-authority",
        gateway_private_key: Optional[bytes] = None,
    ):
        self.gateway_did = gateway_did
        self.gateway_private_key = gateway_private_key or secrets.token_bytes(32)
        
        # In-memory storage
        self._dids: Dict[str, DIDDocument] = {}
        self._credentials: Dict[str, List[VerifiableCredential]] = {}
        self._sessions: Dict[str, AgentSession] = {}
        self._revoked_credentials: set = set()
        
        # Rate limiting
        self._auth_attempts: Dict[str, List[int]] = {}  # address -> timestamps
        self._max_auth_attempts = 5  # per minute
    
    def generate_did(self, agent_id: str, public_key: Optional[Dict] = None) -> DIDDocument:
        """
        Generate a new DID for an agent.
        
        Args:
            agent_id: Agent's unique identifier
            public_key: Optional public key info
            
        Returns:
            DIDDocument
        """
        # Generate DID
        data = f"{agent_id}:{time.time()}:{secrets.token_hex(8)}"
        did_hash = hashlib.sha256(data.encode()).hexdigest()[:16]
        did = f"did:mcp:{did_hash}"
        
        # Create document
        doc = DIDDocument(
            id=did,
            public_key=public_key or {
                "id": f"{did}#keys-1",
                "type": "EcdsaSecp256k1VerificationKey2019",
                "controller": did,
                "publicKeyHex": secrets.token_hex(33),
            },
            authentication=[f"{did}#keys-1"],
            service=[{
                "id": f"{did}#payment",
                "type": "PaymentService",
                "endpoint": f"https://gateway.mcp.tools/did/{did}",
            }],
        )
        
        self._dids[did] = doc
        self._credentials[did] = []
        
        return doc
    
    def get_did(self, did: str) -> Optional[DIDDocument]:
        """Get a DID document."""
        return self._dids.get(did)
    
    def get_did_by_agent_id(self, agent_id: str) -> Optional[DIDDocument]:
        """Get a DID by agent ID."""
        for did, doc in self._dids.items():
            if agent_id in did:
                return doc
        return None
    
    def issue_credential(
        self,
        issuer_did: str,
        subject_did: str,
        credential_type: CredentialType,
        claims: Dict,
        expiration_days: Optional[int] = 365,
    ) -> VerifiableCredential:
        """
        Issue a verifiable credential.
        
        Args:
            issuer_did: DID of the issuer (typically gateway)
            subject_did: DID of the credential subject
            credential_type: Type of credential
            claims: Credential claims
            expiration_days: Days until expiration
            
        Returns:
            VerifiableCredential
        """
        # Generate credential ID
        cred_id = hashlib.sha256(
            f"{subject_did}:{credential_type.value}:{time.time()}".encode()
        ).hexdigest()[:32]
        
        # Create credential
        vc = VerifiableCredential(
            id=f"urn:uuid:{cred_id}",
            issuer=issuer_did,
            type=["VerifiableCredential", credential_type.value],
            credential_subject={
                "id": subject_did,
                **claims,
            },
            expiration_date=(
                int(time.time()) + expiration_days * 86400
                if expiration_days else None
            ),
        )
        
        # Generate proof (simplified - in production use proper crypto)
        vc.proof = {
            "type": "EcdsaSecp256k1Signature2019",
            "created": int(time.time()),
            "proofPurpose": "assertionMethod",
            "verificationMethod": f"{issuer_did}#keys-1",
            "signatureValue": secrets.token_hex(64),
        }
        
        # Store
        if subject_did not in self._credentials:
            self._credentials[subject_did] = []
        self._credentials[subject_did].append(vc)
        
        return vc
    
    def verify_credential(self, vc: VerifiableCredential) -> tuple[bool, str]:
        """
        Verify a verifiable credential.
        
        Args:
            vc: Credential to verify
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check expiration
        if vc.is_expired:
            return False, "Credential expired"
        
        # Check if revoked
        if vc.id in self._revoked_credentials:
            return False, "Credential revoked"
        
        # Verify issuer
        if vc.issuer != self.gateway_did:
            # In production, verify issuer's signature
            pass
        
        # Verify proof
        if not vc.proof:
            return False, "No proof"
        
        # In production, verify cryptographic proof
        
        return True, "Valid"
    
    def revoke_credential(self, cred_id: str) -> bool:
        """Revoke a credential."""
        self._revoked_credentials.add(cred_id)
        return True
    
    def get_credentials(self, did: str) -> List[VerifiableCredential]:
        """Get all credentials for a DID."""
        return self._credentials.get(did, [])
    
    def create_session(
        self,
        did: str,
        trust_level: TrustLevel = TrustLevel.ANONYMOUS,
        credentials: Optional[List[str]] = None,
    ) -> AgentSession:
        """
        Create a new agent session.
        
        Args:
            did: Agent's DID
            trust_level: Initial trust level
            credentials: List of credential IDs to include
            
        Returns:
            AgentSession
        """
        session_id = hashlib.sha256(
            f"{did}:{time.time()}:{secrets.token_hex(16)}".encode()
        ).hexdigest()[:32]
        
        # Determine permissions based on trust level
        permissions = self._get_permissions_for_level(trust_level)
        
        session = AgentSession(
            agent_id=did,
            did=did,
            trust_level=trust_level,
            session_id=session_id,
            verified_credentials=credentials or [],
            permissions=permissions,
        )
        
        self._sessions[session_id] = session
        
        return session
    
    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get a session by ID."""
        session = self._sessions.get(session_id)
        if session:
            session.last_active = int(time.time())
        return session
    
    def validate_auth(self, address: str, signature: str) -> tuple[bool, Optional[AgentSession]]:
        """
        Validate authentication from an agent.
        
        Args:
            address: Agent's wallet address
            signature: Signature of authentication message
            
        Returns:
            Tuple of (is_valid, session)
        """
        # Check rate limit
        if not self._check_rate_limit(address):
            return False, None
        
        # In production, verify signature
        # For MVP, accept any non-empty signature
        
        # Find or create DID
        did = self._get_did_by_address(address)
        if not did:
            did_doc = self.generate_did(address)
            did = did_doc.id
        
        # Get trust level from credentials
        creds = self.get_credentials(did)
        trust_level = self._determine_trust_level(creds)
        
        # Create session
        session = self.create_session(
            did=did,
            trust_level=trust_level,
            credentials=[c.id for c in creds],
        )
        
        return True, session
    
    def check_permission(self, session_id: str, permission: str) -> bool:
        """Check if a session has a specific permission."""
        session = self.get_session(session_id)
        if not session:
            return False
        return permission in session.permissions
    
    def _get_permissions_for_level(self, level: TrustLevel) -> List[str]:
        """Get default permissions for a trust level."""
        base = ["read:tools", "execute:free"]
        
        if level == TrustLevel.VERIFIED:
            return base + ["execute:paid", "create:tools"]
        elif level == TrustLevel.PREMIUM:
            return base + ["execute:paid", "create:tools", "execute:unlimited", "webhooks"]
        elif level == TrustLevel.GOVERNANCE:
            return base + ["*"]  # All permissions
        else:
            return base  # Just basic permissions
    
    def _determine_trust_level(self, credentials: List[VerifiableCredential]) -> TrustLevel:
        """Determine trust level from credentials."""
        types = [c.type for c in credentials]
        
        if any("KYC" in t for t in types):
            return TrustLevel.VERIFIED
        
        if any("Arbiter" in t for t in types):
            return TrustLevel.GOVERNANCE
        
        return TrustLevel.ANONYMOUS
    
    def _get_did_by_address(self, address: str) -> Optional[str]:
        """Get DID by wallet address."""
        for did, doc in self._dids.items():
            if address.lower() in did.lower():
                return did
        return None
    
    def _check_rate_limit(self, address: str) -> bool:
        """Check authentication rate limit."""
        now = int(time.time())
        minute_ago = now - 60
        
        attempts = self._auth_attempts.get(address, [])
        attempts = [t for t in attempts if t > minute_ago]
        
        if len(attempts) >= self._max_auth_attempts:
            return False
        
        attempts.append(now)
        self._auth_attempts[address] = attempts
        
        return True
    
    def get_stats(self) -> Dict:
        """Get authentication statistics."""
        return {
            "total_dids": len(self._dids),
            "total_credentials": sum(len(v) for v in self._credentials.values()),
            "active_sessions": len(self._sessions),
            "revoked_credentials": len(self._revoked_credentials),
        }
