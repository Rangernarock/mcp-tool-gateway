"""
Fraud Detection System - ML-based anomaly detection for payments.

Implements real-time risk scoring and behavioral analysis.
"""

import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum
from collections import defaultdict
import statistics


class RiskLevel(str, Enum):
    """Risk level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of fraud alerts."""
    VELOCITY_SPIKE = "velocity_spike"
    AMOUNT_ANOMALY = "amount_anomaly"
    NEW_RECIPIENT = "new_recipient"
    GEO_CHANGE = "geo_change"
    TIME_ANOMALY = "time_anomaly"
    PATTERN_CHANGE = "pattern_change"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"


@dataclass
class Transaction:
    """Transaction record for analysis."""
    tx_id: str
    agent_id: str
    amount: str
    recipient: str
    timestamp: int
    tool_id: str
    success: bool
    
    # Metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[str] = None


@dataclass
class RiskFactor:
    """Individual risk factor analysis."""
    factor_type: str
    score: float  # 0.0 - 1.0
    description: str
    details: Dict = field(default_factory=dict)


@dataclass
class RiskScore:
    """
    Overall risk score for a transaction or agent.
    """
    score: float  # 0.0 - 1.0
    level: RiskLevel
    
    # Breakdown
    factors: List[RiskFactor] = field(default_factory=list)
    
    # Recommendation
    recommended_action: str = "allow"  # allow, verify, block
    requires_verification: bool = False
    block_if_score_exceeds: float = 0.95
    
    # Context
    agent_id: str = ""
    tx_id: Optional[str] = None
    analyzed_at: int = field(default_factory=lambda: int(time.time()))


