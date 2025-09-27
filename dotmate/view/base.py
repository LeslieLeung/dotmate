from abc import ABC, abstractmethod
from typing import Any, Dict, Type
from pydantic import BaseModel
from dotmate.api.api import DotClient


class BaseView(ABC):
    """Base class for all view handlers."""

    def __init__(self, client: DotClient, device_id: str):
        self.client = client
        self.device_id = device_id

    @classmethod
    @abstractmethod
    def get_params_class(cls) -> Type[BaseModel]:
        """Return the parameters class for this view."""
        pass

    @classmethod
    def create_params_from_dict(cls, params_dict: Dict[str, Any]) -> BaseModel:
        """Create parameters object from dictionary."""
        params_class = cls.get_params_class()
        return params_class(**params_dict)

    @abstractmethod
    def execute(self, params: BaseModel) -> None:
        """Execute the view with given parameters."""
        pass