/* ============================================================
   NEW ERA — shared site behavior (v2 redesign)
   Theme toggle, header solid-on-scroll, mobile menu, reveal-on-scroll,
   coverflow carousel, single-slide detail carousel, floating CTA,
   disponibilité modal, lightbox. Shared across all pages.
   ============================================================ */

(function(){
  var root = document.documentElement;
  var stored = localStorage.getItem('ne-theme');
  var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  var initial = stored || (prefersDark ? 'dark' : 'light');
  if(initial === 'dark'){ root.setAttribute('data-theme','dark'); }
  var themeBtn = document.getElementById('themeToggle');
  if(themeBtn){
    themeBtn.addEventListener('click', function(){
      var isDark = root.getAttribute('data-theme') === 'dark';
      if(isDark){ root.removeAttribute('data-theme'); localStorage.setItem('ne-theme','light'); }
      else{ root.setAttribute('data-theme','dark'); localStorage.setItem('ne-theme','dark'); }
    });
  }
})();

var siteHeader = document.getElementById('siteHeader');
if(siteHeader){
  var lastScrollY = window.scrollY;
  window.addEventListener('scroll', function(){
    var y = window.scrollY;
    siteHeader.classList.toggle('solid', y > 60);
    if(y > lastScrollY && y > 140){
      siteHeader.classList.add('hide');
    } else if(y < lastScrollY){
      siteHeader.classList.remove('hide');
    }
    lastScrollY = y;
  }, {passive:true});
}

var floatCta = document.getElementById('floatCta');
var floatCard = document.getElementById('floatCard');
if(floatCta && floatCard){
  floatCta.addEventListener('click', function(){ floatCard.classList.toggle('show'); });
  var floatClose = document.getElementById('floatClose');
  if(floatClose) floatClose.addEventListener('click', function(){ floatCard.classList.remove('show'); });
}

var mobileMenu = document.getElementById('mobileMenu');
if(mobileMenu){
  function openMenu(){ mobileMenu.classList.add('open'); document.body.style.overflow = 'hidden'; }
  function closeMenu(){ mobileMenu.classList.remove('open'); document.body.style.overflow = ''; }
  var burgerBtn = document.getElementById('burgerBtn');
  var menuToggle = document.getElementById('menuToggle');
  var mobileMenuClose = document.getElementById('mobileMenuClose');
  if(burgerBtn) burgerBtn.addEventListener('click', openMenu);
  if(menuToggle) menuToggle.addEventListener('click', openMenu);
  if(mobileMenuClose) mobileMenuClose.addEventListener('click', closeMenu);
  document.querySelectorAll('.mobile-menu-links a, .mobile-menu .btn').forEach(function(el){
    el.addEventListener('click', closeMenu);
  });
}

/* ---- Progress rail: tracks which [data-chapter] section is in view, click-to-jump ---- */
var railEl = document.getElementById('rail');
if(railEl){
  var chapters = Array.prototype.slice.call(document.querySelectorAll('[data-chapter]'));
  chapters.forEach(function(ch, i){
    var dot = document.createElement('button');
    dot.className = 'rail-dot' + (i === 0 ? ' active' : '');
    dot.innerHTML = '<span class="dot"></span><span class="rail-label">' + ch.getAttribute('data-chapter') + '</span>';
    dot.addEventListener('click', function(){ ch.scrollIntoView({behavior:'smooth'}); });
    railEl.appendChild(dot);
  });
  var railDots = Array.prototype.slice.call(railEl.querySelectorAll('.rail-dot'));
  var chapterIO = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      var idx = chapters.indexOf(e.target);
      if(e.isIntersecting){
        railDots.forEach(function(d){ d.classList.remove('active'); });
        if(railDots[idx]) railDots[idx].classList.add('active');
      }
    });
  }, {threshold:0.5});
  chapters.forEach(function(ch){ chapterIO.observe(ch); });
}

