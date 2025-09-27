from datetime import datetime
from typing import Optional, Type
from pydantic import BaseModel
from dotmate.api.api import DotClient, DisplayTextRequest
from dotmate.view.base import BaseView


class TextParams(BaseModel):
    message: str
    title: Optional[str] = None


class TextView(BaseView):
    """View handler for custom text messages."""

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        """Return the parameters class for this view."""
        return TextParams

    def execute(self, params: BaseModel) -> None:
        """Send custom text message to device."""
        text_params = TextParams(**params.model_dump())
        # Create display request
        request = DisplayTextRequest(
            refreshNow=True,
            deviceId=self.device_id,
            title=text_params.title,
            message=text_params.message,
            signature=datetime.now().strftime("%H:%M"),
            icon=None,
            link=None,
        )

        try:
            response = self.client.display_text(request)
            print(f"Text message sent to {self.device_id}: {text_params.message} (Response: {response.message})")
        except Exception as e:
            print(f"Error sending text message to {self.device_id}: {e}")


# Legacy function for backward compatibility
def send_text_message(client: DotClient, device_id: str, params: TextParams) -> None:
    """Send custom text message to device (legacy function)."""
    text_view = TextView(client, device_id)
    text_view.execute(params)