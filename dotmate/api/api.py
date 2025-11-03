import requests
import logging
from pydantic import BaseModel, Field
from typing import Literal, Optional

logger = logging.getLogger(__name__)

class DisplayTextRequest(BaseModel):
    refreshNow: bool = Field(..., description="是否立刻显示内容")
    deviceId: str = Field(..., description="设备序列号")
    title: Optional[str] = Field(None, description="标题")
    message: str = Field(..., description="内容")
    signature: Optional[str] = Field(None, description="签名")
    icon: Optional[str] = Field(None, description="base64 编码 PNG 图标数据")
    link: Optional[str] = Field(None, description="碰一碰跳转链接")


class DisplayImageRequest(BaseModel):
    refreshNow: bool = Field(..., description="是否立刻显示内容")
    deviceId: str = Field(..., description="设备序列号")
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
            "DIFFUSION2_D",
        ]
    ] = Field(None, description="抖动算法")

class ApiResponse(BaseModel):
    message: str


class DotClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dot.mindreset.tech/api/open"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _handle_response(self, response: requests.Response) -> "ApiResponse":
        """Unified response handling with error checking and JSON parsing."""
        # Ensure UTF-8 encoding for proper Chinese character display
        response.encoding = "utf-8"

        # Check response status
        if not response.ok:
            logger.error(
                f"API request failed with status {response.status_code}: {response.text}"
            )
            response.raise_for_status()

        # Try to parse JSON response
        try:
            response_data = response.json()
            logger.debug(f"API response: {response_data}")
            return ApiResponse.model_validate(response_data)
        except requests.exceptions.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON response. Status: {response.status_code}, Body: {response.text}"
            )
            raise ValueError(f"Invalid JSON response from API: {response.text}") from e

    def display_text(self, payload: DisplayTextRequest) -> "ApiResponse":
        url = f"{self.base_url}/text"
        request_data = payload.model_dump(exclude_none=True)
        logger.info(f"Sending text display request to {url}")
        logger.info(f"Request parameters: {request_data}")
        response = requests.post(url, json=request_data, headers=self.headers)
        return self._handle_response(response)

    def display_image(self, payload: DisplayImageRequest) -> "ApiResponse":
        url = f"{self.base_url}/image"
        request_data = payload.model_dump(exclude_none=True)
        # Log request without the full base64 image data for readability
        log_data = {
            k: v if k != "image" else f"<base64 data, length: {len(v)}>"
            for k, v in request_data.items()
        }
        logger.info(f"Sending image display request to {url}")
        logger.info(f"Request parameters: {log_data}")
        response = requests.post(url, json=request_data, headers=self.headers)
        return self._handle_response(response)
