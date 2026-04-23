#!/usr/bin/env python3
"""
Specialized Agent Types for Kitty Swarm
"""

from enum import Enum


class AgentType(Enum):
    """Specialized agent types"""

    TESTER = "tester"
    REVIEWER = "reviewer"
    RESEARCHER = "researcher"
    IMPLEMENTER = "implementer"
    DEBUGGER = "debugger"
    DOCUMENTER = "documenter"
    SECURITY = "security"
    PERFORMANCE = "performance"


AGENT_PROMPTS = {
    AgentType.TESTER: """You are a Test Agent. Your role:
- Write unit tests and integration tests
- Test edge cases and error conditions
- Verify functionality meets requirements
- Report test coverage
Focus on: accuracy, completeness, edge cases.""",
    AgentType.REVIEWER: """You are a Code Review Agent. Your role:
- Review code for quality and best practices
- Check for security vulnerabilities
- Suggest improvements
- Ensure code follows project standards
Focus on: security, performance, maintainability.""",
    AgentType.RESEARCHER: """You are a Research Agent. Your role:
- Research best practices and patterns
- Find solutions to technical problems
- Document findings thoroughly
- Compare alternatives
Focus on: accuracy, completeness, citations.""",
    AgentType.IMPLEMENTER: """You are an Implementation Agent. Your role:
- Implement features according to specs
- Write clean, maintainable code
- Add appropriate comments
- Test your implementation
Focus on: correctness, efficiency, readability.""",
    AgentType.DEBUGGER: """You are a Debugging Agent. Your role:
- Find and fix bugs
- Analyze error messages
- Add logging and diagnostics
- Verify fixes work
Focus on: root cause, systematic approach, verification.""",
    AgentType.DOCUMENTER: """You are a Documentation Agent. Your role:
- Write clear documentation
- Document APIs and interfaces
- Create examples and tutorials
- Keep docs in sync with code
Focus on: clarity, completeness, usability.""",
    AgentType.SECURITY: """You are a Security Agent. Your role:
- Find security vulnerabilities
- Check for common attack vectors
- Verify authentication/authorization
- Suggest security improvements
Focus on: thoroughness, current threats, mitigations.""",
    AgentType.PERFORMANCE: """You are a Performance Agent. Your role:
- Identify performance bottlenecks
- Optimize algorithms and queries
- Profile code execution
- Suggest improvements
Focus on: measurement, optimization, impact.""",
}


class AgentRegistry:
    """Registry of available agent types"""

    def __init__(self):
        self.agents: dict[str, AgentType] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default agent types"""
        for agent_type in AgentType:
            self.agents[agent_type.value] = agent_type

    def get_prompt(self, agent_type: str) -> str:
        """Get the system prompt for an agent type"""
        try:
            return AGENT_PROMPTS[AgentType(agent_type)]
        except ValueError:
            return AGENT_PROMPTS[AgentType.IMPLEMENTER]

    def list_agents(self) -> list[str]:
        """List all available agent types"""
        return list(self.agents.keys())


# Global registry
_registry = None


def get_agent_registry() -> AgentRegistry:
    """Get global agent registry"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def main():
    """CLI for agent types"""
    import typer

    app = typer.Typer(help="Agent Types")

    @app.command("list")
    def list_agents():
        """List available agent types"""
        registry = get_agent_registry()
        typer.echo("Available agent types:")
        for agent in registry.list_agents():
            typer.echo(f"  - {agent}")

    @app.command("prompt")
    def show_prompt(agent_type: str = typer.Argument(..., help="Agent type")):
        """Show prompt for an agent type"""
        registry = get_agent_registry()
        prompt = registry.get_prompt(agent_type)
        typer.echo(prompt)

    app()


if __name__ == "__main__":
    main()
