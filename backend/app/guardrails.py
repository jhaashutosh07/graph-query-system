"""
Guardrails system for restricting queries to domain and dataset.

Design Principles (from DESIGN_GUIDELINES.md):
1. Multi-level filtering: keyword → pattern → semantic
2. Fail-safe: reject ambiguous queries
3. Clear, generic error messages (no data leakage)
4. Fast rejection at Level 1 & 2 (before LLM call)

Query Classes:
- IN_SCOPE: Business operations, supply chain, billing
- OUT_OF_SCOPE: Creative writing, general knowledge, irrelevant
- AMBIGUOUS: Unclear if domain-related
"""

import re
from typing import Tuple, Optional
from enum import Enum
from dataclasses import dataclass


class QueryCategory(str, Enum):
    """Query classification"""
    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    AMBIGUOUS = "ambiguous"


@dataclass
class GuardrailCheckResult:
    """Result of guardrail validation"""
    is_valid: bool
    category: QueryCategory
    reason: str
    confidence: float  # 0.0 - 1.0


class Guardrails:
    """
    Multi-level query validation system.
    
    Design Pattern:
    - Level 1 (Keyword): Fast, O(n) complexity
    - Level 2 (Regex): Pattern matching on structured queries
    - Level 3 (Semantic): LLM-based validation (optional, slower)
    """
    
    # ========================================================================
    # Level 1: Domain Keywords
    # ========================================================================
    
    DOMAIN_KEYWORDS = {
        # Core entities
        "order", "orders", "purchase", "sales", "so",
        "delivery", "deliveries", "shipment", "ship", "delivery-note",
        "invoice", "invoices", "bill", "billing", "bill-to",
        "payment", "payments", "settle", "settled",
        
        # Supporting entities
        "customer", "customers", "supplier", "vendor",
        "product", "products", "item", "material", "sku", "part",
        "address", "location", "warehouse", "plant",
        
        # Key operations
        "trace", "flow", "path", "journey", "status",
        "missing", "incomplete", "broken", "failed", "gap",
        "delay", "pending", "completed", "delivered",
        "amount", "price", "revenue", "cost",
        "top", "highest", "lowest", "first", "last",
        "count", "total", "number", "how many",
        
        # Business context
        "billing", "shipping", "transaction", "order-to-cash",
        "fulfillment", "reconciliation", "accounting",
        "logistics", "supply", "chain", "goods",
    }
    
    # ========================================================================
    # Level 2: Out-of-Scope Patterns (Regex)
    # ========================================================================
    
    OUT_OF_SCOPE_PATTERNS = [
        # Creative/entertainment
        r"(write|compose|create|tell|generate).*(poem|story|novel|song|joke|riddle)",
        r"(creative|poetry|fiction|narrative|script|screenplay|plot)",
        
        # General knowledge
        r"(how|what|why|when).*(work|does|is|are)(?!.*order|.*delivery|.*invoice)",
        r"(general|knowledge|science|history|geography|culture|language)",
        r"(explain|teach|learn).*(?!.*order|.*delivery|.*product|.*invoice)",
        
        # Personal/social
        r"(personal|relationship|advice|dating|life|advice|opinion)",
        r"(sports|movies|music|football|cricket|game).*(score|team|player)",
        
        # Politics/controversial
        r"(political|politics|government|president|election|policy)",
        r"(religion|god|faith|belief|atheism)",
        r"(controversial|debate|argue|dispute).*(policy|politics|religion)",
        
        # Technical off-domain
        r"(code|program|algorithm|python|javascript).*(write|debug|optimize|refactor)",
        r"(machine.*learning|ai|neural.*network|deep.*learning).*(train|model)",
        
        # Math/academic (unless related to business)
        r"(solve|calculate).*(equation|integral|derivative|linear.*algebra)(?!.*revenue|.*cost)",
        r"(probability|statistics|distribution).*(theory|proof)(?!.*sales|.*forecast)",
    ]
    
    # ========================================================================
    # Level 3: Semantic Patterns (Simpler keyword-based heuristics)
    # ========================================================================
    
    def __init__(self, llm_provider=None):
        """
        Initialize guardrails system.
        
        Args:
            llm_provider: Optional LLM client for semantic checks (Level 3)
        """
        self.llm_provider = llm_provider
        self._compile_regex_patterns()
    
    def _compile_regex_patterns(self):
        """Pre-compile regex patterns for performance"""
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.OUT_OF_SCOPE_PATTERNS
        ]
    
    # ========================================================================
    # Main Validation Methods
    # ========================================================================
    
    def check_query(self, query: str, use_llm: bool = False) -> GuardrailCheckResult:
        """
        Multi-level query validation.
        
        Design Logic:
        1. Try fast keyword check first (Level 1)
        2. If ambiguous, apply pattern matching (Level 2)
        3. If still ambiguous and LLM available, use semantic check (Level 3)
        4. Default to REJECT if any level marks as out-of-scope
        
        Args:
            query: User query string
            use_llm: Whether to use LLM for semantic validation (slower)
        
        Returns:
            GuardrailCheckResult with decision and explanation
        """
        # Level 1: Keyword check (fastest)
        keyword_result = self._check_keywords(query)
        if keyword_result.category != QueryCategory.AMBIGUOUS:
            return keyword_result
        
        # Level 2: Pattern matching
        pattern_result = self._check_patterns(query)
        if pattern_result.category != QueryCategory.AMBIGUOUS:
            return pattern_result
        
        # Level 3: Semantic check (if available)
        if use_llm and self.llm_provider:
            semantic_result = self._check_semantic(query)
            return semantic_result
        
        # Default: If we can't determine, reject (fail-safe)
        return GuardrailCheckResult(
            is_valid=False,
            category=QueryCategory.AMBIGUOUS,
            reason="Cannot determine if query is about the dataset",
            confidence=0.5
        )
    
    # ========================================================================
    # Level 1: Keyword-Based Check
    # ========================================================================
    
    def _check_keywords(self, query: str) -> GuardrailCheckResult:
        """
        Level 1: Fast keyword matching.
        
        Rules:
        - Query MUST contain at least one domain keyword
        - Rare, unusual queries marked as AMBIGUOUS
        """
        query_lower = query.lower()
        
        # Count domain keywords
        matched_keywords = [
            kw for kw in self.DOMAIN_KEYWORDS 
            if re.search(r'\b' + re.escape(kw) + r'\b', query_lower)
        ]
        
        if not matched_keywords:
            return GuardrailCheckResult(
                is_valid=False,
                category=QueryCategory.OUT_OF_SCOPE,
                reason="Query does not mention business entities (orders, deliveries, etc.)",
                confidence=0.95
            )
        
        if len(matched_keywords) >= 2:
            # Strong signal: Multiple domain keywords
            return GuardrailCheckResult(
                is_valid=True,
                category=QueryCategory.IN_SCOPE,
                reason=f"Strong domain signal (keywords: {', '.join(matched_keywords[:3])})",
                confidence=0.98
            )
        
        # Ambiguous: Only one keyword, need deeper check
        return GuardrailCheckResult(
            is_valid=None,
            category=QueryCategory.AMBIGUOUS,
            reason=f"Weak confidence with single keyword: {matched_keywords[0]}",
            confidence=0.6
        )
    
    # ========================================================================
    # Level 2: Pattern-Based Check
    # ========================================================================
    
    def _check_patterns(self, query: str) -> GuardrailCheckResult:
        """
        Level 2: Reject if matches known out-of-scope patterns.
        
        Rules:
        - Any match → OUT_OF_SCOPE
        - No match → AMBIGUOUS (defer to Level 3)
        """
        for pattern in self.compiled_patterns:
            if pattern.search(query):
                return GuardrailCheckResult(
                    is_valid=False,
                    category=QueryCategory.OUT_OF_SCOPE,
                    reason="Query matches out-of-domain pattern",
                    confidence=0.85
                )
        
        # No out-of-scope pattern matched, still ambiguous
        return GuardrailCheckResult(
            is_valid=None,
            category=QueryCategory.AMBIGUOUS,
            reason="No clear pattern match",
            confidence=0.5
        )
    
    # ========================================================================
    # Level 3: Semantic Check (LLM-based)
    # ========================================================================
    
    def _check_semantic(self, query: str) -> GuardrailCheckResult:
        """
        Level 3: Use LLM to semantically validate query relevance.
        
        This is slower but more accurate for edge cases.
        """
        if not self.llm_provider:
            return GuardrailCheckResult(
                is_valid=False,
                category=QueryCategory.AMBIGUOUS,
                reason="Cannot validate semantic relevance without LLM",
                confidence=0.5
            )
        
        try:
            # Simple yes/no semantic check
            response = self.llm_provider.ask(
                f"""You are a content moderator. Determine if this query is about:
                - Business operations (orders, deliveries, invoices, payments, products, customers)
                - Supply chain, fulfillment, billing, or accounting

                Query: "{query}"

                Answer ONLY with: YES or NO
                """
            )
            
            is_valid = "YES" in response.upper()
            return GuardrailCheckResult(
                is_valid=is_valid,
                category=QueryCategory.IN_SCOPE if is_valid else QueryCategory.OUT_OF_SCOPE,
                reason="Semantic validation via LLM",
                confidence=0.90
            )
        
        except Exception as e:
            # LLM error: default to REJECT
            return GuardrailCheckResult(
                is_valid=False,
                category=QueryCategory.AMBIGUOUS,
                reason=f"Semantic check failed: {str(e)}",
                confidence=0.3
            )
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def get_rejection_message(self, result: GuardrailCheckResult) -> str:
        """
        Generate user-facing error message.
        
        Design Principle: Generic messages (no data/schema leakage)
        """
        if result.is_valid is False:
            return (
                "This system is designed to answer questions related to the provided dataset only. "
                "Please ask about orders, deliveries, invoices, payments, customers, or products."
            )
        elif result.is_valid is None:
            return (
                "I cannot determine if this query is within my domain. "
                "I can help with business operations questions about the dataset."
            )
        return ""
    
    def validate_cypher_query(self, cypher: str) -> Tuple[bool, str]:
        """
        Validate generated Cypher query before execution.
        
        Safety Checks:
        - No DELETE, DROP, ALTER operations
        - No access to system nodes
        - Reasonable query complexity
        """
        dangerous_keywords = ["DELETE", "DROP", "ALTER", "DETACH"]
        system_prefixes = ["__", "neo4j.", "system."]
        
        cypher_upper = cypher.upper()
        
        # Check for dangerous operations
        for keyword in dangerous_keywords:
            if keyword in cypher_upper:
                return False, f"Query contains prohibited operation: {keyword}"
        
        # Check for system access
        for prefix in system_prefixes:
            if prefix in cypher:
                return False, f"Query accesses restricted namespace: {prefix}"
        
        # Check query complexity (simple heuristic)
        hop_count = cypher.count("--")
        if hop_count > 10:
            return False, "Query is too complex (too many hops)"
        
        return True, "Query is safe"


# ============================================================================
# Example Usage & Testing
# ============================================================================

if __name__ == "__main__":
    guardrails = Guardrails()
    
    # Test cases
    test_queries = [
        ("Which products are in the most orders?", True),
        ("Write a poem about shipping", False),
        ("How does machine learning work?", False),
        ("Trace order ORD-123 to delivery", True),
        ("Can you tell a joke?", False),
        ("Find customers with incomplete payments", True),
        ("What is the capital of France?", False),
    ]
    
    print("Testing Guardrails System:")
    print("=" * 80)
    
    for query, expected in test_queries:
        result = guardrails.check_query(query)
        status = "✓" if (result.is_valid == expected) else "✗"
        print(f"{status} Query: {query}")
        print(f"  Result: {result.is_valid} ({result.category.value}) - {result.reason}")
        print()
