"""Device Pairing and Remote Execution Manager for NOVA."""

import time
import uuid
import secrets
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("nova.remote")

PAIRING_CODE_TTL_SECONDS = 300  # 5 minutes
DEVICE_OFFLINE_THRESHOLD_SECONDS = 35.0


class DeviceManager:
    """Manages paired Windows computers and remote execution dispatching."""

    def __init__(self, token_manager, audit_logger):
        self.token_manager = token_manager
        self.audit_logger = audit_logger

        # Ephemeral active pairing codes: code -> {expires_at, device_id, device_name}
        self.pending_pairing_codes: Dict[str, Dict[str, Any]] = {}

        # Registered paired devices: device_id -> device dict
        self.paired_devices: Dict[str, Dict[str, Any]] = {}

        # Register the primary local Windows agent as the default device
        local_id = "local-agent-win11"
        self.paired_devices[local_id] = {
            "device_id": local_id,
            "device_name": "Local Windows PC",
            "os": "Windows 11",
            "status": "online",
            "paired_at": datetime.now(timezone.utc).isoformat(),
            "last_seen": time.time(),
            "ip_address": "127.0.0.1",
            "device_key": secrets.token_hex(24),
            "capabilities": ["desktop_automation", "browser_automation", "filesystem", "voice", "system_monitor"],
        }

    def generate_pairing_code(self, device_id: Optional[str] = None, device_name: str = "Windows PC") -> str:
        """Generate a cryptographically random 6-character pairing code with 5-min TTL."""
        # Clean expired codes
        now = time.time()
        self.pending_pairing_codes = {
            c: info for c, info in self.pending_pairing_codes.items() if info["expires_at"] > now
        }

        # Format: NOVA-XXXX (e.g. NOVA-7829)
        random_suffix = secrets.randbelow(9000) + 1000
        code = f"NOVA-{random_suffix}"

        dev_id = device_id or str(uuid.uuid4())
        self.pending_pairing_codes[code] = {
            "code": code,
            "device_id": dev_id,
            "device_name": device_name,
            "created_at": now,
            "expires_at": now + PAIRING_CODE_TTL_SECONDS,
        }
        return code

    def confirm_pairing(self, code: str, client_ip: str) -> Optional[Tuple[Dict[str, Any], str]]:
        """Validate pairing code, register device, and return device info + auth token."""
        now = time.time()
        code_upper = code.strip().upper()

        if code_upper not in self.pending_pairing_codes:
            self.audit_logger.log("DEVICE_PAIR_FAILED", "unknown", client_ip, False, {"code": code_upper, "reason": "invalid_code"})
            return None

        info = self.pending_pairing_codes[code_upper]
        if info["expires_at"] < now:
            del self.pending_pairing_codes[code_upper]
            self.audit_logger.log("DEVICE_PAIR_FAILED", "unknown", client_ip, False, {"code": code_upper, "reason": "code_expired"})
            return None

        dev_id = info["device_id"]
        dev_name = info["device_name"]

        # Register or update paired device
        device_entry = {
            "device_id": dev_id,
            "device_name": dev_name,
            "os": "Windows 11",
            "status": "online",
            "paired_at": datetime.now(timezone.utc).isoformat(),
            "last_seen": now,
            "ip_address": client_ip,
            "device_key": secrets.token_hex(24),
            "capabilities": ["desktop_automation", "browser_automation", "filesystem", "system_monitor"],
        }
        self.paired_devices[dev_id] = device_entry
        del self.pending_pairing_codes[code_upper]

        # Issue short-lived access token for the paired device
        token = self.token_manager.create_token({
            "sub": dev_id,
            "device_name": dev_name,
            "role": "paired_device",
        })

        self.audit_logger.log("DEVICE_PAIRED", dev_id, client_ip, True, {"device_name": dev_name})
        return device_entry, token

    def record_heartbeat(self, device_id: str) -> bool:
        """Update last seen timestamp for a paired device."""
        if device_id in self.paired_devices:
            self.paired_devices[device_id]["last_seen"] = time.time()
            self.paired_devices[device_id]["status"] = "online"
            return True
        return False

    def list_devices(self) -> List[Dict[str, Any]]:
        """List all paired devices and dynamically compute online/offline status."""
        now = time.time()
        results = []
        for dev in self.paired_devices.values():
            is_online = (now - dev.get("last_seen", 0)) < DEVICE_OFFLINE_THRESHOLD_SECONDS
            results.append({
                "device_id": dev["device_id"],
                "device_name": dev["device_name"],
                "os": dev["os"],
                "status": "online" if is_online else "offline",
                "paired_at": dev["paired_at"],
                "last_seen_seconds_ago": int(now - dev.get("last_seen", 0)),
                "capabilities": dev.get("capabilities", []),
            })
        return results

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get info for a single device."""
        dev = self.paired_devices.get(device_id)
        if not dev:
            return None
        now = time.time()
        is_online = (now - dev.get("last_seen", 0)) < DEVICE_OFFLINE_THRESHOLD_SECONDS
        return {
            **dev,
            "status": "online" if is_online else "offline",
        }