/* ---- Chapter progress counter (e.g. "02 / 09") ---- */
var progressEls = Array.prototype.slice.call(document.querySelectorAll('.chapter-progress[data-total]'));
if(progressEls.length){
  var allChapters = Array.prototype.slice.call(document.querySelectorAll('[data-chapter]'));
  var progIO = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting){
        var idx = allChapters.indexOf(e.target) + 1;
        progressEls.forEach(function(p){ p.textContent = String(idx).padStart(2,'0') + ' / ' + p.getAttribute('data-total'); });
      }
    });
  }, {threshold:0.5});
  allChapters.forEach(function(ch){ progIO.observe(ch); });
}

var io = new IntersectionObserver(function(entries){
  entries.forEach(function(e){
    if(e.isIntersecting){ e.target.classList.add('in-view'); io.unobserve(e.target); }
  });
}, {threshold:0.12});
document.querySelectorAll('.reveal, .reveal-img').forEach(function(el){ io.observe(el); });

/* ---- Scroll progress bar: thin fixed line at the very top, familiar wayfinding cue ---- */
var progressBar = document.getElementById('scrollProgress');
if(progressBar){
  var updateProgress = function(){
    var h = document.documentElement;
    var scrolled = h.scrollTop;
    var max = h.scrollHeight - h.clientHeight;
    progressBar.style.width = (max > 0 ? (scrolled / max) * 100 : 0) + '%';
  };
  window.addEventListener('scroll', updateProgress, {passive:true});
  updateProgress();
}

var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---- Fan carousel (every gallery site-wide): drag + mouse-wheel stacked cards. Generalized, multi-instance port of the reference "carousel with drag and wheel" interaction — each instance keeps its own progress/active/isDown state in a closure, and wheel/drag listeners are scoped to that instance's own container instead of the document. ---- */
function initFanCarousel(root){
  var items = Array.prototype.slice.call(root.querySelectorAll('.fan-item'));
  var n = items.length;
  if(!n) return;
  var progress = 50, active = 0, isDown = false, startX = 0, dragged = false;

  items.forEach(function(item){ item.style.setProperty('--items', n); });

  function zArr(activeIdx){
    return items.map(function(_, i){ return i === activeIdx ? n : n - Math.abs(activeIdx - i); });
  }
  function display(){
    var z = zArr(active);
    items.forEach(function(item, i){
      item.style.setProperty('--zIndex', z[i]);
      item.style.setProperty('--active', (i - active) / n);
    });
  }
  function animate(){
    progress = Math.max(0, Math.min(progress, 100));
    active = Math.floor(progress / 100 * (n - 1));
    display();
  }
  animate();

  items.forEach(function(item, i){
    item.addEventListener('click', function(){
      if(dragged){ dragged = false; return; }
      if(i === active){
        if(item.hasAttribute('data-group') && typeof openLightbox === 'function'){
          openLightbox(item.getAttribute('data-group'), parseInt(item.getAttribute('data-index'), 10));
        }
        return;
      }
      progress = (i / n) * 100 + (100 / n) / 2;
      animate();
    });
  });

  function handleWheel(e){
    e.preventDefault();
    progress += e.deltaY * 0.02;
    animate();
  }
  function handleDown(e){
    isDown = true;
    dragged = false;
    startX = e.clientX || (e.touches && e.touches[0].clientX) || 0;
  }
  function handleMove(e){
    if(!isDown) return;
    var x = e.clientX || (e.touches && e.touches[0].clientX) || 0;
    if(Math.abs(x - startX) > 3) dragged = true;
    progress += (x - startX) * -0.1;
    startX = x;
    animate();
  }
  function handleUp(){ isDown = false; }

  root.addEventListener('wheel', handleWheel, { passive: false });
  root.addEventListener('mousedown', handleDown);
  window.addEventListener('mousemove', handleMove);
  window.addEventListener('mouseup', handleUp);
  root.addEventListener('touchstart', handleDown, { passive: true });
  window.addEventListener('touchmove', handleMove, { passive: true });
  window.addEventListener('touchend', handleUp);

  /* Prev/next arrow buttons — injected so every fan-carousel gets them for free, no markup changes needed */
  function step(dir){ progress += (100 / n) * dir; animate(); }
  var prevBtn = document.createElement('button');
  prevBtn.type = 'button';
  prevBtn.className = 'fan-arrow fan-prev';
  prevBtn.setAttribute('aria-label', 'Précédent');
  prevBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>';
  var nextBtn = document.createElement('button');
  nextBtn.type = 'button';
  nextBtn.className = 'fan-arrow fan-next';
  nextBtn.setAttribute('aria-label', 'Suivant');
  nextBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg>';
  prevBtn.addEventListener('click', function(e){ e.stopPropagation(); step(-1); });
  nextBtn.addEventListener('click', function(e){ e.stopPropagation(); step(1); });
  root.appendChild(prevBtn);
  root.appendChild(nextBtn);
}
document.querySelectorAll('.fan-carousel').forEach(initFanCarousel);

