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

from icons import ICONS as ICON_LIBRARY

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

def gallery_item_html(item, i):
    asset = item.get("asset")
    if not asset:
        return ""
    cap = esc(item.get("caption", ""))
    cap_html = '<div class="cap">{}</div>'.format(cap) if cap else ""
    return '    <div class="fan-item" data-group="catalogue" data-index="{i}"><img src="assets/{img}" alt="{cap}">{cap_html}</div>'.format(
        i=i, img=asset, cap=cap, cap_html=cap_html
    )

YOUTUBE_RE = [
    re.compile(r"(?:youtube\.com/watch\?[^#]*\bv=)([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/(?:embed|shorts)/)([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})"),
]

def youtube_id(url):
    url = (url or "").strip()
    for pattern in YOUTUBE_RE:
        m = pattern.search(url)
        if m:
            return m.group(1)
    return None

def video_card_html(item, lang='fr'):
    vid = youtube_id(item.get("url"))
    if not vid:
        return ""
    title = esc((item.get("title_ar") or item.get("title", "")) if lang == 'ar' else item.get("title", ""))
    return (
        '    <div class="video-card reveal" data-youtube-id="{vid}" tabindex="0" role="button" aria-label="{title}">\n'
        '      <div class="video-card__thumb">\n'
        '        <img src="https://img.youtube.com/vi/{vid}/hqdefault.jpg" alt="{title}" loading="lazy">\n'
        '        <div class="video-card__play"><svg viewBox="0 0 24 24" fill="currentColor"><polygon points="9 6 19 12 9 18"/></svg></div>\n'
        '      </div>\n'
        '      <div class="video-card__title">{title}</div>\n'
        '    </div>'
    ).format(vid=vid, title=title)

def fan_gal_item(img, cap, i):
    return '        <div class="fan-item" data-group="gallery" data-index="{i}"><img src="assets/{img}" alt="{cap}"><div class="cap">{cap}</div></div>'.format(img=img, i=i, cap=esc(cap))

def fan_plan_item(img, cap, i):
    return '        <div class="fan-item" data-group="plans" data-index="{i}"><img src="assets/{img}" alt="{cap}"><div class="cap">{cap}</div></div>'.format(img=img, i=i, cap=esc(cap))

# Sourced from icons.py (ICON_LIBRARY) so every icon offered by the admin's
# icon picker (icons-data.js) can actually be rendered on the live site —
# the original 11 "Caractéristiques" icons plus the ~60 ported from
# hamadat-promotion.com's icon library. See icons.py for details.
FEAT_ICONS = {name: entry['d'] for name, entry in ICON_LIBRARY.items()}
FEAT_ICON_DEFAULT = '<circle cx="12" cy="12" r="9"/><path d="M9 12l2 2 4-4"/>'

def feat_line(icon, label):
    svg_body = FEAT_ICONS.get(icon, FEAT_ICON_DEFAULT)
    svg = ('<svg class="feat-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
           'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>').format(svg_body)
    return '        <li>{svg}<span>{label}</span></li>'.format(svg=svg, label=esc(label))

def gs_interior_card(img, title, bullets):
    lis = ''.join('<li>{}</li>'.format(esc(b)) for b in bullets)
    return ('            <div class="swiper-slide"><div class="gs-card">\n'
            '              <div class="gs-card__image"><img src="assets/{img}" alt="{title}"></div>\n'
            '              <div class="gs-card__content"><b class="gs-card__title">{title}</b>\n'
            '                <ul class="gs-card__bullets">{lis}</ul>\n'
            '              </div>\n'
            '            </div></div>').format(img=img, title=esc(title), lis=lis)

def switch_card(href, img, name, loc, lang='fr'):
    return ('    <a class="switch-card tilt" href="{href}"><div class="thumb"><img src="assets/{img}" alt="{pre} {name}">'
            '</div><div class="switch-cap"><b>{name}</b><span>{loc}</span></div></a>'
            ).format(href=href, img=img, name=esc(name), loc=esc(loc), pre='فيلا' if lang == 'ar' else 'Villa')

PROGRESS_SQ_START = '<!-- AVANCEMENT:START -->'
PROGRESS_SQ_END = '<!-- AVANCEMENT:END -->'

def progress_square_html(v, lang='fr'):
    """Avancement du projet : petit carré rouge STATIQUE, à la suite du
    badge « Partenariat algéro-allemand » et de la même hauteur — uniquement
    sur la fiche résidence (plus rien sur les cartes de l'accueil, plus de
    cercle ni de remplissage animé)."""
    pct = v.get('progress_pct')
    ar = lang == 'ar'
    label = 'نسبة التقدّم' if ar else 'Avancement'
    if pct is None:
        val = 'قيد التأكيد' if ar else 'À confirmer'
        cls = ' is-pending'
    else:
        val = '{}%'.format(int(pct))
        cls = ''
    return (PROGRESS_SQ_START + '<span class="v-chip v-chip--progress{c}" role="img" aria-label="{l} : {v}" title="{l}">{v}</span>'
            + PROGRESS_SQ_END).format(c=cls, l=esc(label), v=esc(val))

