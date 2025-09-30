import base64
from typing import Optional, Type, Literal, Union
from pydantic import BaseModel
from PIL import ImageFont
from dotmate.api.api import DisplayImageRequest
from dotmate.view.base import BaseView
from dotmate.font import FontManager


class ImageParams(BaseModel):
    image_data: bytes
    link: Optional[str] = None
    border: Optional[int] = None
    dither_type: Optional[Literal["DIFFUSION", "ORDERED", "NONE"]] = None
    dither_kernel: Optional[Literal[
        "THRESHOLD",
        "ATKINSON",
        "BURKES",
        "FLOYD_STEINBERG",
        "SIERRA2",
        "STUCKI",
        "JARVIS_JUDICE_NINKE",
        "DIFFUSION_ROW",
        "DIFFUSION_COLUMN",
        "DIFFUSION2_D"
    ]] = None


class ImageView(BaseView):
    """Base view handler for image display with optional font management."""

    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.font_manager = FontManager()
        self.custom_font_name: Optional[str] = None
        self.font_weight: Optional[int] = None

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        """Return the parameters class for this view."""
        return ImageParams

    def _get_font(self, size: int) -> Union[ImageFont.ImageFont, ImageFont.FreeTypeFont]:
        """Get font with specified size, using custom settings if configured.

        Subclasses can override custom_font_name and font_weight in __init__.
        """
        return self.font_manager.get_font(size, self.custom_font_name, self.font_weight)

    def _encode_image_data(self, image_data: bytes) -> str:
        """Encode PNG binary data to base64."""
        return base64.b64encode(image_data).decode('utf-8')

    def execute(self, params: BaseModel) -> None:
        """Send image to device."""
        image_params = ImageParams(**params.model_dump())

        # Encode image data
        image_base64 = self._encode_image_data(image_params.image_data)

        # Create display request
        request = DisplayImageRequest(
            refreshNow=True,
            deviceId=self.device_id,
            image=image_base64,
            link=image_params.link,
            border=image_params.border,
            ditherType=image_params.dither_type,
            ditherKernel=image_params.dither_kernel,
        )

        try:
            response = self.client.display_image(request)
            print(f"Image sent to {self.device_id}: {len(image_params.image_data)} bytes (Response: {response.message})")
        except Exception as e:
            print(f"Error sending image to {self.device_id}: {e}")