/* INFLUE — Controller (mobile-first)
 * Objetivo desta etapa:
 * - Usuário usa 3 créditos de SESSÃO sem barreira de login.
 * - Abrir modal de login SOMENTE quando os créditos acabarem
 *   (ou quando o usuário tentar comprar créditos).
 * - Botões do modal funcionam (Fechar, Entrar, Criar conta).
 * - Fluxo de análise foto/texto funcional com consumo de crédito.
 * - Compra mock funcional (exige login).
 */

(function () {
  "use strict";

  // -----------------------------
  // Shortcuts / elementos
  // -----------------------------
  const $ = (sel) => document.querySelector(sel);

  // Rodapé
  const elYear = $("#year");

  // Header (estado e créditos)
  const elCredits = $("#credits-left");
  const elBtnOpenAuth = $("#btn-open-auth");
  const elBtnLogout = $("#btn-logout");
  const elBtnPurchase = $("#btn-purchase");
  const elUserLabel = $("#user-label");
  const elUserState = $("#user-state");

  // Modal (campos e botões)
  const elAuthEmail = $("#auth-email");
  const elAuthPassword = $("#auth-password");
  const elBtnLogin = $("#btn-login");
  const elBtnRegister = $("#btn-register");

  // Home / análise
  const elFeedback = $("#feedback");
  const elInputPhoto = $("#photo-input");
  const elBtnPhoto = $("#btn-photo");
  const elTextarea = $("#textcontent");
  const elBtnSubmitText = $("#btn-submit-text");

  // Saída de análise
  const elOut = $("#analysis-output");
  const elOutSummary = $("#analysis-summary");
  const elOutScore = $("#analysis-score");
  const elOutTags = $("#analysis-tags");
  const elOutRecs = $("#analysis-recs");

  // Modal controls expostos pelo base.html
  const showAuth = window.__influe_show_auth__ || (() => {});
  const hideAuth = window.__influe_hide_auth__ || (() => {});

  // -----------------------------
  // Utilidades
  // -----------------------------
  if (elYear) elYear.textContent = new Date().getFullYear();

  function setFeedback(msg) {
    if (elFeedback) elFeedback.textContent = msg || "";
  }

  function showAnalysis(analysis) {
    const score =
      typeof analysis.score_risk === "number" ? analysis.score_risk : "—";
    const tags = Array.isArray(analysis.tags)
      ? analysis.tags.join(", ")
      : "—";
    const recs = Array.isArray(analysis.recommendations)
      ? analysis.recommendations
      : [];

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
  // Auth helpers (token)
  // -----------------------------
  function getToken() {
    return localStorage.getItem("influe_token") || null;
  }
  function setToken(token) {
    if (token) localStorage.setItem("influe_token", token);
  }
  function clearToken() {
    localStorage.removeItem("influe_token");
  }
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
  // Créditos (status) + Gate
  // -----------------------------
  async function updateCreditsLabel() {
    try {
      const res = await fetch("/credits_status", { headers: authHeaders() });
      const json = await res.json();
      if (!json?.ok) return;
      const data = json.data || {};
      const s = data.session ?? "—";
      const u = data.user ?? "—";
      if (elCredits) elCredits.textContent = `Sessão: ${s} | Usuário: ${u}`;
    } catch (_) {
      // silencioso
    }
  }

  async function requireLoginIfNoCredits() {
    // Pergunta ao backend se precisamos de login (quando for comprar ou sem créditos)
    try {
      const res = await fetch("/gate/login", { headers: authHeaders() });
      const json = await res.json();
      if (json?.ok && json.require_login) {
        showAuth();
        return true;
      }
    } catch (_) {}
    return false;
  }

  // -----------------------------
  // Login / Registro (modal)
  // -----------------------------
  async function loginOrRegister(isRegister = false) {
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

      if (json.ok && json.token) {
        setToken(json.token);
        hideAuth();
        setFeedback(isRegister ? "Conta criada com sucesso." : "Login efetuado.");
        updateAuthUI();
        await updateCreditsLabel();
      } else {
        setFeedback(json.error || "Falha na autenticação.");
      }
    } catch (_) {
      setFeedback("Erro de rede.");
    }
  }

 elBtnLogin?.addEventListener("click", (e) => {
  e.preventDefault();
  loginOrRegister(false);
});

elBtnRegister?.addEventListener("click", (e) => {
  e.preventDefault();
  loginOrRegister(true);
});

elBtnLogout?.addEventListener("click", (e) => {
  e.preventDefault();
  clearToken();
  updateAuthUI();
  updateCreditsLabel();
});

  // -----------------------------
  // Compra (mock) — abre login se necessário
  // -----------------------------
  elBtnPurchase?.addEventListener("click", async () => {
    // Se não há token, pede login
    if (!getToken()) {
      showAuth();
      return;
    }
    setFeedback("Processando compra...");
    try {
      const res = await fetch("/purchase", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ package: 10 }),
      });
      // 401 => precisa logar
      if (res.status === 401) {
        showAuth();
        return;
      }
      const json = await res.json();
      if (json.ok) {
        setFeedback("Créditos adicionados (mock).");
        await updateCreditsLabel();
      } else {
        setFeedback(json.error || "Falha na compra.");
      }
    } catch (_) {
      setFeedback("Erro de rede.");
    }
  });

  // -----------------------------
  // Compressão de imagem (canvas)
  // -----------------------------
  // Polyfill de toBlob
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
      const blob = await new Promise((resolve) =>
        canvas.toBlob((b) => resolve(b), "image/jpeg", quality)
      );
      if (!blob) return file;
      const name = file.name?.replace(/\.(png|jpeg|jpg|heic)$/i, "") || "image";
      return new File([blob], `${name}.jpg`, { type: "image/jpeg" });
    } catch {
      return file;
    }
  }

  // -----------------------------
  // Envio: /analyze_photo
  // - Não abre login no início
  // - Se acabar crédito, então abre modal
  // -----------------------------
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
      const res = await fetch("/analyze_photo", {
        method: "POST",
        headers: authHeaders(),
        body: fd,
      });

      // 402 => sem créditos
      if (res.status === 402) {
        await updateCreditsLabel();
        // Pergunta ao backend se precisamos exigir login (créditos acabaram)
        const gated = await requireLoginIfNoCredits();
        if (!gated) setFeedback("Sem créditos disponíveis.");
        return;
      }

      const json = await res.json();
      if (json.ok) {
        showAnalysis(json.analysis);
        setFeedback("Análise concluída.");
      } else {
        setFeedback(json.error || "Falha na análise da foto.");
      }
    } catch (_) {
      setFeedback("Erro de rede ao enviar foto.");
    } finally {
      if (elInputPhoto) elInputPhoto.value = "";
      await updateCreditsLabel();
    }
  });

  // -----------------------------
  // Envio: /analyze_text
  // - Mesmo comportamento do de foto
  // -----------------------------
  elBtnSubmitText?.addEventListener("click", async () => {
    const text = (elTextarea?.value || "").trim();
    if (!text) {
      setFeedback("Digite um texto para analisar.");
      return;
    }

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
      if (json.ok) {
        showAnalysis(json.analysis);
        setFeedback("Análise concluída.");
      } else {
        setFeedback(json.error || "Falha na análise do texto.");
      }
    } catch (_) {
      setFeedback("Erro de rede ao enviar texto.");
    } finally {
      await updateCreditsLabel();
    }
  });

  // -----------------------------
  // UX: Botão “Enviar texto/legenda” foca textarea (sem abrir modal)
  // -----------------------------
  $("#btn-text")?.addEventListener("click", () => elTextarea?.focus());

  // -----------------------------
  // Boot
  // -----------------------------
  document.addEventListener("DOMContentLoaded", () => {
    updateAuthUI();
    updateCreditsLabel();
  });
})();
