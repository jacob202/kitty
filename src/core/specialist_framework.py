#!/usr/bin/env python3
"""Specialist Framework - Domain experts with LLM + knowledge base integration."""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_memory_instance = None
_lightrag_stores: dict[str, Any] = {}
_kb_cache: dict[str, str] = {}
_KB_CACHE_MAX_SIZE = 500


def _get_memory():
    global _memory_instance
    if _memory_instance is None:
        from src.memory.kitty_memory_enhanced import KittyMemoryEnhanced

        _memory_instance = KittyMemoryEnhanced()
    return _memory_instance


def _get_lightrag_for_domain(domain: str):
    """Get or create a LightRAGStore for a specific domain."""
    global _lightrag_stores
    if domain not in _lightrag_stores:
        from src.memory.lightrag_store import LightRAGStore

        _lightrag_stores[domain] = LightRAGStore(domain=domain)
    return _lightrag_stores[domain]


@dataclass
class SpecialistResponse:
    """Standard response format from any specialist"""

    content: str
    confidence: float
    sources: list[str]
    safety_warnings: list[str]
    suggested_followups: list[str]
    diagnostics: dict[str, Any] | None = None


def _query_knowledge_base(question: str, domain: str, store: Any | None = None) -> str:
    """Query LightRAG or ChromaDB for domain-relevant context with caching."""
    cache_key = f"{domain}:{question[:100]}"
    if cache_key in _kb_cache:
        return _kb_cache[cache_key]

    try:
        if store is None:
            store = _get_lightrag_for_domain(domain)
        result = store.search(question)
        if result and "not found" not in result.lower():
            _kb_cache[cache_key] = result[:3000]
            if len(_kb_cache) > _KB_CACHE_MAX_SIZE:
                oldest_key = next(iter(_kb_cache))
                del _kb_cache[oldest_key]
            return _kb_cache[cache_key]
    except Exception as e:
        logger.debug(f"LightRAG unavailable for domain {domain}: {e}")

    try:
        mem = _get_memory()
        context = mem.retrieve_context(question, n_conversations=0, n_facts=0, n_documents=5, domain=domain)
        docs = context.get("documents", [])
        if docs:
            content = "\n---\n".join(docs)[:3000]
            _kb_cache[cache_key] = content
            if len(_kb_cache) > _KB_CACHE_MAX_SIZE:
                oldest_key = next(iter(_kb_cache))
                del _kb_cache[oldest_key]
            return content
    except Exception as e:
        logger.debug(f"ChromaDB unavailable: {e}")

    return ""


def ingest_domain_documents(watch_dir: str = "data/staging", domain: str | None = None) -> dict[str, int]:
    """Ingest documents from staging directory into specialist KB.

    Args:
        watch_dir: Directory containing .md and .pdf files to ingest
        domain: Specific domain to ingest into

    Returns:
        Dict mapping filename to chunk count stored
    """
    from src.memory.ingest_engine import IngestEngine

    engine = IngestEngine(watch_dir=watch_dir)
    return engine.ingest_directory(store_in_kb=True, domain=domain)


