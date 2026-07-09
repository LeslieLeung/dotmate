import argparse
import logging
import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotmate.config import load_config
from dotmate.platforms import PlatformRegistry, get_demo_client
from dotmate.platforms.base import PlatformProfile
from dotmate.view.factory import ViewFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def setup_scheduler(config_path: str = "config.yaml"):
    """Setup APScheduler with jobs from config file."""
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    scheduler = BlockingScheduler()

    # Add jobs for each device and schedule (per-device client + profile)
    for device in config.devices:
        client = PlatformRegistry.create_client(device.platform, config, device)
        profile = PlatformRegistry.get_profile(device.platform)
        if device.schedules:
            for schedule in device.schedules:
                if schedule.cron is None:
                    print(
                        f"Skipping schedule for device '{device.name}' because cron is None"
                    )
                    continue
                if ViewFactory.is_registered(schedule.type):
                    overlay = {
                        "show_battery_icon": device.show_battery_icon,
                        "show_battery_percentage": device.show_battery_percentage,
                        "show_refresh_time": device.show_refresh_time,
                    }
                    scheduler.add_job(
                        func=ViewFactory.execute_view,
                        trigger=CronTrigger.from_crontab(schedule.cron),
                        args=[
                            schedule.type,
                            client,
                            device.device_id,
                            schedule.params or {},
                            overlay,
                            profile,
                        ],
                        id=f"{schedule.type}_{device.name}_{schedule.cron}",
                        name=f"{schedule.type.capitalize()} job for {device.name}",
                    )
                    print(
                        f"Scheduled {schedule.type} job for device '{device.name}' "
                        f"(platform={device.platform}, {profile.width}x{profile.height}) "
                        f"with cron: {schedule.cron}"
                    )
                else:
                    print(f"Unknown schedule type '{schedule.type}' for device '{device.name}'")

    return scheduler


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print("\nShutdown signal received. Stopping dotmate...")
    sys.exit(0)


