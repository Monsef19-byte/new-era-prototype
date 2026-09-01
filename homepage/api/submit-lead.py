# -*- coding: utf-8 -*-
"""
submit-lead.py — public endpoint hit by every form on the site (villa RDV
forms, Opportunités form). No auth (visitors are anonymous).

Flow, in this exact order (never reversed): the lead is written to Vercel
Blob FIRST, then — only once storage has succeeded — an email attempt is
made. If the email fails (bad SMTP creds, provider down, etc.) the lead is
still safely stored and visible in the dashboard "Leads" page; nothing is
ever lost because of an email problem.

Classification: every lead is tagged with one of exactly 7 CRM codes so an
external CRM bot can auto-file incoming notification emails (the code is
appended at the end of the email body/subject). See CRM_CODES below.
"""
import os
import re
import json
import time
import random
import string
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler

# ---- inlined from _common.py (Vercel Python doesn't reliably bundle sibling
# underscore-prefixed modules, so each endpoint is self-contained) ----
BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_seed")


def _blob_headers(extra=None):
    h = {"authorization": "Bearer " + BLOB_TOKEN}
    if extra:
        h.update(extra)
    return h


def blob_list(prefix):
    if not BLOB_TOKEN:
        return []
    url = "https://blob.vercel-storage.com/?prefix=" + urllib.parse.quote(prefix) + "&limit=1000"
    req = urllib.request.Request(url, headers=_blob_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8")).get("blobs", [])
    except Exception:
        return []


def blob_find_url(pathname):
    for b in blob_list(pathname):
        if b.get("pathname") == pathname:
            return b.get("url")
    return None


def blob_get_bytes(pathname):
    url = blob_find_url(pathname)
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read()
    except Exception:
        return None


def blob_put_bytes(pathname, data, content_type="application/octet-stream"):
    url = "https://blob.vercel-storage.com/" + urllib.parse.quote(pathname)
    req = urllib.request.Request(url, data=data, method="PUT", headers=_blob_headers({
        "x-content-type": content_type,
        "x-add-random-suffix": "0",
        "x-allow-overwrite": "1",
    }))
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def blob_put_json(pathname, obj):
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return blob_put_bytes(pathname, data, "application/json; charset=utf-8")


def _seed_path(name):
    return os.path.join(SEED_DIR, name)


def load_content(name, default=None):
    raw = blob_get_bytes("content/" + name)
    if raw is not None:
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            pass
    seed = _seed_path(name)
    if os.path.exists(seed):
        with open(seed, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def send_json(handler, obj, status=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        return {}


# ---------------------------------------------------------------- CRM classification
# Exactly 7 codes, as agreed: 4 résidences (type 1) + 3 terrain sous-types (type 2).
# The code is appended to every notification email so an external CRM bot can
# auto-parse and file it without any manual triage.
CRM_CODES = {
    "residence": {
        "villa-agata": "NE-RES-AGATA",
        "villa-veronica": "NE-RES-VERONICA",
        "villa-christina": "NE-RES-CHRISTINA",
        "villa-catrina": "NE-RES-CATRINA",
    },
    "terrain": {
        "vente": "NE-TER-VENDRE",
        "achat": "NE-TER-ACHETER",
        "troc": "NE-TER-TROC",
    },
}


def classify(payload):
    """Returns (type_label, subtype_label, code). Never raises — an
    unrecognized combination falls back to a generic, still-visible-in-
    the-dashboard classification rather than rejecting the lead."""
    lead_type = (payload.get("lead_type") or "").strip().lower()
    if lead_type == "residence":
        slug = (payload.get("residence_slug") or "").strip().lower()
        code = CRM_CODES["residence"].get(slug)
        if code:
            return ("Résidence", slug, code)
    if lead_type == "terrain":
        sub = (payload.get("terrain_type") or "").strip().lower()
        code = CRM_CODES["terrain"].get(sub)
        if code:
            return ("Terrain", sub, code)
    return ("Autre", lead_type or "non-classé", "NE-AUTRE")


def gen_id():
    ts = str(int(time.time() * 1000))
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return ts + "-" + rand


def clean(s, maxlen=500):
    s = (s or "").strip()
    return s[:maxlen]


def is_valid_email(s):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s or ""))


def send_lead_email(settings, lead):
    recipient = clean(settings.get("lead_recipient"), 200)
    host = clean(settings.get("smtp_host"), 200)
    port = settings.get("smtp_port") or 587
    user = clean(settings.get("smtp_user"), 200)
    # SMTP password lives only in the SMTP_PASSWORD Vercel env var — never in
    # settings.json/Blob — same "no secrets in stored content" convention as
    # hamadat-promotion.com.
    password = os.environ.get("SMTP_PASSWORD") or ""
    sender_name = clean(settings.get("smtp_sender_name"), 100) or "New Era — Site Web"

    if not (recipient and host and user and password):
        return False, "Réglages email incomplets (à configurer dans le dashboard)."

    lines = [
        "Nouvelle demande reçue sur newera-promotion.com",
        "",
        "Type : {} — {}".format(lead["type_label"], lead["subtype_label"]),
        "Page source : {}".format(lead.get("page", "")),
        "",
    ]
    for k, v in lead["fields"].items():
        if v:
            lines.append("{} : {}".format(k, v))
    lines.append("")
    lines.append("Reçu le : {}".format(lead["received_at"]))
    lines.append("")
    lines.append("Code CRM : {}".format(lead["code"]))
    body = "\n".join(lines)

    subject = "[New Era] Nouvelle demande — {} — {}".format(lead["type_label"], lead["code"])
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name, user))
    msg["To"] = recipient

    try:
        context = ssl.create_default_context()
        if int(port) == 465:
            with smtplib.SMTP_SSL(host, int(port), timeout=15, context=context) as server:
                server.login(user, password)
                server.sendmail(user, [recipient], msg.as_string())
        else:
            with smtplib.SMTP(host, int(port), timeout=15) as server:
                server.starttls(context=context)
                server.login(user, password)
                server.sendmail(user, [recipient], msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        payload = read_json_body(self)

        # honeypot — a hidden field real visitors never fill; bots often do
        if clean(payload.get("hp")):
            return send_json(self, {"ok": True})  # pretend success, drop silently

        nom = clean(payload.get("nom"), 120)
        tel = clean(payload.get("tel"), 40)
        if not nom or not tel:
            return send_json(self, {"ok": False, "error": "Nom et téléphone requis."}, 400)

        email_val = clean(payload.get("email"), 160)
        if email_val and not is_valid_email(email_val):
            return send_json(self, {"ok": False, "error": "Email invalide."}, 400)

        type_label, subtype_label, code = classify(payload)

        fields = {
            "Nom & Prénom": nom,
            "Téléphone": tel,
            "Email": email_val,
        }
        extra_fields = payload.get("extra") or {}
        if isinstance(extra_fields, dict):
            for k, v in list(extra_fields.items())[:20]:
                fields[clean(str(k), 60)] = clean(str(v), 500)

        lead_id = gen_id()
        lead = {
            "id": lead_id,
            "received_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "ts": int(time.time()),
            "type_label": type_label,
            "subtype_label": subtype_label,
            "code": code,
            "page": clean(payload.get("page"), 200),
            "fields": fields,
        }

        # 1) STORE FIRST — the lead must never be lost even if email fails below.
        try:
            blob_put_json("leads/" + lead_id + ".json", lead)
        except Exception as e:
            return send_json(self, {"ok": False, "error": "Stockage impossible : " + str(e)}, 500)

        # 2) THEN attempt the notification email — best-effort, non-blocking for the visitor.
        settings = load_content("settings.json", {}) or {}
        emailed, email_error = send_lead_email(settings, lead)

        send_json(self, {"ok": True, "stored": True, "emailed": emailed})