def res_equal_card(v):
    prog = ''
    return (
        '    <a class="res-equal-card" href="{slug}.html">\n'
        '      <div class="thumb">\n'
        '        <img src="assets/{img}" alt="Villa {name}">\n'
        '        <div class="thumb-scrim"></div>\n'
        '        <div class="res-logo"><img src="assets/logo-wordmark-white-badge.png" alt="New Era"></div>\n'
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

# ---------------------------------------------------------------- localisation exacte
# Brief client : le nom de la ville doit mener à la localisation EXACTE de la
# résidence (pas à une recherche générique « Hydra, Alger »). Priorité :
#   1. coordonnées GPS saisies dans le dashboard (« 36.7466, 3.0421 ») ;
#   2. lien Google Maps collé dans le dashboard ;
#   3. à défaut seulement, recherche par adresse (repli, signalé au dashboard).
GPS_RE = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
URL_COORD_RES = [
    re.compile(r"@(-?\d{1,2}\.\d+),(-?\d{1,3}\.\d+)"),
    re.compile(r"[?&](?:q|query|ll|destination)=(-?\d{1,2}\.\d+)(?:%2C|,)\s*(-?\d{1,3}\.\d+)"),
    re.compile(r"!3d(-?\d{1,2}\.\d+)!4d(-?\d{1,3}\.\d+)"),
]

def villa_coords(v):
    m = GPS_RE.match(str(v.get('gps') or ''))
    if m:
        return m.group(1), m.group(2)
    url = str(v.get('google_maps') or '')
    for r in URL_COORD_RES:
        m = r.search(url)
        if m:
            return m.group(1), m.group(2)
    return None

def villa_address(v):
    loc = v.get('loc_full') or v.get('loc') or ''
    return loc if 'algérie' in loc.lower() else loc + ', Algérie'

def villa_maps_link(v):
    c = villa_coords(v)
    if c and GPS_RE.match(str(v.get('gps') or '')):
        return 'https://www.google.com/maps/search/?api=1&query={},{}'.format(c[0], c[1])
    url = (v.get('google_maps') or '').strip()
    if url:
        return url
    return 'https://www.google.com/maps/search/?api=1&query=' + urllib.parse.quote_plus(villa_address(v))

def villa_map_embed(v):
    c = villa_coords(v)
    q = '{},{}'.format(c[0], c[1]) if c else villa_address(v)
    return 'https://maps.google.com/maps?q={}&t=&z={}&ie=UTF8&iwloc=&output=embed'.format(
        urllib.parse.quote(q), 17 if c else 15)

PIN_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
           'stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;'
           'vertical-align:-2px;margin-inline-end:4px;" aria-hidden="true"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z"/>'
           '<circle cx="12" cy="10" r="3"/></svg>')

def loc_link_html(v, text, pin=True):
    return '<a class="vs-loc-link" href="{u}" target="_blank" rel="noopener" data-maps-link>{pin}{t}</a>'.format(
        u=esc(villa_maps_link(v)), pin=PIN_SVG if pin else '', t=text)

# ---------------------------------------------------------------- finitions
# Section « Finitions » des fiches résidence : carrousel de finitions, chaque
# finition = image + titre + description (FR/AR), description affichée au
# survol (ordinateur) ou au toucher (mobile). Contenu : content/finitions.json
# (onglet « Finitions » du dashboard), commun à toutes les résidences.
FINITIONS_START = '<!-- FINITIONS:START -->'
FINITIONS_END = '<!-- FINITIONS:END -->'

def _fin_text(fin, key, ar):
    return (fin.get(key + '_ar') or fin.get(key) or '') if ar else (fin.get(key) or '')

def render_finitions_carousel(fin, lang='fr', asset_prefix='assets/', indent='      '):
    """Carrousel de cartes finition + aide « survol / toucher » (commun aux
    fiches résidence et à la section Savoir-faire de l'accueil)."""
    fin = fin or {}
    ar = lang == 'ar'
    cards = []
    for it in fin.get('items', []):
        if not it.get('image'):
            continue
        title = _fin_text(it, 'title', ar)
        desc = _fin_text(it, 'description', ar)
        cards.append(
            '{i}      <div class="swiper-slide"><div class="gs-card media-only fin-card" tabindex="0" role="button" aria-expanded="false"{lbl}>\n'
            '{i}        <div class="gs-card__image"><img src="{pre}{img}" alt="{title}" loading="lazy"></div>\n'
            '{i}        <div class="cap">{title}</div>\n'
            '{desc_html}'
            '{i}      </div></div>'.format(
                i=indent, pre=asset_prefix, img=esc(it['image']), title=esc(title),
                lbl=' aria-label="{}"'.format(esc(title)) if title else '',
                desc_html=('{i}        <div class="fin-desc"><b>{t}</b><p>{d}</p></div>\n'
                           '{i}        <span class="fin-hint" aria-hidden="true">+</span>\n').format(i=indent, t=esc(title), d=esc(desc)) if desc else ''))
    prev_lbl, next_lbl = ('السابق', 'التالي') if ar else ('Précédent', 'Suivant')
    hint = ('مرّروا المؤشر على إحدى التشطيبات — أو المسوها على الهاتف — لاكتشاف وصفها.' if ar
            else 'Survolez une finition — ou touchez-la sur mobile — pour découvrir sa description.')
    has_desc = any(_fin_text(it, 'description', ar) for it in fin.get('items', []))
    arrow = '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="{}"/></svg>'
    return (
        '{i}<div class="gallery-swiper on-dark fin-swiper">\n'
        '{i}  <div class="gallery-swiper__nav">\n'
        '{i}    <button class="gs-arrow gs-prev" aria-label="{prev}">{ap}</button>\n'
        '{i}    <button class="gs-arrow gs-next" aria-label="{next}">{an}</button>\n'
        '{i}  </div>\n'
        '{i}  <div class="swiper gs-swiper">\n'
        '{i}    <div class="swiper-wrapper">\n{cards}\n{i}    </div>\n'
        '{i}  </div>\n'
        '{i}  <div class="gs-pagination"></div>\n'
        '{i}</div>\n'
        '{hint}'
    ).format(i=indent, prev=prev_lbl, next=next_lbl, ap=arrow.format('M15 18l-6-6 6-6'), an=arrow.format('M9 18l6-6-6-6'),
             cards='\n'.join(cards), hint='{}<p class="fin-help">{}</p>\n'.format(indent, hint) if has_desc else '')

