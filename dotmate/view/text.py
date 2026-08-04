from datetime import datetime
from typing import Optional, Type, Union
from pydantic import BaseModel
from dotmate.platforms.base import PlatformClient, TextPayload
from dotmate.view.base import BaseView


class TextParams(BaseModel):
    message: str
    title: Optional[str] = None
    signature: Optional[str] = None
    icon: Optional[str] = None
    link: Optional[str] = None
    task_key: Optional[str] = None
    task_alias: Optional[Union[str, int]] = None
    styles: Optional[dict] = None


class TextView(BaseView):
    """View handler for custom text messages."""

    requires_text = True

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        """Return the parameters class for this view."""
        return TextParams

    def execute(self, params: BaseModel) -> None:
        """Send custom text message to device."""
        text_params = TextParams(**params.model_dump())
        payload = TextPayload(
            refresh_now=True,
            title=text_params.title,
            message=text_params.message,
            signature=text_params.signature or datetime.now().strftime("%H:%M"),
            icon=text_params.icon,
            link=text_params.link,
            task_key=text_params.task_key,
            task_alias=text_params.task_alias,
            styles=text_params.styles,
        )

        try:
            response = self.client.display_text(self.device_id, payload)
            print(
                f"Text message sent to {self.device_id}: {text_params.message} "
                f"(Response: {response.message})"
            )
        except Exception as e:
            print(f"Error sending text message to {self.device_id}: {e}")
            raise


# Legacy function for backward compatibility
def send_text_message(client: PlatformClient, device_id: str, params: TextParams) -> None:
    """Send custom text message to device (legacy function)."""
    text_view = TextView(client, device_id)
    text_view.execute(params)
