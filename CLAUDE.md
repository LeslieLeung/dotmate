# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dotmate is a Python-based scheduler for managing Quote/0 message push notifications. It supports scheduled tasks using cron expressions to send various types of messages to devices.

## Essential Commands

### Development Setup
```bash
# Install dependencies using uv
uv install

# Copy configuration template
cp config.example.yaml config.yaml
```

### Running the Application
```bash
# Start daemon with scheduler (default mode)
python main.py daemon
# or simply
python main.py

# Manual message pushing
python main.py push <device_name> <message_type> [options]

# Examples:
python main.py push mydevice text --message "Hello World" --title "通知"
python main.py push mydevice work --clock-in "09:00" --clock-out "18:00"
python main.py push mydevice image --image-path "path/to/image.png" --dither-type "DIFFUSION"
python main.py push mydevice title_image --main-title "主标题" --sub-title "副标题" --border 1
python main.py push mydevice code_status --wakatime-url "https://waka.ameow.xyz" --wakatime-api-key "your-key" --wakatime-user-id "username"
python main.py push mydevice umami_stats --umami-host "https://umami.ameow.xyz" --umami-website-id "website-id" --umami-api-key "api-key" --umami-time-range "7d"
python main.py push mydevice github_contributions --github-username "username" --github-token "ghp_xxxxx" --dither-type "NONE"

# Additional image options:
# --link "https://example.com"
# --border <color_number>
# --dither-type "DIFFUSION|ORDERED|NONE"
# --dither-kernel "FLOYD_STEINBERG|ATKINSON|BURKES|..." (many options available)
```

### Environment Requirements
- Python >= 3.12
- uv package manager (recommended)

## Architecture Overview

### Core Components

**main.py**: Application entry point that handles CLI commands and scheduler setup using APScheduler with BlockingScheduler.

**Configuration System** (`dotmate/config/`):
- Uses Pydantic models for type-safe configuration parsing
- YAML-based configuration with models: Config -> Device -> Schedule
- Each device can have multiple scheduled tasks with cron expressions

**View System** (`dotmate/view/`):
- Factory pattern for message type handlers
- BaseView abstract class defines the interface for all message types
- Currently supports: work (countdown timer), text (custom messages), code_status (Wakatime integration), image (binary images), title_image (generated text images), umami_stats (Umami analytics), github_contributions (GitHub contribution heatmap)
- Each view type has its own parameter model extending Pydantic BaseModel
- Image views support dithering options and border colors for e-ink display optimization

**API Client** (`dotmate/api/api.py`):
- DotClient handles communication with the Quote/0 API
- All views use the same client instance for device communication
- Supports both text display and image display endpoints
- Image API supports advanced dithering algorithms and display options

**Font Management System** (`dotmate/font/`):
- FontManager class provides font file discovery and loading from `dotmate/font/resource/`
- Supports TTF, OTF, and TTC font formats
- Custom font selection per View with automatic fallback to default fonts
- Built-in fonts: Hack-Bold (for code), SourceHanSansSC-VF (for Chinese text)
- Variable font support with customizable weight settings in View classes

### Message Type Extension

To add new message types:
1. Create new view class in `dotmate/view/` inheriting from BaseView (or ImageView for image-based types)
2. Implement `get_params_class()` returning a Pydantic model
3. Implement `execute(params)` method with message logic
4. Register the new type in ViewFactory._view_registry

For image-based message types:
- Inherit from ImageView for basic image sending functionality
- Inherit from TitleImageView for generated text-based images
- Set `custom_font_name` in `__init__()` to specify font (e.g., "Hack-Bold", "SourceHanSansSC-VF")
- For variable fonts, set `font_weight` (100-900) to control font weight
- Use `_get_font(size)` method to obtain fonts with custom settings

### Configuration Structure

YAML config format:
```yaml
api_key: "your_api_key"
devices:
  - name: "device_name"
    device_id: "unique_id"
    schedules:
      - cron: "*/5 * * * *"
        type: "work"
        params:
          clock_in: "09:00"
          clock_out: "18:00"
      - cron: "0 12 * * *"
        type: "title_image"
        params:
          main_title: "午餐时间"
          sub_title: "记得按时吃饭"
          dither_type: "NONE"
      - cron: "*/10 * * * *"
        type: "code_status"
        params:
          wakatime_url: "https://waka.ameow.xyz"
          wakatime_api_key: "your-api-key"
          wakatime_user_id: "your-username"
          dither_type: "NONE"
      - cron: "*/30 * * * *"
        type: "umami_stats"
        params:
          umami_host: "https://umami.ameow.xyz"
          umami_website_id: "your-website-id"
          umami_api_key: "your-api-key"
          umami_time_range: "24h"
          dither_type: "NONE"
      - cron: "0 9 * * *"
        type: "github_contributions"
        params:
          github_username: "your-username"
          github_token: "ghp_xxxxx"
          dither_type: "NONE"
```

### Key Dependencies
- APScheduler: Cron-based task scheduling
- Pydantic: Data validation and settings management
- PyYAML: Configuration file parsing
- Requests: HTTP API communication
- Pillow (PIL): Image processing and generation
- Custom fonts: Hack (programming font), SourceHanSansSC (Chinese font)

## Font System Usage

### Available Fonts
- **Hack-Bold.ttf**: Bold programming font, ideal for code displays
- **Hack-Regular.ttf**: Regular programming font
- **SourceHanSansSC-VF.otf**: Variable Chinese font supporting weight adjustment

### Font Configuration in Views

For View classes requiring custom fonts:

```python
class MyCustomView(TitleImageView):
    def __init__(self, client, device_id: str):
        super().__init__(client, device_id)
        self.custom_font_name = "Hack-Bold"  # Specify font
        self.font_weight = 600  # For variable fonts (100-900)
```

### Current Font Assignments
- **CodeStatusView**: Uses Hack-Bold for programming/technical content
- **WorkView**: Uses SourceHanSansSC-VF with SemiBold weight (600) for Chinese text
- **UmamiStatsView**: Uses Hack-Bold for analytics data display

### Font Fallback
If specified font is not found in `dotmate/font/resource/`, the system automatically falls back to PIL's default font.

## Development Notes

The project uses a clean factory pattern for extensibility. The scheduler runs in blocking mode and handles shutdown signals gracefully. Configuration is loaded once at startup and validated using Pydantic models. Font management is handled at the View level, allowing each message type to use appropriate typography.

Please refer to DEVELOPMENT.md for more details.