/* ---- Gallery Swiper (Matériaux / Intérieur / Parties communes): centered auto-width cards, powered by Swiper.js ---- */
document.querySelectorAll('.gallery-swiper').forEach(function(root){
  var el = root.querySelector('.gs-swiper');
  if(!el || typeof Swiper === 'undefined') return;
  var slideCount = el.querySelectorAll('.swiper-slide').length;
  new Swiper(el, {
    slidesPerView: 'auto',
    spaceBetween: 22,
    centeredSlides: true,
    initialSlide: Math.floor(slideCount / 2),
    speed: 600,
    watchSlidesProgress: true,
    navigation: {
      nextEl: root.querySelector('.gs-next'),
      prevEl: root.querySelector('.gs-prev'),
      disabledClass: 'disabled'
    },
    pagination: {
      el: root.querySelector('.gs-pagination'),
      clickable: true
    }
  });
});

/* ---- Detail carousels (Parties communes / Intérieur): one slide at a time, swipeable ---- */
function initDetailCarousel(root){
  var slides = Array.prototype.slice.call(root.querySelectorAll('.dc-slide'));
  var n = slides.length;
  if(!n) return;
  var dotsWrap = root.querySelector('.dc-dots');
  var idx = 0;
  slides.forEach(function(s, i){
    var dot = document.createElement('button');
    dot.className = 'dc-dot' + (i === 0 ? ' active' : '');
    dot.setAttribute('aria-label', 'Image ' + (i + 1) + ' / ' + n);
    dot.addEventListener('click', function(){ go(i); });
    dotsWrap.appendChild(dot);
  });
  var dots = Array.prototype.slice.call(dotsWrap.querySelectorAll('.dc-dot'));
  function go(i){
    slides[idx].classList.remove('active');
    dots[idx].classList.remove('active');
    idx = ((i % n) + n) % n;
    slides[idx].classList.add('active');
    dots[idx].classList.add('active');
  }
  var prevBtn = root.querySelector('.dc-prev');
  var nextBtn = root.querySelector('.dc-next');
  if(prevBtn) prevBtn.addEventListener('click', function(){ go(idx - 1); });
  if(nextBtn) nextBtn.addEventListener('click', function(){ go(idx + 1); });

  var track = root.querySelector('.dc-track');
  var startX = 0, dragging = false;
  track.addEventListener('touchstart', function(e){ startX = e.touches[0].clientX; dragging = true; }, {passive:true});
  track.addEventListener('touchend', function(e){
    if(!dragging) return;
    dragging = false;
    var dx = e.changedTouches[0].clientX - startX;
    if(Math.abs(dx) > 40){ dx < 0 ? go(idx + 1) : go(idx - 1); }
  }, {passive:true});
}
document.querySelectorAll('[data-carousel]').forEach(initDetailCarousel);

