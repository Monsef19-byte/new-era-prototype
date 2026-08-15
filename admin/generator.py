#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generator.py — reads the JSON content files in Admin/content/ and (re)writes
the static site pages in ../Homepage and ../Villa Agata.

This is the "publish" step behind the admin dashboard: nobody has to touch
HTML/CSS by hand. All paths below are computed relative to this file so the
whole Admin folder can be moved/copied together with the site and still work.
"""
import os
import re
import json
import shutil
import urllib.request
import urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))          # .../03 - PROTOTYPE/admin
PROTO = os.path.dirname(BASE)                                # .../03 - PROTOTYPE
HOMEPAGE = os.path.join(PROTO, "homepage")                   # lowercase: matches the actual
                                                               # git-tracked folder name exactly —
                                                               # macOS' default case-insensitive
                                                               # filesystem hid this locally, but
                                                               # Vercel's Linux build image is
                                                               # case-sensitive and needs the exact
                                                               # match.
MIRROR = os.path.join(PROTO, "Villa Agata")
CONTENT = os.path.join(BASE, "content")

# Running as part of a Vercel build (VERCEL=1 is set automatically by
# Vercel's build image). In that environment:
#   - "Villa Agata" isn't part of the git repo (it's a local-only mirror
#     folder on the client's Mac), so it doesn't exist — skip it.
#   - Content is pulled from Vercel Blob (what the online admin panel
#     saves to) instead of the local admin/content/*.json files, so a
#     rebuild picks up edits made from newera-promotion.com/admin.
VERCEL_BUILD = os.environ.get("VERCEL") == "1"
OUT_DIRS = [HOMEPAGE] if VERCEL_BUILD else [HOMEPAGE, MIRROR]

BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")


# ---------------------------------------------------------------- Blob (build-time only)
def _blob_list(prefix):
    if not BLOB_TOKEN:
        return []
    url = "https://blob.vercel-storage.com/?prefix=" + urllib.parse.quote(prefix) + "&limit=1000"
    req = urllib.request.Request(url, headers={"authorization": "Bearer " + BLOB_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8")).get("blobs", [])
    except Exception:
        return []


def _blob_get_json(pathname):
    for b in _blob_list(pathname):
        if b.get("pathname") == pathname:
            try:
                with urllib.request.urlopen(b["url"], timeout=20) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception:
                return None
    return None


def sync_blob_assets():
    """Download everything the online admin has ever uploaded (images under
    assets/, plus the hero video) into homepage/assets/, overwriting the
    git-committed baseline where a Blob copy exists. Blob is always the
    source of truth here: builds start from a fresh git checkout that never
    has these files, since they're never committed back to the repo."""
    if not BLOB_TOKEN:
        return
    assets_dir = os.path.join(HOMEPAGE, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    for b in _blob_list("assets/"):
        pathname = b.get("pathname", "")
        fname = pathname[len("assets/"):] if pathname.startswith("assets/") else None
        if not fname or "/" in fname:
            continue
        try:
            with urllib.request.urlopen(b["url"], timeout=60) as resp:
                data = resp.read()
            with open(os.path.join(assets_dir, fname), "wb") as f:
                f.write(data)
        except Exception:
            pass  # best-effort — a single bad asset shouldn't fail the whole build


# ---------------------------------------------------------------- content IO
def load(name):
    """Local admin/content/<name> is always the baseline (works exactly as
    before for the local admin panel, and is what a fresh Vercel build falls
    back to for any section the online admin hasn't touched yet). On Vercel,
    Blob content — if that section was ever saved from the online admin —
    takes precedence, so publishing there is reflected on the next build."""
    path = os.path.join(CONTENT, name)
    local = None
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            local = json.load(f)
    if VERCEL_BUILD:
        remote = _blob_get_json("content/" + name)
        if remote is not None:
            return remote
    return local

def save(name, data):
    path = os.path.join(CONTENT, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------- write helper
def write_all(filename, html):
    """Write the same file into every output folder (keeps Homepage/ and
    'Villa Agata'/ mirrors in sync automatically, so nobody has to copy files
    by hand anymore)."""
    for d in OUT_DIRS:
        path = os.path.join(d, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

def write_all_bytes(rel_path, content_bytes):
    for d in OUT_DIRS:
        path = os.path.join(d, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content_bytes)

def read_current(filename):
    path = os.path.join(HOMEPAGE, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# ============================================================================
# VILLA PAGES
# ============================================================================
ICONS = {
    'archi': '<path d="M2 10l10-6 10 6"/><path d="M4 10v11M8 10v11M12 10v11M16 10v11M20 10v11"/><path d="M3 21h18"/>',
    'typo': '<rect x="3" y="3" width="8" height="8"/><rect x="13" y="3" width="8" height="8"/><rect x="3" y="13" width="8" height="8"/><rect x="13" y="13" width="8" height="8"/>',
    'marbre': '<path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/>',
    'clim': '<path d="M3 8h11a3 3 0 1 0-3-3"/><path d="M3 12h15a3 3 0 1 1-3 3"/><path d="M3 16h8a2 2 0 1 1-2 2"/>',
    'parking': '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 17V7h4a3 3 0 0 1 0 6H9"/>',
    'securite': '<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z"/>',
    'ascenseur': '<rect x="6" y="2" width="12" height="20" rx="1"/><path d="M10 7l2-2 2 2M10 17l2 2 2-2"/>',
    'isolation': '<path d="M3 12a9 9 0 1 0 18 0 9 9 0 0 0-18 0z"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18z"/>',
    'domotique': '<line x1="4" y1="6" x2="20" y2="6"/><circle cx="9" cy="6" r="2"/><line x1="4" y1="12" x2="20" y2="12"/><circle cx="15" cy="12" r="2"/><line x1="4" y1="18" x2="20" y2="18"/><circle cx="7" cy="18" r="2"/>',
    'blocs': '<rect x="3" y="9" width="8" height="12"/><rect x="13" y="4" width="8" height="17"/>',
    'galerie': '<rect x="3" y="3" width="18" height="14" rx="1"/><circle cx="8.5" cy="9" r="1.5"/><path d="M21 15l-5-5-4 4-3-3-6 6"/>',
}

def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def fan_gal_item(img, cap, i):
    return '        <div class="fan-item" data-group="gallery" data-index="{i}"><img src="assets/{img}" alt="{cap}"><div class="cap">{cap}</div></div>'.format(img=img, i=i, cap=esc(cap))

def fan_plan_item(img, cap, i):
    return '        <div class="fan-item" data-group="plans" data-index="{i}"><img src="assets/{img}" alt="{cap}"><div class="cap">{cap}</div></div>'.format(img=img, i=i, cap=esc(cap))

def feat_line(icon, label):
    return '        <li>{}</li>'.format(esc(label))

def gs_interior_card(img, title, bullets):
    lis = ''.join('<li>{}</li>'.format(esc(b)) for b in bullets)
    return ('            <div class="swiper-slide"><div class="gs-card">\n'
            '              <div class="gs-card__image"><img src="assets/{img}" alt="{title}"></div>\n'
            '              <div class="gs-card__content"><b class="gs-card__title">{title}</b>\n'
            '                <ul class="gs-card__bullets">{lis}</ul>\n'
            '              </div>\n'
            '            </div></div>').format(img=img, title=esc(title), lis=lis)

def switch_card(href, img, name, loc):
    return ('    <a class="switch-card tilt" href="{href}"><div class="thumb"><img src="assets/{img}" alt="Villa {name}">'
            '</div><div class="switch-cap"><b>{name}</b><span>{loc}</span></div></a>'
            ).format(href=href, img=img, name=esc(name), loc=esc(loc))

def res_equal_card(v):
    pct = v.get('progress_pct')
    if pct is None:
        prog = '<div class="res-progress-circle" style="--pct:0"><div class="res-progress-circle-inner"><span class="pending">à<br>confirmer</span></div></div>'
    else:
        prog = '<div class="res-progress-circle" style="--pct:{p}"><div class="res-progress-circle-inner"><span>{p}%</span></div></div>'.format(p=pct)
    return (
        '    <a class="res-equal-card" href="{slug}.html">\n'
        '      <div class="thumb">\n'
        '        <img src="assets/{img}" alt="Villa {name}">\n'
        '        <div class="thumb-scrim"></div>\n'
        '        <div class="res-logo"><img src="assets/logo-wordmark-white-badge.png" alt="New Era"></div>\n'
        '        {prog}\n'
        '        <div class="res-overlay-info"><b>{name}</b><span>{loc} · {count} appts</span></div>\n'
        '      </div>\n'
        '    </a>'
    ).format(slug=v['slug'], img=v['card_image'], name=esc(v['name']), prog=prog, loc=esc(v['loc']), count=v['count'])

def render_dispo(dispo, name):
    rows = []
    details = []
    for t in dispo.get('typologies', []):
        status_class = 'pending' if not t.get('confirmed') else ''
        rows.append('        <tr><td>{name}</td><td class="status">{count}</td><td><span class="status-pill {sc}">{label}</span></td></tr>'.format(
            name=esc(t['name']), count=esc(t['count']), sc=status_class, label=esc(t['status_label'])))
        imgs = ''.join('<img src="assets/{}" alt="Plan {} — {}">'.format(im, esc(t['name']), esc(name)) for im in t.get('detail_images', []))
        body = esc(t.get('detail_text', '')) + imgs
        details.append('    <details class="dispo-details"><summary>{n} — voir détails</summary><div class="dd-body">{body}</div></details>'.format(n=esc(t['name']), body=body))
    return (
        '    <h3>Disponibilité — Villa {name}</h3>\n'
        '    <div class="sub">{intro}</div>\n'
        '    <table class="dispo-table">\n'
        '      <thead><tr><th>Typologie</th><th>Nb. d\'appartements</th><th>Statut</th></tr></thead>\n'
        '      <tbody>\n{rows}\n      </tbody>\n'
        '    </table>\n{details}\n'
        '    <div class="dispo-pending" style="margin-top:16px;">{note}</div>'
    ).format(name=esc(name), intro=esc(dispo.get('intro', '')), rows='\n'.join(rows), details='\n'.join(details), note=dispo.get('note', ''))

def load_template():
    path = os.path.join(BASE, "template_villa.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def render_villa(v, all_villas, settings):
    tpl = load_template()
    name = v['name']
    gallery_fan_items = '\n'.join(fan_gal_item(img, cap, i) for i, (img, cap) in enumerate(v['gallery']))
    gallery_lb = ',\n'.join("    {{src:'assets/{}', cap:'{}'}}".format(img, cap.replace("'", "\\'")) for img, cap in v['gallery'])
    plan_fan_items = '\n'.join(fan_plan_item(img, cap, i) for i, (img, cap) in enumerate(v['plans']))
    plan_lb = ',\n'.join("    {{src:'assets/{}', cap:'{}'}}".format(img, cap.replace("'", "\\'")) for img, cap in v['plans'])
    feat_items = '\n'.join(feat_line(icon, label) for icon, label in v['feats'])
    interior_cards = '\n'.join(gs_interior_card(img, title, bullets) for img, title, bullets in v['interior'])
    others = [o for o in all_villas if o['slug'] != v['slug']]
    switch_cards = '\n'.join(switch_card(o['slug'] + '.html', o['card_image'], o['name'], o['loc']) for o in others)
    residence_options = '\n'.join('          <option{sel}>Villa {n}</option>'.format(n=o['name'], sel=' selected' if o['slug'] == v['slug'] else '') for o in all_villas)
    typebien_options = '\n'.join('          <option>{}</option>'.format(t) for t in v.get('typebien_opts', []))
    dispo_content = render_dispo(v['dispo'], name)

    pct = v.get('progress_pct')
    if pct is None:
        progress_style = '--pct:0'
        progress_inner = '<span class="pending">à<br>confirmer</span>'
    else:
        progress_style = '--pct:{}'.format(pct)
        progress_inner = '<span>{}%</span>'.format(pct)

    html = tpl.format(
        slug=v['slug'], name=name, loc=v['loc'], loc_full=v['loc_full'], count=v['count'], typologie=v['typologie'],
        hero_img=v['hero_img'], description=v['description'],
        feat_items=feat_items, gallery_fan_items=gallery_fan_items, gallery_lb=gallery_lb,
        plan_fan_items=plan_fan_items, plan_lb=plan_lb, interior_cards=interior_cards,
        switch_cards=switch_cards, residence_options=residence_options, typebien_options=typebien_options,
        dispo_content=dispo_content, progress_style=progress_style, progress_inner=progress_inner,
    )
    html = apply_contact(html, settings)
    html = apply_blog_nav(html, settings)
    write_all(v['slug'] + '.html', html)

# ============================================================================
# GLOBAL CONTACT / BLOG-NAV SUBSTITUTION (applied to every generated/patched page)
# ============================================================================
def apply_contact(html, settings):
    html = html.replace('tel:+213000000000', 'tel:' + settings['phone_tel'])
    html = html.replace('213000000000', settings['whatsapp_number'])
    return html

BLOG_LINK_HTML = '<a href="blog.html">Blog</a>\n    '

def apply_blog_nav(html, settings):
    enabled = settings.get('enable_blog', False)
    has_link = 'href="blog.html"' in html
    if enabled and not has_link:
        html = html.replace('<a href="opportunites.html">Opportunités</a>\n',
                             '<a href="opportunites.html">Opportunités</a>\n    <a href="blog.html">Blog</a>\n', 1)
        # second occurrence lives in the mobile menu block
        html = html.replace('<a href="opportunites.html">Opportunités</a>\n',
                             '<a href="opportunites.html">Opportunités</a>\n    <a href="blog.html">Blog</a>\n', 1)
    if not enabled and has_link:
        html = re.sub(r'\s*<a href="blog\.html">Blog</a>\n?', '\n', html)
    return html

def replace_balanced_div(html, open_tag_pattern, new_inner_html):
    """Find <div ...> matching open_tag_pattern, then replace everything up
    to ITS matching closing </div> (properly counting nested divs) with
    open_tag + new_inner_html + </div>. Safer than a non-greedy regex when
    the block contains nested <div> children (like manifesto-stats' cards)."""
    m = re.search(open_tag_pattern, html)
    if not m:
        return html
    start = m.end()
    depth = 1
    i = start
    while depth > 0:
        nxt_open = html.find('<div', i)
        nxt_close = html.find('</div>', i)
        if nxt_close == -1:
            return html  # malformed, bail out safely
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
        else:
            depth -= 1
            i = nxt_close + 6
    close_start = i - 6
    return html[:start] + new_inner_html + html[close_start:]

# ============================================================================
# HOMEPAGE / A PROPOS / OPPORTUNITES — targeted patch (keeps all hand-authored
# content that isn't modeled in JSON untouched; only swaps the fields the
# dashboard actually exposes)
# ============================================================================
def patch_homepage(home, villas, settings):
    html = read_current('index.html')

    html = re.sub(
        r"<h1 class=\"h1\">.*?</h1>",
        '<h1 class="h1">{t} <span class="hl-accent flow">{a}</span></h1>'.format(t=esc(home['hero_title']), a=esc(home['hero_accent'])),
        html, count=1, flags=re.S)
    html = re.sub(r'(<h1 class="h1">.*?</h1>\s*<p class="lede">).*?(</p>)',
                   r'\g<1>' + esc(home['hero_lede']) + r'\g<2>', html, count=1, flags=re.S)

    html = re.sub(r'(<div class="kicker manifesto-kicker">).*?(</div>)', r'\g<1>' + esc(home['manifesto_kicker']) + r'\g<2>', html, count=1)
    html = re.sub(r'(<h2 class="manifesto-claim">).*?(</h2>)',
                   r'\g<1>' + esc(home['manifesto_claim']) + ' <span class="hl-accent">' + esc(home['manifesto_claim_accent']) + '</span>' + r'\g<2>',
                   html, count=1, flags=re.S)
    html = re.sub(r'(<p class="manifesto-sub">).*?(</p>)', r'\g<1>' + esc(home['manifesto_sub']) + r'\g<2>', html, count=1)

    stats = home['stats']
    cards = []
    for s in stats:
        cards.append('    <div class="ms-card" tabindex="0">\n      <b>{v}</b><span>{l}</span>\n      <div class="ms-detail">{d}</div>\n    </div>'.format(
            v=esc(s['value']), l=esc(s['label']), d=esc(s['detail'])))
    html = replace_balanced_div(html, r'<div class="manifesto-stats">', '\n' + '\n'.join(cards) + '\n  ')

    by_slug = {v['slug']: v for v in villas}
    featured = [by_slug[s] for s in home.get('featured_villas', []) if s in by_slug]
    res_cards_html = '\n'.join(res_equal_card(v) for v in featured)
    html = replace_balanced_div(html, r'<div class="res-equal reveal">', '\n' + res_cards_html + '\n  ')

    html = apply_contact(html, settings)
    html = apply_blog_nav(html, settings)
    write_all('index.html', html)

# ============================================================================
# PAGE /liens — le lien du QR code print. Entièrement pilotée par
# content/liens.json (logo, nom, accroche, sous-titre, et la liste des
# cartes). Régénération complète depuis template_liens.txt à chaque
# publication : aucune valeur par défaut codée en dur dans le HTML.
# ============================================================================
LIENS_ICONS = {
    'site': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20z"/></svg>',
    'residences': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg>',
    'call': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.362 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.338 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
    'whatsapp': '<svg viewBox="0 0 24 24" fill="#fff"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.77.46 3.45 1.28 4.9L2 22l5.29-1.38a9.9 9.9 0 0 0 4.75 1.21h.01c5.46 0 9.9-4.45 9.9-9.92C21.96 6.45 17.5 2 12.04 2zm0 18.1h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.14.82.84-3.06-.2-.31a8.18 8.18 0 0 1-1.26-4.32c0-4.52 3.68-8.2 8.27-8.2 2.21 0 4.28.86 5.84 2.42a8.15 8.15 0 0 1 2.42 5.8c0 4.52-3.69 8.18-8.27 8.18zm4.53-6.13c-.25-.12-1.47-.72-1.7-.81-.23-.08-.39-.12-.56.13-.16.24-.64.8-.78.97-.14.16-.29.18-.53.06-.25-.12-1.04-.38-1.99-1.22-.73-.66-1.23-1.46-1.37-1.71-.14-.24-.02-.38.11-.5.11-.11.25-.29.37-.43.13-.15.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.35-.77-1.85-.2-.48-.41-.42-.56-.42h-.48c-.16 0-.42.06-.65.31-.22.24-.85.83-.85 2.03s.87 2.36.99 2.52c.12.16 1.71 2.6 4.14 3.65.58.25 1.03.4 1.38.51.58.18 1.11.16 1.53.1.47-.07 1.47-.6 1.67-1.18.21-.58.21-1.08.15-1.18-.06-.1-.22-.16-.47-.28z"/></svg>',
    'instagram': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="5.5"/><circle cx="12" cy="12" r="4.2"/><circle cx="17.35" cy="6.65" r="1" fill="#fff" stroke="none"/></svg>',
    'facebook': '<svg viewBox="0 0 24 24" fill="#fff"><path d="M15.12 5.32H17V2.14A26.11 26.11 0 0 0 14.26 2c-2.72 0-4.58 1.66-4.58 4.7v2.62H6.61v3.56h3.07V22h3.68v-9.12h3.06l.46-3.56h-3.52V7.05c0-1.03.28-1.73 1.76-1.73z"/></svg>',
    'linkedin': '<svg viewBox="0 0 24 24" fill="#fff"><path d="M6.94 5a2 2 0 1 1 0 4 2 2 0 0 1 0-4zM3.5 9.5h4V21h-4V9.5zM10 9.5h3.8v1.6h.05c.53-1 1.83-2.06 3.77-2.06 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.4c0-1.3-.02-2.96-1.8-2.96-1.8 0-2.08 1.4-2.08 2.87V21h-4V9.5z"/></svg>',
    'tiktok': '<svg viewBox="0 0 24 24" fill="#fff"><path d="M16.6 5.82c-.9-.86-1.44-2.02-1.5-3.32h-3.02v13.3a3.06 3.06 0 1 1-2.16-2.93V9.75a6.1 6.1 0 1 0 5.18 6.05V9.4a8.6 8.6 0 0 0 5.02 1.6V7.98a5.2 5.2 0 0 1-3.52-2.16z"/></svg>',
    'email': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v16H4z"/><path d="M22 6l-10 7L2 6"/></svg>',
    'link': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
}

def liens_card_html(card):
    if not card.get('enabled', True):
        return ''
    href = card.get('href') or '#'
    external = not (href.startswith('tel:') or href.startswith('mailto:'))
    target_attrs = ' target="_blank" rel="noopener"' if external else ''
    svg = LIENS_ICONS.get(card.get('icon'), LIENS_ICONS['link'])
    return (
        '    <a class="liens-card" href="{href}"{target}>\n'
        '      <span class="liens-ico">{svg}</span>\n'
        '      <span class="liens-card-label">{label}</span>\n'
        '    </a>'
    ).format(href=esc(href), target=target_attrs, svg=svg, label=esc(card.get('label', '')))

def load_liens_template():
    path = os.path.join(BASE, "template_liens.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def render_liens(liens, settings):
    """Full regeneration of Homepage/liens/index.html from content/liens.json
    — logo, name, tagline, subtitle and every card are admin-editable, so
    unlike the old apply_liens() patch this never depends on a value already
    present in a previously-published file."""
    if not liens:
        return
    tpl = load_liens_template()
    cards_html = '\n'.join(liens_card_html(c) for c in liens.get('cards', []))
    html = tpl
    html = html.replace('%%LOGO_IMG%%', liens.get('logo') or 'logo-mono-white.png')
    html = html.replace('%%NAME%%', esc(liens.get('name', '')))
    html = html.replace('%%TAGLINE%%', esc(liens.get('tagline', '')))
    html = html.replace('%%SUBTITLE%%', esc(liens.get('subtitle', '')))
    html = html.replace('%%CARDS_HTML%%', cards_html)
    for d in OUT_DIRS:
        out_dir = os.path.join(d, "liens")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

def patch_simple_hero(filename, data, settings):
    html = read_current(filename)
    html = re.sub(r'(<h1 class="h1"[^>]*>).*?(</h1>)',
                   lambda m: m.group(1) + esc(data['hero_title']) + '<span class="hl-accent" style="font-size:clamp(16px,2vw,22px);text-transform:none;letter-spacing:0;font-weight:600;">' + esc(data['hero_accent']) + '</span>' + m.group(2),
                   html, count=1, flags=re.S)
    html = re.sub(r'(<p class="lede">).*?(</p>)', r'\g<1>' + esc(data['hero_lede']) + r'\g<2>', html, count=1, flags=re.S)
    html = apply_contact(html, settings)
    html = apply_blog_nav(html, settings)
    write_all(filename, html)

# ============================================================================
# BLOG
# ============================================================================
BLOG_LIST_TEMPLATE = None
BLOG_POST_TEMPLATE = None

def load_blog_templates():
    global BLOG_LIST_TEMPLATE, BLOG_POST_TEMPLATE
    with open(os.path.join(BASE, "template_blog_list.txt"), "r", encoding="utf-8") as f:
        BLOG_LIST_TEMPLATE = f.read()
    with open(os.path.join(BASE, "template_blog_post.txt"), "r", encoding="utf-8") as f:
        BLOG_POST_TEMPLATE = f.read()

def slugify(s):
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    return s or "article"

def render_blog(posts, settings):
    if not settings.get('enable_blog'):
        for d in OUT_DIRS:
            p = os.path.join(d, 'blog.html')
            if os.path.exists(p):
                os.remove(p)
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    if fn.startswith('blog-') and fn.endswith('.html'):
                        os.remove(os.path.join(d, fn))
        return
    load_blog_templates()
    cards = []
    for p in posts:
        cards.append(
            '<a class="switch-card tilt" href="blog-{slug}.html"><div class="thumb"><img src="assets/{img}" alt="{title}"></div>'
            '<div class="switch-cap"><b>{title}</b><span>{date}</span></div></a>'.format(
                slug=p['slug'], img=p.get('image', 'villa-agata.jpg'), title=esc(p['title']), date=esc(p.get('date', ''))))
    html = BLOG_LIST_TEMPLATE.format(cards='\n'.join(cards))
    html = apply_contact(html, settings)
    html = apply_blog_nav(html, settings)
    write_all('blog.html', html)

    existing = set()
    for d in OUT_DIRS:
        for fn in os.listdir(d):
            if fn.startswith('blog-') and fn.endswith('.html'):
                existing.add(fn)
    keep = set('blog-{}.html'.format(p['slug']) for p in posts)
    for fn in existing - keep:
        for d in OUT_DIRS:
            fp = os.path.join(d, fn)
            if os.path.exists(fp):
                os.remove(fp)

    for p in posts:
        body_html = ''.join('<p class="lede">{}</p>'.format(esc(para)) for para in p.get('body', '').split('\n') if para.strip())
        html = BLOG_POST_TEMPLATE.format(title=esc(p['title']), date=esc(p.get('date', '')), image=p.get('image', 'villa-agata.jpg'), body=body_html)
        html = apply_contact(html, settings)
        html = apply_blog_nav(html, settings)
        write_all('blog-{}.html'.format(p['slug']), html)

# ============================================================================
# ENTRY POINT
# ============================================================================
def publish():
    if VERCEL_BUILD:
        sync_blob_assets()
    settings = load('settings.json')
    villas = load('villas.json')
    home = load('home.json')
    apropos = load('apropos.json')
    opportunites = load('opportunites.json')
    blog = load('blog.json') or []
    liens = load('liens.json')

    for v in villas:
        render_villa(v, villas, settings)

    patch_homepage(home, villas, settings)
    patch_simple_hero('a-propos.html', apropos, settings)
    patch_simple_hero('opportunites.html', opportunites, settings)
    render_liens(liens, settings)
    render_blog(blog, settings)

    # keep main.js's own hardcoded contact number (used by the RDV modal) in sync too
    mjs_path = os.path.join(HOMEPAGE, 'assets', 'main.js')
    with open(mjs_path, 'r', encoding='utf-8') as f:
        mjs = f.read()
    mjs = apply_contact(mjs, settings)
    for d in OUT_DIRS:
        with open(os.path.join(d, 'assets', 'main.js'), 'w', encoding='utf-8') as f:
            f.write(mjs)

    return {"ok": True, "villas": len(villas), "blog_enabled": settings.get('enable_blog', False), "blog_posts": len(blog)}

if __name__ == '__main__':
    result = publish()
    print(json.dumps(result, ensure_ascii=False))
