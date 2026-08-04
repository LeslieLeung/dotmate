from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, Type
from pydantic import BaseModel

from dotmate.platforms.base import PlatformClient


class BaseView(ABC):
    """Base class for all view handlers.

    Class attribute ``requires_text`` declares whether a view needs the text
    display capability. The config validator uses this to reject text-based
    scenarios on image-only platforms at load time.
    """

    requires_text: ClassVar[bool] = False

    def __init__(self, client: PlatformClient, device_id: str):
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
