/* ABLE Enrichment — simple Q&A chat widget (no AI backend; answers from site facts) */
(function () {
  "use strict";

  var PHONE_DISPLAY = "(518) 390-7346";
  var PHONE_LINK = "tel:+15183907346";
  var SMS_LINK = "sms:+15183907346";

  // Each entry: keywords (any match scores) + answer (HTML allowed)
  var QA = [
    {
      keys: ["summer", "classes", "program", "schedule", "timing", "months", "what months"],
      answer: "Our SAT prep classes run during the <strong>summer only</strong>, every year — timed for the <strong>August SAT</strong>."
    },
    {
      keys: ["register", "registration", "sign up", "signup", "enroll", "how do i join", "how to join"],
      answer: "Registration opens in <strong>January</strong> and spots are <strong>first come, first served</strong>. They fill up every year, so reach out early! Text us at <a href=\"" + SMS_LINK + "\">" + PHONE_DISPLAY + "</a> or use the inquiry form below."
    },
    {
      keys: ["how many", "slots", "spots", "seats", "class size", "students max", "maximum", "full"],
      answer: "We cap each summer class at <strong>15 students</strong> — once we're full, we don't accept more. Small groups are how every student gets our full attention."
    },
    {
      keys: ["cost", "price", "pricing", "tuition", "how much", "fee", "fees", "charge"],
      answer: "For pricing, our instructor will go over it with you directly. Just fill out the inquiry form or text us at <a href=\"" + SMS_LINK + "\">" + PHONE_DISPLAY + "</a> to reach out!"
    },
    {
      keys: ["where", "location", "located", "address", "latham", "albany"],
      answer: "Our classes meet at <strong>981 Loudon Rd, Cohoes, NY 12047</strong> — in a conference room. We serve families across the Capital Region — Albany, Colonie, Clifton Park, Niskayuna, Troy, Schenectady, and beyond — in person and online."
    },
    {
      keys: ["phone", "call", "text", "number", "contact", "reach", "talk to"],
      answer: "You can text or call us at <a href=\"" + PHONE_LINK + "\">" + PHONE_DISPLAY + "</a> — or send the quick inquiry form on this page."
    },
    {
      keys: ["august"],
      answer: "Yes — our summer SAT prep is built around the <strong>August SAT</strong> test date."
    },
    {
      keys: ["score", "results", "improve", "1580", "points"],
      answer: "Our students see real jumps — recent examples include <strong>1310 → 1580</strong>, <strong>1300 → 1530</strong>, and <strong>1070 → 1340</strong>."
    },
    {
      keys: ["college", "accept", "admission", "university", "schools", "mit", "harvard", "yale"],
      answer: "Over the last 5 years our students have been accepted to schools including MIT, Yale, Princeton, Columbia, Dartmouth, Northwestern, Carnegie Mellon, UC Berkeley, UCLA, NYU, Johns Hopkins, Tufts, and more."
    },
    {
      keys: ["consulting", "essay", "essays", "college essay", "application", "common app"],
      answer: "Yes! Beyond SAT prep we offer <strong>college admissions consulting</strong> and <strong>essay coaching</strong> — help with applications, essays, and choosing the right schools. Sessions are available <strong>in person and online</strong>."
    },
    {
      keys: ["mentor", "mentorship"],
      answer: "Yes — we offer <strong>high school mentorship</strong>: ongoing guidance on academics, study habits, and planning for college. Sessions are available <strong>in person and online</strong>."
    },
    {
      keys: ["what is able", "about able", "who are you", "who runs", "ceecee", "dr chung"],
      answer: "<strong>ABLE Enrichment</strong> is a Latham, NY education company led by Dr. Ceecee Chung. We offer personalized SAT prep, college admissions consulting, essay coaching, and student mentorship."
    },
    {
      keys: ["subject", "reading", "writing", "math", "what do you teach", "sections"],
      answer: "We cover <strong>SAT Reading &amp; Writing</strong>, <strong>SAT Math</strong>, plus test-taking strategies, pacing, and individualized feedback — all tailored to the student."
    },
    {
      keys: ["online", "virtual", "zoom", "in person", "in-person"],
      answer: "We work with students <strong>in person and online</strong>, so Capital Region families can join either way."
    },
    {
      keys: ["grade", "freshman", "sophomore", "junior", "senior", "what age", "high school"],
      answer: "We work with <strong>high school students</strong> (grades 9–12). Most SAT prep students are rising juniors and seniors getting ready for the August test."
    },
    {
      keys: ["diagnostic", "assessment", "test first", "evaluation"],
      answer: "Yes — we start with a <strong>diagnostic</strong> to see exactly where your child stands, then build the plan around what will move their score fastest."
    },
    {
      keys: ["hi", "hello", "hey"],
      answer: "Hi there! 👋 Ask me about our summer SAT program, registration, class size, pricing, or anything else about ABLE."
    }
  ];

  var FALLBACK = "Hmm, I'm not sure about that one — but we'd love to help! Text us at <a href=\"" + SMS_LINK + "\">" + PHONE_DISPLAY + "</a> (usually same-day reply) or send the inquiry form on this page.";

  var QUICK = ["When is registration?", "How many students per class?", "How much does it cost?", "Where are you located?"];

  function normalize(s) {
    return " " + s.toLowerCase().replace(/[^a-z0-9\s]/g, " ") + " ";
  }

  function findAnswer(text) {
    var n = normalize(text);
    var best = null, bestScore = 0;
    for (var i = 0; i < QA.length; i++) {
      var score = 0;
      for (var j = 0; j < QA[i].keys.length; j++) {
        if (n.indexOf(QA[i].keys[j]) !== -1) { score += QA[i].keys[j].length; }
      }
      if (score > bestScore) { bestScore = score; best = QA[i]; }
    }
    return best ? best.answer : FALLBACK;
  }

  function el(tag, cls, html) {
    var d = document.createElement(tag);
    if (cls) d.className = cls;
    if (html != null) d.innerHTML = html;
    return d;
  }

  function init() {
    // Button
    var btn = el("button", "able-chat-btn");
    btn.setAttribute("aria-label", "Chat with us");
    btn.innerHTML =
      '<svg class="able-chat-bubble-icon" viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/></svg>' +
      '<svg class="able-chat-close-icon" viewBox="0 0 24 24"><path d="M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>';

    // Panel
    var panel = el("div", "able-chat-panel");
    panel.innerHTML =
      '<div class="able-chat-head">' +
        '<div class="able-chat-avatar">A</div>' +
        '<div><h3>Ask ABLE</h3><p>We usually reply instantly — a bot with the basics</p></div>' +
      '</div>' +
      '<div class="able-chat-body"></div>' +
      '<div class="able-chat-input">' +
        '<input type="text" placeholder="Type your question…" aria-label="Type your question">' +
        '<button class="able-chat-send" aria-label="Send"><svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg></button>' +
      '</div>';

    document.body.appendChild(btn);
    document.body.appendChild(panel);

    var body = panel.querySelector(".able-chat-body");
    var input = panel.querySelector("input");
    var sendBtn = panel.querySelector(".able-chat-send");
    var opened = false;

    function addMsg(text, who) {
      var m = el("div", "able-msg " + who, text);
      body.appendChild(m);
      body.scrollTop = body.scrollHeight;
      return m;
    }

    function addChips() {
      var wrap = el("div", "able-chips");
      QUICK.forEach(function (q) {
        var c = el("button", "able-chip", q);
        c.addEventListener("click", function () { ask(q); });
        wrap.appendChild(c);
      });
      body.appendChild(wrap);
      body.scrollTop = body.scrollHeight;
    }

    function reply(text) {
      addMsg(text, "user");
      setTimeout(function () { addMsg(findAnswer(text), "bot"); }, 350);
    }

    function ask(text) {
      if (opened) reply(text);
    }

    function toggle(force) {
      opened = (typeof force === "boolean") ? force : !opened;
      btn.classList.toggle("open", opened);
      panel.classList.toggle("open", opened);
      if (opened && !panel.dataset.greeted) {
        panel.dataset.greeted = "1";
        addMsg("Hi! I'm the ABLE assistant. Ask me about our SAT program, registration, or anything else — or tap a question below.", "bot");
        addChips();
      }
      if (opened) setTimeout(function () { input.focus(); }, 250);
    }

    btn.addEventListener("click", function () { toggle(); });
    sendBtn.addEventListener("click", function () {
      var v = input.value.trim();
      if (v) { input.value = ""; reply(v); }
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        var v = input.value.trim();
        if (v) { input.value = ""; reply(v); }
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
