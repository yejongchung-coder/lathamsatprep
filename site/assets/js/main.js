/* ABLE Enrichment — shared behavior */

(function () {
  "use strict";

  // Mobile menu
  var toggle = document.querySelector(".menu-toggle");
  var nav = document.querySelector(".nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      nav.classList.toggle("open");
    });
  }

  // Text number: fetched from /api/config so the SMS number can change
  // without editing every page. Falls back to the default in the markup.
  fetch("/api/config")
    .then(function (r) { return r.json(); })
    .catch(function () { return {}; })
    .then(function (cfg) {
      if (cfg && cfg.text_number) {
        document.querySelectorAll("[data-text-number]").forEach(function (el) {
          el.textContent = cfg.text_number_display || cfg.text_number;
        });
        document.querySelectorAll("[data-sms-link]").forEach(function (el) {
          el.setAttribute("href", "sms:" + cfg.text_number);
        });
      }
    });

  // Inquiry forms: any <form data-inquiry> posts JSON to /api/inquiry
  document.querySelectorAll("form[data-inquiry]").forEach(function (form) {
    var status = form.querySelector(".form-status");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (status) { status.className = "form-status"; status.textContent = ""; }

      var get = function (name) {
        var el = form.querySelector('[name="' + name + '"]');
        return el ? el.value.trim() : "";
      };
      var radio = function (name) {
        var el = form.querySelector('[name="' + name + '"]:checked');
        return el ? el.value : "";
      };
      var payload = {
        student_name: get("student_name"),
        grade: get("grade"),
        school: get("school"),
        parent_name: get("parent_name"),
        parent_phone: get("parent_phone"),
        parent_email: get("parent_email"),
        interest: radio("interest"),
        source: radio("source"),
        company: get("company") // honeypot
      };

      // Light client-side validation
      var bad = [];
      if (!payload.student_name) bad.push("student_name");
      if (!payload.grade) bad.push("grade");
      if (!payload.school) bad.push("school");
      if (!payload.parent_name) bad.push("parent_name");
      if (!payload.parent_phone) bad.push("parent_phone");
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(payload.parent_email)) bad.push("parent_email");
      form.querySelectorAll(".err").forEach(function (el) { el.classList.remove("err"); });
      bad.forEach(function (n) {
        var el = form.querySelector('[name="' + n + '"]');
        if (el) el.classList.add("err");
      });
      if (bad.length) {
        if (status) { status.className = "form-status bad"; status.textContent = "Please complete the highlighted fields."; }
        return;
      }

      var btn = form.querySelector('button[type="submit"]');
      var original = btn ? btn.textContent : "";
      if (btn) { btn.disabled = true; btn.textContent = "Sending…"; }

      fetch("/api/inquiry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
        .then(function (res) {
          if (res.ok) {
            form.reset();
            if (status) { status.className = "form-status ok"; status.textContent = "Thanks — we got your inquiry and will reach out shortly."; }
          } else {
            if (status) { status.className = "form-status bad"; status.textContent = res.error || "Something went wrong. Please try again or text us."; }
          }
        })
        .catch(function () {
          if (status) { status.className = "form-status bad"; status.textContent = "Something went wrong. Please try again or text us."; }
        })
        .finally(function () {
          if (btn) { btn.disabled = false; btn.textContent = original; }
        });
    });
  });

  // Footer year
  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = new Date().getFullYear();
  });

  // Chat widget: load its CSS + JS on every page
  var chatCss = document.createElement("link");
  chatCss.rel = "stylesheet";
  chatCss.href = "/assets/css/chatbot.css";
  document.head.appendChild(chatCss);
  var chatJs = document.createElement("script");
  chatJs.src = "/assets/js/chatbot.js";
  chatJs.defer = true;
  document.head.appendChild(chatJs);
})();