def render_finitions_block(fin, lang='fr', num='05', asset_prefix='assets/'):
    fin = fin or {}
    ar = lang == 'ar'
    lede = _fin_text(fin, 'lede', ar)
    return (
        FINITIONS_START + '\n'
        '    <div class="vs-block dark" id="finitions">\n'
        '      <div class="kicker on-dark"><span class="num">{num}</span></div>\n'
        '      <h2 class="h3">{title}</h2>\n'
        '{lede}'
        '{carousel}'
        '    </div>\n' + FINITIONS_END
    ).format(num=esc(num), title=esc(_fin_text(fin, 'title', ar)),
             lede='      <p class="lede">{}</p>\n'.format(esc(lede)) if lede else '',
             carousel=render_finitions_carousel(fin, lang, asset_prefix, '      '))

FINCARDS_START = '<!-- FINITIONS-CARDS:START -->'
FINCARDS_END = '<!-- FINITIONS-CARDS:END -->'

def replace_home_finitions(html, fin, lang, asset_prefix):
    """Section « Savoir-faire » de l'accueil : même carrousel de finitions
    (en-tête de section conservé). Idempotent via marqueurs."""
    if not fin or not fin.get('items'):
        return html
    if FINCARDS_START in html and FINCARDS_END in html:
        a = html.index(FINCARDS_START)
        b = html.index(FINCARDS_END) + len(FINCARDS_END)
    else:
        anchor = html.find('materials-stone')
        if anchor == -1:
            return html
        a = html.rfind('<div class="gallery-swiper on-dark', 0, anchor)
        if a == -1:
            return html
        b = _balanced_div_end(html, a)
        if b == -1:
            return html
        note = re.match(r'\s*<p class="materials-note">.*?</p>', html[b:], flags=re.S)
        if note:
            b += note.end()
        a = html.rfind('\n', 0, a) + 1
    return html[:a] + FINCARDS_START + '\n' + render_finitions_carousel(fin, lang, asset_prefix, '  ') + FINCARDS_END + html[b:]

def _balanced_div_end(html, start):
    """Index just after the </div> closing the <div ...> that starts at `start`."""
    depth, i = 0, start
    while True:
        nxt_open = html.find('<div', i)
        nxt_close = html.find('</div>', i)
        if nxt_close == -1:
            return -1
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
        else:
            depth -= 1
            i = nxt_close + 6
            if depth == 0:
                return i

def replace_finitions(html, fin, lang, asset_prefix):
    """Idempotent : entre les marqueurs si déjà présents, sinon remplace
    l'ancien bloc « matériaux » (vs-block dark contenant materials-stone)."""
    if FINITIONS_START in html and FINITIONS_END in html:
        a = html.index(FINITIONS_START)
        b = html.index(FINITIONS_END) + len(FINITIONS_END)
        old = html[a:b]
    else:
        anchor = html.find('materials-stone')
        if anchor == -1:
            return html
        a = html.rfind('<div class="vs-block dark">', 0, anchor)
        if a == -1:
            return html
        b = _balanced_div_end(html, a)
        if b == -1:
            return html
        a = html.rfind('\n', 0, a) + 1  # keep indentation clean
        old = html[a:b]
    m = re.search(r'<span class="num">([^<]*)</span>', old)
    num = m.group(1) if m else '05'
    return html[:a] + render_finitions_block(fin, lang, num, asset_prefix) + html[b:]

# Ordre des sections de la fiche : Disponibilité juste après
# Caractéristiques (avant Localisation), puis numérotation 01, 02… recalculée
# dans l'ordre réel des blocs — idempotent, FR comme AR.
NUM_KICKER_RE = re.compile(r'(<div class="kicker(?: on-dark)?"><span class="num">)\d{2}(</span></div>)')

def renumber_blocks(html):
    counter = [0]
    def sub(m):
        counter[0] += 1
        return '{}{:02d}{}'.format(m.group(1), counter[0], m.group(2))
    return NUM_KICKER_RE.sub(sub, html)

def move_dispo_after_feats(html):
    start = html.find('    <!-- DISPONIBILITÉ -->\n')
    feats = html.find('    <!-- CARACTÉRISTIQUES -->')
    if start == -1 or feats == -1:
        return html
    div_start = html.find('<div', start)
    end = _balanced_div_end(html, div_start)
    if end == -1:
        return html
    end = html.find('\n', end) + 1
    while html[end:end + 1] == '\n':
        end += 1
    block = html[start:end]
    rest = html[:start] + html[end:]
    fs = rest.find('    <!-- CARACTÉRISTIQUES -->')
    fdiv = rest.find('<div', fs)
    fend = _balanced_div_end(rest, fdiv)
    fend = rest.find('\n', fend) + 1
    while rest[fend:fend + 1] == '\n':
        fend += 1
    return rest[:fend] + block + rest[fend:]

def load_template_ar():
    with open(os.path.join(BASE, "template_villa_ar.txt"), "r", encoding="utf-8") as f:
        return f.read()

