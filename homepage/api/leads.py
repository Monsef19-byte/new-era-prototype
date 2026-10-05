# -*- coding: utf-8 -*-
"""
leads.py — admin-only. Lists stored leads (Vercel Blob, prefix "leads/")
and returns basic statistics for the dashboard "Leads" page. Session-authed
like every other admin endpoint (ne_session cookie).

POST {id, status: "new"|"handled"} marque une demande comme traitée (ou
nouvelle). Une demande sans statut (reçue avant cette fonction) compte comme
« new » : c'est ce compteur qu'affiche la pastille du menu du dashboard.
"""
import os
import re
import json
import time
import hmac
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor

BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
# Espace de noms Blob : la production lit et écrit à la racine (content/…,
# assets/…, leads/…) ; tout autre environnement Vercel (preview) sous
# « preview/ », pour qu'un dashboard de preview ne touche jamais au contenu
# de production. BLOB_NAMESPACE permet de forcer une valeur.
BLOB_NS = os.environ["BLOB_NAMESPACE"] if "BLOB_NAMESPACE" in os.environ else (
    "" if os.environ.get("VERCEL_ENV", "production") == "production" else "preview/")
SESSION_SECRET = os.environ.get("ADMIN_SESSION_SECRET", "")


def verify_session_token(tok):
    if not tok or "." not in tok or not SESSION_SECRET:
        return False
    exp_s, sig = tok.split(".", 1)
    expected = hmac.new(SESSION_SECRET.encode("utf-8"), exp_s.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        return int(exp_s) > int(time.time())
    except ValueError:
        return False


def get_cookie(headers, name):
    cookie = headers.get("Cookie") or headers.get("cookie") or ""
    m = re.search(r"(?:^|;\s*)" + re.escape(name) + r"=([^;]+)", cookie)
    return m.group(1) if m else None


def is_authed(headers):
    return verify_session_token(get_cookie(headers, "ne_session"))


def _blob_headers(extra=None):
    h = {"authorization": "Bearer " + BLOB_TOKEN}
    if extra:
        h.update(extra)
    return h


def blob_list(prefix):
    if not BLOB_TOKEN:
        return []
    url = "https://blob.vercel-storage.com/?prefix=" + urllib.parse.quote(BLOB_NS + prefix) + "&limit=1000"
    req = urllib.request.Request(url, headers=_blob_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            blobs = json.loads(resp.read().decode("utf-8")).get("blobs", [])
    except Exception:
        return []
    out = []
    for b in blobs:
        p = b.get("pathname", "")
        if BLOB_NS and not p.startswith(BLOB_NS):
            continue
        b = dict(b)
        b["pathname"] = p[len(BLOB_NS):]
        out.append(b)
    return out


def blob_get_bytes_url(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read()
    except Exception:
        return None


def blob_put_json(pathname, obj):
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    url = "https://blob.vercel-storage.com/" + urllib.parse.quote(BLOB_NS + pathname)
    req = urllib.request.Request(url, data=data, method="PUT", headers=_blob_headers({
        "x-content-type": "application/json; charset=utf-8",
        "x-add-random-suffix": "0",
        "x-allow-overwrite": "1",
        "x-cache-control-max-age": "60",
    }))
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fresh(url):
    """URL publique du blob sans le cache CDN (statut modifié juste avant)."""
    return (url or "") + ("&" if "?" in (url or "") else "?") + "t=" + str(int(time.time() * 1000))


def send_json(handler, obj, status=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not is_authed(self.headers):
            return send_json(self, {"error": "unauthorized"}, 401)

        blobs = [b for b in blob_list("leads/") if b.get("pathname", "").endswith(".json")]
        # Lectures en parallèle : le dashboard interroge cette route chaque
        # minute pour la pastille « Demandes reçues » ; en série, quelques
        # centaines de demandes dépasseraient le délai d'une fonction Vercel.
        def _read(b):
            raw = blob_get_bytes_url(fresh(b.get("url")))
            if not raw:
                return None
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return None
        with ThreadPoolExecutor(max_workers=16) as pool:
            leads = [l for l in pool.map(_read, blobs) if isinstance(l, dict)]

        leads.sort(key=lambda l: l.get("ts", 0), reverse=True)
        for l in leads:
            if l.get("status") not in ("new", "handled"):
                l["status"] = "new"
        new_count = sum(1 for l in leads if l["status"] == "new")

        stats_by_code = {}
        for l in leads:
            code = l.get("code", "NE-AUTRE")
            stats_by_code[code] = stats_by_code.get(code, 0) + 1

        thirty_days_ago = int(time.time()) - 30 * 86400
        last_30_days = sum(1 for l in leads if l.get("ts", 0) >= thirty_days_ago)

        send_json(self, {
            "leads": leads[:500],
            "total": len(leads),
            "new": new_count,
            "last_30_days": last_30_days,
            "by_code": stats_by_code,
        })

    def do_POST(self):
        if not is_authed(self.headers):
            return send_json(self, {"error": "unauthorized"}, 401)
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads((self.rfile.read(length) if length else b"{}").decode("utf-8") or "{}")
        except Exception:
            return send_json(self, {"error": "invalid json"}, 400)
        lead_id = str(body.get("id") or "")
        status = body.get("status")
        if not re.fullmatch(r"[A-Za-z0-9_-]{4,80}", lead_id) or status not in ("new", "handled"):
            return send_json(self, {"error": "Corps invalide : 'id' et 'status' ('new'|'handled') requis."}, 400)
        pathname = "leads/" + lead_id + ".json"
        match = [b for b in blob_list(pathname) if b.get("pathname") == pathname]
        if not match:
            return send_json(self, {"error": "Demande introuvable."}, 404)
        raw = blob_get_bytes_url(fresh(match[0].get("url")))
        if not raw:
            return send_json(self, {"error": "Lecture impossible."}, 502)
        try:
            lead = json.loads(raw.decode("utf-8"))
        except Exception:
            return send_json(self, {"error": "Demande illisible."}, 502)
        lead["status"] = status
        lead["status_at"] = int(time.time())
        try:
            blob_put_json(pathname, lead)
        except Exception as e:
            return send_json(self, {"error": "Enregistrement impossible : " + str(e)}, 500)
        send_json(self, {"ok": True, "id": lead_id, "status": status})