/* ---- Disponibilité modal ---- */
var dispoModal = document.getElementById('dispoModal');
var dispoOpenBtn = document.getElementById('dispoOpen');
if(dispoModal && dispoOpenBtn){
  dispoOpenBtn.addEventListener('click', function(){
    dispoModal.classList.add('open');
    document.body.style.overflow = 'hidden';
  });
  function closeDispo(){ dispoModal.classList.remove('open'); document.body.style.overflow = ''; }
  var dispoCloseBtn = document.getElementById('dispoClose');
  if(dispoCloseBtn) dispoCloseBtn.addEventListener('click', closeDispo);
  dispoModal.addEventListener('click', function(e){ if(e.target === dispoModal) closeDispo(); });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && dispoModal.classList.contains('open')) closeDispo();
  });
}

/* ---- Lightbox: driven by a page-level `window.NE_GALLERIES` map (group -> [{src,cap}]) ---- */
var lightboxEl = document.getElementById('lightbox');
if(lightboxEl){
  var lb = {group:null, index:0};
  var lbImg = document.getElementById('lbImg');
  var lbCap = document.getElementById('lbCap');
  function updateLightbox(){
    var item = window.NE_GALLERIES[lb.group][lb.index];
    lbImg.src = item.src; lbImg.alt = item.cap;
    lbCap.textContent = item.cap;
  }
  window.openLightbox = function(group, index){
    lb.group = group; lb.index = index;
    updateLightbox();
    lightboxEl.classList.add('open');
    document.body.style.overflow = 'hidden';
  };
  function closeLightbox(){
    lightboxEl.classList.remove('open');
    document.body.style.overflow = '';
  }
  function lbStep(dir){
    var arr = window.NE_GALLERIES[lb.group];
    lb.index = (lb.index + dir + arr.length) % arr.length;
    updateLightbox();
  }
  var lbClose = document.getElementById('lbClose');
  var lbPrev = document.getElementById('lbPrev');
  var lbNext = document.getElementById('lbNext');
  if(lbClose) lbClose.addEventListener('click', closeLightbox);
  if(lbPrev) lbPrev.addEventListener('click', function(){ lbStep(-1); });
  if(lbNext) lbNext.addEventListener('click', function(){ lbStep(1); });
  lightboxEl.addEventListener('click', function(e){ if(e.target === lightboxEl) closeLightbox(); });
  document.addEventListener('keydown', function(e){
    if(!lightboxEl.classList.contains('open')) return;
    if(e.key === 'Escape') closeLightbox();
    if(e.key === 'ArrowRight') lbStep(1);
    if(e.key === 'ArrowLeft') lbStep(-1);
  });
}

/* ---- Magnetic tilt on cards: subtle 3D tilt that follows the cursor ---- */
if(!reduceMotion && window.matchMedia && window.matchMedia('(hover:hover) and (pointer:fine)').matches){
  document.querySelectorAll('.tilt').forEach(function(el){
    var rect = null;
    el.addEventListener('mouseenter', function(){ rect = el.getBoundingClientRect(); });
    el.addEventListener('mousemove', function(e){
      if(!rect) rect = el.getBoundingClientRect();
      var px = (e.clientX - rect.left) / rect.width;
      var py = (e.clientY - rect.top) / rect.height;
      var rx = (0.5 - py) * 4.5;
      var ry = (px - 0.5) * 4.5;
      el.style.transform = 'perspective(900px) rotateX(' + rx.toFixed(2) + 'deg) rotateY(' + ry.toFixed(2) + 'deg) translateZ(0)';
    });
    el.addEventListener('mouseleave', function(){
      el.style.transform = 'perspective(900px) rotateX(0deg) rotateY(0deg) translateZ(0)';
      rect = null;
    });
  });
}

