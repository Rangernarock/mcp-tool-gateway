"""
Tool Registry - Registration and management of MCP tools.

Stores tool metadata, schemas, pricing, and execution endpoints.
"""

import hashlib
import time
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pydantic import BaseModel, Field


class PricingType(str, Enum):
    """Pricing model types."""
    PER_CALL = "per_call"
    PER_TOKEN = "per_token"
    SUBSCRIPTION = "subscription"
    FREEMIUM = "freemium"
    TIERED = "tiered"


class ToolStatus(str, Enum):
    """Tool status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"


class SubscriptionPlan(BaseModel):
    """Subscription plan definition."""
    name: str
    price: str  # Amount per period
    period: str = "month"  # day, month, year
    calls: int | str = "unlimited"  # or specific number
    features: List[str] = []


class PricingConfig(BaseModel):
    """Tool pricing configuration."""
    type: PricingType
    price: Optional[str] = None  # For per_call
    price_per_token: Optional[str] = None  # For per_token
    free_calls: Optional[int] = 0  # For freemium
    plans: Optional[List[SubscriptionPlan]] = None  # For subscription/tiered
    max_price: Optional[str] = None  # Cap for variable pricing


class ToolSchema(BaseModel):
    """Input/output schema for a tool."""
    input_schema: Dict[str, Any] = {}
    output_schema: Dict[str, Any] = {}
    examples: Optional[List[Dict]] = None


class ToolLimits(BaseModel):
    """Execution limits for a tool."""
    max_execution_time_ms: int = 30000
    max_memory_mb: int = 512
    max_tokens: int = 8000
    max_network_calls: int = 10
    allowed_domains: Optional[List[str]] = None  # For HTTP calls


@dataclass
class Tool:
    """
    MCP Tool definition.
    
    Represents a callable tool that agents can use via the gateway.
    """
    # Core identity
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    
    # Provider
    provider_id: str
    provider_address: str
    provider_name: Optional[str] = None
    
    # Category & tags
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    
    # Capability description
    capabilities: List[str] = field(default_factory=list)  # e.g., ["web-search", "image-gen"]
    
    # Pricing
    pricing: Optional[PricingConfig] = None
    
    # Schema
    schema: Optional[ToolSchema] = None
    schema_hash: Optional[str] = None  # IPFS CID in production
    
    # Limits
    limits: ToolLimits = field(default_factory=ToolLimits)
    
    # Status
    status: ToolStatus = ToolStatus.ACTIVE
    
    # Execution
    endpoint: Optional[str] = None  # HTTP endpoint for execution
    handler: Optional[Any] = None  # Callable handler (for local tools)
    
    # Ratings & stats
    rating: float = 0.0
    rating_count: int = 0
    total_executions: int = 0
    successful_executions: int = 0
    avg_execution_time_ms: float = 0.0
    
    # Quotas
    daily_quota: Optional[int] = None
    used_today: int = 0
    last_reset: int = field(default_factory=lambda: int(time.time()))
    
    # Subscription (if applicable)
    is_subscription: bool = False
    subscription_url: Optional[str] = None
    
    # Trust & security
    requires_verification: bool = False  # Requires KYC/VC
    trusted_by: List[str] = field(default_factory=list)  # List of verified agents
    
    # Timestamps
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    
    # History
    version_history: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        # Remove handler from dict (not serializable)
        if "handler" in d:
            d.pop("handler")
        return d
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions
    
    @property
    def is_available(self) -> bool:
        """Check if tool is available for execution."""
        if self.status != ToolStatus.ACTIVE:
            return False
        
        # Check daily quota
        if self.daily_quota is not None:
            self._reset_daily_if_needed()
            if self.used_today >= self.daily_quota:
                return False
        
        return True
    
    def _reset_daily_if_needed(self) -> None:
        """Reset daily counter if day has changed."""
        day = self.last_reset // 86400
        today = int(time.time()) // 86400
        if today > day:
            self.used_today = 0
            self.last_reset = int(time.time())
    
    def increment_usage(self) -> None:
        """Increment usage counters."""
        self.used_today += 1
        self.total_executions += 1
    
    def record_success(self, execution_time_ms: float) -> None:
        """Record a successful execution."""
        self.successful_executions += 1
        # Update rolling average
        n = self.successful_executions
        self.avg_execution_time_ms = (
            (self.avg_execution_time_ms * (n - 1) + execution_time_ms) / n
        )
    
    def record_failure(self) -> None:
        """Record a failed execution."""
        # No change to success rate calculation
    
    def get_price(self, agent_id: Optional[str] = None) -> Optional[str]:
        """Get the price for an agent."""
        if self.pricing is None:
            return None
        
        if self.pricing.type == PricingType.PER_CALL:
            return self.pricing.price
        
        if self.pricing.type == PricingType.SUBSCRIPTION:
            # Return first plan's price for display
            if self.pricing.plans:
                return self.pricing.plans[0].price
        
        return self.pricing.price
    
    def get_free_calls(self, agent_id: Optional[str] = None) -> int:
        """Get free calls remaining for an agent."""
        if self.pricing and self.pricing.type == PricingType.FREEMIUM:
            return self.pricing.free_calls or 0
        return 0


class ToolRegistry:
    """
    Registry for MCP tools.
    
    Manages tool registration, discovery, and execution routing.
    """
    
    def __init__(self):
        # In-memory storage for MVP
        self._tools: Dict[str, Tool] = {}
        self._tools_by_name: Dict[str, Tool] = {}
        self._tools_by_provider: Dict[str, List[str]] = {}
        self._tools_by_category: Dict[str, List[str]] = {}
        
        # Index for search
        self._name_index: Dict[str, List[str]] = {}  # word -> tool_ids
        self._tag_index: Dict[str, List[str]] = {}  # tag -> tool_ids
    
    def register_tool(
        self,
        tool: Tool,
    ) -> Tool:
        """
        Register a new tool.
        
        Args:
            tool: Tool to register
            
        Returns:
            Registered tool
        """
        # Generate ID if not set
        if not tool.id:
            tool.id = self._generate_tool_id(tool.name, tool.provider_id)
        
        # Check for duplicate
        if tool.id in self._tools:
            raise ValueError(f"Tool already registered: {tool.id}")
        
        if tool.name in self._tools_by_name:
            raise ValueError(f"Tool name already taken: {tool.name}")
        
        # Store tool
        self._tools[tool.id] = tool
        self._tools_by_name[tool.name] = tool
        
        # Index by provider
        if tool.provider_id not in self._tools_by_provider:
            self._tools_by_provider[tool.provider_id] = []
        self._tools_by_provider[tool.provider_id].append(tool.id)
        
        # Index by category
        if tool.category not in self._tools_by_category:
            self._tools_by_category[tool.category] = []
        self._tools_by_category[tool.category].append(tool.id)
        
        # Index for search
        self._index_tool(tool)
        
        return tool
    
    def update_tool(self, tool: Tool) -> Tool:
        """
        Update an existing tool.
        
        Args:
            tool: Updated tool data
            
        Returns:
            Updated tool
        """
        if tool.id not in self._tools:
            raise ValueError(f"Tool not found: {tool.id}")
        
        # Update timestamp
        tool.updated_at = int(time.time())
        
        # Add to version history
        old_tool = self._tools[tool.id]
        tool.version_history.append({
            "version": old_tool.version,
            "updated_at": tool.updated_at,
        })
        
        # Update storage
        self._tools[tool.id] = tool
        self._tools_by_name[tool.name] = tool
        
        # Re-index
        self._unindex_tool(old_tool)
        self._index_tool(tool)
        
        return tool
    
    def get_tool(self, tool_id: str) -> Optional[Tool]:
        """Get a tool by ID."""
        return self._tools.get(tool_id)
    
    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools_by_name.get(name)
    
    def get_tools_by_provider(self, provider_id: str) -> List[Tool]:
        """Get all tools by a provider."""
        tool_ids = self._tools_by_provider.get(provider_id, [])
        return [self._tools[tid] for tid in tool_ids if tid in self._tools]
    
    def get_tools_by_category(self, category: str) -> List[Tool]:
        """Get all tools in a category."""
        tool_ids = self._tools_by_category.get(category, [])
        return [self._tools[tid] for tid in tool_ids if tid in self._tools]
    
    def list_tools(
        self,
        status: Optional[ToolStatus] = None,
        category: Optional[str] = None,
        provider_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Tool]:
        """
        List tools with optional filters.
        
        Args:
            status: Filter by status
            category: Filter by category
            provider_id: Filter by provider
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of matching tools
        """
        results = list(self._tools.values())
        
        # Apply filters
        if status:
            results = [t for t in results if t.status == status]
        if category:
            results = [t for t in results if t.category == category]
        if provider_id:
            results = [t for t in results if t.provider_id == provider_id]
        
        # Sort by rating (descending)
        results.sort(key=lambda t: t.rating, reverse=True)
        
        # Paginate
        return results[offset:offset + limit]
    
    def search_tools(
        self,
        query: str,
        category: Optional[str] = None,
        max_price: Optional[str] = None,
        min_rating: Optional[float] = None,
        capabilities: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Tool]:
        """
        Search tools by text query.
        
        Args:
            query: Search query
            category: Filter by category
            max_price: Maximum price
            min_rating: Minimum rating
            capabilities: Required capabilities
            limit: Max results
            
        Returns:
            List of matching tools
        """
        # Tokenize query
        words = query.lower().split()
        
        # Find matching tools
        scores: Dict[str, float] = {}
        for word in words:
            # Check name index
            for tid in self._name_index.get(word, []):
                scores[tid] = scores.get(tid, 0) + 2.0
            
            # Check tag index
            for tid in self._tag_index.get(word, []):
                scores[tid] = scores.get(tid, 0) + 1.5
        
        # Filter and sort
        results = []
        for tool_id, score in scores.items():
            tool = self._tools.get(tool_id)
            if not tool:
                continue
            
            # Apply filters
            if tool.status != ToolStatus.ACTIVE:
                continue
            if category and tool.category != category:
                continue
            if max_price and tool.pricing:
                tool_price = tool.get_price()
                if tool_price and float(tool_price) > float(max_price):
                    continue
            if min_rating and tool.rating < min_rating:
                continue
            if capabilities:
                if not any(cap in tool.capabilities for cap in capabilities):
                    continue
            
            results.append((tool, score))
        
        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)
        
        return [tool for tool, _ in results[:limit]]
    
    def get_categories(self) -> List[Dict]:
        """Get all categories with tool counts."""
        categories = {}
        for tool in self._tools.values():
            if tool.status != ToolStatus.ACTIVE:
                continue
            if tool.category not in categories:
                categories[tool.category] = {
                    "name": tool.category,
                    "count": 0,
                }
            categories[tool.category]["count"] += 1
        
        return list(categories.values())
    
    def get_capabilities(self) -> List[str]:
        """Get all unique capabilities across tools."""
        caps = set()
        for tool in self._tools.values():
            caps.update(tool.capabilities)
        return sorted(list(caps))
    
    def delete_tool(self, tool_id: str) -> bool:
        """Delete a tool (soft delete - marks as deprecated)."""
        tool = self._tools.get(tool_id)
        if not tool:
            return False
        
        tool.status = ToolStatus.DEPRECATED
        tool.updated_at = int(time.time())
        
        # Unindex
        self._unindex_tool(tool)
        
        return True
    
    def _index_tool(self, tool: Tool) -> None:
        """Index a tool for search."""
        # Index name words
        for word in tool.name.lower().split():
            if word not in self._name_index:
                self._name_index[word] = []
            if tool.id not in self._name_index[word]:
                self._name_index[word].append(tool.id)
        
        # Index tags
        for tag in tool.tags:
            tag_lower = tag.lower()
            if tag_lower not in self._tag_index:
                self._tag_index[tag_lower] = []
            if tool.id not in self._tag_index[tag_lower]:
                self._tag_index[tag_lower].append(tool.id)
    
    def _unindex_tool(self, tool: Tool) -> None:
        """Remove a tool from search index."""
        for word in tool.name.lower().split():
            if word in self._name_index:
                self._name_index[word] = [
                    tid for tid in self._name_index[word] if tid != tool.id
                ]
        
        for tag in tool.tags:
            tag_lower = tag.lower()
            if tag_lower in self._tag_index:
                self._tag_index[tag_lower] = [
                    tid for tid in self._tag_index[tag_lower] if tid != tool.id
                ]
    
    def _generate_tool_id(self, name: str, provider_id: str) -> str:
        """Generate a unique tool ID."""
        data = f"{name}:{provider_id}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def get_stats(self) -> Dict:
        """Get registry statistics."""
        active = [t for t in self._tools.values() if t.status == ToolStatus.ACTIVE]
        
        return {
            "total_tools": len(self._tools),
            "active_tools": len(active),
            "total_executions": sum(t.total_executions for t in self._tools.values()),
            "categories": len(self._tools_by_category),
            "providers": len(self._tools_by_provider),
            "avg_rating": sum(t.rating for t in active) / len(active) if active else 0,
        }


# Example tool definition
def create_web_search_tool(
    provider_id: str,
    provider_address: str,
) -> Tool:
    """Create an example web search tool."""
    return Tool(
        id="",
        name="web-search",
        description="Search the web for information using multiple search engines",
        provider_id=provider_id,
        provider_address=provider_address,
        provider_name="WebSearch Pro",
        category="search",
        tags=["search", "web", "information", "research"],
        capabilities=["web-search", "news-search"],
        pricing=PricingConfig(
            type=PricingType.PER_CALL,
            price="500000",  # 0.0005 USDC (micro units)
            free_calls=10,
        ),
        schema=ToolSchema(
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10},
                    "freshness": {"type": "string", "enum": ["day", "week", "month", "year"]},
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "results": {"type": "array"},
                    "total": {"type": "integer"},
                },
            },
        ),
        limits=ToolLimits(
            max_execution_time_ms=10000,
            max_network_calls=3,
        ),
        daily_quota=1000,
    )
