"""
The admin dashboard. Run this with:

    uvicorn dashboard:app --reload --port 8000

Then open http://localhost:8000
(Put it behind a login / VPN / reverse-auth before exposing it publicly —
 this starter project has no authentication of its own.)
"""
import time
from datetime import datetime

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

import database as db

app = FastAPI(title="Bot Admin Dashboard")
templates = Jinja2Templates(directory="templates")
templates.env.filters["fmt_time"] = lambda ts: datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "—"

db.init_db()


@app.get("/")
def home(request: Request):
    stats = db.subscriber_stats()
    broadcasts = db.list_broadcasts()
    return templates.TemplateResponse(
        "index.html", {"request": request, "stats": stats, "broadcasts": broadcasts}
    )


@app.get("/compose")
def compose_get(request: Request):
    return templates.TemplateResponse("compose.html", {"request": request})


@app.post("/compose")
def compose_post(text: str = Form(...), schedule_at: str = Form("")):
    scheduled_ts = None
    if schedule_at:
        # schedule_at comes from an <input type="datetime-local">, e.g. 2026-11-24T09:30
        scheduled_ts = int(time.mktime(time.strptime(schedule_at, "%Y-%m-%dT%H:%M")))
    db.create_broadcast(text, scheduled_ts)
    return RedirectResponse("/", status_code=303)


@app.get("/support")
def support_list(request: Request, status: str = "open"):
    tickets = db.list_tickets(status=status)
    return templates.TemplateResponse(
        "support.html", {"request": request, "tickets": tickets, "status": status, "ticket": None, "messages": []}
    )


@app.get("/support/{ticket_id}")
def support_detail(request: Request, ticket_id: int):
    ticket, messages = db.get_ticket(ticket_id)
    tickets = db.list_tickets(status="open")
    return templates.TemplateResponse(
        "support.html",
        {"request": request, "tickets": tickets, "status": "open", "ticket": ticket, "messages": messages},
    )


@app.post("/support/{ticket_id}/reply")
def support_reply(ticket_id: int, text: str = Form(...)):
    # delivered=False: the bot process's background loop picks this up and
    # actually sends it on Telegram, then marks it delivered.
    db.add_ticket_message(ticket_id, "admin", text, delivered=False)
    return RedirectResponse(f"/support/{ticket_id}", status_code=303)


@app.post("/support/{ticket_id}/close")
def support_close(ticket_id: int):
    db.close_ticket(ticket_id)
    return RedirectResponse("/support", status_code=303)