/* ---- Parallax: hero media drifts slower than scroll for depth ---- */
if(!reduceMotion){
  var parallaxEls = Array.prototype.slice.call(document.querySelectorAll('[data-parallax]'));
  if(parallaxEls.length){
    var ticking = false;
    function applyParallax(){
      var y = window.scrollY;
      parallaxEls.forEach(function(el){
        var speed = parseFloat(el.getAttribute('data-parallax')) || 0.18;
        var offset = Math.min(y * speed, 160);
        el.style.transform = 'translateY(' + offset + 'px) scale(1.08)';
      });
      ticking = false;
    }
    window.addEventListener('scroll', function(){
      if(!ticking){ window.requestAnimationFrame(applyParallax); ticking = true; }
    }, {passive:true});
    applyParallax();
  }
}

/* ---- Résidences index: hovering/focusing a name swaps the large photo + facts instead of a static grid ---- */
var riItems = Array.prototype.slice.call(document.querySelectorAll('.ri-item'));
if(riItems.length){
  var riImg = document.getElementById('resIndexImg');
  var riName = document.getElementById('resIndexName');
  var riLoc = document.getElementById('resIndexLoc');
  var riProgVal = document.getElementById('resIndexProgVal');
  var riProgFill = document.getElementById('resIndexProgFill');
  var riLink = document.getElementById('resIndexLink');
  function setRi(item){
    riItems.forEach(function(i){ i.classList.remove('active'); });
    item.classList.add('active');
    var img = item.getAttribute('data-img');
    if(riImg && img && riImg.getAttribute('src') !== img){
      riImg.classList.add('swapping');
      setTimeout(function(){
        riImg.setAttribute('src', img);
        riImg.classList.remove('swapping');
      }, 220);
    }
    if(riName) riName.textContent = item.getAttribute('data-name');
    if(riLoc) riLoc.textContent = item.getAttribute('data-loc');
    var prog = item.getAttribute('data-prog');
    var progLabel = item.getAttribute('data-prog-label');
    if(riProgFill) riProgFill.style.width = prog + '%';
    if(riProgVal){
      riProgVal.textContent = progLabel;
      riProgVal.classList.toggle('pending', prog === '0');
    }
    if(riLink) riLink.setAttribute('href', item.getAttribute('href'));
  }
  riItems.forEach(function(item){
    item.addEventListener('mouseenter', function(){ setRi(item); });
    item.addEventListener('focus', function(){ setRi(item); });
  });
}

/* ---- Villa page sticky tabs: highlight the tab matching whichever section is currently in view ---- */
var villaTabs = document.getElementById('villaTabs');
if(villaTabs){
  var tabLinks = Array.prototype.slice.call(villaTabs.querySelectorAll('.vt-link'));
  var tabSections = Array.prototype.slice.call(document.querySelectorAll('[data-tab-section]'));
  var tabIO = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting){
        var id = e.target.getAttribute('id');
        tabLinks.forEach(function(l){ l.classList.toggle('active', l.getAttribute('href') === '#' + id); });
      }
    });
  }, {rootMargin:'-30% 0px -60% 0px', threshold:0});
  tabSections.forEach(function(s){ tabIO.observe(s); });
}

