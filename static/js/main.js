/* INFLUE — Controller (mobile-first)
 * Objetivo:
 * - Home sempre acessível.
 * - Modal de autenticação com modos: Entrar / Criar conta (com confirmações).
 * - 3 créditos de SESSÃO sem barreira; exigir login só ao esgotar ou ao comprar.
 * - Botões do modal: Entrar e Criar conta funcionais.
 * - Fluxo de análise (foto/texto), consumo de crédito e compra (mock).
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

  // Modal (campos e botões — ENTRAR)
  const elAuthEmail = $("#auth-email");
  const elAuthPassword = $("#auth-password");
  const formLogin = $("#form-login");
  const elBtnLogin = $("#btn-login");

  // Modal (campos e botões — CRIAR CONTA)
  const formSignup = $("#form-signup");
  const elRegEmail = $("#reg-email");
  const elRegEmail2 = $("#reg-email2");
  const elRegPass = $("#reg-pass");
  const elRegPass2 = $("#reg-pass2");
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

  // Modal controls fornecidos por base.html
  const showAuth = window.__influe_show_auth__ || (() => {});
  const hideAuth = window.__influe_hide_auth__ || (() => {});
  const setAuthTab = window.__influe_set_auth_tab__ || (() => {});

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

      // ===== alteração cirúrgica: exibir Sessão como x/3 usando free_credits =====
      const free = typeof data.free_credits === "number" ? data.free_credits : 3;
      const sText =
        typeof s === "number" ? `${s}/${free}` : "—";
      const uText =
        typeof u === "number" ? String(u) : "—";

      if (elCredits) elCredits.textContent = `Sessão: ${sText} | Usuário: ${uText}`;
    } catch (_) {
      // silencioso
    }
  }

  // Retorna objeto para o chamador decidir mensagens/ações.
  async function checkGateForCredits() {
    try {
      const res = await fetch("/gate/login", { headers: authHeaders() });
      const json = await res.json();
      if (!json?.ok) return { gated: false, need_purchase: false, logged_in: false };

      // ===== alteração cirúrgica: tratar need_purchase para logado sem créditos =====
      if (json.require_login) {
        return { gated: true, need_purchase: false, logged_in: !!json.logged_in };
      }
      if (json.need_purchase) {
        return { gated: false, need_purchase: true, logged_in: true };
      }
      return { gated: false, need_purchase: false, logged_in: !!json.logged_in };
    } catch (_) {
      return { gated: false, need_purchase: false, logged_in: false };
    }
  }

  async function requireLoginIfNoCredits() {
    const res = await checkGateForCredits();
    if (res.gated) {
      setAuthTab('login');
      showAuth();
      return true;
    }
    if (res.need_purchase) {
      setFeedback("Você está logado, mas sem créditos. Clique em “Comprar créditos”.");
    }
    return false;
  }

  // -----------------------------
  // Validações simples
  // -----------------------------
  function isValidEmail(v) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
  }

  // -----------------------------
  // Login / Registro (modal)
  // -----------------------------
  async function doLogin(email, password) {
    setFeedback("Entrando...");
    try {
      const res = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const json = await res.json();
      if (json.ok && json.token) {
        setToken(json.token);
        hideAuth();
        setFeedback("Login efetuado.");
        updateAuthUI();
        await updateCreditsLabel();
      } else {
        setFeedback(json.error || "Falha na autenticação.");
      }
    } catch (_) {
      setFeedback("Erro de rede.");
    }
  }

  async function doRegister(email, password) {
    setFeedback("Criando conta...");
    try {
      const res = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const json = await res.json();
      if (json.ok && json.token) {
        // Após criar conta: já tratar como logado.
        setToken(json.token);
        setFeedback("Conta criada com sucesso.");
        hideAuth();
        updateAuthUI();
        await updateCreditsLabel();
      } else {
        setFeedback(json.error || "Falha ao criar conta.");
      }
    } catch (_) {
      setFeedback("Erro de rede.");
    }
  }

  // ENTRAR: submit
  formLogin?.addEventListener("submit", (e) => {
    e.preventDefault();
    const email = (elAuthEmail?.value || "").trim().toLowerCase();
    const password = elAuthPassword?.value || "";
    if (!email || !password) {
      setFeedback("Informe e-mail e senha.");
      return;
    }
    if (!isValidEmail(email)) {
      setFeedback("E-mail inválido.");
      return;
    }
    doLogin(email, password);
  });

  // CRIAR CONTA: submit (com confirmações)
  formSignup?.addEventListener("submit", (e) => {
    e.preventDefault();

    const email  = (elRegEmail?.value || "").trim().toLowerCase();
    const email2 = (elRegEmail2?.value || "").trim().toLowerCase();
    const pass   = elRegPass?.value || "";
    const pass2  = (elRegPass2?.value || "");

    if (!email || !email2 || !pass || !pass2) {
      setFeedback("Preencha todos os campos.");
      return;
    }
    if (!isValidEmail(email)) {
      setFeedback("E-mail inválido.");
      return;
    }
    if (email !== email2) {
      setFeedback("Os e-mails não conferem.");
      return;
    }
    if (pass.length < 6) {
      setFeedback("Senha muito curta (mín. 6).");
      return;
    }
    if (pass !== pass2) {
      setFeedback("As senhas não conferem.");
      return;
    }
    doRegister(email, pass);
  });

  // Logout
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
    if (!getToken()) {
      setAuthTab('login');
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
      if (res.status === 401) {
        setAuthTab('login');
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
  // Compressão de imagem (canvas) — igual
  // -----------------------------
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

      if (res.status === 402) {
        await updateCreditsLabel();
        const gated = await requireLoginIfNoCredits(); // respeita need_purchase
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
        const gated = await requireLoginIfNoCredits(); // respeita need_purchase
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
  // Boot
  // -----------------------------
  document.addEventListener("DOMContentLoaded", () => {
    updateAuthUI();
    updateCreditsLabel();
  });
})();
