import os
import httpx
from datetime import datetime

_zapier_log: list = []


def get_zapier_log() -> list:
    return _zapier_log[-50:]


def _log(event_type: str, payload: dict, result: str):
    _zapier_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "type": event_type,
        "payload": payload,
        "result": result,
    })
    if len(_zapier_log) > 100:
        _zapier_log.pop(0)


async def trigger_zapier(event: str, data: dict) -> dict:
    """Send data to Zapier webhook (or simulate if URL not set)."""
    zapier_url = os.getenv("ZAPIER_WEBHOOK_URL", "").strip()
    payload = {
        "event": event,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    }

    if not zapier_url:
        result = f"[SIMULATED] Zapier trigger '{event}' fired with {len(data)} fields"
        _log("zapier_trigger", payload, result)
        return {"status": "simulated", "event": event, "message": result, "payload": payload}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(zapier_url, json=payload)
            result = f"Zapier responded {resp.status_code}"
            _log("zapier_trigger", payload, result)
            return {"status": "sent", "zapier_status": resp.status_code, "event": event}
    except Exception as e:
        result = f"Zapier request failed: {str(e)}"
        _log("zapier_error", payload, result)
        return {"status": "error", "message": result}


async def trigger_hot_lead_zap(contact: dict) -> dict:
    """Auto-trigger Zapier when a lead is scored Hot."""
    return await trigger_zapier(
        "hot_lead_detected",
        {
            "contact_name": contact.get("name"),
            "contact_email": contact.get("email"),
            "contact_phone": contact.get("phone"),
            "score": contact.get("score"),
            "notes": contact.get("notes"),
            "action": "schedule_immediate_followup",
        },
    )
