/* Albert's Auto Electrical — site behaviour */
(function () {
  "use strict";

  /* ----- Mobile navigation ----- */
  var toggle = document.querySelector(".nav-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  /* Mobile services dropdown */
  document.querySelectorAll(".has-sub > a").forEach(function (link) {
    link.addEventListener("click", function (e) {
      if (window.innerWidth <= 860) {
        e.preventDefault();
        link.parentElement.classList.toggle("open");
      }
    });
  });

  /* Close mobile nav after choosing a page link */
  document.querySelectorAll(".main-nav a[href]:not(.parent-link)").forEach(function (a) {
    a.addEventListener("click", function () {
      document.body.classList.remove("nav-open");
    });
  });

  /* ----- Header shadow on scroll + back-to-top ----- */
  var header = document.querySelector(".site-header");
  var toTop = document.querySelector(".to-top");
  function onScroll() {
    var y = window.scrollY;
    if (header) header.classList.toggle("scrolled", y > 8);
    if (toTop) toTop.classList.toggle("show", y > 600);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  if (toTop) {
    toTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  /* ----- Testimonial slider ----- */
  var track = document.querySelector(".t-track");
  if (track) {
    var prev = document.querySelector("[data-t-prev]");
    var next = document.querySelector("[data-t-next]");
    function step() {
      var card = track.querySelector(".t-card");
      if (!card) return 320;
      var gap = parseFloat(getComputedStyle(track).columnGap || 26);
      return card.getBoundingClientRect().width + gap;
    }
    function update() {
      if (!prev || !next) return;
      prev.disabled = track.scrollLeft <= 4;
      next.disabled = track.scrollLeft >= track.scrollWidth - track.clientWidth - 4;
    }
    if (prev) prev.addEventListener("click", function () { track.scrollBy({ left: -step(), behavior: "smooth" }); });
    if (next) next.addEventListener("click", function () { track.scrollBy({ left: step(), behavior: "smooth" }); });
    track.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  /* ----- Gallery filters ----- */
  var filterBar = document.querySelector(".filter-bar");
  if (filterBar) {
    var buttons = filterBar.querySelectorAll(".filter-btn");
    var items = document.querySelectorAll(".g-item");
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        buttons.forEach(function (b) { b.classList.remove("active"); });
        btn.classList.add("active");
        var f = btn.getAttribute("data-filter");
        items.forEach(function (item) {
          var show = f === "all" || item.getAttribute("data-cat") === f;
          item.classList.toggle("hide", !show);
        });
        if (typeof syncLightboxItems === "function") syncLightboxItems();
      });
    });
  }

  /* ----- Lightbox ----- */
  var lightbox = document.querySelector(".lightbox");
  if (lightbox) {
    var lbImg = lightbox.querySelector("img");
    var lbCap = lightbox.querySelector(".lb-cap");
    var current = 0;
    var visibleItems = function () {
      return Array.prototype.filter.call(document.querySelectorAll(".g-item"), function (i) {
        return !i.classList.contains("hide");
      });
    };
    window.syncLightboxItems = function () {}; // refreshed on open

    function openLb(item) {
      var list = visibleItems();
      current = list.indexOf(item);
      showLb(list);
      lightbox.classList.add("open");
      document.body.style.overflow = "hidden";
    }
    function showLb(list) {
      var item = list[current];
      var img = item.querySelector("img");
      lbImg.src = img.getAttribute("data-full") || img.src;
      lbImg.alt = img.alt;
      if (lbCap) lbCap.textContent = img.alt;
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
    function closeLb() {
      lightbox.classList.remove("open");
      document.body.style.overflow = "";
    }
    lightbox.addEventListener("click", function (e) { if (e.target === lightbox) closeLb(); });
    document.addEventListener("keydown", function (e) {
      if (!lightbox.classList.contains("open")) return;
      if (e.key === "Escape") closeLb();
      if (e.key === "ArrowLeft") move(-1);
      if (e.key === "ArrowRight") move(1);
    });
  }

  /* ----- Accordion ----- */
  document.querySelectorAll(".acc-item").forEach(function (item) {
    var q = item.querySelector(".acc-q");
    var a = item.querySelector(".acc-a");
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

  /* ----- Reveal on scroll ----- */
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length) {
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

  /* ----- Footer year ----- */
  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = new Date().getFullYear();
  });
})();
