# -*- coding: utf-8 -*-
"""POST /api/publish — content edits are already saved to Blob by /api/save
as the admin types (debounced). "Publier" just tells Vercel to rebuild: the
build step (see admin/generator.py) pulls the latest content from Blob and
regenerates every HTML page before the new deployment goes live. There is no
long-running work to do here, so this endpoint just fires the deploy hook."""
from http.server import BaseHTTPRequestHandler
import os
import urllib.request
import _common as C

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not C.is_authed(self.headers):
            return C.send_json(self, {"error": "unauthorized"}, 401)
        hook = os.environ.get("DEPLOY_HOOK_URL", "")
        if not hook:
            return C.send_json(self, {"ok": False, "error": "DEPLOY_HOOK_URL non configuré"}, 500)
        try:
            req = urllib.request.Request(hook, method="POST")
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            return C.send_json(self, {"ok": False, "error": "Échec du déclenchement du déploiement : {}".format(e)}, 500)

        villas = C.load_content("villas.json", [])
        settings = C.load_content("settings.json", {})
        blog = C.load_content("blog.json", [])
        C.send_json(self, {
            "ok": True,
            "villas": len(villas),
            "blog_enabled": settings.get("enable_blog", False),
            "blog_posts": len(blog),
            "message": "Déploiement déclenché — en ligne dans 1 à 2 minutes.",
        })
