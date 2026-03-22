"""
Discovery Engine - Vector-based semantic search for tools.

Provides intelligent tool discovery and recommendations.
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Union
from collections import defaultdict


@dataclass
class SearchResult:
    """Search result with relevance scoring."""
    tool_id: str
    tool_name: str
    description: str
    
    # Scores
    relevance_score: float = 0.0
    price_score: float = 0.0
    rating_score: float = 0.0
    
    # Metadata
    category: str = ""
    capabilities: List[str] = field(default_factory=list)
    price: Optional[str] = None
    
    # Explanation
    match_reason: str = ""


@dataclass
class AgentProfile:
    """Agent profile for recommendations."""
    agent_id: str
    
    # Preferences
    preferred_categories: List[str] = field(default_factory=list)
    preferred_capabilities: List[str] = field(default_factory=list)
    
    # History
    used_tools: List[str] = field(default_factory=list)
    search_queries: List[str] = field(default_factory=list)
    
    # Budget
    budget_tier: str = "standard"  # free, standard, premium
    avg_spending: float = 0.0


class DiscoveryEngine:
    """
    Discovery Engine for MCP tools.
    
    Features:
    - Full-text search
    - Semantic search (vector embeddings)
    - Filtering and faceting
    - Personalized recommendations
    - Similar tool discovery
    """
    
    def __init__(
        self,
        registry: Optional[Any] = None,
        embedding_model: str = "local",
    ):
        self.registry = registry
        
        # Indexes for fast search
        self._name_index: Dict[str, List[str]] = defaultdict(list)
        self._tag_index: Dict[str, List[str]] = defaultdict(list)
        self._category_index: Dict[str, List[str]] = defaultdict(list)
        self._capability_index: Dict[str, List[str]] = defaultdict(list)
        
        # Vector embeddings (simulated for MVP)
        self._embeddings: Dict[str, List[float]] = {}
        
        # Agent profiles
        self._agent_profiles: Dict[str, AgentProfile] = {}
    
    def index_tool(self, tool: Any) -> None:
        """
        Index a tool for discovery.
        
        Args:
            tool: Tool to index
        """
        tool_id = tool.id
        name = tool.name.lower()
        description = tool.description.lower()
        
        # Tokenize name
        for word in name.split():
            if len(word) > 2:
                self._name_index[word].append(tool_id)
        
        # Tokenize description
        for word in description.split():
            if len(word) > 2:
                self._name_index[word].append(tool_id)
        
        # Index tags
        for tag in getattr(tool, "tags", []):
            self._tag_index[tag.lower()].append(tool_id)
        
        # Index category
        category = getattr(tool, "category", "")
        if category:
            self._category_index[category].append(tool_id)
        
        # Index capabilities
        for cap in getattr(tool, "capabilities", []):
            self._capability_index[cap].append(tool_id)
        
        # Generate embedding (simulated)
        self._embeddings[tool_id] = self._generate_embedding(
            f"{name} {description}"
        )
    
    def remove_tool(self, tool_id: str) -> None:
        """Remove a tool from the index."""
        # Remove from all indexes
        for index in [self._name_index, self._tag_index, 
                      self._category_index, self._capability_index]:
            for key, tool_ids in list(index.items()):
                if tool_id in tool_ids:
                    index[key] = [tid for tid in tool_ids if tid != tool_id]
                    if not index[key]:
                        del index[key]
        
        # Remove embedding
        if tool_id in self._embeddings:
            del self._embeddings[tool_id]
    
    def search(
        self,
        query: str,
        category: Optional[str] = None,
        max_price: Optional[str] = None,
        min_rating: Optional[float] = None,
        capabilities: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[SearchResult]:
        """
        Search for tools.
        
        Args:
            query: Search query
            category: Filter by category
            max_price: Maximum price
            min_rating: Minimum rating
            capabilities: Required capabilities
            limit: Max results
            
        Returns:
            List of SearchResult
        """
        results: Dict[str, Tuple[float, str]] = {}
        
        # Tokenize query
        tokens = self._tokenize(query)
        
        # Score by name match
        for token in tokens:
            for word, tool_ids in self._name_index.items():
                if token in word or word in token:
                    for tool_id in tool_ids:
                        if tool_id not in results:
                            results[tool_id] = (0.0, "")
                        score, reason = results[tool_id]
                        results[tool_id] = (score + 2.0, f"Name match: {word}")
        
        # Score by tag match
        for token in tokens:
            for tag, tool_ids in self._tag_index.items():
                if token in tag or tag in token:
                    for tool_id in tool_ids:
                        if tool_id not in results:
                            results[tool_id] = (0.0, "")
                        score, reason = results[tool_id]
                        results[tool_id] = (score + 1.5, f"Tag match: {tag}")
        
        # Score by capability match
        for token in tokens:
            for cap, tool_ids in self._capability_index.items():
                if token in cap or cap in token:
                    for tool_id in tool_ids:
                        if tool_id not in results:
                            results[tool_id] = (0.0, "")
                        score, reason = results[tool_id]
                        results[tool_id] = (score + 1.0, f"Capability: {cap}")
        
        # Score by semantic similarity
        query_embedding = self._generate_embedding(query)
        for tool_id, embedding in self._embeddings.items():
            similarity = self._cosine_similarity(query_embedding, embedding)
            
            if tool_id not in results:
                results[tool_id] = (0.0, "")
            
            score, reason = results[tool_id]
            results[tool_id] = (score + similarity * 3.0, "Semantic similarity")
        
        # Apply filters and create results
        search_results = []
        for tool_id, (score, reason) in sorted(results.items(), key=lambda x: -x[1][0]):
            if len(search_results) >= limit:
                break
            
            # Get tool from registry
            if not self.registry:
                continue
            
            tool = self.registry.get_tool(tool_id)
            if not tool:
                continue
            
            # Apply filters
            if category and tool.category != category:
                continue
            
            if max_price and tool.pricing:
                tool_price = tool.get_price()
                if tool_price and float(tool_price) > float(max_price):
                    continue
            
            if min_rating and tool.rating < min_rating:
                continue
            
            if capabilities:
                tool_caps = getattr(tool, "capabilities", [])
                if not any(cap in tool_caps for cap in capabilities):
                    continue
            
            # Calculate other scores
            price_score = self._calculate_price_score(tool)
            rating_score = getattr(tool, "rating", 0.0) / 5.0
            
            # Combined score
            total_score = (score * 0.6 + price_score * 0.2 + rating_score * 0.2)
            
            search_results.append(SearchResult(
                tool_id=tool_id,
                tool_name=tool.name,
                description=tool.description,
                relevance_score=score,
                price_score=price_score,
                rating_score=rating_score,
                category=tool.category,
                capabilities=getattr(tool, "capabilities", []),
                price=tool.get_price(),
                match_reason=reason,
            ))
        
        # Sort by total score
        search_results.sort(key=lambda x: 
            x.relevance_score * 0.6 + x.price_score * 0.2 + x.rating_score * 0.2,
            reverse=True
        )
        
        return search_results
    
    def recommend_for_agent(
        self,
        agent_id: str,
        limit: int = 10,
    ) -> List[SearchResult]:
        """
        Get personalized recommendations for an agent.
        
        Args:
            agent_id: Agent to recommend for
            limit: Max recommendations
            
        Returns:
            List of SearchResult
        """
        profile = self._agent_profiles.get(agent_id)
        
        if not profile:
            # Cold start: return popular tools
            return self._get_popular_tools(limit)
        
        # Get tools similar to previously used tools
        recommendations = []
        
        # Tools in preferred categories
        for category in profile.preferred_categories:
            tools = self.registry.get_tools_by_category(category) if self.registry else []
            for tool in tools:
                if tool.id not in profile.used_tools:
                    recommendations.append(SearchResult(
                        tool_id=tool.id,
                        tool_name=tool.name,
                        description=tool.description,
                        category=tool.category,
                        capabilities=getattr(tool, "capabilities", []),
                        price=tool.get_price(),
                        match_reason=f"Category: {category}",
                    ))
        
        # Similar to used tools
        for tool_id in profile.used_tools[-5:]:  # Last 5 tools
            similar = self.find_similar(tool_id, limit=3)
            for sim in similar:
                if sim.tool_id not in profile.used_tools:
                    recommendations.append(sim)
        
        # Deduplicate and limit
        seen = set()
        unique = []
        for rec in recommendations:
            if rec.tool_id not in seen:
                seen.add(rec.tool_id)
                unique.append(rec)
        
        return unique[:limit]
    
    def find_similar(
        self,
        tool_id: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        """
        Find tools similar to a given tool.
        
        Args:
            tool_id: Tool to find similar to
            limit: Max results
            
        Returns:
            List of SearchResult
        """
        if tool_id not in self._embeddings:
            return []
        
        tool_embedding = self._embeddings[tool_id]
        
        # Calculate similarity to all other tools
        similarities = []
        for other_id, embedding in self._embeddings.items():
            if other_id == tool_id:
                continue
            
            similarity = self._cosine_similarity(tool_embedding, embedding)
            similarities.append((other_id, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Create results
        results = []
        for other_id, similarity in similarities[:limit]:
            tool = self.registry.get_tool(other_id) if self.registry else None
            if not tool:
                continue
            
            results.append(SearchResult(
                tool_id=other_id,
                tool_name=tool.name,
                description=tool.description,
                relevance_score=similarity,
                category=tool.category,
                capabilities=getattr(tool, "capabilities", []),
                price=tool.get_price(),
                match_reason=f"Similar to {tool.name} ({similarity:.2f})",
            ))
        
        return results
    
    def update_agent_profile(self, agent_id: str, event: str, data: Dict) -> None:
        """
        Update agent profile based on events.
        
        Args:
            agent_id: Agent ID
            event: Event type (search, execute, view)
            data: Event data
        """
        if agent_id not in self._agent_profiles:
            self._agent_profiles[agent_id] = AgentProfile(agent_id=agent_id)
        
        profile = self._agent_profiles[agent_id]
        
        if event == "search":
            profile.search_queries.append(data.get("query", ""))
        elif event == "execute":
            tool_id = data.get("tool_id", "")
            profile.used_tools.append(tool_id)
            
            # Update category preferences
            tool = self.registry.get_tool(tool_id) if self.registry else None
            if tool and tool.category not in profile.preferred_categories:
                profile.preferred_categories.append(tool.category)
        elif event == "view":
            # Track views for implicit preferences
            pass
    
    def get_trending_tools(self, limit: int = 10) -> List[SearchResult]:
        """Get trending tools based on recent activity."""
        # In production, track execution counts over time
        # For MVP, return top-rated tools
        return self._get_popular_tools(limit)
    
    def get_category_overview(self) -> Dict:
        """Get overview of all categories."""
        categories = defaultdict(lambda: {
            "count": 0,
            "avg_price": 0,
            "avg_rating": 0,
            "tools": [],
        })
        
        if not self.registry:
            return {}
        
        for tool in self.registry.list_tools():
            cat = tool.category
            categories[cat]["count"] += 1
            
            price = tool.get_price()
            if price:
                categories[cat]["avg_price"] = (
                    (categories[cat]["avg_price"] * (categories[cat]["count"] - 1) + float(price))
                    / categories[cat]["count"]
                )
            
            categories[cat]["avg_rating"] = (
                (categories[cat]["avg_rating"] * (categories[cat]["count"] - 1) + tool.rating)
                / categories[cat]["count"]
            )
            
            categories[cat]["tools"].append({
                "id": tool.id,
                "name": tool.name,
                "rating": tool.rating,
            })
        
        return dict(categories)
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for indexing."""
        # Simple tokenization
        tokens = []
        for word in text.lower().split():
            # Remove punctuation
            word = ''.join(c for c in word if c.isalnum())
            if len(word) > 2:
                tokens.append(word)
        return tokens
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate vector embedding for text.
        
        In production, use a proper embedding model:
        - OpenAI text-embedding-3-small
        - E5-mistral-7b
        - Local embedding model
        
        For MVP, generate a deterministic pseudo-embedding.
        """
        # Simulated embedding (not real semantic vectors)
        import hashlib
        
        # Create a fixed-size vector
        dim = 128
        embedding = []
        
        # Hash the text multiple times to create vector
        for i in range(dim):
            hash_input = f"{text}:{i}:{len(text)}"
            hash_val = hashlib.md5(hash_input.encode()).hexdigest()
            value = int(hash_val[:8], 16) / 0xFFFFFFFF
            embedding.append(value)
        
        # Normalize
        magnitude = sum(x**2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        
        mag_a = sum(x**2 for x in a) ** 0.5
        mag_b = sum(x**2 for x in b) ** 0.5
        
        if mag_a == 0 or mag_b == 0:
            return 0.0
        
        return dot_product / (mag_a * mag_b)
    
    def _calculate_price_score(self, tool: Any) -> float:
        """Calculate price score (lower price = higher score)."""
        price = tool.get_price()
        if not price:
            return 0.5  # Free tool
        
        try:
            price_val = float(price)
            # Normalize: 0 = expensive, 1 = free
            # Assuming max reasonable price is 1000000 (1 USDC)
            return max(0, 1 - (price_val / 1000000))
        except:
            return 0.5
    
    def _get_popular_tools(self, limit: int) -> List[SearchResult]:
        """Get popular tools (highest rated)."""
        if not self.registry:
            return []
        
        tools = self.registry.list_tools(limit=limit)
        return [
            SearchResult(
                tool_id=tool.id,
                tool_name=tool.name,
                description=tool.description,
                rating_score=tool.rating / 5.0,
                category=tool.category,
                capabilities=getattr(tool, "capabilities", []),
                price=tool.get_price(),
                match_reason="Popular tool",
            )
            for tool in tools
        ]
