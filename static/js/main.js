/* INFLUE — Controller (mobile-first)
 * Fluxos: autenticação, compra, envio de foto/texto, feedback, loader e SIDEBAR Inteligente.
 */

(function () {
  "use strict";

  // -----------------------------
  // Helpers DOM
  // -----------------------------
  const $ = (sel) => document.querySelector(sel);

  // Rodapé
  const elYear = $("#year");

  // Header
  const elCredits = $("#credits-left");
  const elBtnOpenAuth = $("#btn-open-auth");
  const elBtnLogout = $("#btn-logout");
  const elBtnPurchase = $("#btn-purchase");
  const elUserLabel = $("#user-label");
  const elUserState = $("#user-state");

  // Sidebar
  const elSidebar = $("#influe-sidebar");
  const elSidebarOverlay = $("#influe-sidebar-overlay");
  const elSidebarToggle = $("#sidebar-toggle");
  const elSidebarClose = $("#sidebar-close");

  // Modal (login)
  const formLogin = $("#form-login");
  const elAuthEmail = $("#auth-email");
  const elAuthPassword = $("#auth-password");

  // Modal (signup)
  const formSignup = $("#form-signup");
  const elRegEmail = $("#reg-email");
  const elRegEmail2 = $("#reg-email2");
  const elRegPass = $("#reg-pass");
  const elRegPass2 = $("#reg-pass2");

  // Upload card
  const elInputPhoto = $("#photo-input");
  const elBtnPhoto = $("#btn-photo");
  const elTextarea = $("#textcontent");
  const elBtnSubmitText = $("#btn-submit-text");

  // Campo opcional de intenção (se existir)
  const elIntent = $("#intent");

  // Pré-visualização + limpar (se existirem)
  const elPreviewWrap = $("#photo-preview-wrap");
  const elPreviewImg  = $("#photo-preview");
  const elBtnClear    = $("#btn-clear-photo");

  // Saída de análise
  const elOut = $("#analysis-output");
  const elOutSummary = $("#analysis-summary");
  const elOutScore = $("#analysis-score");
  const elOutTags = $("#analysis-tags");
  const elOutRecs = $("#analysis-recs");

  // Modal controls (expostos por base.html)
  const showAuth = window.__influe_show_auth__ || (() => {});
  const hideAuth = window.__influe_hide_auth__ || (() => {});
  const setAuthTab = window.__influe_set_auth_tab__ || (() => {});

  // Seleciona SEMPRE o feedback do CARD (não o do modal)
  function pickMainFeedback() {
    const candidates = [
      document.querySelector("#page-feedback"),
      document.querySelector("#feedback"),
    ].filter(Boolean);
    if (candidates.length) return candidates[0];
    const all = Array.from(document.querySelectorAll("#feedback, #page-feedback"));
    for (const el of all) {
      if (!el.closest("#auth-modal")) return el;
    }
    return null;
  }
  let elFeedback = pickMainFeedback();

  // -----------------------------
  // Loader (spinner + progress)
  // -----------------------------
  (function injectLoaderCSS() {
    // Loader CSS (já existente)
    if (!document.getElementById("influe-loader-css")) {
      const css = `
      .influe-loader-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;z-index:9999;backdrop-filter:saturate(120%) blur(2px)}
      .influe-loader-overlay.show{display:flex;align-items:center;justify-content:center}
      .influe-loader-card{width:min(420px,90vw);background:linear-gradient(180deg, rgba(20,25,40,.98), rgba(10,12,20,.98));border:1px solid rgba(148,163,184,.25);border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,.6);padding:1rem 1.1rem;color:#e8f1ff}
      .influe-row{display:flex;gap:.75rem;align-items:center}
      .influe-spinner{width:26px;height:26px;border-radius:50%;border:3px solid rgba(255,255,255,.22);border-top-color:#3b82f6;animation:influe-spin 0.9s linear infinite;flex:0 0 26px}
      @keyframes influe-spin{to{transform:rotate(360deg)}}
      .influe-title{font-weight:700;margin:0 0 .35rem}
      .influe-msg{margin:0;color:#cfe2ff}
      .influe-progress{margin:.85rem 0 .1rem;height:10px;background:rgba(255,255,255,.12);border-radius:999px;overflow:hidden}
      .influe-bar{height:100%;width:3%;background:#3b82f6;transition:width .25s ease;border-radius:999px}
      .influe-pct{font-size:.9rem;color:#b8c2d9}
      `;
      const s = document.createElement("style");
      s.id = "influe-loader-css";
      s.textContent = css;
      document.head.appendChild(s);
    }
  })();

  // -----------------------------
  // Sidebar CSS (injeção isolada)
  // -----------------------------
  (function injectSidebarCSS() {
    if (document.getElementById("influe-sidebar-css")) return;
    const css = `
    /* Overlay */
    #influe-sidebar-overlay{
      position:fixed;inset:0;background:rgba(0,0,0,.3);backdrop-filter:blur(1px);
      opacity:0;pointer-events:none;transition:opacity .4s cubic-bezier(0.22,1,0.36,1);z-index:8000;
    }
    #influe-sidebar-overlay.show{opacity:1;pointer-events:auto;}

    /* Sidebar */
    #influe-sidebar{
      position:fixed;top:0;left:0;height:100vh;width:320px;max-width:90vw;
      transform:translateX(-105%);transition:transform .4s cubic-bezier(0.22,1,0.36,1);
      background:linear-gradient(180deg,#0A1C3E 0%, #07142c 100%);
      color:#e8f1ff;border-right:1px solid rgba(148,163,184,.18);
      box-shadow:12px 0 30px rgba(0,0,0,.35);z-index:9000;border-top-right-radius:16px;border-bottom-right-radius:16px;
      display:flex;flex-direction:column;
    }
    #influe-sidebar.show{transform:translateX(0);}

    .sidebar-header{
      display:flex;align-items:center;justify-content:space-between;padding:.9rem 1rem;border-bottom:1px solid rgba(148,163,184,.18)
    }
    .sidebar-header .title{font-weight:700}
    .sidebar-content{padding:1rem;overflow:auto}
    .sb-card{background:rgba(255,255,255,.04);border:1px solid rgba(148,163,184,.18);border-radius:16px;padding:.9rem;margin-bottom:1rem;box-shadow:0 4px 16px rgba(0,0,0,.15)}
    .sb-card-title{font-weight:600;margin-bottom:.5rem;color:#A8D8FF}
    .sb-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.5rem}
    .sb-item{display:flex;align-items:center;gap:.6rem;background:rgba(255,255,255,.03);border:1px solid rgba(148,163,184,.15);border-radius:12px;padding:.5rem .6rem}
    .sb-thumb{width:34px;height:34px;border-radius:8px;background:linear-gradient(135deg,#1F80FF,#3CAEFF);display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:.8rem}
    .sb-meta{display:flex;flex-direction:column;line-height:1.2}
    .sb-meta small{opacity:.8}
    .sb-chip{padding:.1rem .4rem;border-radius:999px;font-size:.75rem;border:1px solid rgba(148,163,184,.25)}
    .sb-filters{display:flex;gap:.5rem;margin-bottom:.5rem}
    .sb-filters select{background:#0f224b;border:1px solid rgba(148,163,184,.25);color:#e8f1ff;border-radius:10px;padding:.35rem .5rem}
    .chip{display:inline-flex;align-items:center;gap:.25rem;background:rgba(31,128,255,.15);border:1px solid rgba(60,174,255,.35);padding:.2rem .5rem;border-radius:999px;color:#A8D8FF}
    .thermo{position:relative;height:14px;background:rgba(255,255,255,.08);border-radius:999px;overflow:hidden}
    .thermo-bar{height:100%;width:0%;background:linear-gradient(90deg,#1F80FF,#3CAEFF);box-shadow:0 0 16px rgba(60,174,255,.45) inset;position:relative;transition:width .6s ease}
    .thermo-pct{position:absolute;right:6px;top:-22px;font-size:.8rem;color:#A8D8FF}
    .metric{font-weight:700}
    .donut-wrap{display:flex;align-items:center;justify-content:center;height:140px}
    .btn-icon:hover{filter:brightness(1.1)}
    `;
    const s = document.createElement("style");
    s.id = "influe-sidebar-css";
    s.textContent = css;
    document.head.appendChild(s);
  })();

  let loader = null;
  let progressTimer = null;
  let currentPct = 0;

  function ensureLoader() {
    if (loader) return loader;
    const overlay = document.createElement("div");
    overlay.className = "influe-loader-overlay";
    overlay.innerHTML = `
      <div class="influe-loader-card">
        <div class="influe-row">
          <div class="influe-spinner"></div>
          <div>
            <h3 class="influe-title" id="influe-loader-title">Processando…</h3>
            <p class="influe-msg" id="influe-loader-msg">Por favor, aguarde.</p>
          </div>
        </div>
        <div class="influe-progress">
          <div class="influe-bar" id="influe-loader-bar"></div>
        </div>
        <div class="influe-pct" id="influe-loader-pct">0%</div>
      </div>`;
    document.body.appendChild(overlay);
    loader = {
      overlay,
      title: overlay.querySelector("#influe-loader-title"),
      msg: overlay.querySelector("#influe-loader-msg"),
      bar: overlay.querySelector("#influe-loader-bar"),
      pct: overlay.querySelector("#influe-loader-pct"),
    };
    return loader;
  }

  function updateProgress(p) {
    const L = ensureLoader();
    const pct = Math.max(0, Math.min(100, Math.floor(p)));
    L.bar.style.width = pct + "%";
    L.pct.textContent = pct + "%";
  }

  function showLoader(title = "Processando…", message = "Por favor, aguarde.") {
    const L = ensureLoader();
    L.title.textContent = title;
    L.msg.textContent = message;
    currentPct = 1;
    updateProgress(1);
    L.overlay.classList.add("show");
    clearInterval(progressTimer);
    progressTimer = setInterval(() => {
      if (currentPct < 95) {
        currentPct += Math.max(1, Math.round((100 - currentPct) * 0.03));
        updateProgress(currentPct);
      }
    }, 350);
  }

  function hideLoader() {
    if (!loader) return;
    clearInterval(progressTimer);
    progressTimer = null;
    updateProgress(100);
    setTimeout(() => {
      loader.overlay.classList.remove("show");
      updateProgress(0);
    }, 180);
  }

  // Desabilita ações repetidas
  function setActionsDisabled(disabled) {
    const toggle = (el) => { if (el) el.disabled = disabled; };
    toggle(elBtnPhoto);
    toggle(elBtnSubmitText);
    formLogin?.querySelectorAll("button, input").forEach((n) => { n.disabled = disabled; });
    formSignup?.querySelectorAll("button, input").forEach((n) => { n.disabled = disabled; });
  }

  // -----------------------------
  // Utilidades gerais
  // -----------------------------
  if (elYear) elYear.textContent = new Date().getFullYear();

  function setFeedback(msg) {
    if (!elFeedback) elFeedback = pickMainFeedback();
    if (elFeedback) elFeedback.textContent = msg || "";
  }

  function parseJSONSafe(res) {
    return res.text().then((t) => {
      try { return JSON.parse(t); } catch { return { __raw: t }; }
    });
  }

  function showAnalysis(analysis) {
    const score = typeof analysis.score_risk === "number" ? analysis.score_risk : "—";
    const tags = Array.isArray(analysis.tags) ? analysis.tags.join(", ") : "—";
    const recs = Array.isArray(analysis.recommendations) ? analysis.recommendations : [];

    if (elOutSummary) elOutSummary.textContent = analysis.summary || "Análise concluída.";
    if (elOutScore) elOutScore.textContent = String(score);
    if (elOutTags) elOutTags.textContent = tags;

    if (elOutRecs) {
      elOutRecs.innerHTML = "";
      recs.slice(0, 3).forEach((r) => {
        const li = document.createElement("li");
        li.textContent = r;
        elOutRecs.appendChild(li);
      });
    }
    if (elOut) elOut.style.display = "block";
  }

  // -----------------------------
  // Token
  // -----------------------------
  function getToken() { return localStorage.getItem("influe_token") || null; }
  function setToken(token) { if (token) localStorage.setItem("influe_token", token); }
  function clearToken() { localStorage.removeItem("influe_token"); }
  function authHeaders() {
    const t = getToken();
    return t ? { Authorization: "Bearer " + t } : {};
  }

  function setUserState(label, color = "#6aa8ff") {
    if (elUserLabel) elUserLabel.textContent = label;
    const circle = elUserState?.querySelector("circle");
    if (circle) circle.setAttribute("fill", color);
  }

  function updateAuthUI() {
    const logged = !!getToken();
    if (elBtnOpenAuth) elBtnOpenAuth.style.display = logged ? "none" : "";
    if (elBtnLogout) elBtnLogout.style.display = logged ? "" : "none";
    if (logged) setUserState("Logado", "#00e676");
    else setUserState("Convidado", "#6aa8ff");
  }

  // -----------------------------
  // Créditos
  // -----------------------------
  async function updateCreditsLabel() {
    try {
      const res = await fetch("/credits_status", { headers: authHeaders() });
      if (!res.ok) return;
      const json = await res.json();
      if (!json?.ok) return;
      const data = json.data || {};
      const s = data.session ?? "—";
      const u = data.user ?? "—";
      const free = typeof data.free_credits === "number" ? data.free_credits : 0;
      const sText = typeof s === "number" && free > 0 ? `${s}/${free}` : String(s);
      const uText = typeof u === "number" ? String(u) : "—";
      if (elCredits) elCredits.textContent = `Sessão: ${sText} | Usuário: ${uText}`;
      // Atualiza chip na sidebar (se existir)
      const sbChip = $("#sb-credits-chip");
      if (sbChip) sbChip.textContent = `Créditos: ${uText !== "—" ? uText : sText}`;
    } catch {}
  }

  async function checkGateForCredits() {
    try {
      const res = await fetch("/gate/login", { headers: authHeaders() });
      const json = await res.json();
      if (!json?.ok) return { gated: false, need_purchase: false, logged_in: false };
      if (json.require_login) return { gated: true, need_purchase: false, logged_in: !!json.logged_in };
      if (json.need_purchase) return { gated: false, need_purchase: true, logged_in: true };
      return { gated: false, need_purchase: false, logged_in: !!json.logged_in };
    } catch { return { gated: false, need_purchase: false, logged_in: false }; }
  }

  async function requireLoginIfNoCredits() {
    const res = await checkGateForCredits();
    if (res.gated) { setAuthTab("login"); showAuth(); return true; }
    if (res.need_purchase) setFeedback('Você está logado, mas sem créditos. Clique em “Comprar créditos”.');
    return false;
  }

  // -----------------------------
  // Auth
  // -----------------------------
  function isValidEmail(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); }

  formLogin?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = (elAuthEmail?.value || "").trim().toLowerCase();
    const password = elAuthPassword?.value || "";
    if (!email || !password) { setFeedback("Informe e-mail e senha."); return; }
    if (!isValidEmail(email)) { setFeedback("E-mail inválido."); return; }

    setActionsDisabled(true);
    showLoader("Entrando…", "Validando suas credenciais.");
    setFeedback("Entrando...");

    try {
      const res = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (res.status === 401) { setFeedback("Credenciais inválidas."); return; }
      if (res.status >= 500) { setFeedback("Servidor indisponível (erro 5xx). Tente novamente em instantes."); return; }

      const json = await parseJSONSafe(res);
      if (json.ok && json.token) {
        setToken(json.token);
        hideAuth();
        setFeedback("Login efetuado.");
        updateAuthUI();
        await updateCreditsLabel();
      } else {
        setFeedback(json.error || "Falha na autenticação.");
      }
    } catch {
      setFeedback("Erro de rede.");
    } finally {
      hideLoader();
      setActionsDisabled(false);
    }
  });

  formSignup?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email  = (elRegEmail?.value || "").trim().toLowerCase();
    const email2 = (elRegEmail2?.value || "").trim().toLowerCase();
    const pass   = elRegPass?.value || "";
    const pass2  = elRegPass2?.value || "";
    if (!email || !email2 || !pass || !pass2) { setFeedback("Preencha todos os campos."); return; }
    if (!isValidEmail(email)) { setFeedback("E-mail inválido."); return; }
    if (email !== email2) { setFeedback("Os e-mails não conferem."); return; }
    if (pass.length < 6) { setFeedback("Senha muito curta (mín. 6)."); return; }
    if (pass !== pass2) { setFeedback("As senhas não conferem."); return; }

    setActionsDisabled(true);
    showLoader("Criando conta…", "Preparando seu acesso.");
    setFeedback("Criando conta...");

    try {
      const res = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: pass }),
      });

      if (res.status === 409) { setFeedback("E-mail já cadastrado."); return; }
      if (res.status >= 500) { setFeedback("Servidor indisponível (erro 5xx). Tente novamente."); return; }

      const json = await parseJSONSafe(res);
      if (json.ok && json.token) {
        setToken(json.token);
        hideAuth();
        setFeedback("Conta criada com sucesso.");
        updateAuthUI();
        await updateCreditsLabel();
      } else {
        setFeedback(json.error || "Falha ao criar conta.");
      }
    } catch {
      setFeedback("Erro de rede.");
    } finally {
      hideLoader();
      setActionsDisabled(false);
    }
  });

  elBtnLogout?.addEventListener("click", (e) => {
    e.preventDefault();
    clearToken();
    updateAuthUI();
    updateCreditsLabel();
    setFeedback("Sessão encerrada.");
  });

  // -----------------------------
  // Compra
  // -----------------------------
  elBtnPurchase?.addEventListener("click", () => {
    if (!getToken()) { setAuthTab("login"); showAuth(); return; }
    window.location.href = "/buy";
  });

  // -----------------------------
  // Canvas/toBlob polyfill
  // -----------------------------
  if (!HTMLCanvasElement.prototype.toBlob) {
    HTMLCanvasElement.prototype.toBlob = function (callback, type, quality) {
      const dataURL = this.toDataURL(type, quality).split(",")[1];
      const binStr = atob(dataURL);
      const len = binStr.length;
      const arr = new Uint8Array(len);
      for (let i = 0; i < len; i++) arr[i] = binStr.charCodeAt(i);
      callback(new Blob([arr], { type: "image/jpeg" }));
    };
  }

  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("Falha ao ler arquivo."));
      reader.onload = () => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error("Falha ao carregar imagem."));
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  async function compressImage(file, maxW = 1920, maxH = 1920, quality = 0.7) {
    try {
      const img = await loadImage(file);
      const ratio = Math.min(maxW / img.width, maxH / img.height, 1);
      const w = Math.max(1, Math.round(img.width * ratio));
      const h = Math.max(1, Math.round(img.height * ratio));
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, w, h);
      const blob = await new Promise((resolve) =>
        canvas.toBlob((b) => resolve(b), "image/jpeg", quality)
      );
      if (!blob) return file;
      const name = file.name?.replace(/\.(png|jpeg|jpg|heic)$/i, "") || "image";
      return new File([blob], `${name}.jpg`, { type: "image/jpeg" });
    } catch { return file; }
  }

  // -----------------------------
  // /analyze_photo
  // -----------------------------
  const elBtnTextOpen = document.getElementById("btn-text");
  elBtnTextOpen?.addEventListener("click", () => {
    document.getElementById("textcontent")?.focus();
  });

  // Preview helpers
  let lastObjectUrl = null;
  function showPreview(file) {
    if (!elPreviewWrap || !elPreviewImg) return;
    try {
      if (lastObjectUrl) URL.revokeObjectURL(lastObjectUrl);
      lastObjectUrl = URL.createObjectURL(file);
      elPreviewImg.src = lastObjectUrl;
      elPreviewWrap.style.display = "";
    } catch {}
  }
  function clearPreview() {
    if (elInputPhoto) elInputPhoto.value = "";
    if (elPreviewImg) elPreviewImg.src = "";
    if (elPreviewWrap) elPreviewWrap.style.display = "none";
    if (lastObjectUrl) { try { URL.revokeObjectURL(lastObjectUrl); } catch {} lastObjectUrl = null; }
    if (elOut) elOut.style.display = "none";
    setFeedback("");
  }
  elBtnClear?.addEventListener("click", clearPreview);

  elBtnPhoto?.addEventListener("click", () => elInputPhoto?.click());

  elInputPhoto?.addEventListener("change", async () => {
    if (!elInputPhoto.files || !elInputPhoto.files[0]) return;

    setActionsDisabled(true);
    showLoader("Analisando foto…", "Estamos processando sua imagem.");
    setFeedback("Compactando imagem...");

    const original = elInputPhoto.files[0];
    const compressed = await compressImage(original, 1920, 1920, 0.7);

    showPreview(compressed);

    const fd = new FormData();
    fd.append("photo", compressed, compressed.name);
    if (elIntent && typeof elIntent.value === "string") {
      const intentValue = (elIntent.value || "").trim().slice(0, 140);
      if (intentValue) fd.append("intent", intentValue);
    }

    setFeedback("Enviando para análise...");
    try {
      const res = await fetch("/analyze_photo", {
        method: "POST",
        headers: authHeaders(),
        body: fd,
      });

      if (res.status === 402) { hideLoader(); await updateCreditsLabel(); const gated = await requireLoginIfNoCredits(); if (!gated) setFeedback("Sem créditos disponíveis."); return; }
      if (res.status === 429) { hideLoader(); setFeedback("Muitas requisições. Tente novamente em instantes."); return; }
      if (res.status >= 500) {
        const json = await parseJSONSafe(res);
        hideLoader();
        setFeedback(json.error || "Servidor indisponível (erro 5xx).");
        return;
      }

      const json = await parseJSONSafe(res);
      if (json.ok) {
        updateProgress(100);
        showAnalysis(json.analysis);
        setFeedback("Análise concluída.");
      } else {
        setFeedback(json.error || "Falha na análise da foto.");
      }
    } catch {
      setFeedback("Erro de rede ao enviar foto.");
    } finally {
      hideLoader();
      setActionsDisabled(false);
      await updateCreditsLabel();
    }
  });

  // -----------------------------
  // /analyze_text (pode não existir na UI)
  // -----------------------------
  elBtnSubmitText?.addEventListener("click", async () => {
    const text = (elTextarea?.value || "").trim();
    if (!text) { setFeedback("Digite um texto para analisar."); return; }

    setActionsDisabled(true);
    showLoader("Analisando texto…", "Estamos processando sua análise.");
    setFeedback("Analisando texto...");

    try {
      const res = await fetch("/analyze_text", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ text }),
      });

      if (res.status === 402) { hideLoader(); await updateCreditsLabel(); const gated = await requireLoginIfNoCredits(); if (!gated) setFeedback("Sem créditos disponíveis."); return; }
      if (res.status === 429) { hideLoader(); setFeedback("Muitas requisições. Tente novamente em instantes."); return; }
      if (res.status >= 500) {
        const json = await parseJSONSafe(res);
        hideLoader();
        setFeedback(json.error || "Servidor indisponível (erro 5xx).");
        return;
      }

      const json = await parseJSONSafe(res);
      if (json.ok) {
        updateProgress(100);
        showAnalysis(json.analysis);
        setFeedback("Análise concluída.");
      } else {
        setFeedback(json.error || "Falha na análise do texto.");
      }
    } catch {
      setFeedback("Erro de rede ao enviar texto.");
    } finally {
      hideLoader();
      setActionsDisabled(false);
      await updateCreditsLabel();
    }
  });

  // -----------------------------
  // SIDEBAR — Dados e UI
  // -----------------------------
  const motivMessages = [
    "Sua presença digital está subindo! Continue nesse ritmo!",
    "Evite fotos com baixa iluminação — reduzem o impacto visual.",
    "O público reagiu bem às suas cores vibrantes!",
    "Cuidado: excesso de filtros pode parecer artificial.",
    "Seu engajamento está 12% acima da média da semana passada.",
    "Postagens com sorriso autêntico têm +40% de curtidas!",
    "Evite fundos confusos — destaque-se da imagem.",
    "Excelente escolha de enquadramento.",
    "Evite frases polêmicas nas legendas.",
    "Você está entre os 5% mais atrativos do portal!",
    "Atenção: fotos com muita sombra reduzem visibilidade.",
    "Seu tom de pele está sendo bem captado pela iluminação.",
    "Evite imagens com objetos de fundo distrativos.",
    "Tente ângulos mais altos para transmitir confiança.",
    "A cor azul nas roupas aumenta 12% de credibilidade.",
    "Faltou foco na imagem — tente refazer a captura.",
    "Excelente! Seu conteúdo gera empatia e conexão.",
    "Evite fotos com pessoas ao fundo fazendo gestos.",
    "Tente variar expressões para evitar monotonia visual.",
    "Seu estilo está em alta — mantenha consistência!"
  ];

  function trendLabel(arr) {
    if (arr.length < 6) return "Estável";
    const last3 = arr.slice(-3).reduce((a,b)=>a+b,0)/3;
    const prev3 = arr.slice(-6,-3).reduce((a,b)=>a+b,0)/3;
    const diff = last3 - prev3;
    if (diff > 3) return "Crescendo";
    if (diff < -3) return "Caindo";
    return "Estável";
  }

  function drawThermo(pct) {
    const bar = $("#sb-rai-thermo .thermo-bar");
    const label = $("#sb-rai-thermo .thermo-pct");
    if (!bar || !label) return;
    bar.style.width = Math.max(0, Math.min(100, Math.round(pct))) + "%";
    label.textContent = Math.round(pct) + "%";
  }

  function renderDonut(remaining, consumed) {
    const el = $("#sb-donut");
    if (!el) return;
    const total = Math.max(1, remaining + consumed);
    const r = 48, c = 2*Math.PI*r;
    const remPct = remaining/total;
    const consPct = consumed/total;
    const remLen = c*remPct, consLen = c*consPct;

    el.innerHTML = `
      <svg width="140" height="140" viewBox="0 0 140 140">
        <g transform="translate(70,70) rotate(-90)">
          <circle r="${r}" cx="0" cy="0" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="16"/>
          <circle r="${r}" cx="0" cy="0" fill="none" stroke="#3CAEFF" stroke-dasharray="${consLen} ${c-consLen}" stroke-width="16" />
          <circle r="${r}" cx="0" cy="0" fill="none" stroke="#1F80FF" stroke-dasharray="${remLen} ${c-remLen}" stroke-dashoffset="${-consLen}" stroke-width="16" />
        </g>
        <text x="70" y="70" text-anchor="middle" dy="6" fill="#A8D8FF" font-size="14">${remaining} restantes</text>
      </svg>
    `;
  }

  async function loadSidebarData() {
    try {
      const [profRes, credRes] = await Promise.all([
        fetch("/user/profile", { headers: authHeaders() }),
        fetch("/credits_status", { headers: authHeaders() })
      ]);
      const prof = await profRes.json();
      const cred = await credRes.json();

      // Crédits chip
      const sbChip = $("#sb-credits-chip");
      if (sbChip && cred?.ok) {
        const u = cred.data?.user;
        const s = cred.data?.session;
        sbChip.textContent = `Créditos: ${typeof u === "number" ? u : s ?? "—"}`;
      }

      if (!prof?.ok) return;
      const hist = Array.isArray(prof.data?.history) ? prof.data.history : [];

      // 1) Raipômetro a partir das últimas 10 análises de foto
      const photos = hist.filter(h => h.type === "photo");
      const last10 = photos.slice(0,10);
      const impactSeries = last10.map(x => 100 - (x.score_risk ?? 50)); // impacto ~ inverso do risco
      const media = impactSeries.length ? Math.round(impactSeries.reduce((a,b)=>a+b,0)/impactSeries.length) : 0;
      drawThermo(media);
      const trend = trendLabel(impactSeries.slice().reverse()); // ordem cronológica
      const mediaEl = $("#sb-rai-media"); const trendEl = $("#sb-rai-trend");
      if (mediaEl) mediaEl.textContent = media ? media + "/100" : "—";
      if (trendEl) trendEl.textContent = trend;
      const msg = motivMessages[Math.floor(Math.random()*motivMessages.length)];
      const msgEl = $("#sb-rai-msg"); if (msgEl) msgEl.textContent = msg;

      // 3) Últimas análises (5)
      const lastList = $("#sb-last-list");
      if (lastList) {
        lastList.innerHTML = "";
        hist.slice(0,5).forEach((h) => {
          const li = document.createElement("li");
          li.className = "sb-item";
          const label = h.score_risk <= 33 ? "Positiva" : (h.score_risk >= 67 ? "Risco" : "Neutra");
          li.innerHTML = `
            <div class="sb-thumb">${h.type === "photo" ? "📷" : "📝"}</div>
            <div class="sb-meta">
              <strong>${label}</strong>
              <small>${new Date(h.created_at).toLocaleString()}</small>
            </div>
            <div style="margin-left:auto" class="sb-chip">${h.score_risk ?? "—"}/100</div>
          `;
          lastList.appendChild(li);
        });
      }

      // 4) Histórico (contagem)
      const histCount = $("#sb-hist-count");
      if (histCount) histCount.textContent = `Total de análises realizadas: ${hist.length}`;

      // 5) Créditos & atividade — donut simples
      let remaining = 0;
      if (cred?.ok) {
        remaining = typeof cred.data?.user === "number" ? cred.data.user : (cred.data?.session ?? 0);
      }
      // Consumo estimado: quantidade de análises do usuário nos últimos 60 dias (1 crédito p/ análise)
      const cutoff = Date.now() - 60*24*60*60*1000;
      const consumed = hist.filter(h => new Date(h.created_at).getTime() >= cutoff).length;
      renderDonut(remaining, consumed);

      const msgs = [
        "Você está utilizando bem seus créditos — parabéns!",
        "Créditos baixos: recarregue e continue analisando suas fotos!",
        "Usuários ativos mantêm imagem mais profissional!",
        "Seus créditos rendem melhor com fotos de alta qualidade.",
        "Recarregue agora e desbloqueie relatórios detalhados!"
      ];
      const msgUl = $("#sb-credits-msgs");
      if (msgUl) { msgUl.innerHTML = msgs.map(m => `<li>• ${m}</li>`).join(""); }

    } catch (e) {
      // Falha silenciosa para não travar UI
    }
  }

  function openSidebar() {
    if (!elSidebar || !elSidebarOverlay) return;
    elSidebar.classList.add("show");
    elSidebar.setAttribute("aria-hidden", "false");
    elSidebarOverlay.classList.add("show");
    elSidebarOverlay.setAttribute("aria-hidden", "false");
    loadSidebarData();
  }
  function closeSidebar() {
    if (!elSidebar || !elSidebarOverlay) return;
    elSidebar.classList.remove("show");
    elSidebar.setAttribute("aria-hidden", "true");
    elSidebarOverlay.classList.remove("show");
    elSidebarOverlay.setAttribute("aria-hidden", "true");
  }

  elSidebarToggle?.addEventListener("click", () => {
    if (!elSidebar) return;
    if (elSidebar.classList.contains("show")) closeSidebar();
    else openSidebar();
  });
  elSidebarClose?.addEventListener("click", closeSidebar);
  elSidebarOverlay?.addEventListener("click", closeSidebar);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSidebar(); });

  // Botão “+ Nova Análise” (abre o input de foto existente)
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("#sb-new-analysis");
    if (btn && elBtnPhoto) {
      closeSidebar();
      elBtnPhoto.click();
    }
  });

  // -----------------------------
  // Boot
  // -----------------------------
  document.addEventListener("DOMContentLoaded", () => {
    elFeedback = pickMainFeedback();
    updateAuthUI();
    updateCreditsLabel();
  });
})();
