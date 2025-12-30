"""Base tool interface"""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class Tool(ABC):
    name: str
    description: str
    
    @abstractmethod
    def get_parameters_schema(self) -> dict:
        """Return JSON schema for parameters"""
        pass
    
    @abstractmethod
    async def execute(self, args: dict, context: dict) -> str:
        """Execute the tool and return result"""
        pass
