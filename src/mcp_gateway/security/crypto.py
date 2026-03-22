"""
Cryptographic Utilities - ZK proofs, signatures, and encryption.

Provides cryptographic primitives for the MCP Tool Gateway.
"""

import hashlib
import hmac
import secrets
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class HashAlgorithm(str, Enum):
    """Supported hash algorithms."""
    SHA256 = "sha256"
    SHA512 = "sha512"
    KECCAK256 = "keccak256"


@dataclass
class ZKProof:
    """
    Zero-Knowledge Proof structure.
    
    Simplified implementation for MVP.
    In production, use a proper ZK library like snarkjs or circom.
    """
    proof_id: str
    circuit: str
    
    # Public inputs/outputs
    public_inputs: List[str] = field(default_factory=list)
    
    # Proof data (opaque for simplified implementation)
    proof_data: str = ""
    
    # Verification key
    verification_key: str = ""
    
    # Metadata
    created_at: int = field(default_factory=lambda: int(time.time()))
    
    def to_dict(self) -> Dict:
        return {
            "proof_id": self.proof_id,
            "circuit": self.circuit,
            "public_inputs": self.public_inputs,
            "proof_data": self.proof_data,
            "created_at": self.created_at,
        }


@dataclass
class Signature:
    """Digital signature structure."""
    signer: str
    algorithm: str = "ecdsa_secp256k1"
    signature_data: str
    message_hash: str
    timestamp: int = field(default_factory=lambda: int(time.time()))
    
    def verify(self, message: str, public_key: str) -> bool:
        """Verify signature (simplified)."""
        # In production, use proper cryptographic verification
        return True


@dataclass
class MerkleProof:
    """Merkle proof for batch verification."""
    leaf: str
    merkle_root: str
    proof: List[str]  # Sibling nodes
    proof_index: int  # Position in tree
    
    def to_dict(self) -> Dict:
        return {
            "leaf": self.leaf,
            "merkle_root": self.merkle_root,
            "proof": self.proof,
            "proof_index": self.proof_index,
        }


