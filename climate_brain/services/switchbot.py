"""SwitchBot API client for device control and sensor reading."""

import hashlib
import hmac
import base64
import time
import uuid
import httpx
from climate_brain.config import settings

BASE_URL = "https://api.switch-bot.com/v1.1"


def _make_headers() -> dict:
    """Generate authenticated headers for SwitchBot API v1.1."""
    token = settings.switchbot_token
    secret = settings.switchbot_secret
    nonce = uuid.uuid4().hex
    t = int(round(time.time() * 1000))
    string_to_sign = f"{token}{t}{nonce}"
    sign = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            msg=string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    return {
        "Authorization": token,
        "sign": sign,
        "nonce": nonce,
        "t": str(t),
        "Content-Type": "application/json",
    }


async def get_devices() -> dict:
    """List all SwitchBot devices on the account."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/devices", headers=_make_headers())
        resp.raise_for_status()
        data = resp.json()
        if data.get("statusCode") != 100:
            raise Exception(f"SwitchBot API error: {data}")
        return data["body"]


async def get_device_status(device_id: str) -> dict:
    """Get current status of a device (temperature, humidity, etc.)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/devices/{device_id}/status",
            headers=_make_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("statusCode") != 100:
            raise Exception(f"SwitchBot API error: {data}")
        return data["body"]


async def send_ir_command(device_id: str, command: str, parameter: str = "default",
                          command_type: str = "command") -> dict:
    """
    Send an IR command through a SwitchBot Hub.

    For AC control, the command format is:
      command_type: "command"
      command: "setAll"
      parameter: "{temp},{mode},{fan_speed},{power_state}"

    Example: "26,1,3,on"
      - temp: 26
      - mode: 1=auto, 2=cool, 3=dry, 4=fan, 5=heat
      - fan_speed: 1=auto, 2=low, 3=medium, 4=high
      - power_state: on/off
    """
    payload = {
        "commandType": command_type,
        "command": command,
        "parameter": parameter,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/devices/{device_id}/commands",
            headers=_make_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("statusCode") != 100:
            raise Exception(f"SwitchBot command error: {data}")
        return data["body"]


async def send_custom_ir(device_id: str, learned_code: str) -> dict:
    """Send a custom learned IR code."""
    return await send_ir_command(
        device_id=device_id,
        command=learned_code,
        command_type="customize",
    )


# === Convenience functions for AC control ===

MODE_MAP = {
    "auto": 1, "cool": 2, "dry": 3, "fan": 4, "heat": 5,
}
MODE_MAP_REVERSE = {v: k for k, v in MODE_MAP.items()}

FAN_MAP = {
    "auto": 1, "low": 2, "medium": 3, "high": 4,
}
FAN_MAP_REVERSE = {v: k for k, v in FAN_MAP.items()}


async def set_ac(device_id: str, temperature: int, mode: str = "cool",
                 fan_speed: str = "auto", power: str = "on") -> dict:
    """
    Set AC state via SwitchBot Hub IR.

    Args:
        device_id: SwitchBot Hub device ID
        temperature: Target temperature (16-30)
        mode: auto, cool, dry, fan, heat
        fan_speed: auto, low, medium, high
        power: on, off
    """
    mode_code = MODE_MAP.get(mode, 2)
    fan_code = FAN_MAP.get(fan_speed, 1)
    parameter = f"{temperature},{mode_code},{fan_code},{power}"
    return await send_ir_command(device_id, "setAll", parameter)


async def turn_off_ac(device_id: str) -> dict:
    """Turn off AC."""
    return await send_ir_command(device_id, "turnOff")


async def get_meter_reading(device_id: str) -> dict:
    """Get temperature and humidity from a SwitchBot Meter."""
    status = await get_device_status(device_id)
    return {
        "temperature": status.get("temperature"),
        "humidity": status.get("humidity"),
    }
