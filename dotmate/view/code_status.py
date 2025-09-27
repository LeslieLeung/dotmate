from datetime import datetime
from typing import Type
from pydantic import BaseModel
from dotmate.api.api import DotClient, DisplayTextRequest
from dotmate.view.base import BaseView


class CodeStatusParams(BaseModel):
    pass


class CodeStatusView(BaseView):
    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        return CodeStatusParams

    def execute(self, params: BaseModel) -> None:
        request = DisplayTextRequest(
            refreshNow=True,
            deviceId=self.device_id,
            title="Code Status",
            message="Working...",
            signature=datetime.now().strftime("%H:%M"),
            icon=None,
            link=None,
        )

        try:
            response = self.client.display_text(request)
            print(f"Code status message sent to {self.device_id} (Response: {response.message})")
        except Exception as e:
            print(f"Error sending code status message to {self.device_id}: {e}")