def load_template():
    path = os.path.join(BASE, "template_villa.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _t(obj, key, lang):
    """Texte d'un champ dans la langue voulue : `key_ar` en arabe (repli sur
    le français s'il est vide — jamais de trou sur la page), `key` sinon."""
    if lang == 'ar':
        return obj.get(key + '_ar') or obj.get(key) or ''
    return obj.get(key) or ''

def _pair(item, i_fr, i_ar, lang):
    """Élément de liste [valeur, texte FR, texte AR…] (légendes, libellés)."""
    fr = item[i_fr] if len(item) > i_fr else ''
    if lang == 'ar':
        return (item[i_ar] if len(item) > i_ar and item[i_ar] else fr) or ''
    return fr or ''

def render_dispo_lang(dispo, name, lang):
    if lang != 'ar':
        return render_dispo(dispo, name)
    rows, details = [], []
    for t in dispo.get('typologies', []):
        sc = 'pending' if not t.get('confirmed') else ''
        tname = _t(t, 'name', 'ar')
        label = t.get('status_label_ar') or ('مؤكد' if t.get('confirmed') else 'قيد التأكيد')
        rows.append('        <tr><td>{n}</td><td class="status">{c}</td><td><span class="status-pill {sc}">{l}</span></td></tr>'.format(
            n=esc(tname), c=esc(_t(t, 'count', 'ar')), sc=sc, l=esc(label)))
        imgs = ''.join('<img src="assets/{}" alt="مخطط {} — {}">'.format(im, esc(tname), esc(name)) for im in t.get('detail_images', []))
        details.append('    <details class="dispo-details"><summary>{n} — عرض التفاصيل</summary><div class="dd-body">{b}</div></details>'.format(
            n=esc(tname), b=esc(_t(t, 'detail_text', 'ar')) + imgs))
    return (
        '    <h3>التوفر — فيلا {name}</h3>\n'
        '    <div class="sub">{intro}</div>\n'
        '    <table class="dispo-table">\n'
        '      <thead><tr><th>النمط</th><th>عدد الشقق</th><th>الحالة</th></tr></thead>\n'
        '      <tbody>\n{rows}\n      </tbody>\n'
        '    </table>\n{details}\n'
        '    <div class="dispo-pending" style="margin-top:16px;">{note}</div>'
    ).format(name=esc(name), intro=esc(_t(dispo, 'intro', 'ar')), rows='\n'.join(rows), details='\n'.join(details), note=_t(dispo, 'note', 'ar'))

AR_ASSETS_RE = re.compile(r"(src=\"|src:')assets/")

def render_villa(v, all_villas, settings, finitions=None, lang='fr'):
    """Fiche résidence complète, en français (homepage/<slug>.html) ou en
    arabe (homepage/ar/<slug>.html) — les deux à partir des mêmes données du
    dashboard (champs `_ar` pour l'arabe, repli sur le français si vides)."""
    ar = lang == 'ar'
    tpl = load_template_ar() if ar else load_template()
    name = _t(v, 'name', lang)
    loc_full = _t(v, 'loc_full', lang)
    gal = [(g[0], _pair(g, 1, 2, lang)) for g in v.get('gallery', [])]
    plans = [(g[0], _pair(g, 1, 2, lang)) for g in v.get('plans', [])]
    gallery_fan_items = '\n'.join(fan_gal_item(img, cap, i) for i, (img, cap) in enumerate(gal))
    gallery_lb = ',\n'.join("    {{src:'assets/{}', cap:'{}'}}".format(img, cap.replace("'", "\\'")) for img, cap in gal)
    plan_fan_items = '\n'.join(fan_plan_item(img, cap, i) for i, (img, cap) in enumerate(plans))
    plan_lb = ',\n'.join("    {{src:'assets/{}', cap:'{}'}}".format(img, cap.replace("'", "\\'")) for img, cap in plans)
    feat_items = '\n'.join(feat_line(f[0], _pair(f, 1, 2, lang)) for f in v.get('feats', []))
    def interior(c):
        title = (c[3] if ar and len(c) > 3 and c[3] else c[1]) if len(c) > 1 else ''
        bullets = (c[4] if ar and len(c) > 4 and c[4] else c[2]) if len(c) > 2 else []
        return gs_interior_card(c[0], title, bullets)
    interior_cards = '\n'.join(interior(c) for c in v.get('interior', []))
    others = [o for o in all_villas if o['slug'] != v['slug']]
    switch_cards = '\n'.join(switch_card(o['slug'] + '.html', o['card_image'], _t(o, 'name', lang), _t(o, 'loc', lang), lang) for o in others)
    residence_options = '\n'.join('          <option{sel}>{p} {n}</option>'.format(p='فيلا' if ar else 'Villa', n=esc(_t(o, 'name', lang)), sel=' selected' if o['slug'] == v['slug'] else '') for o in all_villas)
    opts = (v.get('typebien_opts_ar') if ar else None) or v.get('typebien_opts', [])
    typebien_options = '\n'.join('          <option>{}</option>'.format(esc(t)) for t in opts)
    dispo_content = render_dispo_lang(v['dispo'], name, lang)

    # Ville toujours cliquable → localisation exacte (voir villa_maps_link).
    loc_maps = loc_link_html(v, esc(loc_full))
    loc_stat = loc_link_html(v, esc(loc_full), pin=False)
    maps_url = villa_maps_link(v)
    maps_block = (
        '    <!-- LOCALISATION -->\n'
        '    <div class="vs-block">\n'
        '      <div class="kicker"><span class="num">04</span></div>\n'
        '      <h2 class="h3">{h}</h2>\n'
        '      <p class="lede">{vl} {name} — {loc_full}. <a class="vs-loc-link" href="{u}" target="_blank" rel="noopener">{go}</a></p>\n'
        '      <div class="map-embed">\n'
        '        <iframe src="{src}" loading="lazy" referrerpolicy="no-referrer-when-downgrade" title="{h} {vl} {name}"></iframe>\n'
        '      </div>\n'
        '    </div>\n'
    ).format(name=esc(name), loc_full=esc(loc_full), u=esc(maps_url), src=esc(villa_map_embed(v)),
             h='الموقع' if ar else 'Localisation', vl='فيلا' if ar else 'Villa',
             go='عرض الاتجاهات على خرائط جوجل' if ar else "Voir l'itinéraire sur Google Maps")

    desc = _t(v, 'description', lang)
    share_text = '{} {} — {}. {}'.format('فيلا' if ar else 'Villa', name, loc_full, desc)[:180]
    share_url = 'https://newera-promotion.com/{}{}.html'.format('ar/' if ar else '', v['slug'])
    kicker = _t(v, 'kicker', lang) or ("فنّ العيش في كل تفاصيله" if ar else "L'art de vivre en toute exclusivité")

    html = tpl.format(
        slug=v['slug'], name=esc(name), loc=esc(_t(v, 'loc', lang)), loc_full=esc(loc_full), loc_maps=loc_maps, loc_stat=loc_stat,
        count=v['count'], count_units=ar_units(v['count']), typologie=esc(_t(v, 'typologie', lang)), kicker=esc(kicker),
        finitions_block=render_finitions_block(finitions, lang, '05', 'assets/'),
        hero_img=v['hero_img'], description=esc(desc),
        feat_items=feat_items, gallery_fan_items=gallery_fan_items, gallery_lb=gallery_lb,
        plan_fan_items=plan_fan_items, plan_lb=plan_lb, interior_cards=interior_cards,
        switch_cards=switch_cards, residence_options=residence_options, typebien_options=typebien_options,
        dispo_content=dispo_content, progress_square=progress_square_html(v, lang),
        maps_block=maps_block, share_text=esc(share_text), share_url=esc(share_url),
    )
    if ar:
        # Fragments générés en assets/… : depuis /ar/, le bon chemin est ../assets/…
        html = AR_ASSETS_RE.sub(lambda m: m.group(1) + '../assets/', html)
    html = renumber_blocks(html)
    html = apply_contact(html, settings)
    html = apply_float_cta(html, settings, lang)
    html = apply_cta_toggles(html, settings)
    html = apply_social_footer(html, settings, lang)
    if ar:
        os.makedirs(os.path.join(HOMEPAGE, 'ar'), exist_ok=True)
        with open(os.path.join(HOMEPAGE, 'ar', v['slug'] + '.html'), 'w', encoding='utf-8') as f:
            f.write(html)
    else:
        html = apply_blog_nav(html, settings)
        write_all(v['slug'] + '.html', html)

# ============================================================================
# GLOBAL CONTACT / BLOG-NAV SUBSTITUTION (applied to every generated/patched page)
# ============================================================================
def apply_contact(html, settings):
    """Remplace TOUS les numéros d'appel / WhatsApp du HTML par ceux des
    Réglages — pas seulement d'anciens numéros factices connus. Les pages
    patchées en place (accueil, À propos, Opportunités) et les pages AR
    gardaient sinon indéfiniment le premier numéro réel publié : un
    changement de numéro dans le dashboard n'y était jamais répercuté."""
    tel = (settings.get('phone_tel') or '').strip()
    wa = re.sub(r'\D', '', settings.get('whatsapp_number') or '') or re.sub(r'\D', '', tel)
    if tel:
        html = re.sub(r'tel:\+?\d{8,15}', 'tel:' + tel, html)
    if wa:
        html = re.sub(r'wa\.me/\d{8,15}', 'wa.me/' + wa, html)
    return html

PHONE_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
             '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.362 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.338 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>')

