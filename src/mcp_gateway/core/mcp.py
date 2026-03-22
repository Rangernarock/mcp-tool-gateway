"""
MCP Protocol Adapter - MCP (Model Context Protocol) implementation.

Implements the MCP specification for tool discovery and execution.
"""

import hashlib
import json
import time
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Awaitable, Union
from enum import Enum
from pydantic import BaseModel, Field


class MCPErrorCode(int, Enum):
    """MCP JSON-RPC error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # Gateway-specific errors
    PAYMENT_REQUIRED = -32002
    TOOL_NOT_FOUND = -32001
    TOOL_UNAVAILABLE = -32003
    RATE_LIMITED = -32004
    UNAUTHORIZED = -32005
    EXECUTION_FAILED = -32006
    ESCROW_REQUIRED = -32007


@dataclass
class MCPRequest:
    """
    MCP JSON-RPC 2.0 Request.
    
    Implements: https://www.jsonrpc.org/specification
    """
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str = ""
    params: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MCPRequest":
        """Parse from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method", ""),
            params=data.get("params"),
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
        }
        if self.id is not None:
            result["id"] = self.id
        if self.params is not None:
            result["params"] = self.params
        return result


@dataclass
class MCPResponse:
    """
    MCP JSON-RPC 2.0 Response.
    
    Success or error response format.
    """
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    
    # Success
    result: Optional[Dict] = None
    
    # Error
    error: Optional[Dict] = None
    
    @classmethod
    def success(cls, id: Optional[str | int], result: Dict) -> "MCPResponse":
        """Create a success response."""
        return cls(jsonrpc="2.0", id=id, result=result)
    
    @classmethod
    def error(
        cls,
        id: Optional[str | int],
        code: MCPErrorCode,
        message: str,
        data: Optional[Any] = None,
    ) -> "MCPResponse":
        """Create an error response."""
        error_dict = {
            "code": code.value,
            "message": message,
        }
        if data is not None:
            error_dict["data"] = data
        return cls(jsonrpc="2.0", id=id, error=error_dict)
    
    def is_error(self) -> bool:
        """Check if this is an error response."""
        return self.error is not None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            result["id"] = self.id
        if self.result is not None:
            result["result"] = self.result
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass
class ToolCall:
    """A tool call request."""
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    
    # Payment info
    payment: Optional[Dict] = None
    auth_id: Optional[str] = None


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    
    # Execution metadata
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    
    # Attestation
    attestation_id: Optional[str] = None
    output_hash: Optional[str] = None
    
    def to_mcp_result(self) -> Dict:
        """Convert to MCP result format."""
        if self.success:
            return {
                "success": True,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(self.output) if isinstance(self.output, (dict, list)) else str(self.output),
                    }
                ],
                "metadata": {
                    "execution_time_ms": self.execution_time_ms,
                    "tokens_used": self.tokens_used,
                },
            }
        else:
            return {
                "success": False,
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": self.error or "Unknown error",
                    }
                ],
                "metadata": {
                    "execution_time_ms": self.execution_time_ms,
                },
            }


@dataclass
class MCPToolInfo:
    """Information about a tool (for discovery)."""
    name: str
    description: str
    input_schema: Dict
    output_schema: Optional[Dict] = None
    
    # Pricing
    price: Optional[str] = None
    pricing_type: Optional[str] = None
    free_calls: Optional[int] = None
    
    # Capabilities
    capabilities: List[str] = field(default_factory=list)
    category: Optional[str] = None


