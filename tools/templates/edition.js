// Online HTML edition: table of contents, reading progress, resume, chapter
// links, footnote pop-ups, theme and text size. Without it the page is still
// the plain text with its table of contents.
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const D = JSON.parse($("#edition-data").textContent);
  const store = {
    get: k => { try { return localStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
  };
  const root = document.documentElement;
  const sections = $$("main section.level1");
  const tocLinks = new Map($$("#TOC a").map(a => [decodeURIComponent(a.hash.slice(1)), a]));
  const titleOf = s => s.querySelector("h1").textContent.replace(/^#\s*/, "").trim();
  const esc = s => s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  // heading anchors and previous / next chapter
  sections.forEach((s, i) => {
    const h = s.querySelector("h1");
    h.insertAdjacentHTML("afterbegin", `<a class="anchor" href="#${esc(s.id)}" aria-hidden="true" tabindex="-1">#</a>`);
    const link = (j, cls, label) => j < 0 || j >= sections.length ? "" :
      `<a class="${cls}" href="#${esc(sections[j].id)}"><small>${label}</small>${esc(titleOf(sections[j]))}</a>`;
    const nav = document.createElement("nav");
    nav.className = "chapnav";
    nav.innerHTML = link(i - 1, "prev", "← " + D.ui.prev) + link(i + 1, "next", D.ui.next + " →");
    s.append(nav);
  });

  // contents drawer (narrow screens)
  const openToc = on => document.body.classList.toggle("toc-open", on);
  $("#toc-btn")?.addEventListener("click", () => openToc(!document.body.classList.contains("toc-open")));
  $(".scrim")?.addEventListener("click", () => openToc(false));
  $("#TOC").addEventListener("click", e => { if (e.target.closest("a")) openToc(false); });

  // current chapter, progress, saved position
  const bar = $(".progress");
  const key = "wic:" + D.key;
  let current = -1, saveTimer;
  const onScroll = () => {
    const max = root.scrollHeight - innerHeight;
    bar.style.width = (max > 0 ? Math.min(100, scrollY / max * 100) : 0) + "%";
    let i = -1;
    sections.forEach((s, j) => { if (s.getBoundingClientRect().top < 90) i = j; });
    if (i !== current) {
      tocLinks.get(sections[current]?.id)?.classList.remove("current");
      const a = tocLinks.get(sections[i]?.id);
      a?.classList.add("current");
      if (a && !document.body.classList.contains("toc-open")) a.scrollIntoView({ block: "nearest" });
      current = i;
    }
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      if (current >= 0) store.set(key, JSON.stringify({ id: sections[current].id, f: scrollY / root.scrollHeight }));
    }, 400);
  };
  let ticking = false;
  addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(() => { onScroll(); ticking = false; }); } }, { passive: true });
  onScroll();

  // offer to continue where the reader stopped
  try {
    const saved = JSON.parse(store.get(key) || "null");
    const s = saved && document.getElementById(saved.id);
    if (s && !location.hash && saved.f > 0.02) {
      const t = document.createElement("div");
      t.className = "toast";
      t.setAttribute("role", "status");
      t.innerHTML = `<a href="#${esc(saved.id)}">${esc(D.ui.resume)}: «${esc(titleOf(s))}»</a>` +
        `<button class="btn" type="button" aria-label="×">✕</button>`;
      t.querySelector("a").addEventListener("click", e => {
        e.preventDefault();
        scrollTo({ top: saved.f * root.scrollHeight });
        t.remove();
      });
      t.querySelector("button").addEventListener("click", () => t.remove());
      document.body.append(t);
      setTimeout(() => t.remove(), 15000);
    }
  } catch { /* nothing saved */ }

  // the same chapter in another language
  $$("[data-parts]").forEach(a => a.addEventListener("click", () => {
    const parts = a.dataset.parts.split(" ");
    if (current >= 0 && parts[current]) a.href = a.dataset.base + "#sec:" + parts[current];
  }));

  // footnotes as pop-ups
  let pop;
  const closePop = () => { pop?.remove(); pop = null; };
  $$("a.footnote-ref").forEach(ref => ref.addEventListener("click", e => {
    const note = document.getElementById(decodeURIComponent(ref.hash.slice(1)));
    if (!note) return;
    e.preventDefault();
    e.stopPropagation();
    closePop();
    pop = document.createElement("div");
    pop.className = "note-pop";
    pop.setAttribute("role", "note");
    pop.innerHTML = note.innerHTML;
    pop.querySelectorAll(".footnote-back").forEach(b => b.remove());
    document.body.append(pop);
    const r = ref.getBoundingClientRect();
    const left = Math.max(12, Math.min(r.left + scrollX - 20, scrollX + innerWidth - pop.offsetWidth - 12));
    pop.style.left = left + "px";
    pop.style.top = (r.bottom + scrollY + 8) + "px";
  }));
  document.addEventListener("click", e => {
    if (pop && !pop.contains(e.target)) closePop();
    $$("details.menu[open]").forEach(d => { if (!d.contains(e.target)) d.open = false; });
  });
  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    closePop();
    openToc(false);
    $$("details.menu[open]").forEach(d => { d.open = false; });
  });

  // theme and text size
  const themeButtons = $$("[data-theme-set]");
  const setTheme = t => {
    if (t === "auto") root.removeAttribute("data-theme"); else root.dataset.theme = t;
    themeButtons.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.themeSet === t)));
    store.set("wic:theme", t);
  };
  themeButtons.forEach(b => b.addEventListener("click", () => setTheme(b.dataset.themeSet)));
  setTheme(store.get("wic:theme") || "auto");
  const SIZES = [15, 16.5, 17.5, 19, 20.5, 22, 24];
  $$("[data-fs]").forEach(b => b.addEventListener("click", () => {
    const now = parseFloat(getComputedStyle(root).getPropertyValue("--fs")) || 19;
    let i = SIZES.findIndex(s => s >= now - 0.1);
    if (i < 0) i = SIZES.length - 1;
    const px = SIZES[Math.max(0, Math.min(SIZES.length - 1, i + Number(b.dataset.fs)))];
    const y = scrollY / root.scrollHeight;
    root.style.setProperty("--fs", px + "px");
    store.set("wic:fs", String(px));
    scrollTo({ top: y * root.scrollHeight });
  }));
})();