def apply_float_cta(html, settings, lang='fr'):
    """Bouton « Call » (brief client, même principe que Hamadat) : la bulle
    flottante affiche une icône TÉLÉPHONE (et non plus une bulle de
    discussion), et « Appeler maintenant » / WhatsApp sont de vrais liens
    tel:/wa.me vers le numéro des Réglages — auparavant c'étaient des
    <button> sans action : cliquer « Appeler maintenant » ne faisait rien.
    Idempotent (réappliqué à chaque build sur les pages patchées en place)."""
    tel = (settings.get('phone_tel') or '').strip()
    wa = re.sub(r'\D', '', settings.get('whatsapp_number') or '') or re.sub(r'\D', '', tel)
    label = 'اتصل بنا' if lang == 'ar' else 'Appeler'
    html = re.sub(r'(<div class="float-cta" id="floatCta"[^>]*>)\s*<svg.*?</svg>\s*(</div>)',
                  lambda m: m.group(1)[:-1].replace(' role="button"', '').replace(' tabindex="0"', '').replace(' aria-label="' + label + '"', '')
                  + ' role="button" tabindex="0" aria-label="' + label + '">' + PHONE_SVG + m.group(2), html, count=1, flags=re.S)
    html = re.sub(r'<(?:button|a) class="float-btn call"[^>]*>(.*?)</(?:button|a)>',
                  lambda m: '<a class="float-btn call" href="tel:{}">{}</a>'.format(esc(tel), m.group(1)), html)
    html = re.sub(r'<(?:button|a) class="float-btn wa"[^>]*>(.*?)</(?:button|a)>',
                  lambda m: '<a class="float-btn wa" href="https://wa.me/{}" target="_blank" rel="noopener">{}</a>'.format(esc(wa), m.group(1)), html)
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

def set_section_hidden(html, section_open_tag, hidden):
    """Toggle display:none on a <section ...> tag without touching its inner
    content. index.html is patched IN PLACE on every build (read_current
    re-reads the live output, there is no pristine template to fall back
    to) — so a disabled section's markup and content must survive the
    toggle intact, ready to reappear the moment it's re-enabled. Stripping
    the section outright would destroy that on the first disabled build."""
    hidden_tag = section_open_tag[:-1] + ' style="display:none">'
    if section_open_tag not in html and hidden_tag not in html:
        return html  # section not present, nothing to toggle
    html = html.replace(hidden_tag, section_open_tag)  # normalize first (idempotent)
    if hidden:
        html = html.replace(section_open_tag, hidden_tag, 1)
    return html

def toggle_tag_hidden(html, tag_regex, hidden):
    """Comme set_section_hidden, mais repère la balise par regex — elle peut
    porter des attributs variables (aria-label FR/AR, role, tabindex…)."""
    m = re.search(tag_regex, html)
    if not m:
        return html
    tag = m.group(0).replace(' style="display:none"', '')
    if hidden:
        tag = tag[:-1] + ' style="display:none">'
    return html[:m.start()] + tag + html[m.end():]

