import requests
from pydantic import BaseModel, Field
from typing import Literal, Optional

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

    def display_text(self, payload: DisplayTextRequest) -> "ApiResponse":
        url = f"{self.base_url}/text"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload.model_dump(exclude_none=True), headers=headers)
        return ApiResponse.model_validate(response.json())

    def display_image(self, payload: DisplayImageRequest) -> "ApiResponse":
        url = f"{self.base_url}/image"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload.model_dump(exclude_none=True), headers=headers)
        return ApiResponse.model_validate(response.json())
