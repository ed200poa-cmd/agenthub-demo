import os
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from agent.agent import run_agent
from agent.memory import get_history, clear_session, list_sessions
from integrations.supabase_client import (
    get_contacts,
    get_contact_by_id,
    upsert_contact,
    is_demo_mode,
)
from integrations.ghl_webhook import sync_contact_to_ghl, update_pipeline_stage, get_event_log
from integrations.zapier_webhook import trigger_zapier, trigger_hot_lead_zap, get_zapier_log


@asynccontextmanager
async def lifespan(app: FastAPI):
    mode = "DEMO" if is_demo_mode() else "LIVE (Supabase)"
    print(f"AgentHub started — Mode: {mode}")
    yield


app = FastAPI(
    title="AgentHub — AI CRM Automation Platform",
    description="LangChain + Claude + Supabase + GoHighLevel + Zapier",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Request/Response Models ───────────────────────────────────────────────

class AgentRequest(BaseModel):
    message: str
    session_id: str = ""


class ContactCreate(BaseModel):
    name: str
    email: str
    phone: str = ""
    score: str = "Cold"
    status: str = "new"
    notes: str = ""


class WebhookGHL(BaseModel):
    type: str = "contact.created"
    data: dict = {}


class WebhookZapier(BaseModel):
    event: str
    data: dict = {}


class WebhookForm(BaseModel):
    name: str
    email: str
    phone: str = ""
    message: str = ""


# ─── Routes ────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": "demo" if is_demo_mode() else "live",
        "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        "supabase_connected": not is_demo_mode(),
    }


@app.post("/agent/run")
async def agent_run(req: AgentRequest):
    """Run the AI agent with a user message."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")
    session_id = req.session_id or str(uuid.uuid4())
    try:
        result = await run_agent(session_id, req.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/history/{session_id}")
async def agent_history(session_id: str):
    """Get conversation history for a session."""
    return {"session_id": session_id, "history": get_history(session_id)}


@app.delete("/agent/session/{session_id}")
async def clear_agent_session(session_id: str):
    clear_session(session_id)
    return {"cleared": session_id}


@app.get("/agent/sessions")
async def agent_sessions():
    return {"sessions": list_sessions()}


@app.get("/contacts")
async def list_contacts():
    """List all contacts from Supabase (or demo data)."""
    contacts = await get_contacts()
    return {"contacts": contacts, "mode": "demo" if is_demo_mode() else "live", "count": len(contacts)}


@app.get("/contacts/{contact_id}")
async def get_contact(contact_id: str):
    """Get a single contact with AI analysis."""
    contact = await get_contact_by_id(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"contact": contact, "mode": "demo" if is_demo_mode() else "live"}


@app.post("/contacts")
async def create_contact(data: ContactCreate):
    """Create or update a contact."""
    contact = await upsert_contact(data.model_dump())
    return {"contact": contact, "mode": "demo" if is_demo_mode() else "live"}


@app.post("/webhook/gohighlevel")
async def webhook_ghl(payload: WebhookGHL):
    """Receive GoHighLevel CRM webhook events."""
    contact_data = payload.data
    event_type = payload.type

    if event_type in ("contact.created", "contact.updated") and contact_data.get("email"):
        saved = await upsert_contact({
            "name": f"{contact_data.get('firstName', '')} {contact_data.get('lastName', '')}".strip(),
            "email": contact_data.get("email"),
            "phone": contact_data.get("phone", ""),
            "status": "ghl_import",
        })
        return {"status": "processed", "event": event_type, "contact": saved}

    return {"status": "received", "event": event_type}


@app.post("/webhook/zapier")
async def webhook_zapier(payload: WebhookZapier):
    """Receive Zapier workflow triggers."""
    event = payload.event
    data = payload.data

    if event == "new_lead" and data.get("email"):
        contact = await upsert_contact({
            "name": data.get("name", ""),
            "email": data.get("email"),
            "phone": data.get("phone", ""),
            "status": "zapier_import",
        })
        return {"status": "processed", "event": event, "contact": contact}

    return {"status": "received", "event": event, "data": data}


@app.post("/webhook/form")
async def webhook_form(payload: WebhookForm):
    """Handle new lead form submissions."""
    contact = await upsert_contact({
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "notes": payload.message,
        "status": "form_submission",
        "score": "Cold",
    })
    await sync_contact_to_ghl(contact)
    return {"status": "received", "contact": contact, "message": "Lead captured and synced to CRM"}


@app.get("/events/ghl")
async def ghl_event_log():
    return {"events": get_event_log()}


@app.get("/events/zapier")
async def zapier_event_log():
    return {"events": get_zapier_log()}


@app.post("/demo/trigger-zapier")
async def demo_trigger_zapier():
    """Demo button: fire a test Zapier hot lead event."""
    result = await trigger_hot_lead_zap({
        "name": "Demo Lead",
        "email": "demo@example.com",
        "phone": "+1-555-0199",
        "score": "Hot",
        "notes": "Demo trigger from AgentHub dashboard",
    })
    return {"status": "triggered", "result": result}


@app.post("/demo/sync-ghl")
async def demo_sync_ghl():
    """Demo button: sync a test contact to GHL."""
    result = await sync_contact_to_ghl({
        "name": "Demo Contact",
        "email": "demo@example.com",
        "phone": "+1-555-0199",
        "score": "Hot",
        "notes": "Demo sync from AgentHub dashboard",
    })
    pipeline = await update_pipeline_stage("demo-contact", "Hot")
    return {"sync": result, "pipeline": pipeline}