def apply_cta_toggles(html, settings):
    """Independently show/hide the floating call/WhatsApp bubble+card and the
    mobile mini-cta-bar, per dashboard toggle — mirrors Hamadat's per-element
    CTA toggles. Non-destructive, same reasoning as set_section_hidden above.
    Also emits a small JS flag object so main.js's own rdv-modal builder
    (which constructs the modal dynamically, not from static markup) can be
    gated by the third toggle (cta_rdv_modal_enabled)."""
    float_off = not settings.get('cta_float_enabled', True)
    html = toggle_tag_hidden(html, r'<div class="float-cta" id="floatCta"[^>]*>', float_off)
    html = toggle_tag_hidden(html, r'<div class="float-card" id="floatCard"[^>]*>', float_off)
    html = toggle_tag_hidden(html, r'<nav class="mini-cta-bar"[^>]*>', not settings.get('cta_minibar_enabled', True))

    flags = {
        'float': settings.get('cta_float_enabled', True),
        'minibar': settings.get('cta_minibar_enabled', True),
        'rdvModal': settings.get('cta_rdv_modal_enabled', True),
    }
    html = re.sub(r'\s*<script>window\.NEWERA_CTA_FLAGS=.*?</script>\n?', '\n', html)
    flags_script = '<script>window.NEWERA_CTA_FLAGS=' + json.dumps(flags) + ';</script>\n'
    if '</body>' in html:
        html = html.replace('</body>', flags_script + '</body>', 1)
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
def patch_homepage(home, villas, settings, videos=None, gallery=None, finitions=None):
    html = read_current('index.html')

    # Titre du hero optionnel : si "Titre" et "Accent" sont vides dans le
    # panneau (Page d'accueil), on n'affiche aucun texte sur l'image
    # principale — le <h1> reste présent (vide) pour ne pas casser la mise
    # en page ni le repérage du <p class="lede"> juste après.
    hero_title = (home.get('hero_title') or '').strip()
    hero_accent = (home.get('hero_accent') or '').strip()
    if hero_title or hero_accent:
        hero_h1 = '<h1 class="h1">{t} <span class="hl-accent flow">{a}</span></h1>'.format(t=esc(hero_title), a=esc(hero_accent))
    else:
        hero_h1 = '<h1 class="h1"></h1>'
    html = re.sub(
        r"<h1 class=\"h1\">.*?</h1>",
        hero_h1,
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

    if videos:
        html = re.sub(r'(<section class="sec" id="videos">.*?<span class="num">).*?(</span>)',
                       r'\g<1>' + esc(videos.get('section_kicker', '')) + r'\g<2>', html, count=1, flags=re.S)
        html = re.sub(r'(<section class="sec" id="videos">.*?<h2 class="h2"[^>]*>).*?(</h2>)',
                       r'\g<1>' + esc(videos.get('section_title', '')) + r'\g<2>', html, count=1, flags=re.S)
        html = re.sub(r'(<section class="sec" id="videos">.*?<p class="lede">).*?(</p>)',
                       r'\g<1>' + esc(videos.get('section_lede', '')) + r'\g<2>', html, count=1, flags=re.S)
        cards_html = '\n'.join(c for c in (video_card_html(it) for it in videos.get('items', [])) if c)
        html = replace_balanced_div(html, r'<div class="video-carousel__track" data-video-track>', '\n' + cards_html + '\n    ')

    if gallery:
        html = re.sub(r'(<section class="sec alt" id="catalogue"[^>]*>.*?<span class="num">).*?(</span>)',
                       r'\g<1>' + esc(gallery.get('kicker', '')) + r'\g<2>', html, count=1, flags=re.S)
        html = re.sub(r'(<section class="sec alt" id="catalogue"[^>]*>.*?<h2 class="h2"[^>]*>).*?(</h2>)',
                       r'\g<1>' + esc(gallery.get('title', '')) + r'\g<2>', html, count=1, flags=re.S)
        html = re.sub(r'(<section class="sec alt" id="catalogue"[^>]*>.*?<p class="lede">).*?(</p>)',
                       r'\g<1>' + esc(gallery.get('lede', '')) + r'\g<2>', html, count=1, flags=re.S)
        items_html = '\n'.join(c for c in (gallery_item_html(it, i) for i, it in enumerate(gallery.get('items', []))) if c)
        html = replace_balanced_div(html, r'<div class="fan-carousel reveal" id="catalogueCarousel">', '\n' + items_html + '\n  ')
        html = set_section_hidden(html, '<section class="sec alt" id="catalogue">', not gallery.get('enabled', True))

    html = replace_home_finitions(html, finitions, 'fr', 'assets/')
    html = apply_contact(html, settings)
    html = apply_float_cta(html, settings, 'fr')
    html = apply_cta_toggles(html, settings)
    html = apply_social_footer(html, settings)
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
    html = apply_float_cta(html, settings, 'fr')
    html = apply_cta_toggles(html, settings)
    html = apply_social_footer(html, settings)
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
    html = apply_float_cta(html, settings, 'fr')
    html = apply_cta_toggles(html, settings)
    html = apply_social_footer(html, settings)
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
        html = apply_float_cta(html, settings, 'fr')
        html = apply_cta_toggles(html, settings)
        html = apply_social_footer(html, settings)
        html = apply_blog_nav(html, settings)
        write_all('blog-{}.html'.format(p['slug']), html)

# ---------------------------------------------------------------- réseaux sociaux (pied de page)
SOCIAL_NETWORKS = [('facebook', 'Facebook'), ('instagram', 'Instagram'), ('linkedin', 'LinkedIn'),
                   ('tiktok', 'TikTok'), ('youtube', 'YouTube'), ('x', 'X')]
SOCIAL_START = '<!-- SOCIAL:START -->'
SOCIAL_END = '<!-- SOCIAL:END -->'

def social_footer_html(settings):
    """Icônes réseaux sociaux du pied de page (Réglages → Réseaux sociaux).
    Un champ vide masque l'icône : jamais de lien mort."""
    links = []
    for key, label in SOCIAL_NETWORKS:
        url = (settings.get('social_' + key) or '').strip()
        if not re.match(r'^https?://', url):
            continue
        svg = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
               'stroke-linejoin="round" aria-hidden="true">{}</svg>').format(FEAT_ICONS.get(key, ''))
        links.append('<a class="fsocial-link" href="{u}" target="_blank" rel="noopener" aria-label="{l}" title="{l}">{s}</a>'.format(
            u=esc(url), l=label, s=svg))
    inner = '<div class="fsocial">{}</div>'.format(''.join(links)) if links else ''
    return SOCIAL_START + inner + SOCIAL_END

