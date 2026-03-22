"""
Sandboxed Execution - Secure tool execution environment.

Implements multi-level sandboxing for tool execution safety.
"""

import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum


class SandboxLevel(int, Enum):
    """Sandbox security levels."""
    NONE = 0          # No sandboxing (not recommended)
    WASM = 1          # WebAssembly runtime
    ISOLATED_VM = 2   # Isolated virtual machine (V8/Node.js)
    DOCKER = 3        # Docker container
    AIRGAPPED = 4     # Air-gapped execution


@dataclass
class SandboxConfig:
    """Sandbox configuration."""
    level: SandboxLevel = SandboxLevel.ISOLATED_VM
    
    # Resource limits
    max_execution_time_ms: int = 30000
    max_memory_mb: int = 512
    max_tokens: int = 8000
    max_network_calls: int = 10
    
    # Network access
    network_access: str = "none"  # none, whitelist, all
    allowed_domains: List[str] = field(default_factory=list)
    
    # File system access
    filesystem_access: str = "none"  # none, temp, full
    
    # Environment
    env_vars: Dict[str, str] = field(default_factory=dict)
    
    # Tool-specific overrides
    overrides: Dict[str, "SandboxConfig"] = field(default_factory=dict)


@dataclass
class SandboxResult:
    """Result of sandboxed execution."""
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    
    # Execution metrics
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    tokens_used: int = 0
    
    # Safety
    sandbox_level: SandboxLevel = SandboxLevel.NONE
    was_killed: bool = False
    kill_reason: Optional[str] = None
    
    # Attribution
    sandbox_id: Optional[str] = None


