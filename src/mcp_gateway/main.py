"""
MCP Tool Gateway - Main FastAPI Application.

A decentralized, agent-native tool marketplace with x402 payment integration.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import get_settings, Settings
from .core.payment import PaymentEngine, PaymentChallenge, TokenType
from .core.escrow import EscrowManager, EscrowStatus, DisputeReason
from .core.registry import ToolRegistry, Tool, ToolStatus, PricingConfig, PricingType, create_web_search_tool
from .core.mcp import MCPAdapter, MCPRequest, MCPResponse, MCPToolInfo


# ============ Pydantic Models ============

class ToolCreateRequest(BaseModel):
    """Request to create a new tool."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=1000)
    provider_id: str
    provider_address: str
    category: str = "general"
    tags: List[str] = []
    capabilities: List[str] = []
    pricing: Optional[Dict] = None


class ToolExecuteRequest(BaseModel):
    """Request to execute a tool."""
    tool_name: str
    arguments: Dict = Field(default_factory=dict)
    payment_auth_id: Optional[str] = None
    auto_pay: bool = False
    max_price: Optional[str] = None


class PaymentChallengeRequest(BaseModel):
    """Request to create a payment challenge."""
    tool_id: str
    tool_name: str
    amount: str
    token: str = "USDC"
    recipient_address: Optional[str] = None


class EscrowCreateRequest(BaseModel):
    """Request to create an escrow."""
    payer: str
    beneficiary: str
    provider: str
    tool_id: str
    tool_name: str
    amount: str
    token: str = "USDC"
    input_data: Optional[Dict] = None
    timeout_seconds: Optional[int] = None


class EscrowFundRequest(BaseModel):
    """Request to fund an escrow."""
    tx_hash: str
    from_address: str


# ============ Application State ============

app_state = {
    "initialized": False,
    "payment_engine": None,
    "escrow_manager": None,
    "registry": None,
    "mcp_adapter": None,
}


# ============ Lifespan ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    
    # Initialize components
    payment_engine = PaymentEngine(
        gateway_address="0x0000000000000000000000000000000000000000",
    )
    
    escrow_manager = EscrowManager(
        arbiter_address="0x0000000000000000000000000000000000000001",
    )
    
    registry = ToolRegistry()
    
    mcp_adapter = MCPAdapter(
        registry=registry,
        payment_engine=payment_engine,
        escrow_manager=escrow_manager,
    )
    
    # Register example tools
    web_search = create_web_search_tool(
        provider_id="example-provider",
        provider_address="0x1234567890123456789012345678901234567890",
    )
    registry.register_tool(web_search)
    
    # Register MCP tool info
    mcp_adapter.register_tool_info(MCPToolInfo(
        name="web-search",
        description="Search the web for information",
        input_schema=web_search.schema.input_schema if web_search.schema else {},
        price=web_search.get_price(),
        pricing_type=web_search.pricing.type.value if web_search.pricing else None,
        free_calls=web_search.get_free_calls(),
        capabilities=web_search.capabilities,
        category=web_search.category,
    ))
    
    # Store in app state
    app_state["payment_engine"] = payment_engine
    app_state["escrow_manager"] = escrow_manager
    app_state["registry"] = registry
    app_state["mcp_adapter"] = mcp_adapter
    
    # Start escrow manager
    await escrow_manager.start()
    
    app_state["initialized"] = True
    
    yield
    
    # Cleanup
    await escrow_manager.stop()


# ============ FastAPI App ============

app = FastAPI(
    title="MCP Tool Gateway",
    description="A decentralized, agent-native tool marketplace with x402 payment",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Dependencies ============

def get_payment_engine() -> PaymentEngine:
    return app_state["payment_engine"]

def get_escrow_manager() -> EscrowManager:
    return app_state["escrow_manager"]

def get_registry() -> ToolRegistry:
    return app_state["registry"]

def get_mcp_adapter() -> MCPAdapter:
    return app_state["mcp_adapter"]


# ============ Health Endpoints ============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": get_settings().version,
        "initialized": app_state["initialized"],
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MCP Tool Gateway",
        "version": "0.1.0",
        "description": "A decentralized, agent-native tool marketplace",
    }


# ============ MCP JSON-RPC Endpoints ============

@app.post("/v1/execute")
async def execute_mcp(request: MCPRequest):
    """
    Main MCP JSON-RPC endpoint.
    
    Handles all MCP protocol requests:
    - tools/list
    - tools/discover
    - tools/execute
    - tools/batch
    - ping
    """
    mcp_adapter = get_mcp_adapter()
    response = await mcp_adapter.handle_request(request)
    return response.to_dict()


# ============ Tool Management Endpoints ============

