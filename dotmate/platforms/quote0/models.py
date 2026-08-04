"""Quote/0 (dot.mindreset.tech) wire-format models."""

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

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
    icon: Optional[str] = Field(None, description="PNG Base64 图标数据或可匿名访问的 http(s) 图片 URL")
    link: Optional[str] = Field(None, description="碰一碰跳转链接")
    taskKey: Optional[str] = Field(None, description="指定更新哪个 Text API 内容")
    taskAlias: Optional[Union[str, int]] = Field(None, description="Text API 内容别名")
    styles: Optional[TextStyles] = Field(None, description="标题、正文和签名的字体样式")


class DisplayImageRequest(BaseModel):
    refreshNow: bool = Field(..., description="是否立刻显示内容")
    image: str = Field(..., description="PNG Base64 图像数据或可匿名访问的 http(s) 图片 URL")
    link: Optional[str] = Field(None, description="碰一碰跳转链接")
    border: Optional[Literal[0, 1]] = Field(None, description="屏幕边框颜色：0 为白色，1 为黑色")
    ditherType: Optional[Literal["DIFFUSION", "ORDERED", "NONE"]] = Field(None, description="抖动类型")
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


class DeviceTask(BaseModel):
    type: str
    key: Optional[str] = None
    refreshNow: Optional[bool] = None
    title: Optional[str] = None
    message: Optional[str] = None
    signature: Optional[str] = None
    icon: Optional[str] = None
    link: Optional[str] = None
    styles: Optional[TextStyles] = None
    image: Optional[str] = None
    border: Optional[Literal[0, 1]] = None
    ditherType: Optional[str] = None
    ditherKernel: Optional[str] = None
    taskAlias: Optional[Union[str, int]] = None


__all__ = [
    "TextFontFamily",
    "TextFontWeight",
    "TextStyle",
    "MessageTextStyle",
    "TextStyles",
    "DisplayTextRequest",
    "DisplayImageRequest",
    "DeviceTask",
]
