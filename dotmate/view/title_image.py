import io
from typing import Optional, Type, Literal, Union
from pydantic import BaseModel
from dotmate.view.image import ImageView, ImageParams
from dotmate.font import FontManager
from PIL import Image, ImageDraw, ImageFont


class TitleImageParams(BaseModel):
    main_title: str
    sub_title: Optional[str] = None
    link: Optional[str] = None
    border: Optional[int] = None
    dither_type: Optional[Literal["DIFFUSION", "ORDERED", "NONE"]] = "NONE"
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


class TitleImageView(ImageView):
    """View handler for generating and displaying title images."""

    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.font_manager = FontManager()

    @classmethod
    def get_params_class(cls) -> Type[BaseModel]:
        """Return the parameters class for this view."""
        return TitleImageParams

    def _calculate_optimal_font_size(self, text: str, max_width: int, max_height: int,
                                     initial_size: int = 48, min_size: int = 16) -> int:
        """Calculate optimal font size that fits within max_width and max_height."""
        try:
            font_size = initial_size
            while font_size >= min_size:
                test_font = self.font_manager.get_font(font_size)

                # Create temporary draw to measure text
                temp_img = Image.new('1', (1, 1), 1)
                temp_draw = ImageDraw.Draw(temp_img)
                bbox = temp_draw.textbbox((0, 0), text, font=test_font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                # If using default font, apply a scaling factor based on desired size
                if self.font_manager.is_default_font(test_font):
                    # Default font is roughly equivalent to size 11, so scale accordingly
                    scale_factor = font_size / 11.0
                    text_width = int(text_width * scale_factor)
                    text_height = int(text_height * scale_factor)

                if text_width <= max_width and text_height <= max_height:
                    return font_size

                font_size -= 1

            return min_size
        except Exception:
            return min_size

    def _wrap_text(self, text: str, font: Union[ImageFont.ImageFont, ImageFont.FreeTypeFont], max_width: int) -> list[str]:
        """Wrap text to fit within max_width, returning list of lines."""
        words = text.split()
        lines = []
        current_line: list[str] = []

        # Create temporary draw to measure text
        temp_img = Image.new('1', (1, 1), 1)
        temp_draw = ImageDraw.Draw(temp_img)

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = temp_draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]

            if line_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Single word is too long, just add it anyway
                    lines.append(word)

        if current_line:
            lines.append(' '.join(current_line))

        return lines

    def _draw_text_with_size(self, draw, text, font, font_size, image_width, y_pos):
        """Draw text with proper centering, handling default font size simulation."""
        # Calculate text position for centering
        if self.font_manager.is_default_font(font):
            # For default font, we need to simulate the size effect
            # We can't actually make the default font bigger, but we can draw it multiple times
            # with slight offsets to simulate bold/larger appearance
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (image_width - text_width) // 2

            # For larger "font sizes", draw the text multiple times with offsets
            # to simulate a bolder/thicker appearance
            if font_size >= 32:
                offsets = [(0, 0), (1, 0), (0, 1), (1, 1)]
            elif font_size >= 24:
                offsets = [(0, 0), (1, 0)]
            else:
                offsets = [(0, 0)]

            for dx, dy in offsets:
                draw.text((text_x + dx, y_pos + dy), text, fill=0, font=font)
        else:
            # For TrueType fonts, normal drawing
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (image_width - text_width) // 2
            draw.text((text_x, y_pos), text, fill=0, font=font)

    def _generate_title_image(self, main_title: str, sub_title: Optional[str] = None) -> bytes:
        """Generate a 296x152 PNG image with centered titles and return PNG binary data."""
        # Create image with white background (1-bit black and white for e-ink display)
        width, height = 296, 152
        max_text_width = int(width * 2 / 3)  # Use at most 2/3 of width
        image = Image.new('1', (width, height), 1)  # 1-bit mode, 1=white, 0=black
        draw = ImageDraw.Draw(image)

        try:
            if sub_title:
                # Both titles - calculate optimal sizes for each
                available_height = height - 20  # Leave some padding
                main_height_allocation = int(available_height * 0.6)  # 60% for main title
                sub_height_allocation = int(available_height * 0.4)   # 40% for sub title

                # Calculate optimal font sizes
                main_font_size = self._calculate_optimal_font_size(
                    main_title, max_text_width, main_height_allocation, initial_size=42
                )
                sub_font_size = self._calculate_optimal_font_size(
                    sub_title, max_text_width, sub_height_allocation, initial_size=32
                )

                # Create fonts
                main_font = self.font_manager.get_font(main_font_size)
                sub_font = self.font_manager.get_font(sub_font_size)

                # Wrap text if needed
                main_lines = self._wrap_text(main_title, main_font, max_text_width)
                sub_lines = self._wrap_text(sub_title, sub_font, max_text_width)

                # Calculate line heights - use font metrics for more accurate height
                main_line_height = main_font.getbbox("Ag")[3] - main_font.getbbox("Ag")[1]
                sub_line_height = sub_font.getbbox("Ag")[3] - sub_font.getbbox("Ag")[1]

                # Add some padding for better vertical spacing
                main_line_height = int(main_line_height * 1.2)
                sub_line_height = int(sub_line_height * 1.2)

                # Calculate total text block height (remove extra spacing between lines)
                total_main_height = len(main_lines) * main_line_height
                total_sub_height = len(sub_lines) * sub_line_height
                total_text_height = total_main_height + total_sub_height + 15  # spacing between title blocks

                # Calculate starting Y position to center the entire text block
                start_y = (height - total_text_height) // 2

                # Ensure minimum top padding
                start_y = max(start_y, 10)

                # Draw main title lines
                current_y = start_y
                for line in main_lines:
                    self._draw_text_with_size(draw, line, main_font, main_font_size, width, current_y)
                    current_y += main_line_height

                # Add spacing between title blocks
                current_y += 15

                # Draw sub title lines
                for line in sub_lines:
                    self._draw_text_with_size(draw, line, sub_font, sub_font_size, width, current_y)
                    current_y += sub_line_height

            else:
                # Only main title - calculate optimal size for available space
                available_height = height - 20  # Leave some padding
                main_font_size = self._calculate_optimal_font_size(
                    main_title, max_text_width, available_height, initial_size=48
                )

                # Create font
                main_font = self.font_manager.get_font(main_font_size)

                # Wrap text if needed
                main_lines = self._wrap_text(main_title, main_font, max_text_width)

                # Calculate line height - use font metrics for more accurate height
                main_line_height = main_font.getbbox("Ag")[3] - main_font.getbbox("Ag")[1]

                # Add some padding for better vertical spacing
                main_line_height = int(main_line_height * 1.2)

                # Calculate total text block height
                total_text_height = len(main_lines) * main_line_height

                # Calculate starting Y position to center the text block
                start_y = (height - total_text_height) // 2

                # Ensure minimum top padding
                start_y = max(start_y, 10)

                # Draw main title lines
                current_y = start_y
                for line in main_lines:
                    self._draw_text_with_size(draw, line, main_font, main_font_size, width, current_y)
                    current_y += main_line_height

            # Convert to PNG binary data
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            buffer.seek(0)
            return buffer.read()

        except Exception as e:
            raise Exception(f"Error generating title image: {e}")

    def execute(self, params: BaseModel) -> None:
        """Generate title image and send to device."""
        title_params = TitleImageParams(**params.model_dump())

        # Generate image binary data
        image_data = self._generate_title_image(
            title_params.main_title,
            title_params.sub_title
        )

        # Create ImageParams and use parent execute
        image_params = ImageParams(
            image_data=image_data,
            link=title_params.link,
            border=title_params.border,
            dither_type=title_params.dither_type,
            dither_kernel=title_params.dither_kernel,
        )

        # Use parent's execute method
        super().execute(image_params)