"""Web-facing metadata and validation for schedule types."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import ValidationError
from pydantic_core import PydanticUndefined

from dotmate.view.factory import ViewFactory
from web.backend.device_models import DeviceModelDefinition, get_device_model


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
    "page_id": {
        "label": "Page",
        "description": "Note 4 page slot (1–5).",
        "input": "select",
        "section": "display",
        "options": [
            {"value": 1, "label": "Page 1"},
            {"value": 2, "label": "Page 2"},
            {"value": 3, "label": "Page 3"},
            {"value": 4, "label": "Page 4"},
            {"value": 5, "label": "Page 5"},
        ],
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
        summary_fields=("clock_in", "clock_out", "page_id"),
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
        summary_fields=("wakatime_user_id", "wakatime_url", "page_id"),
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
        summary_fields=("main_title", "sub_title", "page_id"),
        field_overrides={
            "main_title": {"label": "Main Title"},
            "sub_title": {"label": "Subtitle"},
        },
    ),
    "umami_stats": ScheduleTypeMetadata(
        label="Umami Analytics",
        description="Display traffic metrics from an Umami website.",
        summary_fields=("title", "umami_time_range", "page_id"),
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
        summary_fields=("github_username", "page_id"),
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
        summary_fields=("provider", "api_url", "page_id"),
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

# Image protocol fields that may be filtered by device model.
_IMAGE_PROTOCOL_FIELDS = frozenset(
    {
        "link",
        "border",
        "dither_type",
        "dither_kernel",
        "task_key",
        "task_alias",
        "page_id",
    }
)


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


def _apply_model_field_rules(
    field_name: str,
    descriptor: dict[str, Any],
    model: DeviceModelDefinition | None,
) -> dict[str, Any] | None:
    """Filter or adapt a field for a specific device model.

    Returns ``None`` when the field must be omitted from the schema.
    """
    if model is None:
        # Global schema: hide Note 4-only page_id so Quote/0 forms stay clean.
        if field_name == "page_id":
            return None
        return descriptor

    if field_name in _IMAGE_PROTOCOL_FIELDS:
        if field_name not in model.allowed_image_fields:
            return None

    if field_name == "dither_type" and model.id == "note4":
        descriptor = {
            **descriptor,
            "label": "Dithering",
            "description": "Enable or disable dithering for Note 4.",
            "options": [
                {"value": "DIFFUSION", "label": "Enabled"},
                {"value": "NONE", "label": "Disabled"},
            ],
            "input": "select",
        }

    if field_name == "page_id" and model.supports_page_id:
        descriptor = {
            **descriptor,
            **COMMON_FIELD_OVERRIDES["page_id"],
        }

    return descriptor


def get_schedule_type_schema(
    device_model: str | DeviceModelDefinition | None = None,
) -> dict[str, dict[str, Any]]:
    model: DeviceModelDefinition | None
    if isinstance(device_model, DeviceModelDefinition):
        model = device_model
    elif isinstance(device_model, str):
        model = get_device_model(device_model)
    else:
        model = None

    result: dict[str, dict[str, Any]] = {}
    for type_name in ViewFactory.get_available_types():
        metadata = get_type_metadata(type_name)
        if not metadata or not metadata.web_editable:
            continue

        if model is not None and ViewFactory.requires_text(type_name):
            if not model.supports_text:
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

            filtered = _apply_model_field_rules(field_name, descriptor, model)
            if filtered is not None:
                fields[field_name] = filtered

        result[type_name] = {
            "label": metadata.label,
            "description": metadata.description,
            "fields": fields,
        }
    return result


def unsupported_param_errors(
    type_name: str,
    params: dict[str, Any] | None,
    device_model: str | DeviceModelDefinition,
) -> dict[str, str]:
    """Return field errors for params that the device model cannot accept.

    Unsupported optional image-protocol fields are sanitized away rather than
    rejected so legacy Quote/0 params can be cleared when saving for Note 4.
    """
    model = (
        device_model
        if isinstance(device_model, DeviceModelDefinition)
        else get_device_model(device_model)
    )
    if ViewFactory.requires_text(type_name) and not model.supports_text:
        return {
            "type": (
                f"{model.label} does not support text schedules. "
                "Choose an image-based schedule type."
            )
        }

    errors: dict[str, str] = {}
    raw = params or {}
    if model.supports_page_id and "page_id" in raw and raw["page_id"] not in (None, ""):
        try:
            page = int(raw["page_id"])
        except (TypeError, ValueError):
            errors["page_id"] = "Page must be an integer from 1 to 5"
        else:
            if page < 1 or page > 5:
                errors["page_id"] = "Page must be an integer from 1 to 5"
    if model.id == "note4" and raw.get("dither_type") not in (
        None,
        "",
        "DIFFUSION",
        "NONE",
        "ORDERED",
    ):
        errors["dither_type"] = "Choose Enabled or Disabled dithering"
    return errors


def sanitize_params_for_model(
    type_name: str,
    params: dict[str, Any],
    device_model: str | DeviceModelDefinition,
) -> dict[str, Any]:
    """Drop unsupported image protocol fields before persistence/execution."""
    model = (
        device_model
        if isinstance(device_model, DeviceModelDefinition)
        else get_device_model(device_model)
    )
    cleaned = dict(params)
    for field_name in list(cleaned):
        if (
            field_name in _IMAGE_PROTOCOL_FIELDS
            and field_name not in model.allowed_image_fields
        ):
            cleaned.pop(field_name, None)
    if model.id == "note4" and cleaned.get("dither_type") == "ORDERED":
        cleaned["dither_type"] = "DIFFUSION"
    return cleaned


def validate_params(type_name: str, params: dict[str, Any] | None) -> dict[str, Any]:
    params_class = ViewFactory.get_params_class(type_name)
    validated = params_class.model_validate(params or {})
    return validated.model_dump(mode="json", exclude_none=True)


def validate_params_for_device(
    type_name: str,
    params: dict[str, Any] | None,
    device_model: str | DeviceModelDefinition,
) -> dict[str, Any]:
    """Validate schedule params against both the view model and device model.

    Raises ``ValueError`` with a ``fields`` attribute (dict[str, str]) when the
    device model rejects the type or individual fields.
    """
    model_errors = unsupported_param_errors(type_name, params, device_model)
    if model_errors:
        error = ValueError("Schedule is not valid for this device model")
        error.fields = model_errors  # type: ignore[attr-defined]
        raise error
    cleaned = sanitize_params_for_model(type_name, params or {}, device_model)
    return validate_params(type_name, cleaned)


def validation_errors(exc: ValidationError) -> dict[str, str]:
    errors: dict[str, str] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        errors[location or "params"] = error["msg"]
    return errors


def build_summary(
    type_name: str,
    params: dict[str, Any] | None,
    device_model: str | DeviceModelDefinition | None = None,
) -> list[dict[str, str]]:
    metadata = get_type_metadata(type_name)
    if not metadata or not params:
        return []

    fields = get_schedule_type_schema(device_model).get(type_name, {}).get("fields", {})
    summary: list[dict[str, str]] = []
    for field_name in metadata.summary_fields:
        if field_name in _IMAGE_PROTOCOL_FIELDS and field_name not in fields:
            continue
        field_schema = fields.get(field_name, {})
        if field_schema.get("sensitive"):
            continue
        value = params.get(field_name)
        if value in (None, ""):
            continue
        if field_name == "page_id":
            rendered = f"Page {value}"
        else:
            rendered = str(value).replace("\n", " ")
            if len(rendered) > 64:
                rendered = f"{rendered[:61]}..."
        summary.append(
            {
                "label": field_schema.get("label", _field_label(field_name)),
                "value": rendered,
            }
        )
        if len(summary) >= 3:
            break
    return summary
