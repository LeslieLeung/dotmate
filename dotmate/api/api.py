import requests
import logging
import threading
import time
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Any, Literal, Optional, List, Union

logger = logging.getLogger(__name__)

TextFontFamily = Literal[
    "ChillDuanSans",
    "ChillKSans",
    "ChillOrganic",
    "ChillRoundF",
    "ChillRoundGothic",
    "Cusong16",
    "DotGothic16",
    "FusionPixel8",
    "FusionPixel10",
    "FusionPixel12",
    "Liusong24",
    "LogoSCUnboundedSans",
    "MaokenYingBiKaiShuJ0.09",
    "PlayfairDisplay",
    "Quan8",
    "Unifont16",
    "UnifontExMono16",
    "XiaoyaPixel12",
    "Zihunzhoukesong",
    "Zpix12",
]
TextFontWeight = Literal[100, 200, 300, 400, 500, 600, 700, 800, 900]


class TextStyle(BaseModel):
    fontFamily: Optional[TextFontFamily] = Field(None, description="文本字体")
    fontSize: Optional[float] = Field(None, description="字号")
    fontWeight: Optional[TextFontWeight] = Field(None, description="字重")


class MessageTextStyle(TextStyle):
    lineHeight: Optional[float] = Field(None, description="消息正文行高")


class TextStyles(BaseModel):
    title: Optional[TextStyle] = Field(None, description="标题样式")
    message: Optional[MessageTextStyle] = Field(None, description="正文样式")
    signature: Optional[TextStyle] = Field(None, description="签名样式")


class DisplayTextRequest(BaseModel):
    refreshNow: bool = Field(True, description="是否立刻显示内容")
    title: Optional[str] = Field(None, description="标题")
    message: Optional[str] = Field(None, description="内容，支持 \\n 换行和 \\t 制表符")
    signature: Optional[str] = Field(None, description="签名")
    icon: Optional[str] = Field(
        None, description="PNG Base64 图标数据或可匿名访问的 http(s) 图片 URL"
    )
    link: Optional[str] = Field(None, description="碰一碰跳转链接")
    taskKey: Optional[str] = Field(None, description="指定更新哪个 Text API 内容")
    taskAlias: Optional[Union[str, int]] = Field(None, description="Text API 内容别名")
    styles: Optional[TextStyles] = Field(None, description="标题、正文和签名的字体样式")


class DisplayImageRequest(BaseModel):
    refreshNow: bool = Field(..., description="是否立刻显示内容")
    image: str = Field(
        ..., description="PNG Base64 图像数据或可匿名访问的 http(s) 图片 URL"
    )
    link: Optional[str] = Field(None, description="碰一碰跳转链接")
    border: Optional[Literal[0, 1]] = Field(
        None, description="屏幕边框颜色：0 为白色，1 为黑色"
    )
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
    taskAlias: Optional[Union[str, int]] = Field(None, description="Image API 内容别名")


class ApiResponse(BaseModel):
    message: str


class RemoteDevice(BaseModel):
    alias: Optional[str] = None
    location: Optional[str] = None
    series: str
    model: str
    edition: int
    id: str