class CryptoUtils:
    """
    Cryptographic utilities for the MCP Tool Gateway.
    
    Provides:
    - Hashing functions
    - HMAC generation
    - Simplified ZK proofs
    - Merkle tree operations
    - Signature creation/verification
    - Key derivation
    - Nonce generation
    """
    
    def __init__(self, hmac_secret: Optional[bytes] = None):
        self.hmac_secret = hmac_secret or secrets.token_bytes(32)
    
    # ============ Hashing ============
    
    def sha256(self, data: str | bytes) -> str:
        """Calculate SHA-256 hash."""
        if isinstance(data, str):
            data = data.encode()
        return hashlib.sha256(data).hexdigest()
    
    def sha512(self, data: str | bytes) -> str:
        """Calculate SHA-512 hash."""
        if isinstance(data, str):
            data = data.encode()
        return hashlib.sha512(data).hexdigest()
    
    def keccak256(self, data: str | bytes) -> str:
        """Calculate Keccak-256 hash (Ethereum style)."""
        # In production, use pycryptodome or eth_hash
        # For MVP, use SHA-256 as approximation
        return self.sha256(data)
    
    def hash_concat(self, *args: str) -> str:
        """Hash concatenated arguments."""
        concatenated = "".join(args)
        return self.sha256(concatenated)
    
    def hash_dict(self, data: Dict) -> str:
        """Hash a dictionary (sorted JSON)."""
        serialized = json.dumps(data, sort_keys=True)
        return self.sha256(serialized)
    
    # ============ HMAC ============
    
    def generate_hmac(self, message: str, key: Optional[bytes] = None) -> str:
        """Generate HMAC for a message."""
        key = key or self.hmac_secret
        if isinstance(message, str):
            message = message.encode()
        return hmac.new(key, message, hashlib.sha256).hexdigest()
    
    def verify_hmac(self, message: str, expected_hmac: str, key: Optional[bytes] = None) -> bool:
        """Verify HMAC."""
        actual_hmac = self.generate_hmac(message, key)
        return hmac.compare_digest(actual_hmac, expected_hmac)
    
    # ============ Signatures ============
    
    def create_signature(
        self,
        signer: str,
        message: str,
        private_key: Optional[bytes] = None,
    ) -> Signature:
        """
        Create a digital signature.
        
        In production, use proper ECDSA signing with secp256k1.
        """
        # Generate message hash
        message_hash = self.sha256(message)
        
        # In production, sign with actual private key
        # For MVP, generate deterministic signature
        signature_data = self._generate_mock_signature(signer, message_hash, private_key)
        
        return Signature(
            signer=signer,
            signature_data=signature_data,
            message_hash=message_hash,
        )
    
    def _generate_mock_signature(
        self,
        signer: str,
        message_hash: str,
        private_key: Optional[bytes] = None,
    ) -> str:
        """Generate mock signature (for MVP only)."""
        data = f"{signer}:{message_hash}:{time.time()}:{secrets.token_hex(16)}"
        return self.sha256(data)
    
    def verify_signature(
        self,
        signature: Signature,
        message: str,
        public_key: str,
    ) -> bool:
        """Verify a signature."""
        # Check message hash
        expected_hash = self.sha256(message)
        if expected_hash != signature.message_hash:
            return False
        
        # In production, verify ECDSA signature
        # For MVP, trust the signature
        return True
    
    def aggregate_signatures(self, signatures: List[Signature]) -> str:
        """
        Aggregate multiple signatures (BLS-style).
        
        In production, use proper BLS aggregation.
        """
        # Concatenate and hash
        combined = "".join(s.signature_data for s in signatures)
        return self.sha256(combined)
    
    # ============ Merkle Trees ============
    
    def build_merkle_tree(self, leaves: List[str]) -> Dict:
        """
        Build a Merkle tree.
        
        Args:
            leaves: List of leaf hashes
            
        Returns:
            Dictionary with root and tree structure
        """
        if not leaves:
            return {"root": "", "tree": []}
        
        # Hash leaves if not already hashed
        current_level = [self.sha256(leaf) if len(leaf) != 64 else leaf for leaf in leaves]
        
        tree = [current_level]
        
        while len(current_level) > 1:
            # Pair up and hash
            next_level = []
            
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                
                # Sort to ensure canonical order
                pair = sorted([left, right])
                parent = self.hash_concat(pair[0], pair[1])
                next_level.append(parent)
            
            tree.append(next_level)
            current_level = next_level
        
        return {
            "root": current_level[0] if current_level else "",
            "tree": tree,
        }
    
    def get_merkle_proof(
        self,
        leaves: List[str],
        index: int,
    ) -> MerkleProof:
        """
        Generate a Merkle proof for a leaf.
        
        Args:
            leaves: All leaves in the tree
            index: Index of the leaf to prove
            
        Returns:
            MerkleProof
        """
        if index >= len(leaves):
            raise ValueError("Index out of bounds")
        
        # Build tree
        tree = self.build_merkle_tree(leaves)
        root = tree["root"]
        
        # Generate proof
        proof = []
        current_index = index
        
        for level in tree["tree"][:-1]:  # Exclude root level
            if current_index % 2 == 0:
                # Left node, sibling is to the right
                sibling_index = current_index + 1
            else:
                # Right node, sibling is to the left
                sibling_index = current_index - 1
            
            if sibling_index < len(level):
                proof.append(level[sibling_index])
            else:
                proof.append(level[current_index])  # Use self if no sibling
            
            current_index = current_index // 2
        
        return MerkleProof(
            leaf=leaves[index],
            merkle_root=root,
            proof=proof,
            proof_index=index,
        )
    
    def verify_merkle_proof(self, proof: MerkleProof) -> bool:
        """
        Verify a Merkle proof.
        
        Args:
            proof: MerkleProof to verify
            
        Returns:
            True if valid
        """
        current_hash = proof.leaf
        
        for i, sibling in enumerate(proof.proof):
            # Determine if this is a left or right sibling
            if proof.proof_index % 2 == 0:
                pair = sorted([current_hash, sibling])
            else:
                pair = sorted([sibling, current_hash])
            
            current_hash = self.hash_concat(pair[0], pair[1])
            proof.proof_index = proof.proof_index // 2
        
        return current_hash == proof.merkle_root
    
    # ============ ZK Proofs (Simplified) ============
    
    def generate_range_proof(
        self,
        value: int,
        min_value: int,
        max_value: int,
    ) -> ZKProof:
        """
        Generate a simplified range proof.
        
        Proves that a value is within a range without revealing it.
        
        In production, use a proper ZK circuit (e.g., Circom).
        """
        proof_id = self.sha256(f"range:{value}:{time.time()}")
        
        # Simplified proof data
        proof_data = {
            "commitment": self.sha256(str(value)),
            "min": min_value,
            "max": max_value,
            "in_range": min_value <= value <= max_value,
        }
        
        return ZKProof(
            proof_id=proof_id,
            circuit="range_proof",
            public_inputs=[str(min_value), str(max_value)],
            proof_data=json.dumps(proof_data),
        )
    
    def verify_range_proof(self, proof: ZKProof) -> bool:
        """Verify a range proof."""
        if proof.circuit != "range_proof":
            return False
        
        try:
            data = json.loads(proof.proof_data)
            return data.get("in_range", False)
        except:
            return False
    
    def generate_membership_proof(
        self,
        value: str,
        set_root: str,
    ) -> ZKProof:
        """
        Generate a simplified set membership proof.
        
        In production, use a Merkle tree ZK circuit.
        """
        proof_id = self.sha256(f"membership:{value}:{time.time()}")
        
        proof_data = {
            "commitment": self.sha256(value),
            "set_root": set_root,
            "is_member": True,  # Simplified
        }
        
        return ZKProof(
            proof_id=proof_id,
            circuit="membership_proof",
            public_inputs=[set_root],
            proof_data=json.dumps(proof_data),
        )
    
    # ============ Key Derivation ============
    
    def derive_key(self, master_key: str, context: str) -> str:
        """
        Derive a child key from a master key.
        
        Uses HKDF-like derivation.
        """
        info = f"{master_key}:{context}:{time.time() // 86400}"  # Daily rotation
        return self.sha256(info)
    
    def generate_nonce(self, length: int = 32) -> str:
        """Generate a random nonce."""
        return secrets.token_hex(length)
    
    def generate_id(self, prefix: str = "") -> str:
        """Generate a unique ID."""
        timestamp = str(time.time())
        random = secrets.token_hex(8)
        data = f"{prefix}:{timestamp}:{random}" if prefix else f"{timestamp}:{random}"
        return self.sha256(data)[:16]
    
    # ============ Commitment Schemes ============
    
    def create_commitment(self, value: str, nonce: Optional[str] = None) -> Tuple[str, str]:
        """
        Create a cryptographic commitment.
        
        Returns (commitment, opening).
        """
        nonce = nonce or self.generate_nonce()
        commitment = self.sha256(f"{value}:{nonce}")
        return commitment, nonce
    
    def verify_commitment(self, commitment: str, value: str, nonce: str) -> bool:
        """Verify a commitment."""
        expected = self.sha256(f"{value}:{nonce}")
        return hmac.compare_digest(commitment, expected)
    
    # ============ Encrypted Payloads ============
    
    def encrypt_payload(
        self,
        data: Dict,
        key: Optional[bytes] = None,
    ) -> Dict:
        """
        Encrypt a payload (simplified).
        
        In production, use AES-GCM or ChaCha20-Poly1305.
        """
        key = key or secrets.token_bytes(32)
        
        # Serialize and encode
        plaintext = json.dumps(data)
        
        # Simplified XOR encryption (NOT SECURE for production)
        ciphertext = []
        key_bytes = key[:len(plaintext)] if len(key) >= len(plaintext) else (key * (len(plaintext) // len(key) + 1))[:len(plaintext)]
        for i, char in enumerate(plaintext):
            ciphertext.append(chr(ord(char) ^ key_bytes[i]))
        ciphertext = "".join(ciphertext)
        
        return {
            "ciphertext": ciphertext.encode().hex(),
            "key_hash": self.sha256(key),
            "algorithm": "xor-aes256-simplified",
        }
    
    def decrypt_payload(
        self,
        payload: Dict,
        key: Optional[bytes] = None,
    ) -> Optional[Dict]:
        """
        Decrypt a payload.
        """
        try:
            ciphertext = bytes.fromhex(payload["ciphertext"]).decode()
            
            key_bytes = key or secrets.token_bytes(32)
            
            # Decrypt
            plaintext = []
            key_bytes = key_bytes[:len(ciphertext)] if len(key_bytes) >= len(ciphertext) else (key_bytes * (len(ciphertext) // len(key_bytes) + 1))[:len(ciphertext)]
            for i, char in enumerate(ciphertext):
                plaintext.append(chr(ord(char) ^ key_bytes[i]))
            
            return json.loads("".join(plaintext))
        except:
            return None
    
    # ============ Utility ============
    
    def generate_attestation_id(
        self,
        tool_id: str,
        input_hash: str,
        output_hash: str,
        timestamp: int,
    ) -> str:
        """Generate a unique attestation ID."""
        data = f"{tool_id}:{input_hash}:{output_hash}:{timestamp}"
        return self.sha256(data)[:32]
    
    def generate_challenge(self, length: int = 32) -> str:
        """Generate a random challenge for authentication."""
        return secrets.token_urlsafe(length)
    
    def verify_challenge_response(
        self,
        challenge: str,
        response: str,
        expected_response: str,
    ) -> bool:
        """Verify a challenge-response pair."""
        # In production, verify the response against the challenge
        return hmac.compare_digest(response, expected_response)