class Sandbox:
    """
    Sandboxed execution environment.
    
    Provides secure execution of untrusted tool code.
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._active_sandboxes: Dict[str, Any] = {}
    
    async def execute(
        self,
        code: str,
        language: str = "javascript",
        input_data: Optional[Dict] = None,
        tool_id: Optional[str] = None,
        config_override: Optional[SandboxConfig] = None,
    ) -> SandboxResult:
        """
        Execute code in a sandbox.
        
        Args:
            code: Code to execute
            language: Programming language
            input_data: Input data for the code
            tool_id: Optional tool ID for config lookup
            config_override: Optional config override
            
        Returns:
            SandboxResult
        """
        start_time = time.time()
        
        # Get effective config
        config = self._get_effective_config(tool_id, config_override)
        
        try:
            # Select execution method based on level
            if config.level == SandboxLevel.NONE:
                result = await self._execute_direct(code, language, input_data)
            elif config.level == SandboxLevel.WASM:
                result = await self._execute_wasm(code, language, input_data, config)
            elif config.level == SandboxLevel.ISOLATED_VM:
                result = await self._execute_vm(code, language, input_data, config)
            elif config.level == SandboxLevel.DOCKER:
                result = await self._execute_docker(code, language, input_data, config)
            else:
                result = await self._execute_airgapped(code, language, input_data, config)
            
            # Add execution metrics
            result.execution_time_ms = (time.time() - start_time) * 1000
            result.sandbox_level = config.level
            
            return result
            
        except Exception as e:
            return SandboxResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
                sandbox_level=config.level,
            )
    
    async def execute_handler(
        self,
        handler: Callable,
        input_data: Dict,
        tool_id: Optional[str] = None,
        config_override: Optional[SandboxConfig] = None,
    ) -> SandboxResult:
        """
        Execute a Python handler function in a sandbox.
        
        Args:
            handler: Async callable handler
            input_data: Input data
            tool_id: Optional tool ID
            config_override: Optional config override
            
        Returns:
            SandboxResult
        """
        start_time = time.time()
        
        config = self._get_effective_config(tool_id, config_override)
        
        try:
            # Execute handler with timeout
            result = await asyncio.wait_for(
                handler(input_data),
                timeout=config.max_execution_time_ms / 1000
            )
            
            return SandboxResult(
                success=True,
                output=result,
                execution_time_ms=(time.time() - start_time) * 1000,
                sandbox_level=config.level,
            )
            
        except asyncio.TimeoutError:
            return SandboxResult(
                success=False,
                error="Execution timeout",
                execution_time_ms=(time.time() - start_time) * 1000,
                sandbox_level=config.level,
                was_killed=True,
                kill_reason="timeout",
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
                sandbox_level=config.level,
            )
    
    async def _execute_direct(
        self,
        code: str,
        language: str,
        input_data: Optional[Dict],
    ) -> SandboxResult:
        """Execute code directly (no sandbox - use with caution)."""
        # WARNING: This is potentially unsafe!
        # Only use for trusted code
        
        try:
            # For MVP, we simulate execution
            output = {"status": "simulated", "code_length": len(code)}
            return SandboxResult(success=True, output=output)
        except Exception as e:
            return SandboxResult(success=False, error=str(e))
    
    async def _execute_wasm(
        self,
        code: str,
        language: str,
        input_data: Optional[Dict],
        config: SandboxConfig,
    ) -> SandboxResult:
        """
        Execute code in WebAssembly sandbox.
        
        In production, use a proper WASM runtime like Wasmtime or Wasmer.
        """
        try:
            # Simulated WASM execution
            # In production:
            # import wasmtime
            # engine = wasmtime.Engine()
            # module = wasmtime.Module(engine, compiled_wasm)
            # linker = wasmtime.Linker(engine)
            # instance = linker.instantiate(module)
            
            output = {
                "status": "wasm_simulated",
                "language": language,
                "input": input_data,
            }
            return SandboxResult(success=True, output=output)
        except Exception as e:
            return SandboxResult(success=False, error=str(e))
    
    async def _execute_vm(
        self,
        code: str,
        language: str,
        input_data: Optional[Dict],
        config: SandboxConfig,
    ) -> SandboxResult:
        """
        Execute code in isolated VM.
        
        In production, use Node.js VM or V8 isolates.
        """
        try:
            # Simulated VM execution
            # In production:
            # vm = require('vm');
            # context = vm.createContext({ input: input_data });
            # vm.runInContext(code, context, { timeout: config.max_execution_time_ms });
            
            output = {
                "status": "vm_simulated",
                "language": language,
                "input": input_data,
                "memory_limit_mb": config.max_memory_mb,
            }
            return SandboxResult(success=True, output=output)
        except Exception as e:
            return SandboxResult(success=False, error=str(e))
    
    async def _execute_docker(
        self,
        code: str,
        language: str,
        input_data: Optional[Dict],
        config: SandboxConfig,
    ) -> SandboxResult:
        """
        Execute code in Docker container.
        
        In production, use Docker SDK for Python.
        """
        try:
            # Simulated Docker execution
            # In production:
            # client = docker.from_env()
            # container = client.containers.run(
            #     image=f"{language}:latest",
            #     command=f"python -c '{code}'",
            #     mem_limit=f"{config.max_memory_mb}m",
            #     cpu_period=100000,
            #     cpu_quota=50000,
            #     network_mode="none" if config.network_access == "none" else "bridge",
            #     remove=True,
            # )
            
            output = {
                "status": "docker_simulated",
                "language": language,
                "network_mode": config.network_access,
            }
            return SandboxResult(success=True, output=output)
        except Exception as e:
            return SandboxResult(success=False, error=str(e))
    
    async def _execute_airgapped(
        self,
        code: str,
        language: str,
        input_data: Optional[Dict],
        config: SandboxConfig,
    ) -> SandboxResult:
        """
        Execute code in air-gapped environment.
        
        For maximum security requirements.
        """
        try:
            # Simulated air-gapped execution
            # No network, minimal resources, maximum isolation
            
            output = {
                "status": "airgapped_simulated",
                "language": language,
                "security_level": "maximum",
            }
            return SandboxResult(success=True, output=output)
        except Exception as e:
            return SandboxResult(success=False, error=str(e))
    
    def _get_effective_config(
        self,
        tool_id: Optional[str],
        override: Optional[SandboxConfig],
    ) -> SandboxConfig:
        """Get effective sandbox config for a tool."""
        if override:
            return override
        
        if tool_id and tool_id in self.config.overrides:
            return self.config.overrides[tool_id]
        
        return self.config
    
    def set_tool_config(self, tool_id: str, config: SandboxConfig) -> None:
        """Set sandbox config for a specific tool."""
        self.config.overrides[tool_id] = config
    
    def get_tool_config(self, tool_id: str) -> Optional[SandboxConfig]:
        """Get sandbox config for a specific tool."""
        return self.config.overrides.get(tool_id)
