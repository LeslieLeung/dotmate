import requests
import logging
from pydantic import BaseModel, Field
from typing import Literal, Optional, List

logger = logging.getLogger(__name__)

class DisplayTextRequest(BaseModel):
    refreshNow: bool = Field(..., description="是否立刻显示内容")
    title: Optional[str] = Field(None, description="标题")
    message: str = Field(..., description="内容")
    signature: Optional[str] = Field(None, description="签名")
    icon: Optional[str] = Field(None, description="base64 编码 PNG 图标数据")
    link: Optional[str] = Field(None, description="碰一碰跳转链接")
    taskKey: Optional[str] = Field(None, description="指定更新哪个 Text API 内容")


class DisplayImageRequest(BaseModel):
    refreshNow: bool = Field(..., description="是否立刻显示内容")
    image: str = Field(..., description="base64 编码 PNG 图像数据")
    link: Optional[str] = Field(None, description="碰一碰跳转链接")
    border: Optional[int] = Field(None, description="屏幕边缘的颜色编号")
    ditherType: Optional[Literal["DIFFUSION", "ORDERED", "NONE"]] = Field(
        None, description="抖动类型"
    )
    ditherKernel: Optional[
        Literal[
            "THRESHOLD",
            "ATKINSON",
            "BURKES",
            "FLOYD_STEINBERG",
            "SIERRA2",
            "STUCKI",
            "JARVIS_JUDICE_NINKE",
            "DIFFUSION_ROW",
            "DIFFUSION_COLUMN",
            "DIFFUSION_2D",
        ]
    ] = Field(None, description="抖动算法")
    taskKey: Optional[str] = Field(None, description="指定更新哪个 Image API 内容")

class ApiResponse(BaseModel):
    message: str


class DeviceStatus(BaseModel):
    deviceId: str
    alias: Optional[str] = None
    location: Optional[str] = None
    status: dict
    renderInfo: dict


class DeviceTask(BaseModel):
    type: str
    key: Optional[str] = None
    refreshNow: Optional[bool] = None
    title: Optional[str] = None
    message: Optional[str] = None
    signature: Optional[str] = None
    icon: Optional[str] = None
    link: Optional[str] = None
    image: Optional[str] = None
    border: Optional[int] = None
    ditherType: Optional[str] = None
    ditherKernel: Optional[str] = None


class DotClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dot.mindreset.tech/api/authV2/open/device"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _handle_response(self, response: requests.Response) -> "ApiResponse":
        """Unified response handling with error checking and JSON parsing."""
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

    def display_text(self, device_id: str, payload: DisplayTextRequest) -> "ApiResponse":
        url = f"{self.base_url}/{device_id}/text"
        request_data = payload.model_dump(exclude_none=True)
        logger.info(f"Sending text display request to {url}")
        logger.info(f"Request parameters: {request_data}")
        response = requests.post(url, json=request_data, headers=self.headers)
        return self._handle_response(response)

    def display_image(self, device_id: str, payload: DisplayImageRequest) -> "ApiResponse":
        url = f"{self.base_url}/{device_id}/image"
        request_data = payload.model_dump(exclude_none=True)
        log_data = {
            k: v if k != "image" else f"<base64 data, length: {len(v)}>"
            for k, v in request_data.items()
        }
        logger.info(f"Sending image display request to {url}")
        logger.info(f"Request parameters: {log_data}")
        response = requests.post(url, json=request_data, headers=self.headers)
        return self._handle_response(response)

    def get_device_status(self, device_id: str) -> "DeviceStatus":
        url = f"{self.base_url}/{device_id}/status"
        logger.info(f"Getting device status from {url}")
        response = requests.get(url, headers=self.headers)
        response.encoding = "utf-8"

        if not response.ok:
            logger.error(
                f"API request failed with status {response.status_code}: {response.text}"
            )
            response.raise_for_status()

        response_data = response.json()
        logger.debug(f"Device status response: {response_data}")
        return DeviceStatus.model_validate(response_data)

    def switch_next_content(self, device_id: str) -> "ApiResponse":
        url = f"{self.base_url}/{device_id}/next"
        logger.info(f"Switching to next content for device {device_id}")
        response = requests.post(url, headers=self.headers)
        return self._handle_response(response)

    def list_device_content(self, device_id: str, task_type: str = "loop") -> List["DeviceTask"]:
        url = f"{self.base_url}/{device_id}/{task_type}/list"
        logger.info(f"Listing device content from {url}")
        response = requests.get(url, headers=self.headers)
        response.encoding = "utf-8"

        if not response.ok:
            logger.error(
                f"API request failed with status {response.status_code}: {response.text}"
            )
            response.raise_for_status()

        response_data = response.json()
        logger.debug(f"Device content list response: {response_data}")
        return [DeviceTask.model_validate(item) for item in response_data]
