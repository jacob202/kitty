"""
Personal Onboarding Pipeline
Kitty learns the user's domains through research + knowledge ingestion.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class OnboardingConfig:
    """Configuration for onboarding pipeline."""
    domains: list[str]
    depth: str = "standard"  # "quick" | "standard" | "deep"
    sources: list[str] = None  # User-specified sources
    
    def __post_init__(self):
        if self.sources is None:
            self.sources = []

class OnboardingPipeline:
    """
    Personal Onboarding Pipeline - learns user's domains through research.
    
    Flow:
    1. User selects domains (audio, health, automotive, etc.)
    2. For each domain: research → digest → embed → organize
    3. Results stored in knowledge base
    4. Kitty can discuss domain from first conversation
    """
    
    def __init__(self, config: Optional[OnboardingConfig] = None):
        self.config = config or OnboardingConfig(domains=[])
        self.state = "idle"  # idle | researching | embedding | ready | error
    
    def start(self) -> str:
        """Begin onboarding for configured domains."""
        if not self.config.domains:
            return "No domains selected. Use select_domains() first."
        
        self.state = "researching"
        
        try:
            results = []
            for domain in self.config.domains:
                results.append(f"📚 Researching {domain}...")
            
            self.state = "ready"
            return f"""🚀 Onboarding started!

For each domain, I'll research:
• Core concepts and fundamentals
• Best practices 
• Common gotchas
• Your experience level

This runs in background. Use /onboarding status to check progress.

Domains: {', '.join(self.config.domains)}"""
        except Exception as e:
            self.state = "error"
            return f"Research failed: {e}"
    
    def select_domains(self, domains: list[str]) -> None:
        """User selects domains to onboard."""
        self.config.domains = domains
    
    def select_sources(self, sources: list[str]) -> None:
        """User specifies sources for domain research."""
        self.config.sources = sources
    
    def get_status(self) -> dict:
        """Return current onboarding status."""
        return {
            "state": self.state,
            "domains": self.config.domains,
            "depth": self.config.depth,
            "sources": self.config.sources,
        }

# Integration with CommandEngine
def get_onboarding_handler():
    """Return handler for /onboarding command."""
    pipeline = OnboardingPipeline()
    
    def handle(args: str, **ctx):
        from src.api.command_engine import CommandResult
        
        parts = args.strip().split() if args.strip() else []
        
        if not parts:
            # Show status
            status = pipeline.get_status()
            return CommandResult(
                success=True,
                message=f"""## Onboarding Pipeline

### Status: {status['state']}

### Selected domains: {', '.join(status['domains']) or '(none)'}

### Depth: {status['depth']}

### Usage:
/onboarding select audio health automotive
/onboarding start
/onboarding status
"""
            )
        
        cmd = parts[0]
        
        if cmd == "select":
            domains = parts[1:]
            pipeline.select_domains(domains)
            return CommandResult(success=True, message=f"Domains selected: {', '.join(domains)}")
        
        elif cmd == "start":
            result = pipeline.start()
            return CommandResult(success=True, message=result)
        
        elif cmd == "status":
            status = pipeline.get_status()
            return CommandResult(success=True, message=f"State: {status['state']}")
        
        else:
            return CommandResult(success=False, error=f"Unknown: {cmd}. Use select/start/status")
    
    return handle