class MCPAdapter:
    """
    MCP Protocol Adapter.
    
    Implements the MCP specification for:
    - Tool discovery (tools/list)
    - Tool execution (tools/execute)
    - Batch execution (tools/batch)
    - Streaming (tools/stream)
    """
    
    def __init__(
        self,
        registry: Any = None,  # ToolRegistry
        payment_engine: Any = None,  # PaymentEngine
        escrow_manager: Any = None,  # EscrowManager
        executor: Any = None,  # ExecutionEngine
    ):
        self.registry = registry
        self.payment_engine = payment_engine
        self.escrow_manager = escrow_manager
        self.executor = executor
        
        # Tool handlers
        self._handlers: Dict[str, Callable] = {}
        
        # Registered tools metadata
        self._tools: Dict[str, MCPToolInfo] = {}
        
        # Statistics
        self._stats = {
            "total_requests": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_execution_time_ms": 0,
        }
    
    def register_handler(self, tool_name: str, handler: Callable) -> None:
        """
        Register a tool handler.
        
        Args:
            tool_name: Name of the tool
            handler: Async callable that takes (arguments: Dict) and returns Any
        """
        self._handlers[tool_name] = handler
    
    def register_tool_info(self, info: MCPToolInfo) -> None:
        """Register tool metadata for discovery."""
        self._tools[info.name] = info
    
    def get_tools_for_discovery(self) -> List[MCPToolInfo]:
        """Get all tools available for discovery."""
        return list(self._tools.values())
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """
        Handle an MCP JSON-RPC request.
        
        Args:
            request: The MCP request
            
        Returns:
            MCP response
        """
        self._stats["total_requests"] += 1
        
        try:
            # Route to appropriate handler
            if request.method == "tools/list":
                return await self._handle_tools_list(request)
            elif request.method == "tools/discover":
                return await self._handle_tools_discover(request)
            elif request.method == "tools/execute":
                return await self._handle_tools_execute(request)
            elif request.method == "tools/batch":
                return await self._handle_tools_batch(request)
            elif request.method == "ping":
                return await self._handle_ping(request)
            elif request.method.startswith("tools/"):
                # Dynamic tool call
                tool_name = request.method.replace("tools/", "")
                return await self._handle_dynamic_tool(request, tool_name)
            else:
                return MCPResponse.error(
                    request.id,
                    MCPErrorCode.METHOD_NOT_FOUND,
                    f"Unknown method: {request.method}"
                )
        
        except Exception as e:
            self._stats["failed_calls"] += 1
            return MCPResponse.error(
                request.id,
                MCPErrorCode.INTERNAL_ERROR,
                f"Internal error: {str(e)}"
            )
    
    async def _handle_tools_list(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/list - list all available tools."""
        params = request.params or {}
        category = params.get("category")
        limit = params.get("limit", 100)
        
        # Get tools from registry
        if self.registry:
            tools = self.registry.list_tools(
                status="active",
                category=category,
                limit=limit,
            )
            tool_list = [
                MCPToolInfo(
                    name=t.name,
                    description=t.description,
                    input_schema=t.schema.input_schema if t.schema else {},
                    output_schema=t.schema.output_schema if t.schema else None,
                    price=t.get_price(),
                    pricing_type=t.pricing.type.value if t.pricing else None,
                    free_calls=t.get_free_calls(),
                    capabilities=t.capabilities,
                    category=t.category,
                )
                for t in tools
            ]
        else:
            tool_list = list(self._tools.values())
        
        return MCPResponse.success(request.id, {
            "tools": [self._tool_to_dict(t) for t in tool_list],
            "count": len(tool_list),
        })
    
    async def _handle_tools_discover(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/discover - search for tools."""
        params = request.params or {}
        query = params.get("query", "")
        category = params.get("category")
        max_price = params.get("max_price")
        min_rating = params.get("min_rating")
        capabilities = params.get("capabilities")
        
        # Search registry
        if self.registry:
            tools = self.registry.search_tools(
                query=query,
                category=category,
                max_price=max_price,
                min_rating=min_rating,
                capabilities=capabilities,
            )
            tool_list = [
                MCPToolInfo(
                    name=t.name,
                    description=t.description,
                    input_schema=t.schema.input_schema if t.schema else {},
                    output_schema=t.schema.output_schema if t.schema else None,
                    price=t.get_price(),
                    pricing_type=t.pricing.type.value if t.pricing else None,
                    free_calls=t.get_free_calls(),
                    capabilities=t.capabilities,
                    category=t.category,
                )
                for t in tools
            ]
        else:
            # Simple search in registered tools
            tool_list = [t for t in self._tools.values() if query.lower() in t.description.lower()]
        
        return MCPResponse.success(request.id, {
            "tools": [self._tool_to_dict(t) for t in tool_list],
            "count": len(tool_list),
        })
    
    async def _handle_tools_execute(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/execute - execute a tool."""
        params = request.params or {}
        tool_name = params.get("tool") or params.get("name")
        arguments = params.get("arguments") or params.get("input") or {}
        
        # Payment info
        payment_info = params.get("payment")
        max_price = params.get("max_price")
        auto_pay = params.get("auto_pay", False)
        
        # Check if tool exists
        tool = self.registry.get_tool_by_name(tool_name) if self.registry else self._handlers.get(tool_name)
        if not tool and tool_name not in self._handlers:
            return MCPResponse.error(
                request.id,
                MCPErrorCode.TOOL_NOT_FOUND,
                f"Tool not found: {tool_name}"
            )
        
        # Get tool metadata
        tool_info = self._tools.get(tool_name)
        
        # Check pricing
        if tool_info and tool_info.price and self.payment_engine:
            # Check if already authorized
            auth_id = params.get("auth_id")
            if auth_id:
                auth = self.payment_engine.use_authorization(auth_id)
                if not auth:
                    return MCPResponse.error(
                        request.id,
                        MCPErrorCode.UNAUTHORIZED,
                        "Invalid or expired authorization"
                    )
            elif auto_pay and max_price:
                # Create payment challenge
                challenge = self.payment_engine.create_challenge(
                    tool_id=tool_name,
                    tool_name=tool_name,
                    amount=tool_info.price,
                    max_usage=1,
                )
                return MCPResponse.error(
                    request.id,
                    MCPErrorCode.PAYMENT_REQUIRED,
                    "Payment required",
                    data=challenge.to_response_body()["error"]["data"]
                )
            else:
                return MCPResponse.error(
                    request.id,
                    MCPErrorCode.PAYMENT_REQUIRED,
                    f"Tool requires payment: {tool_info.price}",
                    data={
                        "tool": tool_name,
                        "price": tool_info.price,
                        "pricing_type": tool_info.pricing_type,
                    }
                )
        
        # Execute tool
        result = await self._execute_tool(tool_name, arguments)
        
        if result.success:
            self._stats["successful_calls"] += 1
        else:
            self._stats["failed_calls"] += 1
        
        self._stats["total_execution_time_ms"] += result.execution_time_ms
        
        return MCPResponse.success(request.id, result.to_mcp_result())
    
    async def _handle_tools_batch(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/batch - execute multiple tools."""
        params = request.params or {}
        calls = params.get("calls", [])
        
        results = []
        for call_data in calls:
            call = ToolCall(
                tool_name=call_data.get("tool") or call_data.get("name"),
                arguments=call_data.get("arguments") or {},
                payment=call_data.get("payment"),
            )
            
            # Check tool exists
            if call.tool_name not in self._handlers:
                results.append({
                    "tool": call.tool_name,
                    "success": False,
                    "error": f"Tool not found: {call.tool_name}",
                })
                continue
            
            # Execute
            result = await self._execute_tool(call.tool_name, call.arguments)
            results.append({
                "tool": call.tool_name,
                **result.to_mcp_result(),
            })
        
        return MCPResponse.success(request.id, {
            "results": results,
            "count": len(results),
        })
    
    async def _handle_dynamic_tool(self, request: MCPRequest, tool_name: str) -> MCPResponse:
        """Handle dynamic tool calls like tools/web-search."""
        params = request.params or {}
        arguments = params
        
        if tool_name not in self._handlers:
            return MCPResponse.error(
                request.id,
                MCPErrorCode.TOOL_NOT_FOUND,
                f"Tool not found: {tool_name}"
            )
        
        result = await self._execute_tool(tool_name, arguments)
        
        return MCPResponse.success(request.id, result.to_mcp_result())
    
    async def _handle_ping(self, request: MCPRequest) -> MCPResponse:
        """Handle ping - health check."""
        return MCPResponse.success(request.id, {
            "status": "ok",
            "timestamp": int(time.time()),
            "stats": self._stats,
        })
    
    async def _execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> ToolResult:
        """
        Execute a tool with the given arguments.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            ToolResult with output or error
        """
        start_time = time.time()
        
        try:
            handler = self._handlers.get(tool_name)
            
            if handler is None:
                return ToolResult(
                    success=False,
                    error=f"No handler for tool: {tool_name}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            
            # Execute handler
            if asyncio.iscoroutinefunction(handler):
                output = await handler(arguments)
            else:
                output = handler(arguments)
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Generate output hash
            output_str = json.dumps(output, sort_keys=True)
            output_hash = hashlib.sha256(output_str.encode()).hexdigest()
            
            # Generate attestation ID
            attestation_id = hashlib.sha256(
                f"{tool_name}:{output_hash}:{execution_time_ms}:{time.time()}".encode()
            ).hexdigest()[:32]
            
            return ToolResult(
                success=True,
                output=output,
                execution_time_ms=execution_time_ms,
                attestation_id=attestation_id,
                output_hash=output_hash,
            )
        
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )
    
    def _tool_to_dict(self, tool: MCPToolInfo) -> Dict:
        """Convert MCPToolInfo to dictionary."""
        result = {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema,
        }
        if tool.output_schema:
            result["outputSchema"] = tool.output_schema
        if tool.price:
            result["price"] = tool.price
        if tool.pricing_type:
            result["pricingType"] = tool.pricing_type
        if tool.free_calls is not None:
            result["freeCalls"] = tool.free_calls
        if tool.capabilities:
            result["capabilities"] = tool.capabilities
        if tool.category:
            result["category"] = tool.category
        return result
    
    def get_stats(self) -> Dict:
        """Get adapter statistics."""
        avg_time = (
            self._stats["total_execution_time_ms"] / self._stats["total_requests"]
            if self._stats["total_requests"] > 0 else 0
        )
        
        return {
            **self._stats,
            "avg_execution_time_ms": avg_time,
            "success_rate": (
                self._stats["successful_calls"] / self._stats["total_requests"]
                if self._stats["total_requests"] > 0 else 0
            ),
        }


# Example tool handlers
async def web_search_handler(arguments: Dict) -> Dict:
    """Example web search tool handler."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)
    
    # In production, this would call actual search API
    return {
        "query": query,
        "results": [
            {"title": f"Result {i+1} for {query}", "url": f"https://example.com/{i}"}
            for i in range(min(limit, 5))
        ],
        "total": limit,
    }


async def calculator_handler(arguments: Dict) -> Dict:
    """Example calculator tool handler."""
    expression = arguments.get("expression", "0")
    
    # Safe evaluation (in production, use a proper expression evaluator)
    try:
        # Only allow basic math
        allowed = set("0123456789+-*/.() ")
        if all(c in allowed for c in expression):
            result = eval(expression)  # Warning: Not safe for production!
            return {"expression": expression, "result": result}
        else:
            return {"expression": expression, "error": "Invalid characters"}
    except Exception as e:
        return {"expression": expression, "error": str(e)}


async def weather_handler(arguments: Dict) -> Dict:
    """Example weather tool handler."""
    location = arguments.get("location", "unknown")
    
    # In production, this would call a weather API
    return {
        "location": location,
        "temperature": "22°C",
        "conditions": "Sunny",
        "humidity": "45%",
    }
