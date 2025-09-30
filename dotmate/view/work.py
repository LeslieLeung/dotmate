from datetime import datetime, time
from typing import Type
from pydantic import BaseModel
from dotmate.view.title_image import TitleImageView, TitleImageParams


class WorkParams(BaseModel):
    clock_in: str
    clock_out: str


class WorkView(TitleImageView):
    """View handler for work countdown messages."""

    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.custom_font_name = "SourceHanSansSC-VF"  # Use SourceHanSans font
        self.font_weight = 600  # SemiBold weight for better readability

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

        # Convert to hours and minutes (round up to the next minute if there are remaining seconds)
        total_seconds = int(time_diff.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        # Round up minutes when there are remaining seconds
        if seconds > 0:
            minutes += 1
            if minutes == 60:
                hours += 1
                minutes = 0

        if hours > 0:
            return f"距下班 {hours} 小时 {minutes} 分钟"
        else:
            return f"距下班 {minutes} 分钟"

    def execute(self, params: BaseModel) -> None:
        """Send work countdown image to device."""
        work_params = WorkParams(**params.model_dump())
        message = self.calculate_work_status(
            work_params.clock_in, work_params.clock_out
        )
        current_time = datetime.now().strftime("%H:%M")

        # Create title image parameters
        title_image_params = TitleImageParams(
            main_title="还有多久下班",
            sub_title=f"{message}\n{current_time}",
            link=None,
            border=None,
            dither_type="NONE",
            dither_kernel=None,
        )

        # Use parent's execute method to generate and send image
        super().execute(title_image_params)