def apply_social_footer(html, settings, lang='fr'):
    block = social_footer_html(settings)
    if SOCIAL_START in html and SOCIAL_END in html:
        return re.sub(re.escape(SOCIAL_START) + '.*?' + re.escape(SOCIAL_END), lambda m: block, html, count=1, flags=re.S)
    m = re.search(r'(<footer class="sitefooter">.*?<div class="fnav">.*?</div>)', html, flags=re.S)
    if not m:
        return html
    return html[:m.end()] + '\n  ' + block + html[m.end():]

# ============================================================================
# PAGES ARABES — accueil / à propos / opportunités (patch ciblé depuis les
# champs `_ar` du dashboard, même principe que les pages françaises).
# ============================================================================
def ar_units(count):
    """« 7 شقق » / « 14 شقة » : en arabe, le nom est au pluriel de 3 à 10."""
    try:
        n = int(count)
    except (TypeError, ValueError):
        return '{} شقة'.format(count)
    return '{} {}'.format(n, 'شقق' if 3 <= n <= 10 else 'شقة')

def res_equal_card_ar(v):
    return (
        '    <a class="res-equal-card" href="{slug}.html">\n'
        '      <div class="thumb">\n'
        '        <img src="../assets/{img}" alt="فيلا {name}">\n'
        '        <div class="thumb-scrim"></div>\n'
        '        <div class="res-logo"><img src="../assets/logo-wordmark-white-badge.png" alt="New Era"></div>\n'
        '        <div class="res-overlay-info"><b>{name}</b><span>{loc} · {units}</span></div>\n'
        '      </div>\n'
        '    </a>'
    ).format(slug=v['slug'], img=v['card_image'], name=esc(_t(v, 'name', 'ar')), loc=esc(_t(v, 'loc', 'ar')), units=ar_units(v['count']))

def patch_homepage_ar(html, home, villas, videos, gallery, finitions):
    t = lambda k: _t(home, k, 'ar')
    title, accent = t('hero_title').strip(), t('hero_accent').strip()
    h1 = '<h1 class="h1">{} <span class="hl-accent flow">{}</span></h1>'.format(esc(title), esc(accent)) if (title or accent) else '<h1 class="h1"></h1>'
    html = re.sub(r'<h1 class="h1">.*?</h1>', lambda m: h1, html, count=1, flags=re.S)
    html = re.sub(r'(<h1 class="h1">.*?</h1>\s*<p class="lede">).*?(</p>)', lambda m: m.group(1) + esc(t('hero_lede')) + m.group(2), html, count=1, flags=re.S)
    html = re.sub(r'(<div class="kicker manifesto-kicker">).*?(</div>)', lambda m: m.group(1) + esc(t('manifesto_kicker')) + m.group(2), html, count=1)
    html = re.sub(r'(<h2 class="manifesto-claim">).*?(</h2>)', lambda m: m.group(1) + esc(t('manifesto_claim')) + ' <span class="hl-accent">' + esc(t('manifesto_claim_accent')) + '</span>' + m.group(2), html, count=1, flags=re.S)
    html = re.sub(r'(<p class="manifesto-sub">).*?(</p>)', lambda m: m.group(1) + esc(t('manifesto_sub')) + m.group(2), html, count=1)
    cards = ['    <div class="ms-card" tabindex="0">\n      <b>{v}</b><span>{l}</span>\n      <div class="ms-detail">{d}</div>\n    </div>'.format(
        v=esc(_t(s, 'value', 'ar')), l=esc(_t(s, 'label', 'ar')), d=esc(_t(s, 'detail', 'ar'))) for s in home.get('stats', [])]
    html = replace_balanced_div(html, r'<div class="manifesto-stats">', '\n' + '\n'.join(cards) + '\n  ')
    by_slug = {v['slug']: v for v in villas}
    featured = [by_slug[s] for s in home.get('featured_villas', []) if s in by_slug]
    html = replace_balanced_div(html, r'<div class="res-equal reveal">', '\n' + '\n'.join(res_equal_card_ar(v) for v in featured) + '\n  ')
    if videos:
        html = re.sub(r'(<section class="sec" id="videos">.*?<span class="num">).*?(</span>)', lambda m: m.group(1) + esc(_t(videos, 'section_kicker', 'ar')) + m.group(2), html, count=1, flags=re.S)
        html = re.sub(r'(<section class="sec" id="videos">.*?<h2 class="h2"[^>]*>).*?(</h2>)', lambda m: m.group(1) + esc(_t(videos, 'section_title', 'ar')) + m.group(2), html, count=1, flags=re.S)
        html = re.sub(r'(<section class="sec" id="videos">.*?<p class="lede">).*?(</p>)', lambda m: m.group(1) + esc(_t(videos, 'section_lede', 'ar')) + m.group(2), html, count=1, flags=re.S)
        cards_html = '\n'.join(c for c in (video_card_html(it, 'ar') for it in videos.get('items', [])) if c)
        html = replace_balanced_div(html, r'<div class="video-carousel__track" data-video-track>', '\n' + cards_html + '\n    ')
    if gallery:
        html = re.sub(r'(<section class="sec alt" id="catalogue"[^>]*>.*?<span class="num">).*?(</span>)', lambda m: m.group(1) + esc(_t(gallery, 'kicker', 'ar')) + m.group(2), html, count=1, flags=re.S)
        html = re.sub(r'(<section class="sec alt" id="catalogue"[^>]*>.*?<h2 class="h2"[^>]*>).*?(</h2>)', lambda m: m.group(1) + esc(_t(gallery, 'title', 'ar')) + m.group(2), html, count=1, flags=re.S)
        html = re.sub(r'(<section class="sec alt" id="catalogue"[^>]*>.*?<p class="lede">).*?(</p>)', lambda m: m.group(1) + esc(_t(gallery, 'lede', 'ar')) + m.group(2), html, count=1, flags=re.S)
        items = []
        for i, it in enumerate(gallery.get('items', [])):
            if not it.get('asset'):
                continue
            cap = esc(it.get('caption_ar') or it.get('caption', ''))
            items.append('    <div class="fan-item" data-group="catalogue" data-index="{i}"><img src="../assets/{img}" alt="{c}">{ch}</div>'.format(
                i=i, img=it['asset'], c=cap, ch='<div class="cap">{}</div>'.format(cap) if cap else ''))
        html = replace_balanced_div(html, r'<div class="fan-carousel reveal" id="catalogueCarousel">', '\n' + '\n'.join(items) + '\n  ')
        html = set_section_hidden(html, '<section class="sec alt" id="catalogue">', not gallery.get('enabled', True))
    html = replace_home_finitions(html, finitions, 'ar', '../assets/')
    return html

