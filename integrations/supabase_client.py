import os
from supabase import create_client, Client
from typing import Optional

_client: Optional[Client] = None

DEMO_CONTACTS = [
    {
        "id": "demo-001",
        "name": "Sarah Johnson",
        "email": "sarah@techcorp.com",
        "phone": "+1-555-0101",
        "score": "Hot",
        "status": "qualified",
        "notes": "Interested in enterprise plan, has budget approved",
        "created_at": "2024-01-15T10:00:00Z",
    },
    {
        "id": "demo-002",
        "name": "Mike Chen",
        "email": "mike@startup.io",
        "phone": "+1-555-0102",
        "score": "Warm",
        "status": "prospect",
        "notes": "Evaluating competitors, follow up next week",
        "created_at": "2024-01-20T14:30:00Z",
    },
    {
        "id": "demo-003",
        "name": "Emma Wilson",
        "email": "emma@agency.co",
        "phone": "+1-555-0103",
        "score": "Cold",
        "status": "new",
        "notes": "Downloaded whitepaper, no further engagement",
        "created_at": "2024-01-22T09:15:00Z",
    },
]

DEMO_APPOINTMENTS = [
    {"datetime": "2024-02-01 09:00", "status": "available"},
    {"datetime": "2024-02-01 11:00", "status": "booked"},
    {"datetime": "2024-02-01 14:00", "status": "available"},
    {"datetime": "2024-02-02 10:00", "status": "available"},
    {"datetime": "2024-02-02 15:00", "status": "booked"},
]


def get_supabase() -> Optional[Client]:
    global _client
    if _client:
        return _client
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if url and key and not url.startswith("https://your-project"):
        try:
            _client = create_client(url, key)
            return _client
        except Exception:
            return None
    return None


def is_demo_mode() -> bool:
    return get_supabase() is None


async def get_contacts(limit: int = 50) -> list:
    db = get_supabase()
    if db is None:
        return DEMO_CONTACTS
    try:
        result = db.table("contacts").select("*").limit(limit).execute()
        return result.data or DEMO_CONTACTS
    except Exception:
        return DEMO_CONTACTS


async def get_contact_by_id(contact_id: str) -> Optional[dict]:
    db = get_supabase()
    if db is None:
        return next((c for c in DEMO_CONTACTS if c["id"] == contact_id), None)
    try:
        result = db.table("contacts").select("*").eq("id", contact_id).single().execute()
        return result.data
    except Exception:
        return next((c for c in DEMO_CONTACTS if c["id"] == contact_id), None)


async def search_contact(query: str) -> list:
    db = get_supabase()
    q = query.lower()
    if db is None:
        return [c for c in DEMO_CONTACTS if q in c["email"].lower() or q in c["name"].lower() or q in c.get("phone", "")]
    try:
        result = (
            db.table("contacts")
            .select("*")
            .or_(f"email.ilike.%{query}%,name.ilike.%{query}%,phone.ilike.%{query}%")
            .execute()
        )
        return result.data or []
    except Exception:
        return [c for c in DEMO_CONTACTS if q in c["email"].lower() or q in c["name"].lower()]


async def upsert_contact(data: dict) -> dict:
    db = get_supabase()
    if db is None:
        existing = next((c for c in DEMO_CONTACTS if c.get("email") == data.get("email")), None)
        if existing:
            existing.update(data)
            return existing
        new_contact = {"id": f"demo-{len(DEMO_CONTACTS)+1:03d}", **data}
        DEMO_CONTACTS.append(new_contact)
        return new_contact
    try:
        result = db.table("contacts").upsert(data, on_conflict="email").execute()
        return result.data[0] if result.data else data
    except Exception:
        return data


async def log_interaction(contact_id: str, interaction_type: str, content: str, agent_response: str) -> dict:
    db = get_supabase()
    record = {
        "contact_id": contact_id,
        "type": interaction_type,
        "content": content,
        "agent_response": agent_response,
    }
    if db is None:
        return record
    try:
        result = db.table("interactions").insert(record).execute()
        return result.data[0] if result.data else record
    except Exception:
        return record


async def get_appointments() -> list:
    db = get_supabase()
    if db is None:
        return DEMO_APPOINTMENTS
    try:
        result = db.table("appointments").select("*").execute()
        return result.data or DEMO_APPOINTMENTS
    except Exception:
        return DEMO_APPOINTMENTS
