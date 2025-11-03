import argparse
import logging
import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotmate.config import load_config
from dotmate.api.api import DotClient
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

    client = DotClient(config.api_key)
    scheduler = BlockingScheduler()

    # Add jobs for each device and schedule
    for device in config.devices:
        if device.schedules:
            for schedule in device.schedules:
                if schedule.cron is None:
                    print(
                        f"Skipping schedule for device '{device.name}' because cron is None"
                    )
                    continue
                if schedule.type in ViewFactory.get_available_types():
                    # Add job using factory pattern
                    scheduler.add_job(
                        func=ViewFactory.execute_view,
                        trigger=CronTrigger.from_crontab(schedule.cron),
                        args=[schedule.type, client, device.device_id, schedule.params or {}],
                        id=f"{schedule.type}_{device.name}_{schedule.cron}",
                        name=f"{schedule.type.capitalize()} job for {device.name}"
                    )
                    print(f"Scheduled {schedule.type} job for device '{device.name}' with cron: {schedule.cron}")
                else:
                    print(f"Unknown schedule type '{schedule.type}' for device '{device.name}'")

    return scheduler


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print("\nShutdown signal received. Stopping dotmate...")
    sys.exit(0)


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

    client = DotClient(config.api_key)

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

    # Try to find matching schedule for the scenario, but don't require it
    target_schedule = None
    if target_device.schedules:
        for schedule in target_device.schedules:
            if schedule.type == scenario:
                target_schedule = schedule
                break

    # Execute the scenario using factory pattern
    try:
        if scenario in ViewFactory.get_available_types():
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

            print(f"Sending {scenario} message to device '{target_device.name}' ({target_device.device_id})")
            ViewFactory.execute_view(scenario, client, target_device.device_id, scenario_params)
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


def main():
    """Main function with CLI argument parsing."""
    parser = argparse.ArgumentParser(description="Dotmate - Device message scheduler")
    parser.add_argument("--config", "-c", default="config.yaml", help="Config file path (default: config.yaml)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Daemon command (default)
    daemon_parser = subparsers.add_parser("daemon", help="Start the daemon (default)")

    # Force push command
    push_parser = subparsers.add_parser("push", help="Force push update to device")
    push_parser.add_argument("device", help="Device name or device ID")
    push_parser.add_argument(
        "scenario",
        help="Scenario type (e.g., work, text, code_status, image, title_image, umami_stats, github_contributions)",
    )
    push_parser.add_argument("--message", help="Message for text scenario")
    push_parser.add_argument("--title", help="Title for text scenario")
    push_parser.add_argument("--clock-in", help="Clock in time for work scenario")
    push_parser.add_argument("--clock-out", help="Clock out time for work scenario")
    push_parser.add_argument(
        "--image-path", help="Path to PNG image file for image scenario"
    )
    push_parser.add_argument("--main-title", help="Main title for title_image scenario")
    push_parser.add_argument("--sub-title", help="Sub title for title_image scenario")
    push_parser.add_argument(
        "--wakatime-url", help="Wakatime URL for code_status scenario"
    )
    push_parser.add_argument(
        "--wakatime-api-key", help="Wakatime API key for code_status scenario"
    )
    push_parser.add_argument(
        "--wakatime-user-id", help="Wakatime user ID for code_status scenario"
    )
    push_parser.add_argument(
        "--umami-host", help="Umami host URL for umami_stats scenario"
    )
    push_parser.add_argument(
        "--umami-website-id", help="Umami website ID for umami_stats scenario"
    )
    push_parser.add_argument(
        "--umami-api-key", help="Umami API key for umami_stats scenario"
    )
    push_parser.add_argument(
        "--umami-time-range", help="Time range for umami_stats scenario (e.g., 7d, 24h)"
    )
    push_parser.add_argument(
        "--github-username", help="GitHub username for github_contributions scenario"
    )
    push_parser.add_argument(
        "--github-token",
        help="GitHub Personal Access Token for github_contributions scenario",
    )
    push_parser.add_argument("--link", help="Optional link for image scenarios")
    push_parser.add_argument(
        "--border", type=int, help="Optional border color for image scenarios"
    )
    push_parser.add_argument(
        "--dither-type",
        choices=["DIFFUSION", "ORDERED", "NONE"],
        help="Dither type for image scenarios",
    )
    push_parser.add_argument(
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
            "DIFFUSION2_D",
        ],
        help="Dither kernel for image scenarios",
    )

    args = parser.parse_args()

    if args.command == "push":
        # Prepare parameters for force_push
        push_params = {}
        if args.message:
            push_params['message'] = args.message
        if args.title:
            push_params['title'] = args.title
        if args.clock_in:
            push_params['clock_in'] = args.clock_in
        if args.clock_out:
            push_params['clock_out'] = args.clock_out
        if args.image_path:
            push_params["image_path"] = args.image_path
        if args.main_title:
            push_params["main_title"] = args.main_title
        if args.sub_title:
            push_params["sub_title"] = args.sub_title
        if args.wakatime_url:
            push_params["wakatime_url"] = args.wakatime_url
        if args.wakatime_api_key:
            push_params["wakatime_api_key"] = args.wakatime_api_key
        if args.wakatime_user_id:
            push_params["wakatime_user_id"] = args.wakatime_user_id
        if args.umami_host:
            push_params["umami_host"] = args.umami_host
        if args.umami_website_id:
            push_params["umami_website_id"] = args.umami_website_id
        if args.umami_api_key:
            push_params["umami_api_key"] = args.umami_api_key
        if args.umami_time_range:
            push_params["umami_time_range"] = args.umami_time_range
        if args.github_username:
            push_params["github_username"] = args.github_username
        if args.github_token:
            push_params["github_token"] = args.github_token
        if args.link:
            push_params["link"] = args.link
        if args.border:
            push_params["border"] = args.border
        if args.dither_type:
            push_params["dither_type"] = args.dither_type
        if args.dither_kernel:
            push_params["dither_kernel"] = args.dither_kernel

        force_push(args.device, args.scenario, args.config, **push_params)
    else:
        # Default to daemon mode
        start_daemon(args.config)


if __name__ == "__main__":
    main()