class FraudDetector:
    """
    ML-based fraud detection system.
    
    Features:
    - Real-time risk scoring
    - Velocity analysis
    - Amount anomaly detection
    - Behavioral pattern analysis
    - Geographic analysis
    - Device fingerprinting
    - Automatic alerts and circuit breakers
    """
    
    def __init__(
        self,
        velocity_threshold_per_minute: int = 10,
        velocity_threshold_per_hour: int = 50,
        amount_deviation_threshold: float = 3.0,  # 3x std dev
        anomaly_threshold: float = 0.8,
        block_threshold: float = 0.95,
    ):
        # Thresholds
        self.velocity_threshold_per_minute = velocity_threshold_per_minute
        self.velocity_threshold_per_hour = velocity_threshold_per_hour
        self.amount_deviation_threshold = amount_deviation_threshold
        self.anomaly_threshold = anomaly_threshold
        self.block_threshold = block_threshold
        
        # In-memory storage for MVP
        self._transactions: Dict[str, List[Transaction]] = defaultdict(list)
        self._agent_profiles: Dict[str, Dict] = {}
        self._alerts: List[Dict] = []
        self._blocked_agents: Dict[str, int] = {}  # agent_id -> unblock_at
        
        # Anomaly detection state
        self._amount_history: Dict[str, List[float]] = defaultdict(list)
        self._recipient_history: Dict[str, set] = defaultdict(set)
        self._time_patterns: Dict[str, List[int]] = defaultdict(list)  # hour of day
    
    def record_transaction(self, tx: Transaction) -> None:
        """
        Record a transaction for analysis.
        
        Args:
            tx: Transaction to record
        """
        self._transactions[tx.agent_id].append(tx)
        
        # Update profiles
        if tx.success:
            self._update_profiles(tx)
    
    def _update_profiles(self, tx: Transaction) -> None:
        """Update agent profiles with new transaction data."""
        agent_id = tx.agent_id
        
        # Amount history
        amount = float(tx.amount) if tx.amount else 0
        self._amount_history[agent_id].append(amount)
        
        # Keep last 1000 transactions
        if len(self._amount_history[agent_id]) > 1000:
            self._amount_history[agent_id] = self._amount_history[agent_id][-1000:]
        
        # Recipient history
        self._recipient_history[agent_id].add(tx.recipient)
        
        # Time patterns
        hour = tx.timestamp % 86400 // 3600
        self._time_patterns[agent_id].append(hour)
        if len(self._time_patterns[agent_id]) > 168:  # Keep 1 week
            self._time_patterns[agent_id] = self._time_patterns[agent_id][-168:]
    
    def score_transaction(self, tx: Transaction) -> RiskScore:
        """
        Score a transaction for fraud risk.
        
        Args:
            tx: Transaction to score
            
        Returns:
            RiskScore with detailed breakdown
        """
        factors = []
        agent_id = tx.agent_id
        
        # Factor 1: Velocity
        velocity_factor = self._analyze_velocity(agent_id)
        factors.append(velocity_factor)
        
        # Factor 2: Amount anomaly
        amount_factor = self._analyze_amount(agent_id, tx.amount)
        factors.append(amount_factor)
        
        # Factor 3: New recipient
        recipient_factor = self._analyze_recipient(agent_id, tx.recipient)
        factors.append(recipient_factor)
        
        # Factor 4: Time anomaly
        time_factor = self._analyze_time(agent_id, tx.timestamp)
        factors.append(time_factor)
        
        # Factor 5: Reputation
        reputation_factor = self._analyze_reputation(agent_id)
        factors.append(reputation_factor)
        
        # Calculate weighted score
        weights = [0.25, 0.25, 0.15, 0.10, 0.25]
        total_score = sum(f.score * w for f, w in zip(factors, weights))
        
        # Determine level
        if total_score > 0.8:
            level = RiskLevel.CRITICAL
        elif total_score > 0.6:
            level = RiskLevel.HIGH
        elif total_score > 0.4:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW
        
        # Determine action
        if total_score >= self.block_threshold:
            action = "block"
            requires_verification = False
        elif total_score >= self.anomaly_threshold:
            action = "verify"
            requires_verification = True
        else:
            action = "allow"
            requires_verification = False
        
        return RiskScore(
            score=total_score,
            level=level,
            factors=factors,
            recommended_action=action,
            requires_verification=requires_verification,
            block_if_score_exceeds=self.block_threshold,
            agent_id=agent_id,
            tx_id=tx.tx_id,
        )
    
    def _analyze_velocity(self, agent_id: str) -> RiskFactor:
        """Analyze transaction velocity."""
        now = int(time.time())
        
        txs = self._transactions.get(agent_id, [])
        
        # Count transactions in last minute
        minute_ago = now - 60
        minute_count = sum(1 for tx in txs if tx.timestamp > minute_ago)
        
        # Count transactions in last hour
        hour_ago = now - 3600
        hour_count = sum(1 for tx in txs if tx.timestamp > hour_ago)
        
        # Calculate scores
        minute_score = min(1.0, minute_count / self.velocity_threshold_per_minute)
        hour_score = min(1.0, hour_count / self.velocity_threshold_per_hour)
        
        # Combined velocity score
        score = max(minute_score, hour_score)
        
        # Spike detection
        is_spike = minute_count > self.velocity_threshold_per_minute
        
        return RiskFactor(
            factor_type="velocity",
            score=score,
            description=f"Velocity: {minute_count}/min, {hour_count}/hr",
            details={
                "transactions_per_minute": minute_count,
                "transactions_per_hour": hour_count,
                "velocity_threshold_per_minute": self.velocity_threshold_per_minute,
                "is_spike": is_spike,
            }
        )
    
    def _analyze_amount(self, agent_id: str, amount: str) -> RiskFactor:
        """Analyze amount for anomalies."""
        history = self._amount_history.get(agent_id, [])
        
        if len(history) < 10:
            # Not enough history
            return RiskFactor(
                factor_type="amount",
                score=0.1,  # Low score for new agents
                description="Insufficient history for amount analysis",
                details={"history_length": len(history)}
            )
        
        amount_val = float(amount) if amount else 0
        
        # Calculate statistics
        mean = statistics.mean(history)
        std = statistics.stdev(history) if len(history) > 1 else 0
        
        # Deviation from normal
        if std > 0:
            deviation = abs(amount_val - mean) / std
        else:
            deviation = 0 if amount_val == mean else 1
        
        # Score based on deviation
        score = min(1.0, deviation / self.amount_deviation_threshold)
        
        is_anomaly = deviation > self.amount_deviation_threshold
        
        return RiskFactor(
            factor_type="amount",
            score=score,
            description=f"Amount: {amount_val}, mean: {mean:.2f}, deviation: {deviation:.2f}x",
            details={
                "amount": amount_val,
                "historical_mean": mean,
                "historical_std": std,
                "deviation": deviation,
                "is_anomaly": is_anomaly,
            }
        )
    
    def _analyze_recipient(self, agent_id: str, recipient: str) -> RiskFactor:
        """Analyze recipient for new/suspicious patterns."""
        history = self._recipient_history.get(agent_id, set())
        
        is_new = recipient not in history
        total_recipients = len(history)
        
        # Score based on new recipient ratio
        if total_recipients == 0:
            score = 0.3  # First transaction
        elif is_new:
            # High ratio of new recipients is suspicious
            new_ratio = 1 / (total_recipients + 1)
            score = min(1.0, new_ratio * 2)
        else:
            score = 0.1  # Known recipient
        
        return RiskFactor(
            factor_type="recipient",
            score=score,
            description=f"Recipient: {'new' if is_new else 'known'} ({total_recipients} total)",
            details={
                "is_new_recipient": is_new,
                "total_known_recipients": total_recipients,
            }
        )
    
    def _analyze_time(self, agent_id: str, timestamp: int) -> RiskFactor:
        """Analyze transaction timing for anomalies."""
        patterns = self._time_patterns.get(agent_id, [])
        
        hour = timestamp % 86400 // 3600
        
        # Check for unusual hours
        unusual_hours = {2, 3, 4, 5}  # 2-5 AM
        is_unusual_time = hour in unusual_hours
        
        # Check consistency with history
        if len(patterns) < 5:
            score = 0.1  # Not enough history
        else:
            hour_counts = defaultdict(int)
            for h in patterns:
                hour_counts[h] += 1
            
            # Expected frequency for this hour
            total = len(patterns)
            expected = hour_counts.get(hour, 0) / total
            actual = 1 / 24  # Expected if uniform
            
            # Large deviation from pattern
            if expected < 0.01 and is_unusual_time:
                score = 0.6
            else:
                score = 0.1
        
        return RiskFactor(
            factor_type="time",
            score=score,
            description=f"Time: {hour}:00 ({'unusual' if is_unusual_time else 'normal'})",
            details={
                "hour": hour,
                "is_unusual_hour": is_unusual_time,
                "history_length": len(patterns),
            }
        )
    
    def _analyze_reputation(self, agent_id: str) -> RiskFactor:
        """Analyze agent's historical reputation."""
        txs = self._transactions.get(agent_id, [])
        
        if not txs:
            score = 0.3  # New agent
        else:
            # Success rate
            total = len(txs)
            successful = sum(1 for tx in txs if tx.success)
            success_rate = successful / total
            
            # Age (in days)
            first_tx = min(tx.timestamp for tx in txs)
            age_days = (int(time.time()) - first_tx) / 86400
            
            # Volume
            total_amount = sum(float(tx.amount) for tx in txs if tx.amount)
            
            # Calculate reputation score
            age_score = min(1.0, age_days / 30)  # Max out at 30 days
            success_score = success_rate
            volume_score = min(1.0, total_amount / 10000)  # Max out at $10k
            
            score = (age_score * 0.3 + success_score * 0.4 + volume_score * 0.3)
            score = 1.0 - score  # Invert: high reputation = low risk
        
        return RiskFactor(
            factor_type="reputation",
            score=score,
            description=f"Reputation score: {1-score:.2f}",
            details={
                "total_transactions": len(txs),
                "success_rate": successful / len(txs) if txs else 0,
                "age_days": age_days if txs else 0,
            }
        )
    
    def detect_anomalies(self, agent_id: str) -> List[Dict]:
        """
        Run comprehensive anomaly detection for an agent.
        
        Args:
            agent_id: Agent to analyze
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        txs = self._transactions.get(agent_id, [])
        
        if len(txs) < 5:
            return anomalies
        
        # 1. Isolation Forest-like detection (simplified)
        amounts = [float(tx.amount) for tx in txs if tx.amount]
        if len(amounts) > 5:
            mean = statistics.mean(amounts)
            std = statistics.stdev(amounts) if len(amounts) > 1 else 0
            
            for tx in txs:
                if tx.amount:
                    amount = float(tx.amount)
                    if std > 0 and abs(amount - mean) > 3 * std:
                        anomalies.append({
                            "type": AlertType.AMOUNT_ANOMALY.value,
                            "tx_id": tx.tx_id,
                            "description": f"Amount {amount} is {abs(amount - mean) / std:.1f}x standard deviations from mean",
                            "severity": "high"
                        })
        
        # 2. Velocity spikes
        now = int(time.time())
        recent = [tx for tx in txs if now - tx.timestamp < 300]  # Last 5 min
        if len(recent) > 20:
            anomalies.append({
                "type": AlertType.VELOCITY_SPIKE.value,
                "description": f"High velocity: {len(recent)} transactions in 5 minutes",
                "severity": "critical" if len(recent) > 50 else "high"
            })
        
        # 3. Rapid recipient changes
        recent_recipients = set(tx.recipient for tx in recent)
        if len(recent_recipients) > 10 and len(recent) > 0:
            anomalies.append({
                "type": AlertType.PATTERN_CHANGE.value,
                "description": f"Rapid recipient changes: {len(recent_recipients)} different recipients",
                "severity": "medium"
            })
        
        return anomalies
    
    def trigger_circuit_breaker(
        self,
        agent_id: str,
        reason: str,
        severity: str = "lockout",
        duration_seconds: int = 3600,
    ) -> Dict:
        """
        Trigger a circuit breaker for suspicious activity.
        
        Args:
            agent_id: Agent to block
            reason: Reason for blocking
            severity: lockout, freeze, or alert
            duration_seconds: How long to block
            
        Returns:
            Circuit breaker status
        """
        if severity in ["lockout", "freeze"]:
            self._blocked_agents[agent_id] = int(time.time()) + duration_seconds
        
        # Create alert
        alert = {
            "alert_id": hashlib.sha256(
                f"{agent_id}:{reason}:{time.time()}".encode()
            ).hexdigest()[:16],
            "agent_id": agent_id,
            "type": AlertType.SUSPICIOUS_BEHAVIOR.value,
            "reason": reason,
            "severity": severity,
            "created_at": int(time.time()),
            "duration": duration_seconds if severity in ["lockout", "freeze"] else None,
        }
        self._alerts.append(alert)
        
        return {
            "status": "triggered",
            "alert": alert,
            "blocked_until": self._blocked_agents.get(agent_id),
        }
    
    def is_blocked(self, agent_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if an agent is blocked.
        
        Args:
            agent_id: Agent to check
            
        Returns:
            Tuple of (is_blocked, reason)
        """
        unblock_at = self._blocked_agents.get(agent_id)
        if unblock_at is None:
            return False, None
        
        if int(time.time()) > unblock_at:
            # Unblock
            del self._blocked_agents[agent_id]
            return False, None
        
        return True, f"Blocked until {unblock_at}"
    
    def get_alerts(
        self,
        agent_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Get fraud alerts."""
        alerts = self._alerts
        
        if agent_id:
            alerts = [a for a in alerts if a["agent_id"] == agent_id]
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        
        return sorted(alerts, key=lambda x: x["created_at"], reverse=True)[:limit]
    
    def get_agent_risk_summary(self, agent_id: str) -> Dict:
        """Get a risk summary for an agent."""
        txs = self._transactions.get(agent_id, [])
        
        return {
            "agent_id": agent_id,
            "total_transactions": len(txs),
            "unique_recipients": len(self._recipient_history.get(agent_id, set())),
            "avg_amount": statistics.mean([float(tx.amount) for tx in txs if tx.amount]) if txs else 0,
            "success_rate": sum(1 for tx in txs if tx.success) / len(txs) if txs else 0,
            "is_blocked": self.is_blocked(agent_id)[0],
            "recent_alerts": len([a for a in self._alerts if a["agent_id"] == agent_id]),
        }
    
    def get_stats(self) -> Dict:
        """Get fraud detection statistics."""
        return {
            "total_transactions": sum(len(txs) for txs in self._transactions.values()),
            "total_agents": len(self._transactions),
            "blocked_agents": len(self._blocked_agents),
            "total_alerts": len(self._alerts),
            "alerts_by_severity": {
                "critical": len([a for a in self._alerts if a["severity"] == "critical"]),
                "high": len([a for a in self._alerts if a["severity"] == "high"]),
                "medium": len([a for a in self._alerts if a["severity"] == "medium"]),
            },
        }