class BaseSpecialist(ABC):
    """
    Abstract base class for all specialists.
    Each domain expert inherits from this and gets LLM + KB integration.
    Soul files in config/specialists/<name>.md override hardcoded prompts.
    """

    _SOUL_DIR = Path("config/specialists")

    def __init__(self, name: str, domain: str, knowledge_base_path: str):
        self.name = name
        self.domain = domain
        self.knowledge_base_path = knowledge_base_path

        # Load soul file if it exists
        self._soul_content = self._load_soul_file()

        # Extract metadata from soul file if available, otherwise use defaults
        metadata = self._extract_metadata()
        if metadata.get("name"):
            self.name = metadata["name"]
        if metadata.get("domain"):
            self.domain = metadata["domain"]

        # Personality and prompt are derived from soul file or fallbacks
        self.personality = self._extract_personality() or self._get_personality()

        # Domain-specific LightRAG store
        self._kb_store = _get_lightrag_for_domain(self.domain)
        
        # Map to AgentSpec
        from src.agents.custom_agents import AgentSpec
        
        # Tools available to specialists: browse (web), search_files (grep), read_diagnostics (logs)
        agent_tools = ["browse", "search_files", "read_diagnostics", "read_file", "calculate"]
        
        self.agent_spec = AgentSpec(
            name=self.name,
            description=f"{self.domain} specialist",
            model="openrouter/free",  # Default fallback
            system_prompt=self._soul_content if self._soul_content else self._get_system_prompt(),
            tools=agent_tools,
            temperature=0.7
        )

    def _load_soul_file(self) -> str | None:
        """Load the markdown soul file from config/specialists/."""
        # 1. Direct match by name or domain
        paths = [self._SOUL_DIR / f"{self.name.lower()}.md", self._SOUL_DIR / f"{self.domain.lower()}.md"]
        for path in paths:
            if path.exists():
                return path.read_text().strip()

        # 2. Scanning match: check all files for # Domain header matching self.domain
        if self._SOUL_DIR.exists():
            for path in self._SOUL_DIR.glob("*.md"):
                content = path.read_text()
                match = re.search(r"# Domain\n(.*?)(?=\n#|$)", content, re.DOTALL)
                if match and match.group(1).strip().lower() == self.domain.lower():
                    return content.strip()

        return None

    def _extract_metadata(self) -> dict[str, str]:
        """Extract metadata (Name, Domain) from markdown soul content."""
        metadata = {}
        if not self._soul_content:
            return metadata

        # Look for # Name\n<value>
        name_match = re.search(r"# Name\n(.*?)(?=\n#|$)", self._soul_content, re.DOTALL)
        if name_match:
            metadata["name"] = name_match.group(1).strip()

        domain_match = re.search(r"# Domain\n(.*?)(?=\n#|$)", self._soul_content, re.DOTALL)
        if domain_match:
            metadata["domain"] = domain_match.group(1).strip()

        return metadata

    def _extract_personality(self) -> str | None:
        """Extract personality string from markdown soul content if available."""
        if not self._soul_content:
            return None

        # Look for # Personality section
        match = re.search(r"# Personality\n(.*?)(?=\n#|$)", self._soul_content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    @abstractmethod
    def _get_personality(self) -> str:
        pass

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Return the full system prompt for this specialist (fallback if no soul file)."""
        pass

    @abstractmethod
    def _get_safety_topics(self) -> list[str]:
        """Return safety-relevant keywords for this domain."""
        return []

    def query(
        self,
        question: str,
        context: dict[str, Any] | None = None,
        model: str | None = None,
        context_preamble: str = "",
        honcho_approach: str = "",
    ) -> SpecialistResponse:
        """Query the specialist with LLM + knowledge base + temporal cross-check."""
        kb_context = _query_knowledge_base(question, self.domain, store=self._kb_store)

        # ─── Temporal Cross-Check (Memory Weave) ────────────────────────────────
        weave_context = ""
        try:
            from src.memory.memory_weave import get_weave

            weave = get_weave()
            # Single combined query using key entities
            key_entities = list(
                set("".join(filter(str.isalnum, w)) for w in question.split() if len(w) > 4)
            )[:5]
            if key_entities:
                combined_query = " ".join(key_entities)
                fact_query = weave.query(combined_query, "*")
                if fact_query and fact_query.confidence > 0.6:
                    weave_context = (
                        f"\nNote from Memory Weave: {fact_query.fact} (Source: {fact_query.source_chain[0]})"
                    )
        except Exception:
            pass

        prompt_parts = []
        if weave_context:
            prompt_parts.append(f"Previously verified info:{weave_context}\n---")
        if kb_context:
            prompt_parts.append(f"Relevant knowledge:\n{kb_context}\n---")
        if context:
            prompt_parts.append(f"Additional context: {context}")
        prompt_parts.append(f"User question: {question}")
        full_prompt = "\n\n".join(prompt_parts)

        try:
            from src.space_kitty.llm_client import call_llm
            from src.tools.kitty_tools import KittyTools, ToolCallingLoop

            system_prompt = self.agent_spec.system_prompt

            # Inject Honcho approach for emotional adaptation
            if honcho_approach:
                system_prompt = f"{system_prompt}\n\n[Current tone & strategy recommendation: {honcho_approach}]"

            if context_preamble:
                system_prompt = context_preamble + "\n\n" + system_prompt

            model_to_use = model or self.agent_spec.model

            def llm_callback(prompt_text: str) -> str:
                return call_llm(
                    prompt=prompt_text,
                    system_prompt=system_prompt,
                    temperature=self.agent_spec.temperature,
                    model=model_to_use,
                )

            kitty_tools = KittyTools()
            # Filter tools to only those specified in agent_spec
            if self.agent_spec.tools:
                kitty_tools.tools = {k: v for k, v in kitty_tools.tools.items() if k in self.agent_spec.tools}

            loop = ToolCallingLoop(tools=kitty_tools, process_callback=llm_callback)
            content = loop.process(full_prompt)
        except Exception as e:
            logger.warning(f"LLM call failed for {self.name}: {e}")
            content = self._fallback_response(question)

        safety = self._check_safety(question)
        diag = {
            "fallback_used": content.startswith("[offline mode]") or content.startswith(f"[{self.name}]: I'd help with"),
            "mode": (
                "offline"
                if (content.startswith("[offline mode]") or content.startswith(f"[{self.name}]: I'd help with"))
                else "online"
            ),
            "specialist": self.name,
            "domain": self.domain,
            "emotional_adaptation": bool(honcho_approach),
        }
        return SpecialistResponse(
            content=content,
            confidence=0.9 if kb_context else 0.5,
            sources=[self.knowledge_base_path] if kb_context else [],
            safety_warnings=safety,
            suggested_followups=[],
            diagnostics=diag,
        )

    def _fallback_response(self, question: str) -> str:
        """Fallback when no LLM is available."""
        return f"[{self.name}]: I'd help with '{question[:80]}' but no LLM backend is available right now."

    def _check_safety(self, question: str) -> list[str]:
        """Check for safety-relevant content."""
        warnings = []
        q_lower = question.lower()
        for topic in self._get_safety_topics():
            if topic in q_lower:
                warnings.append(f"Safety note: {topic} mentioned — exercise caution.")
        return warnings

    def format_response(self, raw_response: str) -> str:
        return f"[{self.name}]: {raw_response}"

    def offline_response(self, question: str) -> str:
        """Standard offline sentinel response."""
        return f"[offline mode] {self.name} here. No LLM available - test offline sentinel. Raw query: {question[:50]}"


class SpecialistRegistry:
    """Registry of all available specialists with auto-discovery."""

    def __init__(self):
        self.specialists = {}
        self._discover_specialists()

    def _discover_specialists(self):
        """Auto-discover specialists in the src.core.specialists package."""
        import importlib
        import pkgutil

        import src.core.specialists as specialists_pkg

        for loader, module_name, is_pkg in pkgutil.iter_modules(specialists_pkg.__path__):
            if module_name == "soul":
                continue  # Handled specially or mapped to Kitty

            full_module_name = f"src.core.specialists.{module_name}"
            module = importlib.import_module(full_module_name)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseSpecialist)
                    and attr is not BaseSpecialist
                ):
                    # Instantiate with standard paths
                    name = module_name.capitalize()
                    domain = module_name
                    kb_path = f"data/knowledge_bases/{module_name}/"

                    instance = attr(name, domain, kb_path)
                    self.specialists[instance.name] = instance

        # Always add the core Soul
        from src.core.specialists.soul import KittySoulSpecialist

        self.specialists["Kitty"] = KittySoulSpecialist("Kitty", "general", "")

    def get_specialist(self, name: str) -> BaseSpecialist | None:
        return self.specialists.get(name)

    def list_specialists(self) -> list[str]:
        return list(self.specialists.keys())


if __name__ == "__main__":
    registry = SpecialistRegistry()

    print("=" * 80)
    print("SPECIALIST FRAMEWORK - TEST")
    print("=" * 80)
    print()

    for name in registry.list_specialists():
        specialist = registry.get_specialist(name)
        print(f"✅ {name}: {specialist.domain}")
        print(f"   Personality: {specialist.personality}")

    print()
    print("Testing Alex with audio question:")
    alex = registry.get_specialist("Alex")
    response = alex.query("My amp is buzzing")
    print(f"   Response: {response.content}")
    print(f"   Safety: {response.safety_warnings}")

    print()
    print("✅ Specialist Framework ready!")
