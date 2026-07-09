# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dotmate is a Python-based scheduler for managing e-ink message push notifications. It supports Quote/0 (296x152) and Zectrix Note 4 (400x300) devices, with scheduled tasks using cron expressions to send various types of messages (Note 4 uses the image API only).

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
python main.py push mydevice code_status --wakatime-url "https://your.wakatime.site" --wakatime-api-key "your-key" --wakatime-user-id "username"
python main.py push mydevice umami_stats --umami-host "https://your.umami.site" --umami-website-id "website-id" --umami-api-key "api-key" --umami-time-range "7d"
python main.py push mydevice github_contributions --github-username "username" --github-token "ghp_xxxxx" --dither-type "NONE"
python main.py push mydevice code_plan_usage --api-url "http://your.onwatch.site" --provider "anthropic" --api-username "user" --api-password "pass"

# Additional image options:
# --link "https://example.com"
# --border <0|1>
# --task-key <image_api_task_key>
# --task-alias <image_api_task_alias>
# --dither-type "DIFFUSION|ORDERED|NONE"
# --dither-kernel "FLOYD_STEINBERG|ATKINSON|BURKES|..." (many options available)

# Generate demo PNG images without sending to device (use --platform to target resolution)
python main.py demo <message_type> [options]

# Demo examples:
python main.py demo title_image --main-title "测试标题" --sub-title "副标题"
python main.py demo work --clock-in "09:00" --clock-out "18:00"
python main.py demo title_image --main-title "测试" --output "./my-demos"
python main.py demo title_image --main-title "Note 4" --platform zectrix  # render at 400x300

# The demo command supports all the same parameters as push (except device name).
# Generated images are saved to demos/ directory by default. --platform selects
# the target resolution (quote0=296x152, zectrix=400x300; default: quote0).
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
- Config is grouped per platform under `platforms:`; each device declares its `platform`
- Capability validation at load time: text scenarios are rejected on image-only platforms (e.g. scheduling `text` on a `zectrix` device fails fast)

**View System** (`dotmate/view/`):
- Factory pattern for message type handlers
- BaseView abstract class defines the interface for all message types; declares `requires_text` capability
- Currently supports: work (countdown timer), text (custom messages), code_status (Wakatime integration), image (binary images), title_image (generated text images), umami_stats (Umami analytics), github_contributions (GitHub contribution heatmap), code_plan_usage (code plan quota progress bars)
- Each view type has its own parameter model extending Pydantic BaseModel
- Image views support dithering options and border colors for e-ink display optimization
- Layouts are **resolution-adaptive**: views derive font/metric sizes and Y positions from the active `PlatformProfile`, so the same view renders correctly at 296x152 or 400x300

**Platform System** (`dotmate/platforms/`):
- Vendor-neutral abstraction layer; views build vendor-agnostic `ImagePayload` / `TextPayload` (defined in `base.py`) and never touch wire formats
- `PlatformClient` is the abstract contract (`display_image` mandatory; `display_text` optional, platforms without text support inherit a NotImplemented default)
- Each vendor lives in its own subpackage with its own client, wire-format models, and `PlatformProfile`:
  - `platforms/quote0/`: DotClient, JSON base64 models, 296x152, supports text+image
  - `platforms/zectrix/`: ZectrixClient, multipart models, 400x300, image-only
- `platforms/demo.py`: DemoClient saves generated images to the local filesystem for preview/testing
- `platforms/registry.py`: `PlatformRegistry` is the single factory — maps platform name -> (client class, profile) and resolves credentials at client creation

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

Resolution-adaptive layout helpers (on ImageView):
- Views receive a `PlatformProfile` via the constructor (`profile=` kwarg)
- `display_scale` property: geometric-mean scale vs the 296x152 reference
- `_sz(base)`: font/metric size in reference units, scaled to the current resolution (and supersampling-aware)
- `_py(ratio)`: proportional Y position as a fraction of canvas height
- Prefer `_sz(...)` for font sizes/spacing and `_py(...)` for row baselines instead of hardcoding pixel offsets

### Adding a New Platform/Vendor

1. Create a subpackage under `dotmate/platforms/<name>/` with:
   - `client.py`: a `PlatformClient` subclass translating neutral `ImagePayload`/`TextPayload` into the vendor's wire format
   - `models.py`: vendor-specific request/response models (no cross-vendor imports)
   - `profile.py`: a `PlatformProfile` (resolution + `supports_text`/`supports_image` capabilities)
2. Register the platform in `PlatformRegistry._platforms` (name -> client class, profile)
3. Add the platform's config section under `platforms:` in YAML

### Configuration Structure

YAML config format (grouped per platform):
```yaml
platforms:                    # credentials grouped per vendor
  quote0:
    api_key: "your_quote0_api_key"
  zectrix:
    api_key: "zt_your_zectrix_key"   # optional, only if note4 devices exist
request_interval: 1.0
devices:
  - name: "device_name"
    device_id: "unique_id"
    platform: quote0   # or zectrix (MAC address as device_id, 400x300)
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
          wakatime_url: "https://your.wakatime.site"
          wakatime_api_key: "your-api-key"
          wakatime_user_id: "your-username"
          dither_type: "NONE"
      - cron: "*/30 * * * *"
        type: "umami_stats"
        params:
          umami_host: "https://your.umami.site"
          umami_website_id: "your-website-id"
          umami_api_key: "api-key"
          umami_time_range: "7d"
          dither_type: "NONE"
      - cron: "0 9 * * *"
        type: "github_contributions"
        params:
          github_username: "your-username"
          github_token: "ghp_xxxxx"
          dither_type: "NONE"
      - cron: "*/15 * * * *"
        type: "code_plan_usage"
        params:
          api_url: "http://your.onwatch.site"
          provider: "anthropic"
          api_username: "user"
          api_password: "pass"
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
- **CodePlanUsageView**: Uses Hack-Bold for quota/progress bar display

### Font Fallback
If specified font is not found in `dotmate/font/resource/`, the system automatically falls back to PIL's default font.

## Development Notes

The project uses a clean factory pattern for extensibility. The scheduler runs in blocking mode and handles shutdown signals gracefully. Configuration is loaded once at startup and validated using Pydantic models. Font management is handled at the View level, allowing each message type to use appropriate typography.

Please refer to DEVELOPMENT.md for more details.
