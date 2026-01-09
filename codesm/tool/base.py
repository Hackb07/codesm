"""Base tool interface"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel


def load_tool_description(tool_name: str) -> Optional[str]:
    """Load tool description from .txt file if it exists."""
    txt_path = Path(__file__).parent / f"{tool_name}.txt"
    if txt_path.exists():
        return txt_path.read_text().strip()
    return None


class Tool(ABC):
    name: str
    description: str
    
    def __init__(self):
        # Load description from .txt file if available
        txt_description = load_tool_description(self.name)
        if txt_description:
            self.description = txt_description
    
    @abstractmethod
    def get_parameters_schema(self) -> dict:
        """Return JSON schema for parameters"""
        pass
    
    @abstractmethod
    async def execute(self, args: dict, context: dict) -> str:
        """Execute the tool and return result"""
        pass