/* ---- Villa split page: sticky photo pane swaps as you click thumbnails in the scrolling dossier column ---- */
var vsMedia = document.getElementById('villaSplitImg');
if(vsMedia){
  var vsActiveGroup = null, vsActiveIndex = null;
  var vsStrips = Array.prototype.slice.call(document.querySelectorAll('[data-vs-strip]'));
  vsStrips.forEach(function(strip){
    var thumbs = Array.prototype.slice.call(strip.querySelectorAll('.vs-thumb'));
    var infoId = strip.getAttribute('data-vs-text');
    var infoEl = infoId ? document.getElementById(infoId) : null;
    thumbs.forEach(function(thumb){
      thumb.addEventListener('click', function(){
        thumbs.forEach(function(t){ t.classList.remove('active'); });
        thumb.classList.add('active');
        var img = thumb.getAttribute('data-img');
        if(img && vsMedia.getAttribute('src') !== img){
          vsMedia.classList.remove('ken-burns');
          vsMedia.classList.add('swapping');
          setTimeout(function(){
            vsMedia.setAttribute('src', img);
            vsMedia.classList.remove('swapping');
            void vsMedia.offsetWidth;
            vsMedia.classList.add('ken-burns');
          }, 260);
        }
        if(infoEl){
          var title = thumb.getAttribute('data-title');
          var bullets = thumb.getAttribute('data-bullets');
          if(title){
            var ul = '';
            if(bullets){
              var items = bullets.split('|').map(function(b){ return '<li>' + b + '</li>'; }).join('');
              ul = '<ul>' + items + '</ul>';
            }
            infoEl.innerHTML = '<b>' + title + '</b>' + ul;
          }
        }
        vsActiveGroup = thumb.getAttribute('data-group');
        vsActiveIndex = thumb.getAttribute('data-index');
      });
    });
  });
  var vsInitial = document.querySelector('.vs-thumb.active[data-group]');
  if(vsInitial){ vsActiveGroup = vsInitial.getAttribute('data-group'); vsActiveIndex = vsInitial.getAttribute('data-index'); }
  vsMedia.parentElement.style.cursor = 'zoom-in';
  vsMedia.parentElement.addEventListener('click', function(){
    if(vsActiveGroup !== null && typeof openLightbox === 'function'){
      openLightbox(vsActiveGroup, parseInt(vsActiveIndex, 10));
    }
  });

  /* Villa hero: the sticky left photo auto-rotates through the gallery every 3s, with a slight ken-burns zoom on each change */
  if(window.NE_GALLERIES && window.NE_GALLERIES.gallery && window.NE_GALLERIES.gallery.length > 1 && !reduceMotion){
    var heroRotate = window.NE_GALLERIES.gallery;
    var heroRotateIdx = 0;
    setInterval(function(){
      heroRotateIdx = (heroRotateIdx + 1) % heroRotate.length;
      var img = heroRotate[heroRotateIdx].src;
      vsMedia.classList.remove('ken-burns');
      vsMedia.classList.add('swapping');
      setTimeout(function(){
        vsMedia.setAttribute('src', img);
        vsMedia.classList.remove('swapping');
        void vsMedia.offsetWidth;
        vsMedia.classList.add('ken-burns');
      }, 260);
    }, 3000);
  }
}

