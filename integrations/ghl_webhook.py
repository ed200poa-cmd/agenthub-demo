import os
import httpx
import json
from datetime import datetime

_event_log: list = []


def get_event_log() -> list:
    return _event_log[-50:]


def _log_event(event_type: str, payload: dict, result: str):
    _event_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "type": event_type,
        "payload": payload,
        "result": result,
    })
    if len(_event_log) > 100:
        _event_log.pop(0)


async def sync_contact_to_ghl(contact: dict) -> dict:
    """Push contact to GoHighLevel CRM (or simulate if URL not set)."""
    ghl_url = os.getenv("GHL_WEBHOOK_URL", "").strip()
    payload = {
        "type": "contact.created",
        "data": {
            "firstName": contact.get("name", "").split()[0] if contact.get("name") else "",
            "lastName": " ".join(contact.get("name", "").split()[1:]) if contact.get("name") else "",
            "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
            "tags": [f"lead-score-{contact.get('score', 'cold').lower()}"],
            "customFields": {
                "ai_score": contact.get("score", "Cold"),
                "notes": contact.get("notes", ""),
            },
        },
    }

    if not ghl_url:
        result = f"[SIMULATED] Contact {contact.get('email')} synced to GoHighLevel — score: {contact.get('score', 'Unknown')}"
        _log_event("ghl_sync", payload, result)
        return {"status": "simulated", "message": result, "payload": payload}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(ghl_url, json=payload)
            result = f"GHL responded {resp.status_code}"
            _log_event("ghl_sync", payload, result)
            return {"status": "sent", "ghl_status": resp.status_code, "payload": payload}
    except Exception as e:
        result = f"GHL request failed: {str(e)}"
        _log_event("ghl_sync_error", payload, result)
        return {"status": "error", "message": result}


async def update_pipeline_stage(contact_id: str, score: str) -> dict:
    """Move contact to the appropriate pipeline stage based on AI score."""
    stage_map = {"Hot": "demo_scheduled", "Warm": "nurturing", "Cold": "cold_leads"}
    stage = stage_map.get(score, "cold_leads")
    payload = {"contactId": contact_id, "pipelineStage": stage, "score": score}
    ghl_url = os.getenv("GHL_WEBHOOK_URL", "").strip()

    if not ghl_url:
        result = f"[SIMULATED] Pipeline stage updated to '{stage}' for contact {contact_id}"
        _log_event("ghl_pipeline_update", payload, result)
        return {"status": "simulated", "stage": stage, "message": result}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(ghl_url, json={"type": "contact.stage_changed", "data": payload})
            result = f"GHL pipeline update responded {resp.status_code}"
            _log_event("ghl_pipeline_update", payload, result)
            return {"status": "sent", "stage": stage, "ghl_status": resp.status_code}
    except Exception as e:
        result = f"GHL pipeline update failed: {str(e)}"
        _log_event("ghl_pipeline_error", payload, result)
        return {"status": "error", "message": result}
