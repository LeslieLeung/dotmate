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
- Currently supports: work (countdown timer), text (custom messages), code_status, image (binary images), title_image (generated text images)
- Each view type has its own parameter model extending Pydantic BaseModel
- Image views support dithering options and border colors for e-ink display optimization

**API Client** (`dotmate/api/api.py`):
- DotClient handles communication with the Quote/0 API
- All views use the same client instance for device communication
- Supports both text display and image display endpoints
- Image API supports advanced dithering algorithms and display options

**Font Management System** (`dotmate/font/`):
- FontManager class provides cross-platform font discovery and loading
- Prioritizes Source Han Sans SC for Chinese text rendering
- Automatic system font detection for macOS, Linux, and Windows
- Font caching and fallback mechanisms
- Variable font support with weight adjustment

### Message Type Extension

To add new message types:
1. Create new view class in `dotmate/view/` inheriting from BaseView (or ImageView for image-based types)
2. Implement `get_params_class()` returning a Pydantic model
3. Implement `execute(params)` method with message logic
4. Register the new type in ViewFactory._view_registry

For image-based message types:
- Inherit from ImageView for basic image sending functionality
- Inherit from TitleImageView for generated text-based images
- Use FontManager for text rendering with proper Chinese font support

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
```

### Key Dependencies
- APScheduler: Cron-based task scheduling
- Pydantic: Data validation and settings management
- PyYAML: Configuration file parsing
- Requests: HTTP API communication
- Pillow (PIL): Image processing and generation
- Source Han Sans SC: Bundled Chinese font for text rendering

## Development Notes

The project uses a clean factory pattern for extensibility. The scheduler runs in blocking mode and handles shutdown signals gracefully. Configuration is loaded once at startup and validated using Pydantic models.