def patch_simple_hero_ar(html, data):
    html = re.sub(r'(<h1 class="h1"[^>]*>).*?(</h1>)',
                  lambda m: m.group(1) + esc(_t(data, 'hero_title', 'ar')) + '<span class="hl-accent" style="font-size:clamp(16px,2vw,22px);text-transform:none;letter-spacing:0;font-weight:600;">' + esc(_t(data, 'hero_accent', 'ar')) + '</span>' + m.group(2),
                  html, count=1, flags=re.S)
    html = re.sub(r'(<p class="lede">).*?(</p>)', lambda m: m.group(1) + esc(_t(data, 'hero_lede', 'ar')) + m.group(2), html, count=1, flags=re.S)
    return html

def patch_ar_pages(villas, settings, finitions, videos, home=None, apropos=None, opportunites=None, gallery=None):
    """Pages arabes : les fiches résidence sont entièrement régénérées
    (render_villa lang='ar'), l'accueil / À propos / Opportunités sont
    patchés en place à partir des champs `_ar` du dashboard."""
    ar_dir = os.path.join(HOMEPAGE, 'ar')
    if not os.path.isdir(ar_dir):
        return 0
    for v in villas:
        render_villa(v, villas, settings, finitions, 'ar')
    count = 0
    for fn, data in (('index.html', home), ('a-propos.html', apropos), ('opportunites.html', opportunites)):
        path = os.path.join(ar_dir, fn)
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        if fn == 'index.html':
            html = patch_homepage_ar(html, home or {}, villas, videos, gallery, finitions)
        elif data:
            html = patch_simple_hero_ar(html, data)
        html = apply_contact(html, settings)
        html = apply_float_cta(html, settings, 'ar')
        html = apply_cta_toggles(html, settings)
        html = apply_social_footer(html, settings, 'ar')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        count += 1
    return count

def write_icons_data():
    """Regenerate admin/static/icons-data.js from icons.py — the single
    source of truth for icon SVG paths, shared between the generated HTML
    (via FEAT_ICONS, above) and the admin dashboard's visual icon picker
    (browser JS, which can't import a Python module). Mirrors the equivalent
    step in hamadat-promotion.com/build.js."""
    paths = {name: entry['d'] for name, entry in ICON_LIBRARY.items()}
    tags = {name: entry['tags'] for name, entry in ICON_LIBRARY.items()}
    js = (
        "// Fichier généré automatiquement par generator.py à partir de icons.py.\n"
        "// Ne pas éditer à la main — les modifications seraient écrasées au prochain build.\n"
        "window.NEWERA_ICON_PATHS = " + json.dumps(paths, ensure_ascii=False) + ";\n"
        "window.NEWERA_ICON_TAGS = " + json.dumps(tags, ensure_ascii=False) + ";\n"
    )
    static_dir = os.path.join(BASE, "static")
    os.makedirs(static_dir, exist_ok=True)
    with open(os.path.join(static_dir, "icons-data.js"), "w", encoding="utf-8") as f:
        f.write(js)

# ============================================================================
# ENTRY POINT
# ============================================================================
def publish():
    write_icons_data()
    if VERCEL_BUILD:
        sync_blob_assets()
    settings = load('settings.json')
    villas = load('villas.json')
    home = load('home.json')
    apropos = load('apropos.json')
    opportunites = load('opportunites.json')
    blog = load('blog.json') or []
    liens = load('liens.json')
    videos = load('videos.json') or {}
    gallery = load('gallery.json') or {}
    finitions = load('finitions.json') or {}

    for v in villas:
        render_villa(v, villas, settings, finitions)

    patch_homepage(home, villas, settings, videos, gallery, finitions)
    patch_simple_hero('a-propos.html', apropos, settings)
    patch_simple_hero('opportunites.html', opportunites, settings)
    render_liens(liens, settings)
    render_blog(blog, settings)
    patch_ar_pages(villas, settings, finitions, videos, home, apropos, opportunites, gallery)

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
