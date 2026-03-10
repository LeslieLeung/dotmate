from typing import Dict, Type, Any
from dotmate.api.api import DotClient
from dotmate.view.base import BaseView
from dotmate.view.work import WorkView
from dotmate.view.text import TextView
from dotmate.view.code_status import CodeStatusView
from dotmate.view.image import ImageView
from dotmate.view.title_image import TitleImageView
from dotmate.view.umami_stats import UmamiStatsView
from dotmate.view.github_contributions import GitHubContributionsView
from dotmate.view.code_plan_usage import CodePlanUsageView


class ViewFactory:
    """Factory for creating view handlers."""

    _view_registry: Dict[str, Type[BaseView]] = {
        "work": WorkView,
        "text": TextView,
        "code_status": CodeStatusView,
        "image": ImageView,
        "title_image": TitleImageView,
        "umami_stats": UmamiStatsView,
        "github_contributions": GitHubContributionsView,
        "code_plan_usage": CodePlanUsageView,
    }

    @classmethod
    def create_view(cls, view_type: str, client: DotClient, device_id: str) -> BaseView:
        """Create a view handler for the given type."""
        if view_type not in cls._view_registry:
            raise ValueError(f"Unknown view type: {view_type}")

        view_class = cls._view_registry[view_type]
        return view_class(client, device_id)

    @classmethod
    def register_view(cls, view_type: str, view_class: Type[BaseView]) -> None:
        """Register a new view type."""
        cls._view_registry[view_type] = view_class

    @classmethod
    def get_available_types(cls) -> list[str]:
        """Get list of available view types."""
        return list(cls._view_registry.keys())

    @classmethod
    def execute_view(cls, view_type: str, client: DotClient, device_id: str, params: Any, overlay_settings: dict = None) -> None:
        """Create and execute a view in one call."""
        view = cls.create_view(view_type, client, device_id)

        if overlay_settings and isinstance(view, ImageView):
            view.show_battery_icon = overlay_settings.get("show_battery_icon", False)
            view.show_battery_percentage = overlay_settings.get("show_battery_percentage", False)
            view.show_refresh_time = overlay_settings.get("show_refresh_time", False)

        # If params is a dict, create proper params object
        if isinstance(params, dict):
            params_obj = view.create_params_from_dict(params)
        else:
            params_obj = params

        view.execute(params_obj)

    @classmethod
    def get_params_class(cls, view_type: str):
        """Get the params class for a specific view type."""
        if view_type not in cls._view_registry:
            raise ValueError(f"Unknown view type: {view_type}")

        view_class = cls._view_registry[view_type]
        return view_class.get_params_class()
