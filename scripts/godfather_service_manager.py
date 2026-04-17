#!/usr/bin/env python3
"""Godfather Service Manager - Unified launchd service management"""
import json
import subprocess
from pathlib import Path
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))

SERVICES_DIR = (_REPO_ROOT / 'config/services')
LAUNCH_AGENTS_DIR = Path.home() / "Library/LaunchAgents"

def load_services():
    services = []
    for f in SERVICES_DIR.glob("*.json"):
        with open(f) as h:
            services.append(json.load(h))
    return services

def generate_plist(svc):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{svc['label']}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{svc['entry_script']}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{svc['root_dir']}</string>
    <key>RunAtLoad</key>
    <{'true' if svc['run_at_load'] else 'false'}/>
    <key>KeepAlive</key>
    <{'true' if svc['keep_alive'] else 'false'}/>
    <key>StandardOutPath</key>
    <string>{svc['stdout_log']}</string>
    <key>StandardErrorPath</key>
    <string>{svc['stderr_log']}</string>
</dict>
</plist>
"""

def sync():
    """Generate all plist files from service configs"""
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    services = load_services()
    for svc in services:
        plist_path = LAUNCH_AGENTS_DIR / f"{svc['label']}.plist"
        plist_path.write_text(generate_plist(svc))
        print(f"✓ {svc['service_name']}: {plist_path}")
    print(f"\n✓ Generated {len(services)} plist files")

def bootstrap():
    """Bootstrap all enabled services"""
    services = [s for s in load_services() if s['enabled']]
    for svc in services:
        label = svc['label']
        subprocess.run(["launchctl", "bootout", f"gui/{Path.home().stat().st_uid}/{label}"],
                      capture_output=True)
        result = subprocess.run(["launchctl", "bootstrap", f"gui/{Path.home().stat().st_uid}",
                               str(LAUNCH_AGENTS_DIR / f"{label}.plist")],
                              capture_output=True, text=True)
        status = "✓" if result.returncode == 0 else "✗"
        print(f"{status} {svc['service_name']}")
    print(f"\n✓ Bootstrapped {len(services)} services")

def restart():
    """Restart all enabled services"""
    services = [s for s in load_services() if s['enabled']]
    for svc in services:
        result = subprocess.run(["launchctl", "kickstart", "-k",
                               f"gui/{Path.home().stat().st_uid}/{svc['label']}"],
                              capture_output=True, text=True)
        status = "✓" if result.returncode == 0 else "✗"
        print(f"{status} {svc['service_name']}")
    print(f"\n✓ Restarted {len(services)} services")

def status():
    """Check status of all services"""
    services = load_services()
    for svc in services:
        result = subprocess.run(["launchctl", "print",
                               f"gui/{Path.home().stat().st_uid}/{svc['label']}"],
                              capture_output=True, text=True)
        state = "running" if result.returncode == 0 else "stopped"
        enabled = "✓" if svc['enabled'] else "✗"
        print(f"{enabled} {svc['service_name']:15} [{state}]")

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"sync": sync, "bootstrap": bootstrap, "restart": restart, "status": status}[cmd]()
