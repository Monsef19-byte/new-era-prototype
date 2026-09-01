/* Panneau d'administration New Era — vanilla JS, aucune dépendance. */
(function(){
  "use strict";

  var STATE = { villas: [], home: {}, apropos: {}, opportunites: {}, settings: {}, blog: [], liens: {}, videos: {}, gallery: {} };

  var LIENS_ICON_OPTIONS = [
    ["site", "Site web (globe)"],
    ["residences", "Résidences (maison)"],
    ["call", "Téléphone"],
    ["whatsapp", "WhatsApp"],
    ["instagram", "Instagram"],
    ["facebook", "Facebook"],
    ["linkedin", "LinkedIn"],
    ["tiktok", "TikTok"],
    ["email", "Email"],
    ["link", "Lien générique"]
  ];
  var VIEW = "residences";
  var VILLA_EDIT_SLUG = null;
  var VILLA_TAB = "general";
  var SAVE_TIMERS = {};
  var DIRTY = false;

  var contentEl = document.getElementById("content");
  var topTitle = document.getElementById("topTitle");
  var topSub = document.getElementById("topSub");
  var publishStatus = document.getElementById("publishStatus");

  // ------------------------------------------------------------ utils
  function esc(s){
    return (s == null ? "" : String(s)).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }
  function toast(msg, isError){
    var t = document.getElementById("toast");
    t.textContent = msg;
    t.className = "toast show" + (isError ? " error" : "");
    clearTimeout(t._timer);
    t._timer = setTimeout(function(){ t.className = "toast"; }, 3200);
  }

  // ------------------------------------------------------------ icon picker
  // Bibliothèque partagée avec le site (admin/static/icons-data.js, généré
  // au build à partir de admin/icons.py — même registre des deux côtés).
  function iconSvg(name, size){
    var paths = window.NEWERA_ICON_PATHS || {};
    var d = paths[name] || paths["check-circle"] || "";
    return '<svg width="' + (size||18) + '" height="' + (size||18) + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + d + '</svg>';
  }

  // Champ "sélecteur d'icône" : bouton affichant l'icône + son nom, qui ouvre
  // une grille de recherche au clic. onSelect(name) est appelé au choix.
  function iconPickerField(parent, opts){
    var label = opts.label, value = opts.value, onSelect = opts.onSelect;
    var wrap = document.createElement("div");
    wrap.className = "field";
    if(label){
      var lab = document.createElement("label");
      lab.textContent = label;
      wrap.appendChild(lab);
    }
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "icon-picker-btn";
    function paint(name){
      btn.innerHTML = iconSvg(name, 18) + "<span>" + esc(name || "Choisir une icône") + "</span>";
    }
    paint(value);
    btn.addEventListener("click", function(){
      openIconPickerModal(value, function(name){
        value = name;
        paint(name);
        onSelect(name);
      });
    });
    wrap.appendChild(btn);
    parent.appendChild(wrap);
    return wrap;
  }

  var _iconPickerOverlay = null;
  function _iconPickerEscHandler(e){
    if(e.key === "Escape") closeIconPickerModal();
  }
  function closeIconPickerModal(){
    if(_iconPickerOverlay){
      _iconPickerOverlay.remove();
      _iconPickerOverlay = null;
      document.removeEventListener("keydown", _iconPickerEscHandler);
    }
  }

  function openIconPickerModal(currentValue, onPick){
    closeIconPickerModal();
    var paths = window.NEWERA_ICON_PATHS || {};
    var tags = window.NEWERA_ICON_TAGS || {};
    var names = Object.keys(paths).sort();

    var overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML =
      '<div class="modal-card icon-picker-modal">' +
        '<div class="modal-header"><h3>Choisir une icône</h3><button type="button" class="modal-close" aria-label="Fermer">✕</button></div>' +
        '<input type="text" class="icon-picker-search" placeholder="Rechercher (ex : parking, wifi, piscine…)">' +
        '<div class="icon-picker-grid"></div>' +
      '</div>';
    document.body.appendChild(overlay);
    _iconPickerOverlay = overlay;

    var grid = overlay.querySelector(".icon-picker-grid");
    var search = overlay.querySelector(".icon-picker-search");

    function renderGrid(filter){
      var f = (filter || "").trim().toLowerCase();
      grid.innerHTML = "";
      var matches = names.filter(function(name){
        return !f || name.indexOf(f) !== -1 || (tags[name] || "").indexOf(f) !== -1;
      });
      matches.forEach(function(name){
        var cell = document.createElement("button");
        cell.type = "button";
        cell.className = "icon-picker-cell" + (name === currentValue ? " selected" : "");
        cell.innerHTML = iconSvg(name, 22) + "<span>" + esc(name) + "</span>";
        cell.addEventListener("click", function(){
          onPick(name);
          closeIconPickerModal();
        });
        grid.appendChild(cell);
      });
      if(!matches.length){
        var empty = document.createElement("div");
        empty.className = "icon-picker-empty";
        empty.textContent = "Aucune icône ne correspond à « " + f + " ».";
        grid.appendChild(empty);
      }
    }
    renderGrid("");
    search.addEventListener("input", function(){ renderGrid(search.value); });
    setTimeout(function(){ search.focus(); }, 30);

    overlay.querySelector(".modal-close").addEventListener("click", closeIconPickerModal);
    overlay.addEventListener("click", function(e){
      if(e.target === overlay) closeIconPickerModal();
    });
    document.addEventListener("keydown", _iconPickerEscHandler);
  }
  function markDirty(){
    DIRTY = true;
    publishStatus.textContent = "Modifications non publiées";
    publishStatus.className = "publish-status dirty";
  }
  function markClean(){
    DIRTY = false;
    publishStatus.textContent = "À jour";
    publishStatus.className = "publish-status";
  }
  function slugify(s){
    return (s||"").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g,"")
      .replace(/[^a-z0-9\s-]/g,"").trim().replace(/\s+/g,"-") || "residence";
  }
  function debounceSave(section){
    clearTimeout(SAVE_TIMERS[section]);
    SAVE_TIMERS[section] = setTimeout(function(){ saveSection(section); }, 500);
  }
  function saveSection(section){
    return fetch("/api/save?section=" + encodeURIComponent(section), {
      method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(STATE[section])
    }).then(function(r){ return r.json(); }).then(function(res){
      if(res.ok){ markDirty(); } else { toast("Erreur d'enregistrement : " + (res.error||""), true); }
      return res;
    });
  }
  function uploadImage(file, prefix){
    var fd = new FormData();
    fd.append("file", file);
    fd.append("prefix", prefix || "");
    return fetch("/api/upload", {method:"POST", body: fd}).then(function(r){ return r.json(); }).then(function(res){
      if(!res.ok){ toast("Erreur d'envoi de l'image : " + (res.error||""), true); throw new Error(res.error); }
      return res.filename;
    });
  }
  function assetUrl(fname){
    return "/api/preview-assets?file=" + encodeURIComponent(fname || "");
  }
  function uploadVideo(file){
    var fd = new FormData();
    fd.append("file", file);
    fd.append("prefix", "hero-video");
    return fetch("/api/upload", {method:"POST", body: fd}).then(function(r){ return r.json(); }).then(function(res){
      if(!res.ok){ toast("Erreur d'envoi de la vidéo : " + (res.error||""), true); throw new Error(res.error); }
      if(res.warning){ toast(res.warning, true); } else { toast("Vidéo envoyée et compressée automatiquement ✓"); }
      return res;
    });
  }

  // ------------------------------------------------------------ boot
  function loadContent(){
    return fetch("/api/content").then(function(r){
      if(r.status === 401){ window.location.href = "/login"; throw new Error("unauthorized"); }
      return r.json();
    }).then(function(data){
      STATE = data;
      markClean();
      render();
    });
  }

  document.getElementById("logoutBtn").addEventListener("click", function(){
    fetch("/api/logout", {method:"POST"}).then(function(){ window.location.href = "/login"; });
  });
  document.getElementById("publishBtn").addEventListener("click", function(){
    var btn = document.getElementById("publishBtn");
    btn.disabled = true; btn.textContent = "Publication…";
    fetch("/api/publish", {method:"POST"}).then(function(r){ return r.json(); }).then(function(res){
      btn.disabled = false; btn.textContent = "Publier les modifications";
      if(res.ok){ markClean(); toast("Site publié ✓ — " + res.villas + " résidences, blog " + (res.blog_enabled ? "activé" : "désactivé") + "."); }
      else { toast("Erreur de publication : " + (res.error||""), true); }
    }).catch(function(){
      btn.disabled = false; btn.textContent = "Publier les modifications";
      toast("Erreur de publication.", true);
    });
  });

  document.getElementById("sidebarNav").addEventListener("click", function(e){
    var btn = e.target.closest("button[data-view]");
    if(!btn) return;
    document.querySelectorAll("#sidebarNav button").forEach(function(b){ b.classList.remove("active"); });
    btn.classList.add("active");
    VIEW = btn.getAttribute("data-view");
    VILLA_EDIT_SLUG = null;
    render();
  });

  // ------------------------------------------------------------ render dispatch
  function render(){
    var titles = {
      residences: ["Résidences", "Ajoutez, modifiez ou supprimez une résidence."],
      home: ["Page d'accueil", "Le hero, les statistiques et les résidences mises en avant."],
      apropos: ["À Propos", "Le texte d'introduction de la page « À Propos »."],
      opportunites: ["Opportunités", "Le texte d'introduction de la page « Opportunités »."],
      blog: ["Blog", "Activez le blog et gérez les articles."],
      videos: ["Vidéos", "La section vidéos de la page d'accueil — collez un lien YouTube, la miniature et le lecteur se génèrent automatiquement."],
      gallery: ["Catalogue / Galerie", "Le carrousel « Catalogue » de la page d'accueil — photos, plans et documents."],
      liens: ["Page Liens (QR code)", "Tout ce qui apparaît sur newera-promotion.com/liens — logo, textes et cartes de liens."],
      leads: ["Demandes reçues", "Tous les formulaires envoyés depuis le site, stockés ici avant l'envoi de l'email de notification."],
      settings: ["Réglages & contact", "Numéros de téléphone, WhatsApp, réglages email et mot de passe du panneau."]
    };
    var t = titles[VIEW] || ["", ""];
    topTitle.textContent = t[0];
    topSub.textContent = t[1];

    if(VIEW === "residences"){
      if(VILLA_EDIT_SLUG){ renderVillaEditor(); } else { renderResidenceList(); }
    } else if(VIEW === "home"){ renderHome(); }
    else if(VIEW === "apropos"){ renderSimpleHero("apropos"); }
    else if(VIEW === "opportunites"){ renderSimpleHero("opportunites"); }
    else if(VIEW === "blog"){ renderBlog(); }
    else if(VIEW === "videos"){ renderVideos(); }
    else if(VIEW === "gallery"){ renderGallery(); }
    else if(VIEW === "liens"){ renderLiens(); }
    else if(VIEW === "leads"){ renderLeads(); }
    else if(VIEW === "settings"){ renderSettings(); }
  }

  // ============================================================== RÉSIDENCES — LISTE
  function renderResidenceList(){
    var html = '<div class="villa-list">';
    STATE.villas.forEach(function(v){
      var pct = v.progress_pct == null ? "à confirmer" : v.progress_pct + "%";
      html += '<div class="villa-card" data-slug="' + esc(v.slug) + '">' +
        '<div class="thumb" style="background-image:url(\'' + assetUrl(v.card_image) + '\')"><span class="pct">' + esc(pct) + '</span></div>' +
        '<div class="info"><b>' + esc(v.name) + '</b><span>' + esc(v.loc) + ' · ' + esc(v.count) + ' appartements</span></div>' +
        '</div>';
    });
    html += '<div class="add-villa-card" id="addVillaCard">+<br>Ajouter une résidence</div>';
    html += '</div>';
    contentEl.innerHTML = html;

    contentEl.querySelectorAll(".villa-card").forEach(function(card){
      card.addEventListener("click", function(){
        VILLA_EDIT_SLUG = card.getAttribute("data-slug");
        VILLA_TAB = "general";
        render();
      });
    });
    document.getElementById("addVillaCard").addEventListener("click", addVilla);
  }

  function addVilla(){
    var name = prompt("Nom de la nouvelle résidence (ex. « Diana »)");
    if(!name) return;
    var slug = "villa-" + slugify(name);
    if(STATE.villas.some(function(v){ return v.slug === slug; })){
      toast("Une résidence avec ce nom existe déjà.", true); return;
    }
    var v = {
      slug: slug, name: name, hero_img: "villa-agata.jpg", card_image: "villa-agata.jpg",
      loc: "Alger", loc_full: "Alger", google_maps: null, count: 0, typologie: "", progress_pct: null,
      description: "", feats: [], gallery: [], plans: [], interior: [],
      dispo: {intro: "", typologies: [], note: ""}, typebien_opts: []
    };
    STATE.villas.push(v);
    saveSection("villas");
    if(!STATE.home.featured_villas) STATE.home.featured_villas = [];
    STATE.home.featured_villas.push(slug);
    saveSection("home");
    VILLA_EDIT_SLUG = slug; VILLA_TAB = "general";
    render();
  }

  function deleteVilla(slug){
    if(!confirm("Supprimer définitivement cette résidence ? Cette action ne peut pas être annulée (après publication).")) return;
    STATE.villas = STATE.villas.filter(function(v){ return v.slug !== slug; });
    saveSection("villas");
    if(STATE.home.featured_villas){
      STATE.home.featured_villas = STATE.home.featured_villas.filter(function(s){ return s !== slug; });
      saveSection("home");
    }
    VILLA_EDIT_SLUG = null;
    render();
  }

  // ============================================================== RÉSIDENCES — ÉDITEUR
  function getVilla(){ return STATE.villas.find(function(v){ return v.slug === VILLA_EDIT_SLUG; }); }

  function renderVillaEditor(){
    var v = getVilla();
    if(!v){ VILLA_EDIT_SLUG = null; render(); return; }
    var tabs = [["general","Général"],["gallery","Galerie"],["feats","Caractéristiques"],["plans","Plan 3D"],["interior","Intérieur"],["dispo","Disponibilité"]];
    var html = '<button class="back-link" id="backToList">← Toutes les résidences</button>';
    html += '<div class="sub-tabs">' + tabs.map(function(t){
      return '<button data-tab="' + t[0] + '" class="' + (VILLA_TAB===t[0]?"active":"") + '">' + t[1] + '</button>';
    }).join('') + '</div>';
    html += '<div id="villaTabBody"></div>';
    contentEl.innerHTML = html;
    document.getElementById("backToList").addEventListener("click", function(){ VILLA_EDIT_SLUG = null; render(); });
    contentEl.querySelectorAll(".sub-tabs button").forEach(function(b){
      b.addEventListener("click", function(){ VILLA_TAB = b.getAttribute("data-tab"); render(); });
    });
    var body = document.getElementById("villaTabBody");
    if(VILLA_TAB === "general") renderVillaGeneral(body, v);
    else if(VILLA_TAB === "gallery") renderVillaImageList(body, v, "gallery", "Galerie — photos affichées dans le carrousel « Galerie » de la fiche.");
    else if(VILLA_TAB === "feats") renderVillaFeats(body, v);
    else if(VILLA_TAB === "plans") renderVillaImageList(body, v, "plans", "Plans 3D — affichés dans la section « Plan 3D ».");
    else if(VILLA_TAB === "interior") renderVillaInterior(body, v);
    else if(VILLA_TAB === "dispo") renderVillaDispo(body, v);
  }

  function field(label, inputHtml, hint){
    return '<div class="field"><label>' + esc(label) + '</label>' + inputHtml + (hint ? '<div class="hint">' + esc(hint) + '</div>' : '') + '</div>';
  }

  function renderVillaGeneral(body, v){
    body.innerHTML =
      '<div class="panel">' +
        '<h3>Photo de la fiche & de couverture</h3>' +
        '<p class="desc">Utilisée sur la page d\'accueil et en haut de la page de la résidence.</p>' +
        '<div class="img-list">' +
          '<div class="img-item"><div class="thumb" style="background-image:url(\'' + assetUrl(v.card_image) + '\')"></div><div class="hint" style="margin-top:5px;">Vignette (accueil)</div>' +
            '<input type="file" accept="image/*" id="uploadCard" style="margin-top:4px;font-size:11px;"></div>' +
          '<div class="img-item"><div class="thumb" style="background-image:url(\'' + assetUrl(v.hero_img) + '\')"></div><div class="hint" style="margin-top:5px;">Photo principale (fiche)</div>' +
            '<input type="file" accept="image/*" id="uploadHero" style="margin-top:4px;font-size:11px;"></div>' +
        '</div>' +
      '</div>' +
      '<div class="panel">' +
        '<h3>Informations générales</h3>' +
        '<div class="grid2">' +
          field("Nom de la résidence", '<input type="text" id="f_name" value="' + esc(v.name) + '">') +
          field("Statut", '<select id="f_pct_mode"><option value="pending"' + (v.progress_pct==null?' selected':'') + '>à confirmer</option><option value="pct"' + (v.progress_pct!=null?' selected':'') + '>Avancement en %</option></select>' +
            '<input type="number" id="f_pct" min="0" max="100" step="1" placeholder="ex. 45" value="' + (v.progress_pct==null?'':v.progress_pct) + '" style="margin-top:6px;' + (v.progress_pct==null?'display:none':'') + '">', "Choisissez « à confirmer » ou saisissez un pourcentage d'avancement (0 à 100).") +
          field("Localisation courte", '<input type="text" id="f_loc" value="' + esc(v.loc) + '">', "ex. « Hydra »") +
          field("Localisation complète", '<input type="text" id="f_locfull" value="' + esc(v.loc_full) + '">', "ex. « Hydra, Alger »") +
          field("Lien Google Maps", '<input type="text" id="f_maps" value="' + esc(v.google_maps || "") + '">', "Collez le lien « Partager » de Google Maps. Laissez vide pour ne pas afficher le bouton.") +
          field("Nombre d'appartements", '<input type="number" id="f_count" value="' + esc(v.count) + '">') +
          field("Typologie", '<input type="text" id="f_typo" value="' + esc(v.typologie) + '">', "ex. « F3, F4, F5 »") +
        '</div>' +
        field("Description", '<textarea id="f_desc">' + esc(v.description) + '</textarea>') +
      '</div>' +
      '<div class="panel">' +
        '<h3>Danger</h3>' +
        '<button class="btn btn-danger" id="deleteVillaBtn">Supprimer cette résidence</button>' +
      '</div>';

    function bindText(id, key, isNum){
      document.getElementById(id).addEventListener("input", function(){
        v[key] = isNum ? Number(this.value) : this.value;
        debounceSave("villas");
      });
    }
    bindText("f_name","name"); bindText("f_loc","loc"); bindText("f_locfull","loc_full");
    bindText("f_maps","google_maps");
    bindText("f_count","count",true); bindText("f_typo","typologie"); bindText("f_desc","description");
    var pctModeEl = document.getElementById("f_pct_mode");
    var pctInputEl = document.getElementById("f_pct");
    pctModeEl.addEventListener("change", function(){
      if(this.value === "pending"){
        v.progress_pct = null;
        pctInputEl.style.display = "none";
        pctInputEl.value = "";
      } else {
        pctInputEl.style.display = "";
        if(pctInputEl.value === "") pctInputEl.value = 0;
        v.progress_pct = Number(pctInputEl.value);
      }
      debounceSave("villas");
    });
    pctInputEl.addEventListener("input", function(){
      var n = this.value === "" ? 0 : Math.max(0, Math.min(100, Number(this.value)));
      v.progress_pct = n;
      debounceSave("villas");
    });
    document.getElementById("uploadCard").addEventListener("change", function(e){
      if(!e.target.files[0]) return;
      uploadImage(e.target.files[0], v.slug).then(function(fname){ v.card_image = fname; saveSection("villas").then(function(){ render(); }); });
    });
    document.getElementById("uploadHero").addEventListener("change", function(e){
      if(!e.target.files[0]) return;
      uploadImage(e.target.files[0], v.slug + "-hero").then(function(fname){ v.hero_img = fname; saveSection("villas").then(function(){ render(); }); });
    });
    document.getElementById("deleteVillaBtn").addEventListener("click", function(){ deleteVilla(v.slug); });
  }

  function renderVillaImageList(body, v, key, desc){
    function draw(){
      var items = v[key];
      var html = '<div class="panel"><h3>' + (key==="gallery"?"Galerie":"Plans 3D") + '</h3><p class="desc">' + esc(desc) + '</p>';
      html += '<div class="img-list">';
      items.forEach(function(item, i){
        html += '<div class="img-item" data-i="' + i + '">' +
          '<div class="thumb" style="background-image:url(\'' + assetUrl(item[0]) + '\')"><button class="rm" data-i="' + i + '">✕</button></div>' +
          '<input type="text" value="' + esc(item[1]) + '" data-i="' + i + '" placeholder="Légende">' +
          '</div>';
      });
      html += '</div>';
      html += '<div class="dropzone" id="dz_' + key + '">Glissez une image ici, ou cliquez pour en choisir une<input type="file" accept="image/*" id="fi_' + key + '"></div>';
      html += '</div>';
      body.innerHTML = html;

      body.querySelectorAll(".rm").forEach(function(btn){
        btn.addEventListener("click", function(){
          items.splice(Number(btn.getAttribute("data-i")), 1);
          saveSection("villas"); draw();
        });
      });
      body.querySelectorAll('.img-item input[type=text]').forEach(function(inp){
        inp.addEventListener("input", function(){
          items[Number(inp.getAttribute("data-i"))][1] = inp.value;
          debounceSave("villas");
        });
      });
      var dz = document.getElementById("dz_" + key);
      var fi = document.getElementById("fi_" + key);
      dz.addEventListener("click", function(){ fi.click(); });
      fi.addEventListener("change", function(){ if(fi.files[0]) handleFile(fi.files[0]); });
      ["dragover","dragleave","drop"].forEach(function(evt){
        dz.addEventListener(evt, function(e){
          e.preventDefault();
          if(evt==="dragover") dz.classList.add("drag");
          if(evt==="dragleave") dz.classList.remove("drag");
          if(evt==="drop"){ dz.classList.remove("drag"); if(e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); }
        });
      });
      function handleFile(file){
        uploadImage(file, v.slug + "-" + key).then(function(fname){
          items.push([fname, ""]);
          saveSection("villas"); draw();
        });
      }
    }
    draw();
  }

  function renderVillaFeats(body, v){
    function draw(){
      var html = '<div class="panel"><h3>Caractéristiques</h3><p class="desc">La liste affichée dans la section « Caractéristiques » de la fiche. Cliquez sur l\'icône pour la changer.</p><div class="list-editor">';
      v.feats.forEach(function(f, i){
        html += '<div class="row"><div class="icon-picker-slot" data-icon-i="' + i + '"></div><input type="text" value="' + esc(f[1]) + '" data-i="' + i + '"><button data-i="' + i + '">✕</button></div>';
      });
      html += '</div><button class="btn btn-sm add" id="addFeat">+ Ajouter une ligne</button></div>';
      body.innerHTML = html;
      body.querySelectorAll(".icon-picker-slot").forEach(function(slot){
        var i = Number(slot.getAttribute("data-icon-i"));
        iconPickerField(slot, {
          value: v.feats[i][0],
          onSelect: function(name){ v.feats[i][0] = name; saveSection("villas"); }
        });
      });
      body.querySelectorAll(".row input").forEach(function(inp){
        inp.addEventListener("input", function(){ v.feats[Number(inp.getAttribute("data-i"))][1] = inp.value; debounceSave("villas"); });
      });
      body.querySelectorAll(".row button").forEach(function(btn){
        btn.addEventListener("click", function(){ v.feats.splice(Number(btn.getAttribute("data-i")),1); saveSection("villas"); draw(); });
      });
      document.getElementById("addFeat").addEventListener("click", function(){
        v.feats.push(["archi", ""]); saveSection("villas"); draw();
      });
    }
    draw();
  }

  function renderVillaInterior(body, v){
    function draw(){
      var html = '<div class="panel"><h3>Intérieur</h3><p class="desc">Cartes avec photo, titre et points-clés — section « Intérieur » de la fiche.</p>';
      v.interior.forEach(function(card, i){
        html += '<div class="dispo-item" data-i="' + i + '">' +
          '<div class="row">' +
            '<div><div class="thumb" style="width:100%;height:90px;background:var(--paper-alt) center/cover no-repeat;background-image:url(\'' + assetUrl(card[0]) + '\');border-radius:6px;"></div>' +
              '<input type="file" accept="image/*" data-img="' + i + '" style="margin-top:6px;font-size:11px;"></div>' +
            '<div>' +
              '<input type="text" value="' + esc(card[1]) + '" data-title="' + i + '" placeholder="Titre" style="margin-bottom:8px;">' +
              '<textarea data-bullets="' + i + '" placeholder="Un point par ligne" style="width:100%;min-height:80px;padding:8px;border:1px solid var(--line);border-radius:6px;">' + esc(card[2].join("\n")) + '</textarea>' +
            '</div>' +
          '</div>' +
          '<button class="btn btn-sm btn-danger" data-rm="' + i + '">Supprimer cette carte</button>' +
        '</div>';
      });
      html += '<button class="btn btn-sm" id="addInterior">+ Ajouter une carte</button></div>';
      body.innerHTML = html;

      body.querySelectorAll('[data-title]').forEach(function(inp){
        inp.addEventListener("input", function(){ v.interior[Number(inp.getAttribute("data-title"))][1] = inp.value; debounceSave("villas"); });
      });
      body.querySelectorAll('[data-bullets]').forEach(function(ta){
        ta.addEventListener("input", function(){
          v.interior[Number(ta.getAttribute("data-bullets"))][2] = ta.value.split("\n").filter(function(s){ return s.trim(); });
          debounceSave("villas");
        });
      });
      body.querySelectorAll('[data-img]').forEach(function(fi){
        fi.addEventListener("change", function(){
          if(!fi.files[0]) return;
          var i = Number(fi.getAttribute("data-img"));
          uploadImage(fi.files[0], v.slug + "-int").then(function(fname){ v.interior[i][0] = fname; saveSection("villas").then(draw); });
        });
      });
      body.querySelectorAll('[data-rm]').forEach(function(btn){
        btn.addEventListener("click", function(){ v.interior.splice(Number(btn.getAttribute("data-rm")),1); saveSection("villas"); draw(); });
      });
      document.getElementById("addInterior").addEventListener("click", function(){
        v.interior.push(["villa-agata.jpg", "", []]); saveSection("villas"); draw();
      });
    }
    draw();
  }

  function renderVillaDispo(body, v){
    function draw(){
      var d = v.dispo;
      var html = '<div class="panel"><h3>Disponibilité</h3><p class="desc">Le tableau et les détails affichés dans la fenêtre « Voir les disponibilités ».</p>';
      html += field("Texte d'introduction", '<input type="text" id="dispoIntro" value="' + esc(d.intro) + '">');
      d.typologies.forEach(function(t, i){
        if(!t.detail_images) t.detail_images = [];
        var imgsHtml = '<div class="img-list" style="margin:8px 0;">';
        t.detail_images.forEach(function(im, ii){
          imgsHtml += '<div class="img-item" style="width:90px;"><div class="thumb" style="width:90px;height:66px;background-image:url(\'' + assetUrl(im) + '\')"><button class="rm" data-typo="' + i + '" data-img="' + ii + '">✕</button></div></div>';
        });
        imgsHtml += '</div><input type="file" accept="image/*" data-addimg="' + i + '" style="font-size:11px;">';

        html += '<div class="dispo-item" data-i="' + i + '">' +
          '<div class="row">' +
            field("Typologie", '<input type="text" data-name="'+i+'" value="' + esc(t.name) + '">') +
            field("Nb. d\'appartements", '<input type="text" data-count="'+i+'" value="' + esc(t.count) + '">') +
          '</div>' +
          '<div class="toggle-row" style="padding:4px 0 12px;"><span class="lbl" style="font-size:13px;">Confirmé (sinon « à confirmer »)</span>' +
            '<label class="switch"><input type="checkbox" data-confirmed="'+i+'" ' + (t.confirmed?'checked':'') + '><span class="slider"></span></label></div>' +
          field("Détail (texte optionnel)", '<textarea data-text="'+i+'">' + esc(t.detail_text) + '</textarea>') +
          field("Images de cette typologie (plans, photos — affichées dans « voir détails »)", imgsHtml) +
          '<button class="btn btn-sm btn-danger" data-rm="' + i + '">Supprimer cette typologie</button>' +
        '</div>';
      });
      html += '<button class="btn btn-sm" id="addTypo">+ Ajouter une typologie</button>';
      html += field("Note en bas de tableau", '<textarea id="dispoNote">' + esc(d.note) + '</textarea>');
      html += '</div>';
      body.innerHTML = html;

      document.getElementById("dispoIntro").addEventListener("input", function(){ d.intro = this.value; debounceSave("villas"); });
      document.getElementById("dispoNote").addEventListener("input", function(){ d.note = this.value; debounceSave("villas"); });
      body.querySelectorAll('[data-name]').forEach(function(inp){ inp.addEventListener("input", function(){ d.typologies[Number(inp.getAttribute("data-name"))].name = inp.value; debounceSave("villas"); }); });
      body.querySelectorAll('[data-count]').forEach(function(inp){ inp.addEventListener("input", function(){ d.typologies[Number(inp.getAttribute("data-count"))].count = inp.value; debounceSave("villas"); }); });
      body.querySelectorAll('[data-text]').forEach(function(ta){ ta.addEventListener("input", function(){ d.typologies[Number(ta.getAttribute("data-text"))].detail_text = ta.value; debounceSave("villas"); }); });
      body.querySelectorAll('[data-confirmed]').forEach(function(cb){
        cb.addEventListener("change", function(){
          var t = d.typologies[Number(cb.getAttribute("data-confirmed"))];
          t.confirmed = cb.checked;
          t.status_label = cb.checked ? "Confirmé" : "À confirmer";
          saveSection("villas");
        });
      });
      body.querySelectorAll('[data-rm]').forEach(function(btn){
        btn.addEventListener("click", function(){ d.typologies.splice(Number(btn.getAttribute("data-rm")),1); saveSection("villas"); draw(); });
      });
      body.querySelectorAll('.img-item .rm').forEach(function(btn){
        btn.addEventListener("click", function(){
          var ti = Number(btn.getAttribute("data-typo"));
          var ii = Number(btn.getAttribute("data-img"));
          d.typologies[ti].detail_images.splice(ii, 1);
          saveSection("villas"); draw();
        });
      });
      body.querySelectorAll('[data-addimg]').forEach(function(inp){
        inp.addEventListener("change", function(){
          if(!inp.files[0]) return;
          var ti = Number(inp.getAttribute("data-addimg"));
          uploadImage(inp.files[0], v.slug + "-dispo-" + ti).then(function(fname){
            d.typologies[ti].detail_images.push(fname);
            saveSection("villas"); draw();
          });
        });
      });
      document.getElementById("addTypo").addEventListener("click", function(){
        d.typologies.push({name:"", count:"à confirmer", status_label:"À confirmer", confirmed:false, detail_text:"", detail_images:[]});
        saveSection("villas"); draw();
      });
    }
    draw();
  }

  // ============================================================== ACCUEIL
  function renderHome(){
    var h = STATE.home;
    var html = '<div class="panel"><h3>Hero (bandeau principal)</h3><div class="grid2">' +
      field("Titre", '<input type="text" id="h_title" value="' + esc(h.hero_title) + '">') +
      field("Mot en accent (rouge)", '<input type="text" id="h_accent" value="' + esc(h.hero_accent) + '">') +
      '</div>' + field("Sous-titre", '<textarea id="h_lede">' + esc(h.hero_lede) + '</textarea>') + '</div>';

    html += '<div class="panel"><h3>Vidéo d\'accueil (arrière-plan du hero)</h3>' +
      '<p class="desc">Remplace la vidéo qui joue en fond sur la page d\'accueil. Compressée automatiquement si l\'outil ffmpeg est installé sur cet ordinateur ; sinon le fichier est mis en ligne tel quel — pensez à le compresser vous-même avant l\'envoi (ex. avec HandBrake) pour ne pas ralentir le site. La vidéo est mise à jour immédiatement, sans attendre le bouton « Publier ».</p>' +
      '<video src="' + assetUrl("hero-video.mp4") + '?t=' + Date.now() + '" style="width:260px;max-width:100%;border-radius:8px;display:block;margin-bottom:8px;background:#000;" muted controls></video>' +
      '<input type="file" accept="video/*" id="uploadHeroVideo">' +
      '<div id="heroVideoStatus" class="hint" style="margin-top:6px;"></div>' +
      '</div>';

    html += '<div class="panel"><h3>Bloc « Nous bâtissons un patrimoine »</h3><div class="grid2">' +
      field("Kicker (petit texte au-dessus)", '<input type="text" id="h_kicker" value="' + esc(h.manifesto_kicker) + '">') +
      field("Titre", '<input type="text" id="h_claim" value="' + esc(h.manifesto_claim) + '">') +
      field("Mot en accent", '<input type="text" id="h_claimaccent" value="' + esc(h.manifesto_claim_accent) + '">') +
      '</div>' + field("Sous-texte", '<textarea id="h_sub">' + esc(h.manifesto_sub) + '</textarea>') + '</div>';

    html += '<div class="panel"><h3>Statistiques (3 cartes)</h3>';
    h.stats.forEach(function(s, i){
      html += '<div class="dispo-item"><div class="row">' +
        field("Chiffre", '<input type="text" data-v="'+i+'" value="' + esc(s.value) + '">') +
        field("Libellé", '<input type="text" data-l="'+i+'" value="' + esc(s.label) + '">') +
        '</div>' + field("Détail (au survol)", '<input type="text" data-d="'+i+'" value="' + esc(s.detail) + '">') + '</div>';
    });
    html += '</div>';

    html += '<div class="panel"><h3>Résidences mises en avant</h3><p class="desc">Cochez les résidences à afficher sur la page d\'accueil.</p>';
    STATE.villas.forEach(function(v){
      var checked = (h.featured_villas||[]).indexOf(v.slug) !== -1;
      html += '<div class="toggle-row"><span class="lbl">' + esc(v.name) + '</span><label class="switch"><input type="checkbox" data-feat="' + esc(v.slug) + '" ' + (checked?'checked':'') + '><span class="slider"></span></label></div>';
    });
    html += '</div>';

    contentEl.innerHTML = html;

    function bind(id, key){ document.getElementById(id).addEventListener("input", function(){ h[key] = this.value; debounceSave("home"); }); }
    bind("h_title","hero_title"); bind("h_accent","hero_accent"); bind("h_lede","hero_lede");
    bind("h_kicker","manifesto_kicker"); bind("h_claim","manifesto_claim"); bind("h_claimaccent","manifesto_claim_accent"); bind("h_sub","manifesto_sub");

    contentEl.querySelectorAll('[data-v]').forEach(function(inp){ inp.addEventListener("input", function(){ h.stats[Number(inp.getAttribute("data-v"))].value = inp.value; debounceSave("home"); }); });
    contentEl.querySelectorAll('[data-l]').forEach(function(inp){ inp.addEventListener("input", function(){ h.stats[Number(inp.getAttribute("data-l"))].label = inp.value; debounceSave("home"); }); });
    contentEl.querySelectorAll('[data-d]').forEach(function(inp){ inp.addEventListener("input", function(){ h.stats[Number(inp.getAttribute("data-d"))].detail = inp.value; debounceSave("home"); }); });

    contentEl.querySelectorAll('[data-feat]').forEach(function(cb){
      cb.addEventListener("change", function(){
        var slug = cb.getAttribute("data-feat");
        h.featured_villas = h.featured_villas || [];
        if(cb.checked){ if(h.featured_villas.indexOf(slug)===-1) h.featured_villas.push(slug); }
        else { h.featured_villas = h.featured_villas.filter(function(s){ return s !== slug; }); }
        saveSection("home");
      });
    });

    document.getElementById("uploadHeroVideo").addEventListener("change", function(e){
      if(!e.target.files[0]) return;
      var statusEl = document.getElementById("heroVideoStatus");
      statusEl.textContent = "Envoi et compression en cours… cela peut prendre une minute pour une vidéo longue.";
      uploadVideo(e.target.files[0]).then(function(res){
        statusEl.textContent = res.warning || "Vidéo mise à jour et déjà en ligne ✓";
        render();
      }).catch(function(){ statusEl.textContent = "Échec de l'envoi."; });
    });
  }

  // ============================================================== A PROPOS / OPPORTUNITES
  function renderSimpleHero(section){
    var d = STATE[section];
    var html = '<div class="panel"><h3>Texte d\'introduction</h3><p class="desc">Le grand titre affiché en haut de la page.</p>' +
      field("Titre", '<input type="text" id="s_title" value="' + esc(d.hero_title) + '">') +
      field("Sous-titre (accent)", '<input type="text" id="s_accent" value="' + esc(d.hero_accent) + '">') +
      field("Texte descriptif", '<textarea id="s_lede">' + esc(d.hero_lede) + '</textarea>') +
      '</div>';
    contentEl.innerHTML = html;
    document.getElementById("s_title").addEventListener("input", function(){ d.hero_title = this.value; debounceSave(section); });
    document.getElementById("s_accent").addEventListener("input", function(){ d.hero_accent = this.value; debounceSave(section); });
    document.getElementById("s_lede").addEventListener("input", function(){ d.hero_lede = this.value; debounceSave(section); });
  }

  // ============================================================== BLOG
  function renderBlog(){
    var s = STATE.settings;
    var html = '<div class="panel"><div class="toggle-row"><span class="lbl">Activer le blog<div class="d">Affiche le lien « Blog » dans le menu et rend les pages accessibles.</div></span>' +
      '<label class="switch"><input type="checkbox" id="blogToggle" ' + (s.enable_blog?'checked':'') + '><span class="slider"></span></label></div></div>';

    html += '<div class="panel"><h3>Articles</h3><div class="blog-list" id="blogListWrap">';
    if(STATE.blog.length === 0) html += '<div class="empty">Aucun article pour le moment.</div>';
    STATE.blog.forEach(function(p, i){
      html += '<div class="blog-row" data-i="' + i + '">' +
        '<div class="thumb" style="background-image:url(\'' + assetUrl(p.image) + '\')"></div>' +
        '<div class="meta"><b>' + esc(p.title) + '</b><span>' + esc(p.date||"") + '</span></div>' +
        '<button class="btn btn-sm" data-edit="' + i + '">Modifier</button>' +
        '<button class="btn btn-sm btn-danger" data-rm="' + i + '">Supprimer</button>' +
      '</div>';
    });
    html += '</div><button class="btn btn-sm" id="addPost" style="margin-top:12px;">+ Nouvel article</button></div>';
    html += '<div id="postEditor"></div>';
    contentEl.innerHTML = html;

    document.getElementById("blogToggle").addEventListener("change", function(){ s.enable_blog = this.checked; saveSection("settings"); });
    contentEl.querySelectorAll('[data-rm]').forEach(function(btn){
      btn.addEventListener("click", function(){
        if(!confirm("Supprimer cet article ?")) return;
        STATE.blog.splice(Number(btn.getAttribute("data-rm")),1); saveSection("blog"); renderBlog();
      });
    });
    contentEl.querySelectorAll('[data-edit]').forEach(function(btn){
      btn.addEventListener("click", function(){ openPostEditor(Number(btn.getAttribute("data-edit"))); });
    });
    document.getElementById("addPost").addEventListener("click", function(){
      var post = {slug: "article-" + (STATE.blog.length+1), title: "Nouvel article", date: new Date().toISOString().slice(0,10), image: "villa-agata.jpg", body: ""};
      STATE.blog.push(post); saveSection("blog"); openPostEditor(STATE.blog.length - 1);
    });
  }

  function openPostEditor(i){
    var p = STATE.blog[i];
    var wrap = document.getElementById("postEditor");
    wrap.innerHTML = '<div class="panel"><h3>Modifier l\'article</h3>' +
      field("Titre", '<input type="text" id="p_title" value="' + esc(p.title) + '">') +
      field("Date", '<input type="text" id="p_date" value="' + esc(p.date) + '" placeholder="AAAA-MM-JJ">') +
      '<div class="field"><label>Image de couverture</label><div class="img-item"><div class="thumb" style="width:200px;height:130px;background-image:url(\'' + assetUrl(p.image) + '\')"></div><input type="file" accept="image/*" id="p_img" style="margin-top:6px;"></div></div>' +
      field("Contenu", '<textarea id="p_body" style="min-height:180px;">' + esc(p.body) + '</textarea>', "Un paragraphe par ligne.") +
      '<button class="btn btn-primary btn-sm" id="closeEditor">Terminé</button>' +
      '</div>';
    document.getElementById("p_title").addEventListener("input", function(){ p.title = this.value; p.slug = slugify(this.value); debounceSave("blog"); });
    document.getElementById("p_date").addEventListener("input", function(){ p.date = this.value; debounceSave("blog"); });
    document.getElementById("p_body").addEventListener("input", function(){ p.body = this.value; debounceSave("blog"); });
    document.getElementById("p_img").addEventListener("change", function(e){
      if(!e.target.files[0]) return;
      uploadImage(e.target.files[0], "blog-" + p.slug).then(function(fname){ p.image = fname; saveSection("blog").then(renderBlog); });
    });
    document.getElementById("closeEditor").addEventListener("click", renderBlog);
  }

  // ============================================================== VIDEOS
  function ne_youtubeId(url){
    url = (url || "").trim();
    var patterns = [
      /(?:youtube\.com\/watch\?[^#]*\bv=)([a-zA-Z0-9_-]{11})/,
      /(?:youtube\.com\/(?:embed|shorts)\/)([a-zA-Z0-9_-]{11})/,
      /(?:youtu\.be\/)([a-zA-Z0-9_-]{11})/
    ];
    for(var i=0;i<patterns.length;i++){
      var m = url.match(patterns[i]);
      if(m) return m[1];
    }
    return null;
  }

  function renderVideos(){
    var v = STATE.videos;
    if(!v.items) v.items = [];
    function draw(){
      var html = '<div class="panel"><h3>En-tête de la section</h3><div class="grid2">' +
        field("Kicker (petit texte)", '<input type="text" id="v_kicker" value="' + esc(v.section_kicker || "") + '">') +
        field("Titre", '<input type="text" id="v_title" value="' + esc(v.section_title || "") + '">') +
        '</div>' + field("Sous-titre", '<textarea id="v_lede">' + esc(v.section_lede || "") + '</textarea>') + '</div>';

      html += '<div class="panel"><h3>Vidéos</h3><p class="desc">Collez un lien YouTube (youtube.com/watch?v=..., youtu.be/... ou un lien « Partager »). La miniature et le lecteur se génèrent automatiquement — aucune vidéo n\'est affichée tant que le lien n\'est pas valide.</p>';
      v.items.forEach(function(item, i){
        var id = ne_youtubeId(item.url);
        html += '<div class="dispo-item" data-i="' + i + '">' +
          '<div class="row" style="align-items:center;">' +
            (id ? '<img src="https://img.youtube.com/vi/' + id + '/mqdefault.jpg" style="width:110px;height:80px;object-fit:cover;border-radius:8px;">'
                : '<div class="img-picker-empty" style="width:110px;height:80px;">Lien invalide</div>') +
            '<div style="flex:1;">' +
              field("Titre", '<input type="text" data-vtitle="' + i + '" value="' + esc(item.title) + '">') +
              field("Lien YouTube", '<input type="text" data-vurl="' + i + '" value="' + esc(item.url) + '">') +
            '</div>' +
          '</div>' +
          '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
            '<button class="btn btn-sm" data-vup="' + i + '"' + (i===0?' disabled':'') + '>↑ Monter</button>' +
            '<button class="btn btn-sm" data-vdown="' + i + '"' + (i===v.items.length-1?' disabled':'') + '>↓ Descendre</button>' +
            '<button class="btn btn-sm btn-danger" data-vrm="' + i + '">Supprimer</button>' +
          '</div>' +
        '</div>';
      });
      html += '<button class="btn btn-sm" id="addVideo" style="margin-top:10px;">+ Ajouter une vidéo</button></div>';

      contentEl.innerHTML = html;

      document.getElementById("v_kicker").addEventListener("input", function(){ v.section_kicker = this.value; debounceSave("videos"); });
      document.getElementById("v_title").addEventListener("input", function(){ v.section_title = this.value; debounceSave("videos"); });
      document.getElementById("v_lede").addEventListener("input", function(){ v.section_lede = this.value; debounceSave("videos"); });

      contentEl.querySelectorAll('[data-vtitle]').forEach(function(inp){
        inp.addEventListener("input", function(){ v.items[Number(inp.getAttribute("data-vtitle"))].title = inp.value; debounceSave("videos"); });
      });
      contentEl.querySelectorAll('[data-vurl]').forEach(function(inp){
        inp.addEventListener("input", function(){ v.items[Number(inp.getAttribute("data-vurl"))].url = inp.value; debounceSave("videos"); });
        inp.addEventListener("blur", function(){ saveSection("videos"); draw(); });
      });
      contentEl.querySelectorAll('[data-vrm]').forEach(function(btn){
        btn.addEventListener("click", function(){
          if(!confirm("Supprimer cette vidéo ?")) return;
          v.items.splice(Number(btn.getAttribute("data-vrm")), 1); saveSection("videos"); draw();
        });
      });
      contentEl.querySelectorAll('[data-vup]').forEach(function(btn){
        btn.addEventListener("click", function(){
          var i = Number(btn.getAttribute("data-vup"));
          if(i<=0) return;
          var tmp = v.items[i-1]; v.items[i-1] = v.items[i]; v.items[i] = tmp;
          saveSection("videos"); draw();
        });
      });
      contentEl.querySelectorAll('[data-vdown]').forEach(function(btn){
        btn.addEventListener("click", function(){
          var i = Number(btn.getAttribute("data-vdown"));
          if(i>=v.items.length-1) return;
          var tmp = v.items[i+1]; v.items[i+1] = v.items[i]; v.items[i] = tmp;
          saveSection("videos"); draw();
        });
      });
      document.getElementById("addVideo").addEventListener("click", function(){
        v.items.push({title:"Nouvelle vidéo", url:""});
        saveSection("videos"); draw();
      });
    }
    draw();
  }

  // ============================================================== CATALOGUE / GALERIE
  function renderGallery(){
    var g = STATE.gallery;
    if(!g.items) g.items = [];
    function draw(){
      var html = '<div class="panel"><div class="toggle-row"><span class="lbl">Activer le Catalogue / Galerie<div class="d">Quand désactivée, la section disparaît de la page d\'accueil même si des images sont présentes — pratique pour la masquer temporairement sans perdre le contenu.</div></span>' +
        '<label class="switch"><input type="checkbox" id="galleryToggle" ' + (g.enabled !== false ? 'checked' : '') + '><span class="slider"></span></label></div></div>';

      html += '<div class="panel"><h3>En-tête de la section</h3><div class="grid2">' +
        field("Kicker (petit texte)", '<input type="text" id="g_kicker" value="' + esc(g.kicker || "") + '">') +
        field("Titre", '<input type="text" id="g_title" value="' + esc(g.title || "") + '">') +
        '</div>' + field("Sous-titre", '<textarea id="g_lede">' + esc(g.lede || "") + '</textarea>') + '</div>';

      html += '<div class="panel"><h3>Images du catalogue</h3><p class="desc">Photos, plans ou documents affichés dans le carrousel « Catalogue » de la page d\'accueil.</p>';
      g.items.forEach(function(item, i){
        html += '<div class="dispo-item" data-i="' + i + '">' +
          '<div class="row">' +
            '<div><div class="thumb" style="width:100%;height:90px;background:var(--paper-alt) center/cover no-repeat;background-image:url(\'' + assetUrl(item.asset) + '\');border-radius:6px;"></div>' +
              '<input type="file" accept="image/*" data-gimg="' + i + '" style="margin-top:6px;font-size:11px;"></div>' +
            '<div>' +
              field("Légende (optionnelle)", '<input type="text" data-gcap="' + i + '" value="' + esc(item.caption || "") + '">') +
            '</div>' +
          '</div>' +
          '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
            '<button class="btn btn-sm" data-gup="' + i + '"' + (i===0?' disabled':'') + '>↑ Monter</button>' +
            '<button class="btn btn-sm" data-gdown="' + i + '"' + (i===g.items.length-1?' disabled':'') + '>↓ Descendre</button>' +
            '<button class="btn btn-sm btn-danger" data-grm="' + i + '">Supprimer</button>' +
          '</div>' +
        '</div>';
      });
      html += '<button class="btn btn-sm" id="addGalleryItem" style="margin-top:10px;">+ Ajouter une image</button></div>';

      contentEl.innerHTML = html;

      document.getElementById("galleryToggle").addEventListener("change", function(){ g.enabled = this.checked; saveSection("gallery"); });
      document.getElementById("g_kicker").addEventListener("input", function(){ g.kicker = this.value; debounceSave("gallery"); });
      document.getElementById("g_title").addEventListener("input", function(){ g.title = this.value; debounceSave("gallery"); });
      document.getElementById("g_lede").addEventListener("input", function(){ g.lede = this.value; debounceSave("gallery"); });

      contentEl.querySelectorAll('[data-gcap]').forEach(function(inp){
        inp.addEventListener("input", function(){ g.items[Number(inp.getAttribute("data-gcap"))].caption = inp.value; debounceSave("gallery"); });
      });
      contentEl.querySelectorAll('[data-gimg]').forEach(function(fi){
        fi.addEventListener("change", function(){
          if(!fi.files[0]) return;
          var i = Number(fi.getAttribute("data-gimg"));
          uploadImage(fi.files[0], "catalogue").then(function(fname){ g.items[i].asset = fname; saveSection("gallery").then(draw); });
        });
      });
      contentEl.querySelectorAll('[data-grm]').forEach(function(btn){
        btn.addEventListener("click", function(){
          if(!confirm("Supprimer cette image ?")) return;
          g.items.splice(Number(btn.getAttribute("data-grm")), 1); saveSection("gallery"); draw();
        });
      });
      contentEl.querySelectorAll('[data-gup]').forEach(function(btn){
        btn.addEventListener("click", function(){
          var i = Number(btn.getAttribute("data-gup"));
          if(i<=0) return;
          var tmp = g.items[i-1]; g.items[i-1] = g.items[i]; g.items[i] = tmp;
          saveSection("gallery"); draw();
        });
      });
      contentEl.querySelectorAll('[data-gdown]').forEach(function(btn){
        btn.addEventListener("click", function(){
          var i = Number(btn.getAttribute("data-gdown"));
          if(i>=g.items.length-1) return;
          var tmp = g.items[i+1]; g.items[i+1] = g.items[i]; g.items[i] = tmp;
          saveSection("gallery"); draw();
        });
      });
      document.getElementById("addGalleryItem").addEventListener("click", function(){
        g.items.push({asset:"", caption:""});
        saveSection("gallery"); draw();
      });
    }
    draw();
  }

  // ============================================================== PAGE LIENS (QR code)
  function renderLiens(){
    var l = STATE.liens;
    if(!l.cards) l.cards = [];
    function draw(){
      var html = '<div class="panel"><h3>En-tête de la page</h3><p class="desc">Le logo, le nom et les textes affichés en haut de la page <code>/liens</code>.</p>';
      html += '<div class="img-item" style="margin-bottom:14px;"><div class="thumb" style="width:96px;height:96px;border-radius:50%;background:var(--red) center/58% no-repeat;background-image:url(\'' + assetUrl(l.logo) + '\');"></div><div class="hint" style="margin-top:5px;">Logo (rond rouge)</div><input type="file" accept="image/*" id="liensLogoUpload" style="margin-top:4px;font-size:11px;"></div>';
      html += '<div class="grid2">' +
        field("Nom", '<input type="text" id="l_name" value="' + esc(l.name) + '">') +
        field("Accroche (en rouge)", '<input type="text" id="l_tagline" value="' + esc(l.tagline) + '">') +
        '</div>' + field("Sous-titre", '<textarea id="l_subtitle">' + esc(l.subtitle) + '</textarea>') + '</div>';

      html += '<div class="panel"><h3>Cartes de liens</h3><p class="desc">Chaque carte de la grille : icône, libellé, lien, et un interrupteur pour l\'afficher ou la masquer sans la supprimer.</p>';
      l.cards.forEach(function(c, i){
        html += '<div class="dispo-item" data-i="' + i + '">' +
          '<div class="row">' +
            field("Icône", '<select data-icon="' + i + '">' + LIENS_ICON_OPTIONS.map(function(o){
              return '<option value="' + o[0] + '"' + (c.icon===o[0]?' selected':'') + '>' + esc(o[1]) + '</option>';
            }).join('') + '</select>') +
            field("Libellé", '<input type="text" data-label="' + i + '" value="' + esc(c.label) + '">') +
          '</div>' +
          field("Lien", '<input type="text" data-href="' + i + '" value="' + esc(c.href) + '">', "URL complète, ou « tel:+213... », ou « mailto:... »") +
          '<div class="toggle-row" style="padding:4px 0 12px;"><span class="lbl" style="font-size:13px;">Afficher cette carte sur la page</span>' +
            '<label class="switch"><input type="checkbox" data-enabled="' + i + '" ' + (c.enabled!==false?'checked':'') + '><span class="slider"></span></label></div>' +
          '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
            '<button class="btn btn-sm" data-up="' + i + '"' + (i===0?' disabled':'') + '>↑ Monter</button>' +
            '<button class="btn btn-sm" data-down="' + i + '"' + (i===l.cards.length-1?' disabled':'') + '>↓ Descendre</button>' +
            '<button class="btn btn-sm btn-danger" data-rm="' + i + '">Supprimer</button>' +
          '</div>' +
        '</div>';
      });
      html += '<button class="btn btn-sm" id="addLiensCard" style="margin-top:10px;">+ Ajouter une carte</button></div>';

      html += '<div class="panel"><div class="hint">Page publique : <a href="/liens/" target="_blank" rel="noopener">newera-promotion.com/liens</a> — c\'est ce lien qu\'il faut encoder dans le QR code du print. Cliquez « Publier » après modification pour la mettre à jour.</div></div>';

      contentEl.innerHTML = html;

      document.getElementById("l_name").addEventListener("input", function(){ l.name = this.value; debounceSave("liens"); });
      document.getElementById("l_tagline").addEventListener("input", function(){ l.tagline = this.value; debounceSave("liens"); });
      document.getElementById("l_subtitle").addEventListener("input", function(){ l.subtitle = this.value; debounceSave("liens"); });
      document.getElementById("liensLogoUpload").addEventListener("change", function(e){
        if(!e.target.files[0]) return;
        uploadImage(e.target.files[0], "liens-logo").then(function(fname){ l.logo = fname; saveSection("liens").then(draw); });
      });

      contentEl.querySelectorAll('[data-icon]').forEach(function(sel){
        sel.addEventListener("change", function(){ l.cards[Number(sel.getAttribute("data-icon"))].icon = sel.value; saveSection("liens"); });
      });
      contentEl.querySelectorAll('[data-label]').forEach(function(inp){
        inp.addEventListener("input", function(){ l.cards[Number(inp.getAttribute("data-label"))].label = inp.value; debounceSave("liens"); });
      });
      contentEl.querySelectorAll('[data-href]').forEach(function(inp){
        inp.addEventListener("input", function(){ l.cards[Number(inp.getAttribute("data-href"))].href = inp.value; debounceSave("liens"); });
      });
      contentEl.querySelectorAll('[data-enabled]').forEach(function(cb){
        cb.addEventListener("change", function(){ l.cards[Number(cb.getAttribute("data-enabled"))].enabled = cb.checked; saveSection("liens"); });
      });
      contentEl.querySelectorAll('[data-rm]').forEach(function(btn){
        btn.addEventListener("click", function(){
          if(!confirm("Supprimer cette carte ?")) return;
          l.cards.splice(Number(btn.getAttribute("data-rm")), 1); saveSection("liens"); draw();
        });
      });
      contentEl.querySelectorAll('[data-up]').forEach(function(btn){
        btn.addEventListener("click", function(){
          var i = Number(btn.getAttribute("data-up"));
          if(i<=0) return;
          var tmp = l.cards[i-1]; l.cards[i-1] = l.cards[i]; l.cards[i] = tmp;
          saveSection("liens"); draw();
        });
      });
      contentEl.querySelectorAll('[data-down]').forEach(function(btn){
        btn.addEventListener("click", function(){
          var i = Number(btn.getAttribute("data-down"));
          if(i>=l.cards.length-1) return;
          var tmp = l.cards[i+1]; l.cards[i+1] = l.cards[i]; l.cards[i] = tmp;
          saveSection("liens"); draw();
        });
      });
      document.getElementById("addLiensCard").addEventListener("click", function(){
        l.cards.push({icon:"link", label:"Nouveau lien", href:"#", enabled:true});
        saveSection("liens"); draw();
      });
    }
    draw();
  }

  // ============================================================== RÉGLAGES
  function renderSettings(){
    var s = STATE.settings;
    var html = '<div class="panel"><h3>Coordonnées de contact</h3><p class="desc">Utilisées dans tous les boutons Appeler / WhatsApp / RDV du site.</p><div class="grid2">' +
      field("Téléphone (affiché)", '<input type="text" id="c_disp" value="' + esc(s.phone_display) + '">', "ex. « 0561 23 45 67 »") +
      field("Téléphone (format international, pour les liens)", '<input type="text" id="c_tel" value="' + esc(s.phone_tel) + '">', "ex. « +213561234567 »") +
      field("Numéro WhatsApp", '<input type="text" id="c_wa" value="' + esc(s.whatsapp_number) + '">', "ex. « 213561234567 » (sans le +)") +
      field("Email", '<input type="text" id="c_email" value="' + esc(s.email) + '">') +
      '</div></div>';

    html += '<div class="panel"><h3>Boutons d\'action (CTA)</h3><p class="desc">Activez ou désactivez indépendamment chaque bouton d\'appel à l\'action présent sur toutes les pages du site.</p>' +
      '<div class="toggle-row"><span class="lbl">Bulle flottante Appeler / WhatsApp<div class="d">La bulle ronde en bas de l\'écran qui ouvre une petite carte « Appeler maintenant / WhatsApp ».</div></span>' +
      '<label class="switch"><input type="checkbox" id="ctaFloatToggle" ' + (s.cta_float_enabled!==false?'checked':'') + '><span class="slider"></span></label></div>' +
      '<div class="toggle-row"><span class="lbl">Barre d\'actions mobile<div class="d">La barre fixe en bas de l\'écran sur mobile (Appeler / WhatsApp / RDV).</div></span>' +
      '<label class="switch"><input type="checkbox" id="ctaMinibarToggle" ' + (s.cta_minibar_enabled!==false?'checked':'') + '><span class="slider"></span></label></div>' +
      '<div class="toggle-row"><span class="lbl">Fenêtre « Prendre rendez-vous »<div class="d">La fenêtre qui s\'ouvre sur chaque bouton « Prendre rendez-vous » du site (Appeler / Email / Formulaire).</div></span>' +
      '<label class="switch"><input type="checkbox" id="ctaRdvToggle" ' + (s.cta_rdv_modal_enabled!==false?'checked':'') + '><span class="slider"></span></label></div>' +
      '</div>';

    html += '<div class="panel"><h3>Réglages Email — notifications des demandes</h3>' +
      '<p class="desc">C\'est ici, et uniquement ici, que se configure l\'email qui reçoit les demandes envoyées depuis le site (RDV résidences, formulaire Opportunités). Aucune intervention technique n\'est nécessaire : remplissez ces champs comme vous le feriez dans n\'importe quelle boîte mail, puis testez l\'envoi avant de publier.</p>' +
      '<div class="grid2">' +
      field("Email qui reçoit les demandes", '<input type="text" id="e_recipient" value="' + esc(s.lead_recipient) + '">', "L'adresse qui recevra chaque nouvelle demande, ex. contact@newera-promotion.com") +
      field("Nom de l'expéditeur", '<input type="text" id="e_sendername" value="' + esc(s.smtp_sender_name) + '">', "Le nom affiché comme expéditeur, ex. « New Era — Site Web »") +
      field("Adresse email d'envoi (boîte mail)", '<input type="text" id="e_user" value="' + esc(s.smtp_user) + '">', "La boîte mail qui envoie les notifications, ex. contact@newera-promotion.com") +
      field("Serveur SMTP (host)", '<input type="text" id="e_host" value="' + esc(s.smtp_host) + '">', "Hostinger : smtp.hostinger.com — Gmail : smtp.gmail.com") +
      field("Port SMTP", '<input type="text" id="e_port" value="' + esc(s.smtp_port) + '">', "465 (SSL) ou 587 (TLS) selon votre fournisseur") +
      '</div>' +
      '<button class="btn btn-sm" id="testEmailBtn">Tester l\'envoi</button><div class="hint" id="emailTestMsg" style="margin-top:8px;"></div>' +
      '</div>';

    html += '<div class="panel"><h3>Mot de passe SMTP</h3><p class="desc">Volontairement absent de ce dashboard : comme les autres identifiants du projet, il n\'est jamais stocké dans le contenu (Blob), uniquement dans la variable d\'environnement Vercel SMTP_PASSWORD.</p>' +
      '<div class="card-sub" id="smtpPwStatus">' + (s.smtp_password_set
        ? '<span class="badge badge-teal">Configuré</span> — SMTP_PASSWORD est défini côté serveur.'
        : '<span class="badge badge-grey">Non configuré</span> — ajoutez la variable d\'environnement SMTP_PASSWORD dans Vercel (Project Settings → Environment Variables), pour un compte Gmail utilisez un « mot de passe d\'application », pas le mot de passe normal.') +
      '</div></div>';

    html += '<div class="panel"><h3>Mot de passe du panneau</h3><div class="grid2">' +
      field("Mot de passe actuel", '<input type="password" id="pw_current">') +
      field("Nouveau mot de passe", '<input type="password" id="pw_new">') +
      '</div><button class="btn btn-sm" id="changePwBtn">Changer le mot de passe</button><div class="hint" id="pwMsg" style="margin-top:8px;"></div></div>';

    contentEl.innerHTML = html;
    function bind(id, key){ document.getElementById(id).addEventListener("input", function(){ s[key] = this.value; debounceSave("settings"); }); }
    bind("c_disp","phone_display"); bind("c_tel","phone_tel"); bind("c_wa","whatsapp_number"); bind("c_email","email");
    bind("e_recipient","lead_recipient"); bind("e_sendername","smtp_sender_name"); bind("e_user","smtp_user");
    bind("e_host","smtp_host"); bind("e_port","smtp_port");

    document.getElementById("ctaFloatToggle").addEventListener("change", function(){ s.cta_float_enabled = this.checked; saveSection("settings"); });
    document.getElementById("ctaMinibarToggle").addEventListener("change", function(){ s.cta_minibar_enabled = this.checked; saveSection("settings"); });
    document.getElementById("ctaRdvToggle").addEventListener("change", function(){ s.cta_rdv_modal_enabled = this.checked; saveSection("settings"); });

    document.getElementById("testEmailBtn").addEventListener("click", function(){
      var btn = this;
      var msg = document.getElementById("emailTestMsg");
      btn.disabled = true; msg.textContent = "Envoi en cours…"; msg.style.color = "";
      fetch("/api/test-email", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({
        lead_recipient: s.lead_recipient, smtp_host: s.smtp_host, smtp_port: s.smtp_port,
        smtp_user: s.smtp_user, smtp_sender_name: s.smtp_sender_name
      })}).then(function(r){ return r.json(); }).then(function(res){
        btn.disabled = false;
        if(res.ok){ msg.textContent = "Email de test envoyé ✓ — vérifiez la boîte de réception."; msg.style.color = "var(--ok)"; }
        else { msg.textContent = "Échec : " + (res.error || "erreur inconnue"); msg.style.color = "var(--red)"; }
      }).catch(function(){ btn.disabled = false; msg.textContent = "Échec de la requête."; msg.style.color = "var(--red)"; });
    });

    document.getElementById("changePwBtn").addEventListener("click", function(){
      var cur = document.getElementById("pw_current").value;
      var neu = document.getElementById("pw_new").value;
      fetch("/api/change-password", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({current:cur, new:neu})})
        .then(function(r){ return r.json(); }).then(function(res){
          var msg = document.getElementById("pwMsg");
          if(res.ok){ msg.textContent = "Mot de passe changé ✓"; msg.style.color = "var(--ok)"; document.getElementById("pw_current").value=""; document.getElementById("pw_new").value=""; }
          else { msg.textContent = res.error || "Erreur"; msg.style.color = "var(--red)"; }
        });
    });
  }

  // ============================================================== DEMANDES REÇUES (LEADS)
  var LEADS_CACHE = null;
  var LEAD_CODE_LABELS = {
    "NE-RES-AGATA": "Résidence — Agata", "NE-RES-VERONICA": "Résidence — Veronica",
    "NE-RES-CHRISTINA": "Résidence — Christina", "NE-RES-CATRINA": "Résidence — Catrina",
    "NE-TER-VENDRE": "Terrain — Vente", "NE-TER-ACHETER": "Terrain — Achat", "NE-TER-TROC": "Terrain — Troc",
    "NE-AUTRE": "Autre / non classé"
  };
  function renderLeads(){
    contentEl.innerHTML = '<div class="empty">Chargement des demandes…</div>';
    fetch("/api/leads").then(function(r){
      if(r.status === 401){ window.location.href = "/login"; throw new Error("unauthorized"); }
      return r.json();
    }).then(function(data){
      LEADS_CACHE = data;
      paintLeads(data);
    }).catch(function(){
      contentEl.innerHTML = '<div class="empty">Impossible de charger les demandes.</div>';
    });
  }
  function paintLeads(data){
    var statsHtml = '<div class="panel"><h3>Statistiques</h3><div class="grid2">' +
      field("Total des demandes", '<div style="font-size:22px;font-weight:700;">' + data.total + '</div>') +
      field("30 derniers jours", '<div style="font-size:22px;font-weight:700;">' + data.last_30_days + '</div>') +
      '</div><div class="hint" style="margin-top:10px;">' +
      Object.keys(LEAD_CODE_LABELS).map(function(code){
        var n = (data.by_code && data.by_code[code]) || 0;
        return esc(LEAD_CODE_LABELS[code]) + ' : <b>' + n + '</b>';
      }).join(' &nbsp;·&nbsp; ') +
      '</div></div>';

    var rows = (data.leads || []).map(function(l){
      var f = l.fields || {};
      return '<tr><td>' + esc(l.received_at || '') + '</td>' +
        '<td>' + esc(l.type_label || '') + ' — ' + esc(l.subtype_label || '') + '</td>' +
        '<td>' + esc(f['Nom & Prénom'] || '') + '</td>' +
        '<td>' + esc(f['Téléphone'] || '') + '</td>' +
        '<td>' + esc(f['Email'] || '') + '</td>' +
        '<td><code>' + esc(l.code || '') + '</code></td></tr>';
    }).join('');

    var tableHtml = '<div class="panel"><h3>Toutes les demandes (' + (data.leads || []).length + ' affichées)</h3>' +
      (rows ? '<table class="leads-table"><thead><tr><th>Reçu le</th><th>Type</th><th>Nom</th><th>Téléphone</th><th>Email</th><th>Code CRM</th></tr></thead><tbody>' + rows + '</tbody></table>'
            : '<div class="empty">Aucune demande reçue pour le moment.</div>') +
      '</div>';

    contentEl.innerHTML = statsHtml + tableHtml;
  }

  loadContent();
})();