class DeviceIntervalSettings(BaseModel):
    powerMs: Optional[int] = None
    batteryMs: Optional[int] = None

    @field_validator("powerMs", "batteryMs")
    @classmethod
    def validate_interval(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value < 60_000 or value > 43_200_000 or value % 60_000:
            raise ValueError(
                "Interval must be 60,000-43,200,000 ms in one-minute steps"
            )
        return value


class DeviceSleepSettings(BaseModel):
    enabled: bool
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def validate_time(cls, value: str) -> str:
        try:
            hours, minutes = value.split(":")
            valid = (
                len(hours) == 2
                and len(minutes) == 2
                and 0 <= int(hours) <= 23
                and 0 <= int(minutes) <= 59
            )
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ValueError("Time must use HH:mm format")
        return value

    @model_validator(mode="after")
    def validate_range(self):
        if self.start == self.end:
            raise ValueError("Sleep start and end must be different")
        return self


class DeviceSettings(BaseModel):
    alias: Optional[str] = Field(default=None, max_length=100)
    location: Optional[str] = Field(default=None, max_length=100)
    timezone: Optional[str] = None
    interval: Optional[DeviceIntervalSettings] = None
    sleep: Optional[DeviceSleepSettings] = None


class DeviceSettingsUpdate(BaseModel):
    alias: Optional[str] = Field(default=None, max_length=100)
    location: Optional[str] = Field(default=None, max_length=100)
    timezone: Optional[str] = None
    interval: Optional[DeviceIntervalSettings] = None
    sleep: Optional[DeviceSleepSettings] = None


class TimezoneInfo(BaseModel):
    key: str
    name: str
    utcOffsetMinutes: int
    utcOffsetLabel: str


class DeviceRuntimeStatus(BaseModel):
    version: str = ""
    current: str = ""
    description: str = ""
    battery: str = ""
    wifi: str = ""


class DeviceRenderCurrent(BaseModel):
    rotated: bool = False
    border: int = 0
    image: Optional[list[str]] = None


class DeviceRenderNext(BaseModel):
    battery: str = ""
    power: str = ""


class DeviceRenderInfo(BaseModel):
    last: str = ""
    current: DeviceRenderCurrent = Field(default_factory=DeviceRenderCurrent)
    next: DeviceRenderNext = Field(default_factory=DeviceRenderNext)


class DeviceStatus(BaseModel):
    deviceId: str
    alias: Optional[str] = None
    location: Optional[str] = None
    status: DeviceRuntimeStatus = Field(default_factory=DeviceRuntimeStatus)
    renderInfo: DeviceRenderInfo = Field(default_factory=DeviceRenderInfo)


class DeviceTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    key: Optional[str] = None
    refreshNow: Optional[bool] = None
    title: Optional[str] = None
    message: Optional[str] = None
    signature: Optional[str] = None
    icon: Optional[Union[str, dict[str, Any]]] = None
    link: Optional[str] = None
    styles: Optional[TextStyles] = None
    image: Optional[Union[str, dict[str, Any]]] = None
    border: Optional[Literal[0, 1]] = None
    ditherType: Optional[str] = None
    ditherKernel: Optional[str] = None
    taskAlias: Optional[Union[str, int]] = None


class _SharedRateLimiter:
    """Serialize requests that use the same API credential."""

    def __init__(self):
        self.last_request_time = 0.0
        self.lock = threading.Lock()


class DotClient:
    _rate_limiters: dict[str, _SharedRateLimiter] = {}
    _rate_limiters_lock = threading.Lock()

    def __init__(self, api_key: str, request_interval: float = 1.0):
        self.api_key = api_key
        self.api_root = "https://dot.mindreset.tech/api/authV2/open"
        self.base_url = f"{self.api_root}/device"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self._request_interval = request_interval
        with self._rate_limiters_lock:
            self._rate_limiter = self._rate_limiters.setdefault(
                api_key, _SharedRateLimiter()
            )

    def _rate_limited_request(
        self, method: str, url: str, **kwargs
    ) -> requests.Response:
        with self._rate_limiter.lock:
            elapsed = time.monotonic() - self._rate_limiter.last_request_time
            wait = self._request_interval - elapsed
            if wait > 0:
                time.sleep(wait)
            kwargs.setdefault("timeout", 30)
            response = requests.request(method, url, **kwargs)
            self._rate_limiter.last_request_time = time.monotonic()
        return response

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

    def _json_response(self, response: requests.Response):
        response.encoding = "utf-8"
        if not response.ok:
            logger.error(
                "API request failed with status %s: %s",
                response.status_code,
                response.text,
            )
            response.raise_for_status()
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON response from API: {response.text}"
            ) from exc

    def list_devices(self) -> List["RemoteDevice"]:
        response = self._rate_limited_request(
            "GET", f"{self.api_root}/devices", headers=self.headers
        )
        data = self._json_response(response)
        return [RemoteDevice.model_validate(item) for item in data]

    def list_timezones(self) -> List["TimezoneInfo"]:
        response = self._rate_limited_request(
            "GET", f"{self.api_root}/timezones", headers=self.headers
        )
        data = self._json_response(response)
        return [TimezoneInfo.model_validate(item) for item in data]

    def get_device_settings(self, device_id: str) -> "DeviceSettings":
        response = self._rate_limited_request(
            "GET", f"{self.base_url}/{device_id}/settings", headers=self.headers
        )
        return DeviceSettings.model_validate(self._json_response(response))

    def update_device_settings(
        self, device_id: str, payload: "DeviceSettingsUpdate"
    ) -> "DeviceSettings":
        response = self._rate_limited_request(
            "POST",
            f"{self.base_url}/{device_id}/settings",
            json=payload.model_dump(exclude_unset=True, exclude_none=False),
            headers=self.headers,
        )
        if not response.ok:
            self._json_response(response)
        return self.get_device_settings(device_id)

    def display_text(
        self, device_id: str, payload: DisplayTextRequest
    ) -> "ApiResponse":
        url = f"{self.base_url}/{device_id}/text"
        request_data = payload.model_dump(exclude_none=True)
        logger.info(f"Sending text display request to {url}")
        logger.info(f"Request parameters: {request_data}")
        response = self._rate_limited_request(
            "POST", url, json=request_data, headers=self.headers
        )
        return self._handle_response(response)

    def display_image(
        self, device_id: str, payload: DisplayImageRequest
    ) -> "ApiResponse":
        url = f"{self.base_url}/{device_id}/image"
        request_data = payload.model_dump(exclude_none=True)
        log_data = {
            k: v if k != "image" else f"<base64 data, length: {len(v)}>"
            for k, v in request_data.items()
        }
        logger.info(f"Sending image display request to {url}")
        logger.info(f"Request parameters: {log_data}")
        response = self._rate_limited_request(
            "POST", url, json=request_data, headers=self.headers
        )
        return self._handle_response(response)

    def get_device_status(self, device_id: str) -> "DeviceStatus":
        url = f"{self.base_url}/{device_id}/status"
        logger.info(f"Getting device status from {url}")
        response = self._rate_limited_request("GET", url, headers=self.headers)
        response_data = self._json_response(response)
        logger.debug(f"Device status response: {response_data}")
        return DeviceStatus.model_validate(response_data)

    def switch_next_content(self, device_id: str) -> "ApiResponse":
        url = f"{self.base_url}/{device_id}/next"
        logger.info(f"Switching to next content for device {device_id}")
        response = self._rate_limited_request("POST", url, headers=self.headers)
        return self._handle_response(response)

    def list_device_content(
        self, device_id: str, task_type: str = "loop"
    ) -> List["DeviceTask"]:
        url = f"{self.base_url}/{device_id}/{task_type}/list"
        logger.info(f"Listing device content from {url}")
        response = self._rate_limited_request("GET", url, headers=self.headers)
        response_data = self._json_response(response)
        logger.debug(f"Device content list response: {response_data}")
        return [DeviceTask.model_validate(item) for item in response_data]
