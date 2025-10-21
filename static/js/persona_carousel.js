/* INFLUE — Persona Carousel (vanilla, touch-friendly, acessível)
 * Não altera fluxos existentes. Apenas inicializa se #persona-carousel existir.
 * Depende de: /static/data/personas.json e /static/data/messages_persona.json
 */

(function () {
  "use strict";

  const sel = (q, root = document) => root.querySelector(q);
  const selAll = (q, root = document) => Array.from(root.querySelectorAll(q));

  function getIconSVG(name) {
    // Fallback leve (estilo linear coerente com o sistema). Apenas os usados.
    const stroke = '#A8D8FF';
    const sw = 1.7;
    const common = `fill="none" stroke="${stroke}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"`;
    const map = {
      smartphone: `<rect x="8" y="3" width="16" height="26" rx="3" ${common}/><circle cx="16" cy="26" r="1.5" ${common}/>`,
      gavel: `<path d="M8 10l6 6M11 7l6 6M4 22l10-10M3 24h10" ${common}/>`,
      stethoscope: `<path d="M8 6c0 6 6 6 6 0M8 6v6a6 6 0 0012 0V6" ${common}/><circle cx="20" cy="18" r="3" ${common}/>`,
      sparkles: `<path d="M12 4l2 4 4 2-4 2-2 4-2-4-4-2 4-2 2-4z" ${common}/><path d="M22 6l1 2 2 1-2 1-1 2-1-2-2-1 2-1 1-2z" ${common}/>`,
      scissors: `<path d="M8 8l8 8M8 16l3-3M13 11l7 7" ${common}/><circle cx="6" cy="18" r="3" ${common}/><circle cx="6" cy="6" r="3" ${common}/>`,
      cup: `<path d="M7 8h14v4a6 6 0 01-6 6H13a6 6 0 01-6-6V8z" ${common}/><path d="M21 9h2a3 3 0 010 6h-1" ${common}/>`,
      "shopping-bag": `<path d="M6 9h20l-2 14H8L6 9z" ${common}/><path d="M10 9a6 6 0 0012 0" ${common}/>`,
      "chef-hat": `<path d="M8 12h16v8H8z" ${common}/><path d="M10 12a6 6 0 0112 0" ${common}/>`,
      "t-shirt": `<path d="M10 7l6-3 6 3v14H10V7z" ${common}/><path d="M10 7l-4 3v5" ${common}/><path d="M22 7l4 3v5" ${common}/>`,
      camera: `<rect x="6" y="8" width="20" height="14" rx="2" ${common}/><circle cx="16" cy="15" r="5" ${common}/>`,
      briefcase: `<rect x="6" y="10" width="20" height="14" rx="2" ${common}/><path d="M12 10V7h8v3" ${common}/>`,
      tool: `<path d="M13 7l4 4-3 3-4-4M16 11l6 6" ${common}/><circle cx="9" cy="15" r="3" ${common}/>`,
      activity: `<path d="M4 12h5l3 8 4-16 4 8h6" ${common}/>`,
      dumbbell: `<path d="M6 12v6M10 10v10M14 12v6M18 10v10" ${common}/><path d="M10 15h4" ${common}/>`,
      cupcake: `<path d="M8 14h16l-2 8H10l-2-8z" ${common}/><path d="M12 14a6 6 0 0112 0" ${common}/>`,
      home: `<path d="M4 14l12-8 12 8v12H4V14z" ${common}/><path d="M14 26v-8h8v8" ${common}/>`,
      cpu: `<rect x="8" y="8" width="16" height="16" rx="2" ${common}/><path d="M16 8v-4M12 12h8M16 24v4" ${common}/>`,
      truck: `<rect x="6" y="12" width="14" height="9" rx="2" ${common}/><path d="M20 14h6l2 4v3h-3" ${common}/><circle cx="12" cy="24" r="2.5" ${common}/><circle cx="22" cy="24" r="2.5" ${common}/>`,
      book: `<path d="M8 7h12a4 4 0 014 4v12H8a4 4 0 01-4-4V11a4 4 0 014-4z" ${common}/><path d="M24 7v16" ${common}/>`,
      "map-pin": `<path d="M16 26s-8-7-8-12a8 8 0 1116 0c0 5-8 12-8 12z" ${common}/><circle cx="16" cy="14" r="3" ${common}/>`
    };
    return map[name] || `<circle cx="16" cy="16" r="10" ${common}/>`;
  }

  function showToast(message) {
    let t = sel("#persona-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "persona-toast";
      t.setAttribute("role", "status");
      t.style.position = "fixed";
      t.style.left = "50%";
      t.style.bottom = "24px";
      t.style.transform = "translateX(-50%)";
      t.style.background = "rgba(10,16,30,.9)";
      t.style.border = "1px solid rgba(148,163,184,.35)";
      t.style.color = "#E8F1FF";
      t.style.padding = ".65rem .9rem";
      t.style.borderRadius = "12px";
      t.style.boxShadow = "0 10px 30px rgba(0,0,0,.45)";
      t.style.zIndex = "9999";
      t.style.maxWidth = "92vw";
      t.style.fontSize = ".95rem";
      document.body.appendChild(t);
    }
    t.textContent = message;
    t.style.opacity = "0";
    t.style.display = "block";
    requestAnimationFrame(() => {
      t.style.transition = "opacity .25s ease";
      t.style.opacity = "1";
    });
    setTimeout(() => {
      t.style.opacity = "0";
      setTimeout(() => { t.style.display = "none"; }, 200);
    }, 2400);
  }

  function savePersona(p) {
    try {
      sessionStorage.setItem("influe_persona", JSON.stringify({ id: p.id, key: p.key, name: p.title }));
    } catch {}
  }

  function trackPersona(key) {
    try { window.track && window.track("select_persona", { persona: key }); } catch {}
  }

  async function fetchJSON(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error("Falha ao carregar " + url);
    return await res.json();
  }

  function buildCard(persona) {
    const card = document.createElement("button");
    card.className = "pc-card";
    card.type = "button";
    card.setAttribute("aria-label", `${persona.title}: ${persona.subtitle}`);
    card.innerHTML = `
      <div class="pc-ico">
        <svg width="36" height="36" viewBox="0 0 32 32" aria-hidden="true">${getIconSVG(persona.icon?.name || "")}</svg>
      </div>
      <div class="pc-ttl">${persona.title}</div>
      <div class="pc-sub">${persona.subtitle}</div>
      <div class="pc-phrase">${persona.phrase}</div>
    `;
    card.addEventListener("click", () => {
      savePersona(persona);
      trackPersona(persona.key);
      showToast(`Selecionado: ${persona.title}. ${persona.phrase}`);
      // pulso leve no ícone
      const ico = card.querySelector(".pc-ico");
      ico?.classList.add("pulse");
      setTimeout(() => ico?.classList.remove("pulse"), 600);
    });
    return card;
  }

  function buildModal(personas) {
    let modal = sel("#persona-modal");
    let backdrop = sel("#persona-modal-backdrop");
    if (!modal) {
      backdrop = document.createElement("div");
      backdrop.id = "persona-modal-backdrop";
      backdrop.className = "persona-modal-backdrop";
      modal = document.createElement("section");
      modal.id = "persona-modal";
      modal.className = "persona-modal";
      modal.setAttribute("role", "dialog");
      modal.setAttribute("aria-modal", "true");
      modal.innerHTML = `
        <div class="persona-modal-panel">
          <div class="persona-modal-head">
            <strong>Selecione seu perfil</strong>
            <button id="persona-modal-close" class="btn btn-ghost" type="button" aria-label="Fechar">Fechar</button>
          </div>
          <div class="persona-grid" id="persona-grid"></div>
        </div>
      `;
      document.body.appendChild(backdrop);
      document.body.appendChild(modal);
      sel("#persona-modal-close", modal)?.addEventListener("click", () => hideModal());
      backdrop.addEventListener("click", () => hideModal());
    }
    // preencher grid
    const grid = sel("#persona-grid", modal);
    grid.innerHTML = "";
    personas.forEach(p => {
      const item = document.createElement("button");
      item.className = "persona-item";
      item.type = "button";
      item.setAttribute("aria-label", `${p.title}: ${p.subtitle}`);
      item.innerHTML = `
        <div class="pi-ico">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">${getIconSVG(p.icon?.name || "")}</svg>
        </div>
        <div class="pi-ttl">${p.title}</div>
        <div class="pi-sub">${p.subtitle}</div>
      `;
      item.addEventListener("click", () => {
        savePersona(p);
        trackPersona(p.key);
        showToast(`Selecionado: ${p.title}. ${p.phrase}`);
        hideModal();
      });
      grid.appendChild(item);
    });

    function showModal() {
      backdrop.classList.add("show");
      modal.classList.add("show");
    }
    function hideModal() {
      backdrop.classList.remove("show");
      modal.classList.remove("show");
    }
    return { showModal, hideModal };
  }

  async function init() {
    const wrap = sel("#persona-carousel");
    if (!wrap) return;

    let personas = [];
    let messages = null;
    try {
      [personas, messages] = await Promise.all([
        fetchJSON("/static/data/personas.json"),
        fetchJSON("/static/data/messages_persona.json")
      ]);
      // (messages disponível para uso futuro/contextual)
    } catch (e) {
      console.warn("[PersonaCarousel] Falha ao carregar dados:", e);
      return;
    }

    const track = sel(".pc-track", wrap);
    track.innerHTML = "";
    personas.forEach(p => track.appendChild(buildCard(p)));

    const dots = sel(".pc-dots", wrap);
    if (dots) {
      const n = personas.length;
      dots.innerHTML = "";
      for (let i = 0; i < Math.min(n, 8); i++) {
        const d = document.createElement("span");
        d.className = "pc-dot";
        dots.appendChild(d);
      }
      const dotArr = selAll(".pc-dot", dots);
      const updateDots = () => {
        const scrollX = track.scrollLeft;
        const idx = Math.round(scrollX / (track.firstElementChild?.offsetWidth || 1));
        dotArr.forEach((el, i) => el.classList.toggle("active", i === (idx % dotArr.length)));
      };
      track.addEventListener("scroll", () => {
        window.requestAnimationFrame(updateDots);
      });
      updateDots();
    }

    const { showModal } = buildModal(personas);
    sel("#persona-more")?.addEventListener("click", showModal);

    // teclado/acessibilidade: cards recebem foco pelo tab naturalmente (botões).
  }

  document.addEventListener("DOMContentLoaded", init);
})();
