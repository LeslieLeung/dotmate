"""Zectrix (Note 4) cloud API client.

Supports image push and device discovery.

Translates vendor-neutral payloads into the Zectrix multipart wire format
(X-API-Key auth, raw image file upload, boolean dither, optional pageId).

API docs: https://wiki.zectrix.com/zh/software/api-docs
Base URL: https://cloud.zectrix.com/open/v1
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, List, Union

import requests

from dotmate.platforms.base import (
    ApiResponse,
    DeviceStatus,
    ImagePayload,
    PlatformClient,
    RemoteDevice,
)
from dotmate.platforms.zectrix.models import ZectrixDeviceItem, ZectrixImageRequest

logger = logging.getLogger(__name__)


class ZectrixClient(PlatformClient):
    """Client for Zectrix Note 4 open API (image display + device list)."""

    def __init__(self, api_key: str, request_interval: float = 1.0):
        self.api_key = api_key
        self.base_url = "https://cloud.zectrix.com/open/v1"
        self.headers = {
            "X-API-Key": self.api_key,
        }
        self._request_interval = request_interval
        self._last_request_time: float = 0.0
        self._lock = threading.Lock()

    def _rate_limited_request(self, method: str, url: str, **kwargs) -> requests.Response:
        with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            wait = self._request_interval - elapsed
            if wait > 0:
                time.sleep(wait)
            response = requests.request(method, url, **kwargs)
            self._last_request_time = time.monotonic()
        return response

    def _parse_envelope(self, response: requests.Response) -> tuple[Any, str]:
        """Parse Zectrix unified {code, data, msg} response.

        Returns ``(data, message)``. Raises on HTTP or API-level errors.
        """
        response.encoding = "utf-8"
        if not response.ok:
            logger.error(
                f"Zectrix API request failed with status {response.status_code}: {response.text}"
            )
            response.raise_for_status()

        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON response. Status: {response.status_code}, Body: {response.text}"
            )
            raise ValueError(f"Invalid JSON response from Zectrix API: {response.text}") from e

        logger.debug(f"Zectrix API response: {response_data}")
        code = response_data.get("code", -1)
        msg = response_data.get("msg") or response_data.get("message") or ""
        if code != 0:
            error_msg = msg or f"Zectrix API error code {code}"
            logger.error(f"Zectrix API returned error: {error_msg}")
            raise ValueError(error_msg)

        return response_data.get("data"), msg

    def _handle_response(self, response: requests.Response) -> ApiResponse:
        """Parse Zectrix unified response into ApiResponse."""
        data, msg = self._parse_envelope(response)
        if not msg:
            msg = f"success: {data}" if data is not None else "success"
        return ApiResponse(message=str(msg))

    @staticmethod
    def _resolve_page_id(payload: ImagePayload) -> Union[str, None]:
        """Resolve the page slot (1-5) from a neutral payload."""
        if payload.page_id is not None:
            return str(payload.page_id)
        if payload.task_key is not None:
            return str(payload.task_key)
        if payload.task_alias is not None:
            return str(payload.task_alias)
        return None

    @staticmethod
    def _resolve_dither(payload: ImagePayload) -> bool:
        """Map dither_type to Zectrix boolean dither (default True)."""
        if payload.dither_type is None:
            return True
        return payload.dither_type != "NONE"

    def list_devices(self) -> List[RemoteDevice]:
        """List devices bound to this API key.

        Endpoint: GET /devices
        Response data: [{deviceId, alias, board}, ...]
        """
        url = f"{self.base_url}/devices"
        logger.info(f"Listing Zectrix devices from {url}")
        response = self._rate_limited_request("GET", url, headers=self.headers)
        data, _ = self._parse_envelope(response)
        if data is None:
            return []
        if not isinstance(data, list):
            raise ValueError("Zectrix devices response must be a list")

        devices: List[RemoteDevice] = []
        for item in data:
            parsed = ZectrixDeviceItem.model_validate(item)
            device_id = parsed.device_id.strip()
            if not device_id:
                continue
            devices.append(
                RemoteDevice(
                    id=device_id,
                    alias=parsed.alias,
                    model=parsed.board,
                    series="zectrix",
                )
            )
        return devices

    def display_image(self, device_id: str, payload: ImagePayload) -> ApiResponse:
        """Push image via multipart form to Zectrix Note 4.

        Endpoint: POST /devices/{deviceId}/display/image
        Fields: images (file), dither (bool), pageId (optional)
        """
        request = ZectrixImageRequest(
            image_bytes=payload.image_bytes,
            dither=self._resolve_dither(payload),
            page_id=self._resolve_page_id(payload),
        )
        url = f"{self.base_url}/devices/{device_id}/display/image"
        files = {
            "images": ("image.png", request.image_bytes, "image/png"),
        }
        data: dict[str, str] = {"dither": "true" if request.dither else "false"}
        if request.page_id is not None:
            data["pageId"] = request.page_id

        logger.info(f"Sending Zectrix image display request to {url}")
        logger.info(
            f"Request parameters: dither={request.dither}, pageId={request.page_id}, "
            f"image_size={len(request.image_bytes)} bytes"
        )
        response = self._rate_limited_request(
            "POST", url, headers=self.headers, files=files, data=data
        )
        return self._handle_response(response)

    def get_device_status(self, device_id: str) -> DeviceStatus:
        """Zectrix open API does not expose battery/status; return a stub."""
        logger.debug(f"get_device_status not available for Zectrix device {device_id}")
        return DeviceStatus(deviceId=device_id, status={}, renderInfo={})
