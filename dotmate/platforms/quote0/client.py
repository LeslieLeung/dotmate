"""Quote/0 cloud API client (dot.mindreset.tech).

Translates vendor-neutral payloads into the Quote/0 JSON wire format
(base64-encoded image data, Bearer auth).
"""

import base64
import logging
import threading
import time
from typing import List

import requests

from dotmate.platforms.base import (
    ApiResponse,
    DeviceStatus,
    ImagePayload,
    PlatformClient,
    TextPayload,
)
from dotmate.platforms.quote0.models import (
    DeviceTask,
    DisplayImageRequest,
    DisplayTextRequest,
    TextStyles,
)

logger = logging.getLogger(__name__)


class DotClient(PlatformClient):
    """Client for the Quote/0 platform."""

    def __init__(self, api_key: str, request_interval: float = 1.0):
        self.api_key = api_key
        self.base_url = "https://dot.mindreset.tech/api/authV2/open/device"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
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

    def _handle_response(self, response: requests.Response) -> ApiResponse:
        response.encoding = "utf-8"
        if not response.ok:
            logger.error(
                f"API request failed with status {response.status_code}: {response.text}"
            )
            response.raise_for_status()
        try:
            response_data = response.json()
            logger.debug(f"API response: {response_data}")
            return ApiResponse.model_validate(response_data)
        except requests.exceptions.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON response. Status: {response.status_code}, Body: {response.text}"
            )
            raise ValueError(f"Invalid JSON response from API: {response.text}") from e

    # -- image -------------------------------------------------------------- #
    def display_image(self, device_id: str, payload: ImagePayload) -> ApiResponse:
        request = DisplayImageRequest(
            refreshNow=payload.refresh_now,
            image=base64.b64encode(payload.image_bytes).decode("utf-8"),
            link=payload.link,
            border=payload.border,
            ditherType=payload.dither_type,
            ditherKernel=payload.dither_kernel,  # type: ignore[arg-type]
            taskKey=payload.task_key,
            taskAlias=payload.task_alias,
        )
        url = f"{self.base_url}/{device_id}/image"
        log_data = {
            k: (v if k != "image" else f"<base64 data, length: {len(v)}>")
            for k, v in request.model_dump(exclude_none=True).items()
        }
        logger.info(f"Sending image display request to {url}")
        logger.info(f"Request parameters: {log_data}")
        response = self._rate_limited_request(
            "POST", url, json=request.model_dump(exclude_none=True), headers=self.headers
        )
        return self._handle_response(response)

    # -- text --------------------------------------------------------------- #
    def display_text(self, device_id: str, payload: TextPayload) -> ApiResponse:
        styles = None
        if payload.styles is not None:
            styles = TextStyles.model_validate(payload.styles)
        request = DisplayTextRequest(
            refreshNow=payload.refresh_now,
            title=payload.title,
            message=payload.message,
            signature=payload.signature,
            icon=payload.icon,
            link=payload.link,
            taskKey=payload.task_key,
            taskAlias=payload.task_alias,
            styles=styles,
        )
        url = f"{self.base_url}/{device_id}/text"
        logger.info(f"Sending text display request to {url}")
        logger.info(f"Request parameters: {request.model_dump(exclude_none=True)}")
        response = self._rate_limited_request(
            "POST", url, json=request.model_dump(exclude_none=True), headers=self.headers
        )
        return self._handle_response(response)

    # -- status / extras (Quote/0 specific) --------------------------------- #
    def get_device_status(self, device_id: str) -> DeviceStatus:
        url = f"{self.base_url}/{device_id}/status"
        logger.info(f"Getting device status from {url}")
        response = self._rate_limited_request("GET", url, headers=self.headers)
        response.encoding = "utf-8"
        if not response.ok:
            logger.error(
                f"API request failed with status {response.status_code}: {response.text}"
            )
            response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Device status response: {response_data}")
        return DeviceStatus.model_validate(response_data)

    def switch_next_content(self, device_id: str) -> ApiResponse:
        url = f"{self.base_url}/{device_id}/next"
        logger.info(f"Switching to next content for device {device_id}")
        response = self._rate_limited_request("POST", url, headers=self.headers)
        return self._handle_response(response)

    def list_device_content(self, device_id: str, task_type: str = "loop") -> List[DeviceTask]:
        url = f"{self.base_url}/{device_id}/{task_type}/list"
        logger.info(f"Listing device content from {url}")
        response = self._rate_limited_request("GET", url, headers=self.headers)
        response.encoding = "utf-8"
        if not response.ok:
            logger.error(
                f"API request failed with status {response.status_code}: {response.text}"
            )
            response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Device content list response: {response_data}")
        return [DeviceTask.model_validate(item) for item in response_data]
