import json
import asyncio
from langchain.tools import tool
from integrations.supabase_client import search_contact, upsert_contact, get_appointments
from integrations.ghl_webhook import sync_contact_to_ghl, update_pipeline_stage
from integrations.zapier_webhook import trigger_zapier


def _run_async(coro):
    """Run async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@tool
def crm_lookup(query: str) -> str:
    """Search for a contact in the CRM by name, email, or phone number.
    Input: a name, email address, or phone number to search for.
    Returns: matching contact records with score and status."""
    results = _run_async(search_contact(query))
    if not results:
        return f"No contacts found matching '{query}'."
    output = []
    for c in results:
        output.append(
            f"- {c['name']} | {c['email']} | {c.get('phone', 'N/A')} | Score: {c.get('score', 'Unknown')} | Status: {c.get('status', 'Unknown')}\n  Notes: {c.get('notes', '')}"
        )
    return f"Found {len(results)} contact(s):\n" + "\n".join(output)


@tool
def lead_scorer(contact_info: str) -> str:
    """Score a lead as Hot, Warm, or Cold based on their profile information.
    Input: JSON string with contact details (name, email, notes, status, interactions).
    Returns: score (Hot/Warm/Cold) with reasoning."""
    try:
        data = json.loads(contact_info) if contact_info.startswith("{") else {"info": contact_info}
    except json.JSONDecodeError:
        data = {"info": contact_info}

    notes = data.get("notes", data.get("info", "")).lower()
    status = data.get("status", "").lower()

    hot_signals = ["budget approved", "demo scheduled", "ready to buy", "enterprise", "urgent", "asap", "this week"]
    warm_signals = ["evaluating", "interested", "follow up", "considering", "next week", "next month"]
    cold_signals = ["downloaded", "whitepaper", "no engagement", "unsubscribed", "not interested"]

    hot_count = sum(1 for s in hot_signals if s in notes or s in status)
    warm_count = sum(1 for s in warm_signals if s in notes or s in status)
    cold_count = sum(1 for s in cold_signals if s in notes or s in status)

    if hot_count > 0 or status in ["qualified", "demo_scheduled"]:
        score = "Hot"
        reason = "Shows strong buying intent (budget approval, enterprise interest, or qualified status)"
    elif warm_count > 0 or status in ["prospect", "nurturing"]:
        score = "Warm"
        reason = "Has shown interest but is still evaluating — needs nurturing"
    else:
        score = "Cold"
        reason = "Early stage, minimal engagement, or only passive interaction"

    return f"Lead Score: {score}\nReason: {reason}\nSignals detected — Hot: {hot_count}, Warm: {warm_count}, Cold: {cold_count}"


@tool
def email_drafter(contact_json: str) -> str:
    """Draft a personalized follow-up email for a contact.
    Input: JSON string with contact name, score, and notes.
    Returns: a ready-to-send email subject and body."""
    try:
        data = json.loads(contact_json) if contact_json.startswith("{") else {"name": contact_json, "score": "Warm"}
    except json.JSONDecodeError:
        data = {"name": contact_json, "score": "Warm"}

    name = data.get("name", "there")
    first_name = name.split()[0] if name and name != "there" else "there"
    score = data.get("score", "Warm")
    notes = data.get("notes", "")

    if score == "Hot":
        subject = f"Let's schedule your personalized demo, {first_name}"
        body = f"""Hi {first_name},

I noticed you've been exploring our platform and I wanted to reach out personally.

Based on your interest in our enterprise offering, I'd love to set up a 30-minute personalized demo to show you exactly how we can help your team.

I have availability this week — would Tuesday at 2pm or Wednesday at 10am work for you?

Looking forward to connecting!

Best,
Edward Kim
AI Automation Specialist"""
    elif score == "Warm":
        subject = f"Quick question about your automation goals, {first_name}"
        body = f"""Hi {first_name},

Hope you're doing well! I wanted to follow up and see how your evaluation is going.

Many teams in your space are using AI automation to cut manual CRM work by 60%+ — I'd love to share how we can help you achieve similar results.

Would a quick 15-minute call this week make sense? No pressure, just a conversation.

{f"Note: {notes}" if notes else ""}

Best,
Edward Kim
AI Automation Specialist"""
    else:
        subject = f"Resources to help with your automation journey, {first_name}"
        body = f"""Hi {first_name},

Thanks for your interest in AI-powered CRM automation!

I wanted to share a few resources that our most successful customers found helpful when getting started:
• Case study: How TechCorp automated 80% of their lead scoring
• Guide: Setting up your first AI agent in under an hour
• Webinar replay: AI + CRM automation best practices

Feel free to reply with any questions — I'm here to help!

Best,
Edward Kim
AI Automation Specialist"""

    return f"Subject: {subject}\n\n{body}"


@tool
def calendar_checker(date_range: str = "this week") -> str:
    """Check available appointment slots for booking meetings.
    Input: optional date range like 'this week', 'tomorrow', or 'next week'.
    Returns: list of available time slots."""
    appointments = _run_async(get_appointments())
    available = [a for a in appointments if a.get("status") == "available"]
    booked = [a for a in appointments if a.get("status") == "booked"]

    result = f"Availability for {date_range}:\n"
    result += f"\nAvailable slots ({len(available)}):\n"
    for slot in available:
        result += f"  ✓ {slot['datetime']}\n"
    result += f"\nBooked slots ({len(booked)}):\n"
    for slot in booked:
        result += f"  ✗ {slot['datetime']} (booked)\n"
    result += "\nTo book a slot, reply with your preferred time and I'll confirm it."
    return result


@tool
def gohighlevel_sync(contact_json: str) -> str:
    """Sync a contact to GoHighLevel CRM and update their pipeline stage.
    Input: JSON string with contact data (name, email, phone, score, notes).
    Returns: sync status and confirmation."""
    try:
        contact = json.loads(contact_json) if contact_json.startswith("{") else {"email": contact_json}
    except json.JSONDecodeError:
        contact = {"info": contact_json}

    sync_result = _run_async(sync_contact_to_ghl(contact))
    score = contact.get("score", "Cold")
    pipeline_result = _run_async(update_pipeline_stage(contact.get("id", "unknown"), score))

    return (
        f"GoHighLevel Sync Results:\n"
        f"Contact sync: {sync_result.get('status')} — {sync_result.get('message', '')}\n"
        f"Pipeline update: {pipeline_result.get('status')} → stage: {pipeline_result.get('stage', 'unknown')}\n"
        f"Message: {pipeline_result.get('message', '')}"
    )


@tool
def zapier_trigger(event_json: str) -> str:
    """Send data to Zapier to trigger an automated workflow.
    Input: JSON string with event type and data fields, or just a description of what to trigger.
    Returns: trigger status and confirmation."""
    try:
        payload = json.loads(event_json) if event_json.startswith("{") else {"event": "agent_action", "info": event_json}
    except json.JSONDecodeError:
        payload = {"event": "agent_action", "info": event_json}

    event = payload.pop("event", "agent_trigger")
    result = _run_async(trigger_zapier(event, payload))

    default_msg = "Triggered with status " + str(result.get("zapier_status", "unknown"))
    return (
        f"Zapier Trigger Results:\n"
        f"Event: {event}\n"
        f"Status: {result.get('status')}\n"
        f"Message: {result.get('message', default_msg)}"
    )


ALL_TOOLS = [crm_lookup, lead_scorer, email_drafter, calendar_checker, gohighlevel_sync, zapier_trigger]
