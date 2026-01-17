"""
Zotero URL Saver - macOS AppleScript Edition

Opens URLs in your existing Firefox and saves to Zotero.
Supports waiting for manual authentication (Duo push, etc).

Usage:
    zotero-save <url>                    # Interactive mode
    zotero-save --auto 10 <url>          # Auto-save after 10 seconds
    zotero-save --no-open <placeholder>  # Save current tab
"""

import argparse
import subprocess
import sys
import time

# Optional: for Zotero ping check
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

DEFAULT_ZOTERO_PORT = 23119


def check_zotero_running(port: int = DEFAULT_ZOTERO_PORT) -> bool:
    """Check if Zotero desktop is running via connector ping."""
    if not REQUESTS_AVAILABLE:
        # Can't check, assume it's running
        return True
    try:
        r = requests.get(
            f"http://127.0.0.1:{port}/connector/ping",
            timeout=2
        )
        return r.status_code == 200
    except Exception:
        return False


def run_applescript(script: str) -> str:
    """Execute AppleScript and return output."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript error: {result.stderr}")
    return result.stdout.strip()


def open_url_in_firefox(url: str):
    """Open URL in Firefox (new tab if already running)."""
    # Use subprocess to open URL in Firefox
    result = subprocess.run(
        ["open", "-a", "Firefox", url],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Error opening URL: {result.stderr}")

    # Give Firefox time to open the tab, then activate it
    import time
    time.sleep(0.5)

    # Activate Firefox
    activate_script = 'tell application "Firefox" to activate'
    run_applescript(activate_script)


def trigger_zotero_save(shortcut: str = "cmd+shift+z"):
    """Send keyboard shortcut to trigger Zotero Connector save.

    Args:
        shortcut: Keyboard shortcut like "cmd+shift+s" or "ctrl+shift+z"
    """
    # Parse shortcut string into AppleScript modifiers
    parts = shortcut.lower().split("+")
    key = parts[-1]
    modifiers = parts[:-1]

    modifier_map = {
        "cmd": "command down",
        "command": "command down",
        "shift": "shift down",
        "ctrl": "control down",
        "control": "control down",
        "alt": "option down",
        "option": "option down",
    }

    applescript_modifiers = [modifier_map.get(m, m) for m in modifiers]
    modifiers_str = ", ".join(applescript_modifiers)

    script = f'''
    tell application "Firefox"
        activate
    end tell
    delay 0.5
    tell application "System Events"
        keystroke "{key}" using {{{modifiers_str}}}
    end tell
    '''
    run_applescript(script)


def main():
    parser = argparse.ArgumentParser(
        description="Save URLs to Zotero via Firefox + Zotero Connector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://arxiv.org/abs/2301.07041"
      Open URL, wait for Enter, then save to Zotero

  %(prog)s --auto 10 "https://arxiv.org/abs/2301.07041"
      Open URL, wait 10 seconds, then save to Zotero

  %(prog)s --no-open placeholder
      Save the current Firefox tab to Zotero

Prerequisites:
  - macOS (uses AppleScript)
  - Firefox with Zotero Connector extension
  - Zotero desktop app running
        """
    )

    parser.add_argument(
        "url",
        help="URL to save (or placeholder if using --no-open)"
    )
    parser.add_argument(
        "--auto", "-a",
        type=int,
        metavar="SECONDS",
        help="Auto-save after N seconds instead of waiting for Enter"
    )
    parser.add_argument(
        "--no-open", "-n",
        action="store_true",
        help="Don't open URL (assume it's already open in Firefox)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_ZOTERO_PORT,
        help=f"Zotero connector port (default: {DEFAULT_ZOTERO_PORT})"
    )
    parser.add_argument(
        "--shortcut", "-s",
        default="option+cmd+s",
        help="Zotero Connector keyboard shortcut (default: option+cmd+s). "
             "Check Firefox Add-ons > gear icon > Manage Extension Shortcuts."
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip checking if Zotero is running"
    )

    args = parser.parse_args()

    # Check prerequisites
    if not args.skip_check and not check_zotero_running(args.port):
        print(f"Error: Zotero is not running on port {args.port}. Please start Zotero first.")
        print("(Use --skip-check to bypass this check, or --port to specify a different port)")
        sys.exit(1)

    # Open URL in Firefox
    if not args.no_open:
        print(f"Opening: {args.url}")
        try:
            open_url_in_firefox(args.url)
        except RuntimeError as e:
            print(f"Error opening URL: {e}")
            sys.exit(1)

    # Wait for auth/page load
    if args.auto:
        print(f"Waiting {args.auto} seconds for page to load...")
        time.sleep(args.auto)
    else:
        try:
            if sys.stdin.isatty():
                input("Press Enter when page is loaded and ready to save...")
            else:
                # Non-interactive mode, default to 5 second wait
                print("Non-interactive mode: waiting 5 seconds...")
                time.sleep(5)
        except EOFError:
            # stdin closed, default to 5 second wait
            print("No stdin available: waiting 5 seconds...")
            time.sleep(5)

    # Trigger Zotero save
    print(f"Triggering Zotero save ({args.shortcut})...")
    try:
        trigger_zotero_save(args.shortcut)
    except RuntimeError as e:
        print(f"Error triggering save: {e}")
        sys.exit(1)

    print("Done! Check Zotero for the saved item.")


if __name__ == "__main__":
    main()