/* ---- "Prendre rendez-vous" — every matching button/link sitewide gets a calendar icon and opens a small action modal (call / email / go to the form), no per-page markup needed. Elements marked [data-rdv-trigger] (e.g. the mobile mini-cta-bar's compact "RDV" link) also open the modal, keeping their own icon/label as-is. ---- */
(function(){
  var CAL_ICON = '<svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>';
  var textTriggers = Array.prototype.slice.call(document.querySelectorAll('button, a')).filter(function(el){
    return el.textContent.trim() === 'Prendre rendez-vous';
  });
  var attrTriggers = Array.prototype.slice.call(document.querySelectorAll('[data-rdv-trigger]'));
  var triggers = textTriggers.concat(attrTriggers);
  if(!triggers.length) return;

  textTriggers.forEach(function(el){
    if(!el.querySelector('svg')){
      el.innerHTML = CAL_ICON + '<span>' + el.textContent.trim() + '</span>';
    }
  });

  var modal = document.createElement('div');
  modal.className = 'rdv-modal';
  modal.id = 'rdvModal';
  var hasRdvForm = !!document.getElementById('rdv');
  var formHref = hasRdvForm ? '#rdv' : 'villa-agata.html#rdv';
  modal.innerHTML =
    '<div class="rdv-modal-box">' +
      '<button class="rdv-modal-close" id="rdvModalClose" aria-label="Fermer">✕</button>' +
      '<h3>Prendre rendez-vous</h3>' +
      '<p>Choisissez la façon la plus simple pour vous d’entrer en contact avec New Era.</p>' +
      '<div class="rdv-modal-actions">' +
        '<a href="tel:+213561112233"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.362 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.338 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>Nous appeler</a>' +
        '<a href="mailto:contact@newera-immobilier.dz"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v16H4z"/><path d="M22 6l-10 7L2 6"/></svg>Nous écrire un email</a>' +
        '<a href="' + formHref + '" id="rdvModalForm"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>Remplir le formulaire</a>' +
      '</div>' +
    '</div>';
  document.body.appendChild(modal);

  function openRdv(e){
    if(e) e.preventDefault();
    modal.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  function closeRdv(){
    modal.classList.remove('open');
    document.body.style.overflow = '';
  }
  triggers.forEach(function(el){ el.addEventListener('click', openRdv); });
  document.getElementById('rdvModalClose').addEventListener('click', closeRdv);
  modal.addEventListener('click', function(e){ if(e.target === modal) closeRdv(); });
  document.addEventListener('keydown', function(e){ if(e.key === 'Escape' && modal.classList.contains('open')) closeRdv(); });
  if(hasRdvForm){
    document.getElementById('rdvModalForm').addEventListener('click', function(e){
      e.preventDefault();
      closeRdv();
      document.getElementById('rdv').scrollIntoView({behavior:'smooth'});
    });
  }
})();

/* ---- Scroll-scrubbed motion: giant background numerals drift/scale continuously with scroll position, not just a single fade-in ---- */
if(!reduceMotion){
  var scrubEls = Array.prototype.slice.call(document.querySelectorAll('.giant-num'));
  if(scrubEls.length){
    var scrubTicking = false;
    function applyScrub(){
      var vh = window.innerHeight;
      scrubEls.forEach(function(el){
        var r = el.getBoundingClientRect();
        var p = 1 - Math.min(Math.max((r.top + r.height * 0.3) / (vh + r.height), 0), 1);
        el.style.setProperty('--p', p.toFixed(3));
      });
      scrubTicking = false;
    }
    window.addEventListener('scroll', function(){
      if(!scrubTicking){ window.requestAnimationFrame(applyScrub); scrubTicking = true; }
    }, {passive:true});
    window.addEventListener('resize', applyScrub);
    applyScrub();
  }
}

/* ---- Tap-to-reveal: .ms-card (manifesto stats) and .spec-card (Dans chaque résidence) show their detail on hover on desktop, but touch devices have no hover — a tap toggles the same reveal instead. Clicking elsewhere closes it. ---- */
(function(){
  var revealCards = Array.prototype.slice.call(document.querySelectorAll('.ms-card, .spec-card'));
  if(!revealCards.length) return;
  revealCards.forEach(function(card){
    card.addEventListener('click', function(e){
      var wasOpen = card.classList.contains('is-open');
      revealCards.forEach(function(c){ c.classList.remove('is-open'); });
      if(!wasOpen) card.classList.add('is-open');
      e.stopPropagation();
    });
  });
  document.addEventListener('click', function(){
    revealCards.forEach(function(c){ c.classList.remove('is-open'); });
  });
})();

/* ---- Home hero video: skip the ~3MB fetch on small screens, poster stands in ---- */
var heroVideo = document.getElementById('heroVideo');
if(heroVideo){
  var isMobile = window.matchMedia && window.matchMedia('(max-width:700px)').matches;
  if(!isMobile){
    /* resolve relative to this very script's own folder, so pages that load
       main.js from a subdirectory (e.g. /ar/) still find the right file */
    var __selfScript = document.currentScript;
    var __assetsBase = __selfScript ? __selfScript.src.replace(/[^\/]*$/, '') : 'assets/';
    var src = document.createElement('source');
    src.src = __assetsBase + 'hero-video.mp4';
    src.type = 'video/mp4';
    heroVideo.appendChild(src);
    heroVideo.setAttribute('autoplay','');
    heroVideo.load();
    heroVideo.play().catch(function(){});
  }
}