@app.get("/api/v1/tools")
async def list_tools(
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List all registered tools."""
    registry = get_registry()
    status_enum = ToolStatus(status) if status else None
    
    tools = registry.list_tools(
        status=status_enum,
        category=category,
        limit=limit,
        offset=offset,
    )
    
    return {
        "tools": [t.to_dict() for t in tools],
        "count": len(tools),
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/v1/tools/{tool_id}")
async def get_tool(tool_id: str):
    """Get a tool by ID."""
    registry = get_registry()
    tool = registry.get_tool(tool_id)
    
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    return tool.to_dict()


@app.get("/api/v1/tools/by-name/{name}")
async def get_tool_by_name(name: str):
    """Get a tool by name."""
    registry = get_registry()
    tool = registry.get_tool_by_name(name)
    
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    return tool.to_dict()


@app.post("/api/v1/tools")
async def create_tool(request: ToolCreateRequest):
    """Register a new tool."""
    registry = get_registry()
    
    # Build pricing config
    pricing = None
    if request.pricing:
        pricing = PricingConfig(**request.pricing)
    
    # Create tool
    tool = Tool(
        name=request.name,
        description=request.description,
        provider_id=request.provider_id,
        provider_address=request.provider_address,
        category=request.category,
        tags=request.tags,
        capabilities=request.capabilities,
        pricing=pricing,
    )
    
    registered = registry.register_tool(tool)
    
    # Also register with MCP adapter
    mcp_adapter = get_mcp_adapter()
    mcp_adapter.register_tool_info(MCPToolInfo(
        name=registered.name,
        description=registered.description,
        input_schema=registered.schema.input_schema if registered.schema else {},
        price=registered.get_price(),
        pricing_type=registered.pricing.type.value if registered.pricing else None,
        free_calls=registered.get_free_calls(),
        capabilities=registered.capabilities,
        category=registered.category,
    ))
    
    return registered.to_dict()


@app.delete("/api/v1/tools/{tool_id}")
async def delete_tool(tool_id: str):
    """Delete (deprecate) a tool."""
    registry = get_registry()
    success = registry.delete_tool(tool_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    return {"status": "deleted", "tool_id": tool_id}


@app.get("/api/v1/tools/search")
async def search_tools(
    q: str = "",
    category: Optional[str] = None,
    max_price: Optional[str] = None,
    min_rating: Optional[float] = None,
    limit: int = 20,
):
    """Search for tools."""
    registry = get_registry()
    
    tools = registry.search_tools(
        query=q,
        category=category,
        max_price=max_price,
        min_rating=min_rating,
        limit=limit,
    )
    
    return {
        "tools": [t.to_dict() for t in tools],
        "count": len(tools),
    }


@app.get("/api/v1/categories")
async def get_categories():
    """Get all tool categories."""
    registry = get_registry()
    return {"categories": registry.get_categories()}


# ============ Tool Execution Endpoints ============

@app.post("/api/v1/execute")
async def execute_tool(request: ToolExecuteRequest):
    """Execute a tool."""
    mcp_adapter = get_mcp_adapter()
    
    # Build MCP request
    mcp_request = MCPRequest(
        id="api-execute",
        method="tools/execute",
        params={
            "tool": request.tool_name,
            "arguments": request.arguments,
            "auth_id": request.payment_auth_id,
            "auto_pay": request.auto_pay,
            "max_price": request.max_price,
        }
    )
    
    response = await mcp_adapter.handle_request(mcp_request)
    
    if response.is_error():
        error_code = response.error["code"]
        if error_code == -32002:  # Payment required
            return JSONResponse(
                status_code=402,
                content=response.to_dict(),
            )
        raise HTTPException(
            status_code=400,
            detail=response.error.get("message", "Execution failed")
        )
    
    return response.to_dict()


# ============ Payment Endpoints ============

@app.post("/api/v1/payments/challenge")
async def create_payment_challenge(request: PaymentChallengeRequest):
    """Create a payment challenge (HTTP 402)."""
    payment_engine = get_payment_engine()
    
    token = TokenType(request.token) if request.token else TokenType.USDC
    
    challenge = payment_engine.create_challenge(
        tool_id=request.tool_id,
        tool_name=request.tool_name,
        amount=request.amount,
        token=token,
        recipient_address=request.recipient_address,
    )
    
    return challenge.to_response_body()["error"]["data"]


@app.post("/api/v1/payments/verify")
async def verify_payment(
    challenge_id: str,
    tx_hash: str,
    from_address: str,
    amount: str,
):
    """Verify a payment against a challenge."""
    payment_engine = get_payment_engine()
    
    valid, error = payment_engine.verify_payment(
        challenge_id=challenge_id,
        tx_hash=tx_hash,
        from_address=from_address,
        amount=amount,
    )
    
    if not valid:
        raise HTTPException(status_code=400, detail=error)
    
    return {"valid": True, "challenge_id": challenge_id}


@app.post("/api/v1/payments/authorize")
async def authorize_payment(
    agent_id: str,
    challenge_id: str,
    tx_hash: Optional[str] = None,
):
    """Create an authorization after successful payment."""
    payment_engine = get_payment_engine()
    
    auth = payment_engine.authorize_payment(
        agent_id=agent_id,
        challenge_id=challenge_id,
        tx_hash=tx_hash,
    )
    
    if not auth:
        raise HTTPException(status_code=400, detail="Authorization failed")
    
    return {
        "auth_id": auth.auth_id,
        "status": auth.status.value,
        "amount": auth.amount,
        "expires_at": auth.expires_at,
    }


@app.get("/api/v1/payments/spending/{agent_id}")
async def get_agent_spending(agent_id: str):
    """Get spending summary for an agent."""
    payment_engine = get_payment_engine()
    return payment_engine.get_agent_spending(agent_id)


# ============ Escrow Endpoints ============

@app.post("/api/v1/escrow")
async def create_escrow(request: EscrowCreateRequest):
    """Create a new escrow account."""
    escrow_manager = get_escrow_manager()
    
    escrow = await escrow_manager.create_escrow(
        payer=request.payer,
        beneficiary=request.beneficiary,
        provider=request.provider,
        tool_id=request.tool_id,
        tool_name=request.tool_name,
        amount=request.amount,
        token=request.token,
        input_data=request.input_data,
        timeout_seconds=request.timeout_seconds,
    )
    
    return escrow.to_dict()


@app.get("/api/v1/escrow/{escrow_id}")
async def get_escrow(escrow_id: str):
    """Get an escrow by ID."""
    escrow_manager = get_escrow_manager()
    escrow = await escrow_manager.get_escrow(escrow_id)
    
    if not escrow:
        raise HTTPException(status_code=404, detail="Escrow not found")
    
    return escrow.to_dict()


@app.post("/api/v1/escrow/{escrow_id}/fund")
async def fund_escrow(escrow_id: str, request: EscrowFundRequest):
    """Fund an escrow account."""
    escrow_manager = get_escrow_manager()
    
    success, message = await escrow_manager.fund_escrow(
        escrow_id=escrow_id,
        tx_hash=request.tx_hash,
        from_address=request.from_address,
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"status": "funded", "escrow_id": escrow_id}


@app.post("/api/v1/escrow/{escrow_id}/lock")
async def lock_escrow(escrow_id: str):
    """Lock an escrow for execution."""
    escrow_manager = get_escrow_manager()
    
    success, message = await escrow_manager.lock_escrow(escrow_id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"status": "locked", "escrow_id": escrow_id}


@app.post("/api/v1/escrow/{escrow_id}/complete")
async def complete_execution(
    escrow_id: str,
    success: bool,
    output_data: Optional[Dict] = None,
    partial_refund_percent: Optional[float] = None,
):
    """Mark execution as complete."""
    escrow_manager = get_escrow_manager()
    
    result, message = await escrow_manager.complete_execution(
        escrow_id=escrow_id,
        success=success,
        output_data=output_data,
        partial_refund_percent=partial_refund_percent,
    )
    
    if not result:
        raise HTTPException(status_code=400, detail=message)
    
    return {"status": "completed", "message": message, "escrow_id": escrow_id}


@app.post("/api/v1/escrow/{escrow_id}/dispute")
async def open_dispute(
    escrow_id: str,
    opened_by: str,
    reason: str,
    evidence: Optional[List[str]] = None,
):
    """Open a dispute for an escrow."""
    escrow_manager = get_escrow_manager()
    
    reason_enum = DisputeReason(reason)
    
    success, message, dispute_id = await escrow_manager.open_dispute(
        escrow_id=escrow_id,
        opened_by=opened_by,
        reason=reason_enum,
        evidence=evidence,
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"status": "disputed", "dispute_id": dispute_id, "escrow_id": escrow_id}


@app.get("/api/v1/escrow/stats")
async def get_escrow_stats():
    """Get escrow statistics."""
    escrow_manager = get_escrow_manager()
    return escrow_manager.get_stats()


# ============ Statistics Endpoints ============

@app.get("/api/v1/stats")
async def get_stats():
    """Get overall gateway statistics."""
    registry = get_registry()
    escrow_manager = get_escrow_manager()
    mcp_adapter = get_mcp_adapter()
    
    return {
        "registry": registry.get_stats(),
        "escrow": escrow_manager.get_stats(),
        "mcp": mcp_adapter.get_stats(),
    }


# ============ Run ============

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "mcp_gateway.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
