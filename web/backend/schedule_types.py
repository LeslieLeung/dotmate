"""Web-facing metadata and validation for schedule types."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import ValidationError
from pydantic_core import PydanticUndefined

from dotmate.view.factory import ViewFactory


@dataclass(frozen=True)
class ScheduleTypeMetadata:
    label: str
    description: str
    summary_fields: tuple[str, ...] = ()
    web_editable: bool = True
    field_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)


COMMON_FIELD_OVERRIDES: dict[str, dict[str, Any]] = {
    "link": {
        "label": "Link URL",
        "description": "Open this URL when the device content is tapped.",
        "input": "url",
        "section": "display",
    },
    "border": {
        "label": "Border",
        "description": "Choose the e-ink screen border color.",
        "input": "select",
        "section": "display",
        "options": [
            {"value": 0, "label": "White"},
            {"value": 1, "label": "Black"},
        ],
    },
    "dither_type": {
        "label": "Dither Type",
        "description": "Controls how the image is converted for the e-ink display.",
        "input": "select",
        "section": "display",
    },
    "dither_kernel": {
        "label": "Dither Kernel",
        "description": "Fine-tunes diffusion when dithering is enabled.",
        "input": "select",
        "section": "display",
    },
    "task_key": {
        "label": "Task Key",
        "description": "Update a specific existing device task.",
        "section": "advanced",
    },
    "task_alias": {
        "label": "Task Alias",
        "description": "Optional alias for the device task.",
        "section": "advanced",
    },
    "styles": {
        "label": "Text Styles",
        "description": "Existing structured styles are preserved but are not editable yet.",
        "section": "advanced",
        "hidden": True,
    },
}


SCHEDULE_TYPE_METADATA: dict[str, ScheduleTypeMetadata] = {
    "work": ScheduleTypeMetadata(
        label="Work Countdown",
        description="Show the remaining time in a configured work day.",
        summary_fields=("clock_in", "clock_out"),
        field_overrides={
            "clock_in": {"label": "Clock In", "input": "time"},
            "clock_out": {"label": "Clock Out", "input": "time"},
        },
    ),
    "text": ScheduleTypeMetadata(
        label="Text Message",
        description="Send a custom title, message, and optional signature.",
        summary_fields=("message", "title"),
        field_overrides={
            "message": {"label": "Message", "input": "textarea"},
            "title": {"label": "Title"},
            "signature": {"label": "Signature"},
            "icon": {
                "label": "Icon",
                "description": "A public image URL or PNG Base64 value.",
            },
        },
    ),
    "code_status": ScheduleTypeMetadata(
        label="WakaTime Coding Status",
        description="Display today's coding time and top languages from WakaTime.",
        summary_fields=("wakatime_user_id", "wakatime_url"),
        field_overrides={
            "wakatime_url": {"label": "WakaTime URL", "input": "url"},
            "wakatime_api_key": {
                "label": "WakaTime API Key",
                "input": "password",
                "sensitive": True,
            },
            "wakatime_user_id": {"label": "WakaTime User ID"},
        },
    ),
    "image": ScheduleTypeMetadata(
        label="Raw Image",
        description="Raw image schedules are not editable in the web admin yet.",
        web_editable=False,
    ),
    "title_image": ScheduleTypeMetadata(
        label="Title Card",
        description="Generate an e-ink image from a main title and subtitle.",
        summary_fields=("main_title", "sub_title"),
        field_overrides={
            "main_title": {"label": "Main Title"},
            "sub_title": {"label": "Subtitle"},
        },
    ),
    "umami_stats": ScheduleTypeMetadata(
        label="Umami Analytics",
        description="Display traffic metrics from an Umami website.",
        summary_fields=("title", "umami_time_range"),
        field_overrides={
            "umami_host": {"label": "Umami Host", "input": "url"},
            "umami_website_id": {"label": "Website ID"},
            "umami_api_key": {
                "label": "Umami API Key",
                "input": "password",
                "sensitive": True,
            },
            "umami_time_range": {
                "label": "Time Range",
                "description": "Examples: 24h, 7d, or 4w.",
            },
            "title": {"label": "Custom Title"},
        },
    ),
    "github_contributions": ScheduleTypeMetadata(
        label="GitHub Contributions",
        description="Show contribution activity and repository statistics.",
        summary_fields=("github_username",),
        field_overrides={
            "github_username": {"label": "GitHub Username"},
            "github_token": {
                "label": "GitHub Token",
                "input": "password",
                "sensitive": True,
            },
        },
    ),
    "code_plan_usage": ScheduleTypeMetadata(
        label="Code Plan Usage",
        description="Display quota utilization from an OnWatch-compatible API.",
        summary_fields=("provider", "api_url"),
        field_overrides={
            "api_url": {"label": "API URL", "input": "url"},
            "provider": {"label": "Provider"},
            "api_username": {"label": "API Username"},
            "api_password": {
                "label": "API Password",
                "input": "password",
                "sensitive": True,
            },
        },
    ),
}


def get_type_metadata(type_name: str) -> ScheduleTypeMetadata | None:
    return SCHEDULE_TYPE_METADATA.get(type_name)


def get_type_label(type_name: str) -> str:
    metadata = get_type_metadata(type_name)
    return metadata.label if metadata else type_name.replace("_", " ").title()


def is_web_editable(type_name: str) -> bool:
    metadata = get_type_metadata(type_name)
    return bool(metadata and metadata.web_editable)


def _without_none(annotation: Any) -> tuple[Any, ...]:
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return tuple(arg for arg in get_args(annotation) if arg is not type(None))
    return (annotation,)


def _field_type(annotation: Any) -> str:
    annotations = _without_none(annotation)
    if len(annotations) != 1:
        return "string"
    annotation = annotations[0]
    origin = get_origin(annotation)
    if origin is Literal:
        values = get_args(annotation)
        if values and all(isinstance(value, bool) for value in values):
            return "boolean"
        if values and all(isinstance(value, int) for value in values):
            return "integer"
        if values and all(isinstance(value, (int, float)) for value in values):
            return "number"
        return "string"
    if annotation is bool:
        return "boolean"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is bytes:
        return "bytes"
    if isinstance(annotation, type) and hasattr(annotation, "model_fields"):
        return "object"
    return "string"


def _literal_options(annotation: Any) -> list[dict[str, Any]] | None:
    annotations = _without_none(annotation)
    if len(annotations) != 1 or get_origin(annotations[0]) is not Literal:
        return None
    return [
        {"value": value, "label": str(value).replace("_", " ").title()}
        for value in get_args(annotations[0])
    ]


def _field_label(field_name: str) -> str:
    return field_name.replace("_", " ").title()


def get_schedule_type_schema() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for type_name in ViewFactory.get_available_types():
        metadata = get_type_metadata(type_name)
        if not metadata or not metadata.web_editable:
            continue

        params_class = ViewFactory.get_params_class(type_name)
        fields: dict[str, dict[str, Any]] = {}
        for field_name, field_info in params_class.model_fields.items():
            override = {
                **COMMON_FIELD_OVERRIDES.get(field_name, {}),
                **metadata.field_overrides.get(field_name, {}),
            }
            descriptor: dict[str, Any] = {
                "type": _field_type(field_info.annotation),
                "label": override.pop("label", _field_label(field_name)),
                "required": field_info.is_required(),
                "input": override.pop("input", "text"),
                "section": override.pop("section", "main"),
                "sensitive": override.pop("sensitive", False),
                "hidden": override.pop("hidden", False),
            }
            if field_info.description:
                descriptor["description"] = field_info.description
            options = override.pop("options", None) or _literal_options(
                field_info.annotation
            )
            if options:
                descriptor["options"] = options
                descriptor["input"] = "select"
            if field_info.default is not PydanticUndefined:
                descriptor["default"] = field_info.default
            descriptor.update(override)
            fields[field_name] = descriptor

        result[type_name] = {
            "label": metadata.label,
            "description": metadata.description,
            "fields": fields,
        }
    return result


def validate_params(type_name: str, params: dict[str, Any] | None) -> dict[str, Any]:
    params_class = ViewFactory.get_params_class(type_name)
    validated = params_class.model_validate(params or {})
    return validated.model_dump(mode="json", exclude_none=True)


def validation_errors(exc: ValidationError) -> dict[str, str]:
    errors: dict[str, str] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        errors[location or "params"] = error["msg"]
    return errors


def build_summary(
    type_name: str, params: dict[str, Any] | None
) -> list[dict[str, str]]:
    metadata = get_type_metadata(type_name)
    if not metadata or not params:
        return []

    fields = get_schedule_type_schema().get(type_name, {}).get("fields", {})
    summary: list[dict[str, str]] = []
    for field_name in metadata.summary_fields:
        field_schema = fields.get(field_name, {})
        if field_schema.get("sensitive"):
            continue
        value = params.get(field_name)
        if value in (None, ""):
            continue
        rendered = str(value).replace("\n", " ")
        if len(rendered) > 64:
            rendered = f"{rendered[:61]}..."
        summary.append(
            {
                "label": field_schema.get("label", _field_label(field_name)),
                "value": rendered,
            }
        )
        if len(summary) == 2:
            break
    return summary
