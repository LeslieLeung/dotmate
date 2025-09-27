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
- Currently supports: work (countdown timer), text (custom messages), code_status
- Each view type has its own parameter model extending Pydantic BaseModel

**API Client** (`dotmate/api/api.py`):
- DotClient handles communication with the Quote/0 API
- All views use the same client instance for device communication

### Message Type Extension

To add new message types:
1. Create new view class in `dotmate/view/` inheriting from BaseView
2. Implement `get_params_class()` returning a Pydantic model
3. Implement `execute(params)` method with message logic
4. Register the new type in ViewFactory._view_registry

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
```

### Key Dependencies
- APScheduler: Cron-based task scheduling
- Pydantic: Data validation and settings management
- PyYAML: Configuration file parsing
- Requests: HTTP API communication

## Development Notes

The project uses a clean factory pattern for extensibility. The scheduler runs in blocking mode and handles shutdown signals gracefully. Configuration is loaded once at startup and validated using Pydantic models.