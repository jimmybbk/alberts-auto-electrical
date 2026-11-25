/* Albert's Auto Electrical — site behaviour + interactivity */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  /* ----- Mobile navigation ----- */
  var toggle = document.querySelector(".nav-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
  document.querySelectorAll(".has-sub > a").forEach(function (link) {
    link.addEventListener("click", function (e) {
      if (window.innerWidth <= 860) {
        e.preventDefault();
        link.parentElement.classList.toggle("open");
      }
    });
  });
  document.querySelectorAll(".main-nav a[href]:not(.parent-link)").forEach(function (a) {
    a.addEventListener("click", function () {
      document.body.classList.remove("nav-open");
    });
  });

  /* ----- Scroll progress bar ----- */
  var progress = document.createElement("div");
  progress.className = "scroll-progress";
  progress.innerHTML = "<span></span>";
  document.body.appendChild(progress);
  var progressFill = progress.querySelector("span");

  /* ----- Header shadow + back-to-top + progress ----- */
  var header = document.querySelector(".site-header");
  var toTop = document.querySelector(".to-top");
  function onScroll() {
    var y = window.scrollY;
    if (header) header.classList.toggle("scrolled", y > 8);
    if (toTop) toTop.classList.toggle("show", y > 600);
    var max = document.documentElement.scrollHeight - window.innerHeight;
    progressFill.style.width = (max > 0 ? (y / max) * 100 : 0) + "%";
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  onScroll();
  if (toTop) {
    toTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  /* ----- Reveal on scroll (with stagger) ----- */
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length) {
    revealEls.forEach(function (el) {
      var group = el.parentElement ? el.parentElement.querySelectorAll(":scope > .reveal") : null;
      if (group && group.length > 1) {
        var idx = Array.prototype.indexOf.call(group, el);
        el.style.transitionDelay = Math.min(idx * 80, 480) + "ms";
      }
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("in");
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("in"); });
  }
  /* safety net: if observers never fire (embedded browsers, throttling),
     force everything visible so no content is ever stuck invisible */
  window.setTimeout(function () {
    document.querySelectorAll(".reveal:not(.in)").forEach(function (el) {
      el.classList.add("in");
    });
  }, 2500);

  /* ----- Animated count-up stats ----- */
  function animateCount(el) {
    var target = parseFloat(el.getAttribute("data-count"));
    var decimals = parseInt(el.getAttribute("data-decimals") || "0", 10);
    var suffix = el.getAttribute("data-suffix") || "";
    var finalText = target.toFixed(decimals) + suffix;
    if (reduceMotion || isNaN(target)) {
      el.textContent = finalText;
      return;
    }
    var duration = 1500;
    var start = null;
    function frame(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(frame);
      else el.textContent = finalText;
    }
    requestAnimationFrame(frame);
  }
  var strips = document.querySelectorAll(".stats-strip");
  if (strips.length && "IntersectionObserver" in window) {
    var statIo = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.querySelectorAll("[data-count]").forEach(animateCount);
          statIo.unobserve(en.target);
        }
      });
    }, { threshold: 0.3 });
    strips.forEach(function (s) { statIo.observe(s); });
  }

  /* ----- Card cursor spotlight ----- */
  if (finePointer) {
    document.querySelectorAll(".card, .region-card, .info-card").forEach(function (el) {
      el.classList.add("spot");
      el.addEventListener("pointermove", function (e) {
        var r = el.getBoundingClientRect();
        el.style.setProperty("--mx", (e.clientX - r.left) + "px");
        el.style.setProperty("--my", (e.clientY - r.top) + "px");
      });
    });
  }

  /* ----- Hero 3D tilt ----- */
  var heroVisual = document.querySelector(".hero-visual");
  if (heroVisual && finePointer && !reduceMotion) {
    var hvImg = heroVisual.querySelector("img");
    heroVisual.addEventListener("pointermove", function (e) {
      var r = heroVisual.getBoundingClientRect();
      var rx = ((e.clientY - r.top) / r.height - 0.5) * -7;
      var ry = ((e.clientX - r.left) / r.width - 0.5) * 9;
      hvImg.style.transform = "perspective(900px) rotateX(" + rx.toFixed(2) + "deg) rotateY(" + ry.toFixed(2) + "deg)";
    });
    heroVisual.addEventListener("pointerleave", function () {
      hvImg.style.transform = "";
    });
  }

  /* ----- Services scrollspy ----- */
  var spyNav = document.querySelector("[data-scrollspy]");
  if (spyNav && "IntersectionObserver" in window) {
    var spyLinks = spyNav.querySelectorAll('a[href^="#"]');
    var spyMap = {};
    spyLinks.forEach(function (l) { spyMap[l.getAttribute("href").slice(1)] = l; });
    var spyIo = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting && spyMap[en.target.id]) {
          spyLinks.forEach(function (l) { l.classList.remove("active"); });
          spyMap[en.target.id].classList.add("active");
        }
      });
    }, { rootMargin: "-30% 0px -55% 0px" });
    document.querySelectorAll(".service-band").forEach(function (s) { spyIo.observe(s); });
  }

  /* ----- Testimonial slider: arrows, dots, autoplay, drag ----- */
  var track = document.querySelector(".t-track");
  if (track) {
    var prev = document.querySelector("[data-t-prev]");
    var next = document.querySelector("[data-t-next]");
    var dotsWrap = document.createElement("div");
    dotsWrap.className = "t-dots";
    if (prev && next) {
      (prev.parentElement || document.querySelector(".t-nav")).appendChild(dotsWrap);
    } else {
      var slider = track.closest(".t-slider");
      if (slider) {
        var nav = document.createElement("div");
        nav.className = "t-nav";
        nav.appendChild(dotsWrap);
        slider.appendChild(nav);
      }
    }

    function step() {
      var card = track.querySelector(".t-card");
      if (!card) return 320;
      var gap = parseFloat(getComputedStyle(track).columnGap || 26);
      return card.getBoundingClientRect().width + gap;
    }
    function update() {
      if (prev) prev.disabled = track.scrollLeft <= 4;
      if (next) next.disabled = track.scrollLeft >= track.scrollWidth - track.clientWidth - 4;
      var cards = track.querySelectorAll(".t-card");
      var idx = Math.min(Math.round(track.scrollLeft / step()), cards.length - 1);
      dotsWrap.querySelectorAll(".t-dot").forEach(function (d, i) {
        d.classList.toggle("active", i === idx);
      });
    }

    var dots = [];
    track.querySelectorAll(".t-card").forEach(function (card, i) {
      var dot = document.createElement("button");
      dot.className = "t-dot";
      dot.setAttribute("aria-label", "Go to review " + (i + 1));
      dot.addEventListener("click", function () {
        track.scrollTo({ left: i * step(), behavior: "smooth" });
        resetAuto();
      });
      dotsWrap.appendChild(dot);
      dots.push(dot);
    });

    if (prev) prev.addEventListener("click", function () { track.scrollBy({ left: -step(), behavior: "smooth" }); resetAuto(); });
    if (next) next.addEventListener("click", function () { track.scrollBy({ left: step(), behavior: "smooth" }); resetAuto(); });
    track.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();

    /* autoplay — pauses on hover, stops when off-screen */
    var visible = true;
    var autoTimer = null;
    function startAuto() {
      if (reduceMotion || autoTimer || !visible) return;
      autoTimer = setInterval(function () {
        var maxScroll = track.scrollWidth - track.clientWidth;
        if (track.scrollLeft >= maxScroll - 4) track.scrollTo({ left: 0, behavior: "smooth" });
        else track.scrollBy({ left: step(), behavior: "smooth" });
      }, 6000);
    }
    function stopAuto() {
      if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
    }
    function resetAuto() { stopAuto(); startAuto(); }
    track.addEventListener("pointerenter", stopAuto);
    track.addEventListener("pointerleave", function () { startAuto(); });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          visible = en.isIntersecting;
          if (visible) startAuto(); else stopAuto();
        });
      }, { threshold: 0.25 }).observe(track);
    }

    /* mouse drag */
    var isDown = false, dragStartX = 0, dragStartScroll = 0;
    track.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "touch") return;
      isDown = true;
      dragStartX = e.clientX;
      dragStartScroll = track.scrollLeft;
      track.classList.add("dragging");
      track.setPointerCapture(e.pointerId);
      stopAuto();
    });
    track.addEventListener("pointermove", function (e) {
      if (!isDown) return;
      track.scrollLeft = dragStartScroll - (e.clientX - dragStartX);
    });
    ["pointerup", "pointercancel"].forEach(function (t) {
      track.addEventListener(t, function () {
        if (!isDown) return;
        isDown = false;
        track.classList.remove("dragging");
        var s = step();
        track.scrollTo({ left: Math.round(track.scrollLeft / s) * s, behavior: "smooth" });
        resetAuto();
      });
    });
  }

  /* ----- Gallery lightbox (injected if page has .g-grid but no .lightbox) ----- */
  if (document.querySelector(".g-grid") && !document.querySelector(".lightbox")) {
    var lbDiv = document.createElement("div");
    lbDiv.className = "lightbox";
    lbDiv.setAttribute("aria-hidden", "true");
    lbDiv.innerHTML =
      '<button class="lb-btn lb-close" aria-label="Close"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button>' +
      '<button class="lb-btn lb-prev" aria-label="Previous image"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 18-6-6 6-6"/></svg></button>' +
      '<img src="" alt="">' +
      '<button class="lb-btn lb-next" aria-label="Next image"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg></button>' +
      '<div class="lb-cap"></div>';
    document.body.appendChild(lbDiv);
  }

  var lightbox = document.querySelector(".lightbox");
  if (lightbox) {
    var lbImg = lightbox.querySelector("img");
    var lbCap = lightbox.querySelector(".lb-cap");
    var current = 0;

    function visibleItems() {
      return Array.prototype.filter.call(document.querySelectorAll(".g-item"), function (i) {
        return !i.classList.contains("hide");
      });
    }
    function showLb(list) {
      var item = list[current];
      var img = item.querySelector("img");
      lbImg.src = img.getAttribute("data-full") || img.src;
      lbImg.alt = img.alt;
      if (lbCap) lbCap.textContent = img.alt + "  ·  " + (current + 1) + " / " + list.length;
    }
    function openLb(item) {
      var list = visibleItems();
      current = list.indexOf(item);
      showLb(list);
      lightbox.classList.add("open");
      lightbox.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    }
    function closeLb() {
      lightbox.classList.remove("open");
      lightbox.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    }
    function move(dir) {
      var list = visibleItems();
      current = (current + dir + list.length) % list.length;
      showLb(list);
    }

    document.querySelectorAll(".g-item").forEach(function (item) {
      item.addEventListener("click", function () { openLb(item); });
    });
    lightbox.querySelector(".lb-close").addEventListener("click", closeLb);
    lightbox.querySelector(".lb-prev").addEventListener("click", function () { move(-1); });
    lightbox.querySelector(".lb-next").addEventListener("click", function () { move(1); });
    lightbox.addEventListener("click", function (e) { if (e.target === lightbox) closeLb(); });
    document.addEventListener("keydown", function (e) {
      if (!lightbox.classList.contains("open")) return;
      if (e.key === "Escape") closeLb();
      if (e.key === "ArrowLeft") move(-1);
      if (e.key === "ArrowRight") move(1);
    });

    /* swipe */
    var lbDown = false, lbStartX = 0;
    lightbox.addEventListener("pointerdown", function (e) {
      if (e.target.closest(".lb-btn")) return;
      lbDown = true;
      lbStartX = e.clientX;
    });
    ["pointerup", "pointercancel"].forEach(function (t) {
      lightbox.addEventListener(t, function (e) {
        if (!lbDown) return;
        lbDown = false;
        var dx = e.clientX - lbStartX;
        if (dx < -40) move(1);
        else if (dx > 40) move(-1);
      });
    });
  }

  /* ----- Accordion ----- */
  document.querySelectorAll(".acc-item").forEach(function (item) {
    var q = item.querySelector(".acc-q");
    var a = item.querySelector(".acc-a");
    if (!q || !a) return;
    q.addEventListener("click", function () {
      var open = item.classList.contains("open");
      document.querySelectorAll(".acc-item.open").forEach(function (o) {
        o.classList.remove("open");
        o.querySelector(".acc-a").style.maxHeight = null;
        o.querySelector(".acc-q").setAttribute("aria-expanded", "false");
      });
      if (!open) {
        item.classList.add("open");
        a.style.maxHeight = a.scrollHeight + "px";
        q.setAttribute("aria-expanded", "true");
      }
    });
  });

  /* ----- Booking form → mail client ----- */
  var form = document.querySelector("[data-mailto-form]");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var d = new FormData(form);
      var lines = [
        "Name: " + d.get("name"),
        "Phone: " + d.get("phone"),
        "Email: " + d.get("email"),
        "Vehicle: " + (d.get("vehicle") || "-"),
        "Service required: " + (d.get("service") || "-"),
        "",
        "Details:",
        d.get("message") || "-"
      ];
      var subject = "Booking request — " + (d.get("service") || "General enquiry") + " (" + d.get("name") + ")";
      window.location.href =
        "mailto:albert@albertsautoelectrical.com.au?subject=" + encodeURIComponent(subject) +
        "&body=" + encodeURIComponent(lines.join("\n"));
      var note = form.querySelector(".form-confirm");
      if (note) note.hidden = false;
    });
  }

  /* ----- Highlight today in opening hours ----- */
  var day = new Date().getDay(); // 0 Sun … 6 Sat
  var rows = { 1: "mon", 2: "mon", 3: "mon", 4: "mon", 5: "mon", 6: "sat", 0: "sun" };
  var tr = document.querySelector('.hours-table tr[data-day="' + rows[day] + '"]');
  if (tr) tr.classList.add("today");

  /* ----- Blog archive search ----- */
  var blogSearch = document.querySelector("[data-blog-search]");
  if (blogSearch) {
    var grid = document.querySelector("[data-blog-grid]");
    var cards = grid ? Array.prototype.slice.call(grid.querySelectorAll(".post-card")) : [];
    var countEl = document.querySelector("[data-blog-count]");
    var emptyEl = document.querySelector("[data-blog-empty]");
    var total = cards.length;
    function blogFilter() {
      var q = blogSearch.value.trim().toLowerCase();
      var shown = 0;
      cards.forEach(function (card) {
        var match = !q || card.textContent.toLowerCase().indexOf(q) !== -1;
        card.style.display = match ? "" : "none";
        if (match) shown++;
      });
      if (countEl) countEl.textContent = q ? shown + " of " + total + " projects" : total + " projects";
      if (emptyEl) emptyEl.hidden = shown !== 0;
    }
    blogSearch.addEventListener("input", blogFilter);
    blogFilter();
  }

  /* ----- Footer year ----- */
  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = new Date().getFullYear();
  });
})();
