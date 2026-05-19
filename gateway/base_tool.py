"""Base Tool — standardized interface for all model-invokable tools in Kitty.

Provides a consistent interface for tool definition, execution, and result handling.
Includes risk classification and permission system integration.
"""

import abc
import logging
from enum import Enum
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field

logger = logging.getLogger("kitty.base_tool")


class ToolRiskLevel(str, Enum):
    """Risk levels for tool actions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolResult(BaseModel):
    """Standardized tool result format."""
    success: bool = Field(..., description="Whether the tool execution succeeded")
    output: Optional[str] = Field(None, description="Tool output as string")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class BaseTool(abc.ABC):
    """Abstract base class for all Kitty tools."""
    
    # These must be overridden by subclasses
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    
    # Risk level - subclasses should define their risk level
    risk_level: ToolRiskLevel = Field(default=ToolRiskLevel.LOW, description="Risk level of the tool")
    
    # Input schema - subclasses should define their specific fields
    # Example: class InputSchema(BaseModel): path: str = Field(...)
    InputSchema: Type[BaseModel] = Field(default=None, description="Pydantic model for input validation")
    
    def __init__(self):
        if self.InputSchema is None:
            raise NotImplementedError("Subclasses must define InputSchema")
    
    @abc.abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool-specific parameters matching InputSchema
            
        Returns:
            ToolResult: Standardized result object
        """
        pass
    
    def validate_input(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input against the tool's schema.
        
        Args:
            input_data: Raw input data
            
        Returns:
            Dict[str, Any]: Validated input data
            
        Raises:
            ValueError: If input validation fails
        """
        try:
            validated = self.InputSchema(**input_data)
            return validated.dict()
        except Exception as e:
            logger.error(f"Input validation failed for tool {self.name}: {e}")
            raise ValueError(f"Invalid input for tool {self.name}: {str(e)}")
    
    async def __call__(self, **kwargs) -> ToolResult:
        """Make the tool callable directly.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult: Tool execution result
        """
        # Validate input
        validated_input = self.validate_input(kwargs)
        
        # Execute tool
        try:
            result = await self.execute(**validated_input)
            return result
        except Exception as e:
            logger.exception(f"Tool execution failed for {self.name}")
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
                metadata={"tool": self.name, "input": kwargs}
            )
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM tool calling.
        
        Returns:
            Dict[str, Any]: Tool definition in OpenAI function calling format
        """
        # Convert Pydantic model to JSON schema
        schema = self.InputSchema.schema()
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema
            }
        }
    
    def get_risk_explanation(self) -> str:
        """Get an explanation of why this tool has its risk level.
        
        Returns:
            str: Explanation of the risk level
        """
        # Default explanations - subclasses can override
        explanations = {
            ToolRiskLevel.LOW: "This tool performs read-only operations or safe modifications.",
            ToolRiskLevel.MEDIUM: "This tool can modify files or system state but with limited scope.",
            ToolRiskLevel.HIGH: "This tool can make significant changes to the system or execute arbitrary code."
        }
        return explanations.get(self.risk_level, "Risk level not specified.")


# Example implementation - a simple echo tool
class EchoInput(BaseModel):
    message: str = Field(..., description="Message to echo back")


class EchoTool(BaseTool):
    """Example tool that echoes back a message."""
    
    name = "echo"
    description = "Echoes back the provided message"
    risk_level = ToolRiskLevel.LOW  # Echo tool is low risk
    InputSchema = EchoInput
    
    async def execute(self, message: str) -> ToolResult:
        """Echo the provided message."""
        return ToolResult(
            success=True,
            output=message,
            metadata={"echo_length": len(message)}
        )


# Tool registry for easy access
TOOL_REGISTRY: Dict[str, Type[BaseTool]] = {}


def register_tool(tool_class: Type[BaseTool]):
    """Register a tool class in the global registry.
    
    Args:
        tool_class: Tool class to register (must inherit from BaseTool)
    """
    if not issubclass(tool_class, BaseTool):
        raise ValueError("Registered tool must inherit from BaseTool")
    
    tool_instance = tool_class()
    TOOL_REGISTRY[tool_instance.name] = tool_class
    logger.info(f"Registered tool: {tool_instance.name} (risk: {tool_instance.risk_level.value})")


def get_tool(name: str) -> Optional[Type[BaseTool]]:
    """Get a tool class by name from the registry.
    
    Args:
        name: Tool name
        
    Returns:
        Type[BaseTool]: Tool class if found, None otherwise
    """
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[str]:
    """List all registered tool names.
    
    Returns:
        list[str]: List of tool names
    """
    return list(TOOL_REGISTRY.keys())


def get_tool_definitions() -> list[Dict[str, Any]]:
    """Get tool definitions for all registered tools.
    
    Returns:
        list[Dict[str, Any]]: List of tool definitions for LLM tool calling
    """
    definitions = []
    for tool_name, tool_class in TOOL_REGISTRY.items():
        try:
            tool_instance = tool_class()
            definitions.append(tool_instance.get_tool_definition())
        except Exception as e:
            logger.error(f"Failed to get definition for tool {tool_name}: {e}")
    
    return definitions


def get_tools_by_risk_level(risk_level: ToolRiskLevel) -> list[Type[BaseTool]]:
    """Get all tools of a specific risk level.
    
    Args:
        risk_level: The risk level to filter by
        
    Returns:
        list[Type[BaseTool]]: List of tool classes with the specified risk level
    """
    return [
        tool_class for tool_class in TOOL_REGISTRY.values()
        if tool_class().risk_level == risk_level
    ]


# Auto-register example tool
register_tool(EchoTool)