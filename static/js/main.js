/* INFLUE — Controller (mobile-first)
 * Versão focada em: login/registro funcionando SEM travar a UI.
 * - Liga listeners após DOM pronto (robusto).
 * - Previne submit/reload.
 * - Exibe feedback no card e no console para diagnóstico.
 * - Mantém todo o resto (análise, créditos, compra mock).
 */

(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  // ---------- Estado/seletores ----------
  let elYear, elCredits, elBtnOpenAuth, elBtnLogout, elBtnPurchase, elUserLabel, elUserState;
  let elAuthEmail, elAuthPassword, elBtnLogin, elBtnRegister, elFeedback;
  let elInputPhoto, elBtnPhoto, elTextarea, elBtnSubmitText;
  let elOut, elOutSummary, elOutScore, elOutTags, elOutRecs;

  const showAuth = () => window.__influe_show_auth__?.();
  const hideAuth = () => window.__influe_hide_auth__?.();

  // ---------- Util ----------
  function setFeedback(msg) {
    if (elFeedback) elFeedback.textContent = msg || "";
    console.log("[INFLUE]", msg);
  }
  function getToken() { return localStorage.getItem("influe_token") || null; }
  function setToken(t) { if (t) localStorage.setItem("influe_token", t); }
  function clearToken() { localStorage.removeItem("influe_token"); }
  function authHeaders() { const t = getToken(); return t ? { Authorization: "Bearer " + t } : {}; }

  function setUserState(label, color = "#6aa8ff") {
    if (elUserLabel) elUserLabel.textContent = label;
    const circle = elUserState?.querySelector("circle");
    if (circle) circle.setAttribute("fill", color);
  }

  function updateAuthUI() {
    const logged = !!getToken();
    if (elBtnOpenAuth) elBtnOpenAuth.style.display = logged ? "none" : "";
    if (elBtnLogout) elBtnLogout.style.display = logged ? "" : "none";
    if (logged) setUserState("Logado", "#00e676"); else setUserState("Convidado", "#6aa8ff");
  }

  async function updateCreditsLabel() {
    try {
      const res = await fetch("/credits_status", { headers: authHeaders() });
      const json = await res.json();
      if (!json?.ok) return;
      const s = json.data?.session ?? "—";
      const u = json.data?.user ?? "—";
      if (elCredits) elCredits.textContent = `Sessão: ${s} | Usuário: ${u}`;
    } catch {}
  }

  async function requireLoginIfNoCredits() {
    try {
      const res = await fetch("/gate/login", { headers: authHeaders() });
      const json = await res.json();
      if (json?.ok && json.require_login) {
        showAuth();
        return true;
      }
    } catch {}
    return false;
  }

  // ---------- Auth ----------
  async function loginOrRegister(isRegister) {
    const email = (elAuthEmail?.value || "").trim().toLowerCase();
    const password = elAuthPassword?.value || "";
    if (!email || !password) {
      setFeedback("Informe e-mail e senha.");
      return;
    }
    const url = isRegister ? "/auth/register" : "/auth/login";
    setFeedback(isRegister ? "Criando conta..." : "Entrando...");

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const json = await res.json();
      console.log("[INFLUE] Auth response:", json);

      if (json.ok && json.token) {
        setToken(json.token);
        hideAuth();
        setFeedback(isRegister ? "Conta criada com sucesso." : "Login efetuado.");
        updateAuthUI();
        await updateCreditsLabel();
      } else {
        setFeedback(json.error || "Falha na autenticação.");
      }
    } catch (e) {
      console.error(e);
      setFeedback("Erro de rede.");
    }
  }

  function bindAuthEvents() {
    // Evita que Enter em inputs tente submeter algo inexistente
    const stop = (e) => { if (e) e.preventDefault(); };
    elBtnLogin?.addEventListener("click", (e) => { stop(e); loginOrRegister(false); });
    elBtnRegister?.addEventListener("click", (e) => { stop(e); loginOrRegister(true); });

    // Enter para enviar (no foco dos campos)
    elAuthEmail?.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); loginOrRegister(false); }});
    elAuthPassword?.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); loginOrRegister(false); }});

    elBtnLogout?.addEventListener("click", (e) => {
      e?.preventDefault();
      clearToken();
      updateAuthUI();
      updateCreditsLabel();
      setFeedback("");
    });

    // Abrir o modal manualmente pelo botão do topo
    elBtnOpenAuth?.addEventListener("click", (e) => { e?.preventDefault(); showAuth(); });
  }

  // ---------- Compra (mock) ----------
  function bindPurchase() {
    elBtnPurchase?.addEventListener("click", async () => {
      if (!getToken()) { showAuth(); return; }
      setFeedback("Processando compra...");
      try {
        const res = await fetch("/purchase", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ package: 10 }),
        });
        if (res.status === 401) { showAuth(); return; }
        const json = await res.json();
        if (json.ok) {
          setFeedback("Créditos adicionados (mock).");
          await updateCreditsLabel();
        } else {
          setFeedback(json.error || "Falha na compra.");
        }
      } catch { setFeedback("Erro de rede."); }
    });
  }

  // ---------- Análise ----------
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

  // Polyfill toBlob
  if (!HTMLCanvasElement.prototype.toBlob) {
    HTMLCanvasElement.prototype.toBlob = function (callback, type, quality) {
      const dataURL = this.toDataURL(type, quality).split(",")[1];
      const binStr = atob(dataURL);
      const len = binStr.length;
      const arr = new Uint8Array(len);
      for (let i = 0; i < len; i++) arr[i] = binStr.charCodeAt(i);
      callback(new Blob([arr], { type: type || "image/jpeg" }));
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
      const blob = await new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/jpeg", quality));
      if (!blob) return file;
      const name = file.name?.replace(/\.(png|jpeg|jpg|heic)$/i, "") || "image";
      return new File([blob], `${name}.jpg`, { type: "image/jpeg" });
    } catch { return file; }
  }

  function bindAnalyze() {
    $("#btn-text")?.addEventListener("click", () => elTextarea?.focus());

    elBtnPhoto?.addEventListener("click", () => elInputPhoto?.click());

    elInputPhoto?.addEventListener("change", async () => {
      if (!elInputPhoto.files || !elInputPhoto.files[0]) return;

      setFeedback("Compactando imagem...");
      const original = elInputPhoto.files[0];
      const compressed = await compressImage(original, 1920, 1920, 0.7);

      const fd = new FormData();
      fd.append("photo", compressed, compressed.name);

      setFeedback("Enviando para análise...");
      try {
        const res = await fetch("/analyze_photo", { method: "POST", headers: authHeaders(), body: fd });

        if (res.status === 402) {
          await updateCreditsLabel();
          const gated = await requireLoginIfNoCredits();
          if (!gated) setFeedback("Sem créditos disponíveis.");
          return;
        }

        const json = await res.json();
        if (json.ok) { showAnalysis(json.analysis); setFeedback("Análise concluída."); }
        else { setFeedback(json.error || "Falha na análise da foto."); }
      } catch { setFeedback("Erro de rede ao enviar foto."); }
      finally {
        if (elInputPhoto) elInputPhoto.value = "";
        await updateCreditsLabel();
      }
    });

    elBtnSubmitText?.addEventListener("click", async () => {
      const text = (elTextarea?.value || "").trim();
      if (!text) { setFeedback("Digite um texto para analisar."); return; }

      setFeedback("Analisando texto...");
      try {
        const res = await fetch("/analyze_text", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ text }),
        });

        if (res.status === 402) {
          await updateCreditsLabel();
          const gated = await requireLoginIfNoCredits();
          if (!gated) setFeedback("Sem créditos disponíveis.");
          return;
        }

        const json = await res.json();
        if (json.ok) { showAnalysis(json.analysis); setFeedback("Análise concluída."); }
        else { setFeedback(json.error || "Falha na análise do texto."); }
      } catch { setFeedback("Erro de rede ao enviar texto."); }
      finally { await updateCreditsLabel(); }
    });
  }

  // ---------- Boot ----------
  function cacheElements() {
    elYear = $("#year");
    elCredits = $("#credits-left");
    elBtnOpenAuth = $("#btn-open-auth");
    elBtnLogout = $("#btn-logout");
    elBtnPurchase = $("#btn-purchase");
    elUserLabel = $("#user-label");
    elUserState = $("#user-state");

    elAuthEmail = $("#auth-email");
    elAuthPassword = $("#auth-password");
    elBtnLogin = $("#btn-login");
    elBtnRegister = $("#btn-register");

    // ⚠️ Há dois #feedback (um no modal, outro na página). O primeiro no DOM será usado.
    // Para este momento, esse comportamento é suficiente.
    elFeedback = $("#feedback");

    elInputPhoto = $("#photo-input");
    elBtnPhoto = $("#btn-photo");
    elTextarea = $("#textcontent");
    elBtnSubmitText = $("#btn-submit-text");

    elOut = $("#analysis-output");
    elOutSummary = $("#analysis-summary");
    elOutScore = $("#analysis-score");
    elOutTags = $("#analysis-tags");
    elOutRecs = $("#analysis-recs");

    if (elYear) elYear.textContent = new Date().getFullYear();
  }

  function start() {
    cacheElements();
    bindAuthEvents();
    bindPurchase();
    bindAnalyze();
    updateAuthUI();
    updateCreditsLabel();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    // Em teoria, como o script tem defer, o DOM já estará pronto.
    start();
  }
})();