def generate_demo(
    scenario: str,
    config_path: str = "config.yaml",
    output_dir: str = "demos",
    platform: str = "quote0",
    **params,
):
    """Generate demo PNG image for a specific scenario without sending to device."""
    try:
        load_config(config_path)
    except FileNotFoundError:
        # Config optional for demos that don't need secrets — only warn
        print(f"Warning: config file not found: {config_path} (continuing demo)")
    except Exception as e:
        # Validation may fail without keys; still allow pure image demos
        print(f"Warning: could not fully load config: {e} (continuing demo)")

    # Create demo client that saves images to files
    client = get_demo_client(output_dir)

    # Use a dummy device ID for demo
    dummy_device_id = "demo-device"
    profile = PlatformRegistry.get_profile(platform)

    # Execute the scenario using factory pattern
    try:
        if ViewFactory.is_registered(scenario):
            # Use provided params
            scenario_params = params if params else {}

            # Special handling for image scenario - convert file path to binary data
            if scenario == "image" and "image_path" in scenario_params:
                image_path = scenario_params.pop("image_path")
                try:
                    with open(image_path, "rb") as f:
                        scenario_params["image_data"] = f.read()
                    print(f"Loaded image from: {image_path}")
                except FileNotFoundError:
                    print(f"Error: Image file not found: {image_path}")
                    sys.exit(1)
                except Exception as e:
                    print(f"Error reading image file {image_path}: {e}")
                    sys.exit(1)

            print(
                f"Generating demo for scenario: {scenario} "
                f"(platform={platform}, {profile.width}x{profile.height})"
            )
            ViewFactory.execute_view(
                scenario,
                client,
                dummy_device_id,
                scenario_params,
                profile=profile,
            )
        else:
            print(f"Unknown or unsupported scenario: {scenario}")
            available_types = ViewFactory.get_available_types()
            print(f"Available scenarios: {available_types}")
            sys.exit(1)
    except Exception as e:
        print(f"Error generating demo for scenario '{scenario}': {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def force_push(device_name_or_id: str, scenario: str, config_path: str = "config.yaml", **params):
    """Force push update to a device by name or ID for a specific scenario."""
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

    # Find device by name or ID
    target_device = None
    for device in config.devices:
        if device.name == device_name_or_id or device.device_id == device_name_or_id:
            target_device = device
            break

    if not target_device:
        print(f"Device not found: {device_name_or_id}")
        print(f"Available devices: {[d.name + ' (' + d.device_id + ')' for d in config.devices]}")
        sys.exit(1)

    client = PlatformRegistry.create_client(target_device.platform, config, target_device)
    profile: PlatformProfile = PlatformRegistry.get_profile(target_device.platform)

    # Try to find matching schedule for the scenario, but don't require it
    target_schedule = None
    if target_device.schedules:
        for schedule in target_device.schedules:
            if schedule.type == scenario:
                target_schedule = schedule
                break

    # Execute the scenario using factory pattern
    try:
        if ViewFactory.is_registered(scenario):
            # Use provided params if any; otherwise fallback to schedule params
            if params:
                scenario_params = params
            elif target_schedule and target_schedule.params:
                scenario_params = target_schedule.params
            else:
                scenario_params = {}

            # Special handling for image scenario - convert file path to binary data
            if scenario == "image" and "image_path" in scenario_params:
                image_path = scenario_params.pop("image_path")
                try:
                    with open(image_path, "rb") as f:
                        scenario_params["image_data"] = f.read()
                    print(f"Loaded image from: {image_path}")
                except FileNotFoundError:
                    print(f"Error: Image file not found: {image_path}")
                    sys.exit(1)
                except Exception as e:
                    print(f"Error reading image file {image_path}: {e}")
                    sys.exit(1)

            overlay = {
                "show_battery_icon": target_device.show_battery_icon,
                "show_battery_percentage": target_device.show_battery_percentage,
                "show_refresh_time": target_device.show_refresh_time,
            }
            print(
                f"Sending {scenario} message to device '{target_device.name}' "
                f"({target_device.device_id}, platform={target_device.platform}, "
                f"{profile.width}x{profile.height}), overlay settings: {overlay}"
            )
            ViewFactory.execute_view(
                scenario,
                client,
                target_device.device_id,
                scenario_params,
                overlay,
                profile,
            )
        else:
            print(f"Unknown or unsupported scenario: {scenario}")
            available_types = ViewFactory.get_available_types()
            print(f"Available scenarios: {available_types}")
            sys.exit(1)
    except Exception as e:
        print(f"Error executing scenario '{scenario}': {e}")
        sys.exit(1)


def start_daemon(config_path: str = "config.yaml"):
    """Start the daemon with scheduler."""
    print("Starting dotmate daemon...")

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Setup scheduler
    scheduler = setup_scheduler(config_path)

    if not scheduler.get_jobs():
        print("No jobs scheduled. Devices can still be controlled via 'push' command.")
        print("Use 'python main.py push <device> <scenario>' to send messages manually.")

    print(f"Dotmate daemon started with {len(scheduler.get_jobs())} scheduled job(s)")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\nDaemon stopped by user")
    except Exception as e:
        print(f"Error in daemon: {e}")
        sys.exit(1)


def _add_scenario_args(parser):
    """Register the common scenario arguments on a parser (push/demo share these)."""
    parser.add_argument("--message", help="Message for text scenario")
    parser.add_argument("--title", help="Title for text scenario")
    parser.add_argument("--signature", help="Signature for text scenario")
    parser.add_argument("--icon", help="PNG Base64 icon data or http(s) icon URL for text scenario")
    parser.add_argument("--clock-in", help="Clock in time for work scenario")
    parser.add_argument("--clock-out", help="Clock out time for work scenario")
    parser.add_argument(
        "--image-path", help="Path to PNG image file for image scenario"
    )
    parser.add_argument("--main-title", help="Main title for title_image scenario")
    parser.add_argument("--sub-title", help="Sub title for title_image scenario")
    parser.add_argument(
        "--wakatime-url", help="Wakatime URL for code_status scenario"
    )
    parser.add_argument(
        "--wakatime-api-key", help="Wakatime API key for code_status scenario"
    )
    parser.add_argument(
        "--wakatime-user-id", help="Wakatime user ID for code_status scenario"
    )
    parser.add_argument(
        "--umami-host", help="Umami host URL for umami_stats scenario"
    )
    parser.add_argument(
        "--umami-website-id", help="Umami website ID for umami_stats scenario"
    )
    parser.add_argument(
        "--umami-api-key", help="Umami API key for umami_stats scenario"
    )
    parser.add_argument(
        "--umami-time-range", help="Time range for umami_stats scenario (e.g., 7d, 24h)"
    )
    parser.add_argument(
        "--github-username", help="GitHub username for github_contributions scenario"
    )
    parser.add_argument(
        "--github-token",
        help="GitHub Personal Access Token for github_contributions scenario",
    )
    parser.add_argument(
        "--api-url", help="API base URL for code_plan_usage scenario"
    )
    parser.add_argument(
        "--provider", help="Provider name for code_plan_usage scenario (default: anthropic)"
    )
    parser.add_argument(
        "--api-username", help="Basic auth username for code_plan_usage scenario"
    )
    parser.add_argument(
        "--api-password", help="Basic auth password for code_plan_usage scenario"
    )
    parser.add_argument("--link", help="Optional link for image scenarios")
    parser.add_argument(
        "--border",
        type=int,
        choices=[0, 1],
        help="Optional border color for image scenarios (0=white, 1=black)",
    )
    parser.add_argument(
        "--dither-type",
        choices=["DIFFUSION", "ORDERED", "NONE"],
        help="Dither type for image scenarios",
    )
    parser.add_argument(
        "--dither-kernel",
        choices=[
            "THRESHOLD",
            "ATKINSON",
            "BURKES",
            "FLOYD_STEINBERG",
            "SIERRA2",
            "STUCKI",
            "JARVIS_JUDICE_NINKE",
            "DIFFUSION_ROW",
            "DIFFUSION_COLUMN",
            "DIFFUSION_2D",
        ],
        help="Dither kernel for image scenarios",
    )
    parser.add_argument(
        "--task-key",
        help="Optional Image API task key when multiple Image API contents exist",
    )
    parser.add_argument(
        "--task-alias",
        help="Optional Image API task alias when multiple Image API contents exist",
    )
    parser.add_argument(
        "--page-id",
        help="Optional page ID (1-5) for Zectrix Note 4 image push",
    )


def _collect_scenario_params(args):
    """Collect non-None scenario arguments into a params dict."""
    mapping = {
        "message": "message",
        "title": "title",
        "signature": "signature",
        "icon": "icon",
        "clock_in": "clock_in",
        "clock_out": "clock_out",
        "image_path": "image_path",
        "main_title": "main_title",
        "sub_title": "sub_title",
        "wakatime_url": "wakatime_url",
        "wakatime_api_key": "wakatime_api_key",
        "wakatime_user_id": "wakatime_user_id",
        "umami_host": "umami_host",
        "umami_website_id": "umami_website_id",
        "umami_api_key": "umami_api_key",
        "umami_time_range": "umami_time_range",
        "github_username": "github_username",
        "github_token": "github_token",
        "api_url": "api_url",
        "provider": "provider",
        "api_username": "api_username",
        "api_password": "api_password",
        "link": "link",
        "border": "border",
        "dither_type": "dither_type",
        "dither_kernel": "dither_kernel",
        "task_key": "task_key",
        "task_alias": "task_alias",
        "page_id": "page_id",
    }
    params = {}
    for attr, key in mapping.items():
        value = getattr(args, attr, None)
        if value is not None:
            params[key] = value
    return params


def main():
    """Main function with CLI argument parsing."""
    parser = argparse.ArgumentParser(description="Dotmate - Device message scheduler")
    parser.add_argument("--config", "-c", default="config.yaml", help="Config file path (default: config.yaml)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Daemon command (default)
    subparsers.add_parser("daemon", help="Start the daemon (default)")

    # Force push command
    push_parser = subparsers.add_parser("push", help="Force push update to device")
    push_parser.add_argument("device", help="Device name or device ID")
    push_parser.add_argument(
        "scenario",
        help="Scenario type (e.g., work, text, code_status, image, title_image, umami_stats, github_contributions, code_plan_usage)",
    )
    _add_scenario_args(push_parser)

    # Demo command - generate PNG without sending to device
    demo_parser = subparsers.add_parser("demo", help="Generate demo PNG image without sending to device")
    demo_parser.add_argument(
        "scenario",
        help="Scenario type (e.g., work, text, code_status, image, title_image, umami_stats, github_contributions, code_plan_usage)",
    )
    demo_parser.add_argument("--output", "-o", default="demos", help="Output directory for demo images (default: demos)")
    _add_scenario_args(demo_parser)
    demo_parser.add_argument(
        "--platform",
        choices=PlatformRegistry.available(),
        default="quote0",
        help="Target platform for resolution (quote0=296x152, zectrix=400x300; default: quote0)",
    )

    args = parser.parse_args()

    if args.command == "push":
        push_params = _collect_scenario_params(args)
        force_push(args.device, args.scenario, args.config, **push_params)
    elif args.command == "demo":
        demo_params = _collect_scenario_params(args)
        generate_demo(
            args.scenario,
            args.config,
            args.output,
            platform=args.platform,
            **demo_params,
        )
    else:
        # Default to daemon mode
        start_daemon(args.config)


if __name__ == "__main__":
    main()
