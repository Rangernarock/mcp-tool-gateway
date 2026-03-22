"""
Tool Executor - Orchestrates tool execution with payment and attestation.

Coordinates payment, escrow, sandbox, and result delivery.
"""

import time
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable, TYPE_CHECKING, Union
from enum import Enum

if TYPE_CHECKING:
    from .sandbox import Sandbox, SandboxConfig, SandboxResult, SandboxLevel
else:
    # Aliases for runtime (will be properly imported)
    Sandbox = None
    SandboxConfig = None
    SandboxResult = None
    SandboxLevel = None


class ExecutionStatus(str, Enum):
    """Execution status."""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionRequest:
    """Request for tool execution."""
    request_id: str
    tool_id: str
    tool_name: str
    
    # Agent info
    agent_id: str
    agent_did: Optional[str] = None
    
    # Input
    arguments: Dict = field(default_factory=dict)
    input_hash: Optional[str] = None
    
    # Payment
    payment_auth_id: Optional[str] = None
    escrow_id: Optional[str] = None
    
    # Configuration
    sandbox_level: SandboxLevel = SandboxLevel.ISOLATED_VM
    timeout_ms: int = 30000


@dataclass
class ExecutionResult:
    """Result of tool execution."""
    request_id: str
    tool_id: str
    tool_name: str
    
    # Status
    status: ExecutionStatus
    success: bool
    
    # Output
    output: Optional[Any] = None
    error: Optional[str] = None
    
    # Execution metrics
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    memory_used_mb: float = 0.0
    
    # Payment
    cost: Optional[str] = None
    
    # Security
    sandbox_result: Optional[Any] = None
    
    # Attestation
    attestation_id: Optional[str] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    
    # Timestamps
    created_at: int = field(default_factory=lambda: int(time.time()))
    started_at: Optional[int] = None
    completed_at: Optional[int] = None


class Executor:
    """
    Tool Executor.
    
    Orchestrates the full execution lifecycle:
    1. Validate request and authorization
    2. Execute tool in sandbox
    3. Generate attestation
    4. Handle payment/release escrow
    5. Return results
    """
    
    def __init__(
        self,
        sandbox: Optional[Sandbox] = None,
        handlers: Optional[Dict[str, Callable]] = None,
    ):
        self.sandbox = sandbox or Sandbox()
        self.handlers = handlers or {}
        
        # Execution tracking
        self._executions: Dict[str, ExecutionRequest] = {}
        self._results: Dict[str, ExecutionResult] = {}
        
        # Statistics
        self._stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time_ms": 0,
        }
    
    def register_handler(self, tool_name: str, handler: Callable) -> None:
        """Register a tool handler."""
        self.handlers[tool_name] = handler
    
    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute a tool request.
        
        Args:
            request: ExecutionRequest with all details
            
        Returns:
            ExecutionResult with output or error
        """
        self._stats["total_executions"] += 1
        
        # Track execution
        self._executions[request.request_id] = request
        
        # Create result placeholder
        result = ExecutionResult(
            request_id=request.request_id,
            tool_id=request.tool_id,
            tool_name=request.tool_name,
            status=ExecutionStatus.PENDING,
            success=False,
        )
        
        try:
            # Stage 1: Validate authorization
            result.status = ExecutionStatus.AUTHORIZED
            
            # Generate input hash for verification
            input_json = json.dumps(request.arguments, sort_keys=True)
            result.input_hash = hashlib.sha256(input_json.encode()).hexdigest()
            
            # Stage 2: Execute
            result.status = ExecutionStatus.EXECUTING
            result.started_at = int(time.time())
            
            # Execute in sandbox
            sandbox_result = await self._execute_tool(request, result)
            
            result.sandbox_result = sandbox_result
            result.execution_time_ms = sandbox_result.execution_time_ms
            result.memory_used_mb = sandbox_result.memory_used_mb
            
            if sandbox_result.success:
                result.output = sandbox_result.output
                result.success = True
                result.status = ExecutionStatus.COMPLETED
                self._stats["successful_executions"] += 1
            else:
                result.error = sandbox_result.error
                result.success = False
                result.status = ExecutionStatus.FAILED
                self._stats["failed_executions"] += 1
            
            # Stage 3: Generate attestation
            result.completed_at = int(time.time())
            result.attestation_id = self._generate_attestation(request, result)
            
            # Calculate output hash
            if result.output is not None:
                output_json = json.dumps(result.output, sort_keys=True)
                result.output_hash = hashlib.sha256(output_json.encode()).hexdigest()
            
            # Calculate cost
            if result.output is not None:
                result.cost = self._calculate_cost(request, result)
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            result.completed_at = int(time.time())
            self._stats["failed_executions"] += 1
        
        # Store result
        self._results[request.request_id] = result
        self._stats["total_execution_time_ms"] += result.execution_time_ms
        
        return result
    
    async def _execute_tool(
        self,
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> SandboxResult:
        """Execute the actual tool."""
        # Get handler
        handler = self.handlers.get(request.tool_name)
        
        if handler is None:
            return SandboxResult(
                success=False,
                error=f"No handler registered for tool: {request.tool_name}",
            )
        
        # Configure sandbox
        sandbox_config = SandboxConfig(
            level=request.sandbox_level,
            max_execution_time_ms=request.timeout_ms,
        )
        
        # Execute
        if hasattr(handler, "__call__"):
            return await self.sandbox.execute_handler(
                handler=handler,
                input_data=request.arguments,
                tool_id=request.tool_id,
                config_override=sandbox_config,
            )
        else:
            return SandboxResult(
                success=False,
                error="Handler is not callable",
            )
    
    def _generate_attestation(
        self,
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> str:
        """Generate execution attestation ID."""
        data = f"{request.request_id}:{request.tool_id}:{result.output_hash or ''}:{result.completed_at}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    def _calculate_cost(
        self,
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> Optional[str]:
        """Calculate execution cost."""
        # In production, calculate based on tool pricing
        # For MVP, return fixed cost
        return "1000000"  # 0.001 USDC in micro units
    
    def get_execution(self, request_id: str) -> Optional[ExecutionResult]:
        """Get an execution result by request ID."""
        return self._results.get(request_id)
    
    def get_stats(self) -> Dict:
        """Get executor statistics."""
        avg_time = (
            self._stats["total_execution_time_ms"] / self._stats["total_executions"]
            if self._stats["total_executions"] > 0 else 0
        )
        
        return {
            **self._stats,
            "avg_execution_time_ms": avg_time,
            "success_rate": (
                self._stats["successful_executions"] / self._stats["total_executions"]
                if self._stats["total_executions"] > 0 else 0
            ),
        }
