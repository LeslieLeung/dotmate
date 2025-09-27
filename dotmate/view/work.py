from datetime import datetime, time
from typing import Optional, Type
from pydantic import BaseModel
from dotmate.api.api import DotClient, DisplayTextRequest
from dotmate.view.base import BaseView


class WorkParams(BaseModel):
    clock_in: str
    clock_out: str


class WorkView(BaseView):
    """View handler for work countdown messages."""

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        """Return the parameters class for this view."""
        return WorkParams

    def calculate_work_status(self, clock_in: str, clock_out: str) -> str:
        """Calculate work status - either countdown or off work message."""
        now = datetime.now()
        current_time = now.time()

        # Parse clock times (format: "HH:MM")
        try:
            clock_in_time = time.fromisoformat(clock_in)
            clock_out_time = time.fromisoformat(clock_out)
        except ValueError:
            return "时间格式错误"

        # Check if current time is outside work hours
        if current_time < clock_in_time or current_time >= clock_out_time:
            return "已经下班啦"

        # Calculate time until off work
        off_work_datetime = datetime.combine(now.date(), clock_out_time)
        time_diff = off_work_datetime - now

        # Convert to hours and minutes
        total_minutes = int(time_diff.total_seconds() // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60

        if hours > 0:
            return f"距下班 {hours} 小时 {minutes} 分钟"
        else:
            return f"距下班 {minutes} 分钟"

    def execute(self, params: BaseModel) -> None:
        """Send work countdown message to device."""
        work_params = WorkParams(**params.model_dump())
        message = self.calculate_work_status(work_params.clock_in, work_params.clock_out)

        # Create display request
        request = DisplayTextRequest(
            refreshNow=True,
            deviceId=self.device_id,
            title="还有多久下班",
            message=message,
            signature=datetime.now().strftime("%H:%M"),
            icon=None,
            link=None,
        )

        try:
            response = self.client.display_text(request)
            print(f"Work message sent to {self.device_id}: {message} (Response: {response.message})")
        except Exception as e:
            print(f"Error sending work message to {self.device_id}: {e}")


# Legacy function for backward compatibility
def send_work_message(client: DotClient, device_id: str, params: WorkParams) -> None:
    """Send work countdown message to device (legacy function)."""
    work_view = WorkView(client, device_id)
    work_view.execute(params)