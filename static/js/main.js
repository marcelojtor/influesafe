/* INFLUE — Frontend Controller (mobile-first)
 * Etapa 2: Auth + Compra Mock + Créditos Dinâmicos
 */

(function () {
  "use strict";

  // -----------------------------
  // Utilidades e seletores
  // -----------------------------
  const $ = (sel) => document.querySelector(sel);
  const elYear = $("#year");
  const elFeedback = $("#feedback");
  const elCredits = $("#credits-left");
  const elOut = $("#analysis-output");
  const elOutSummary = $("#analysis-summary");
  const elOutScore = $("#analysis-score");
  const elOutTags = $("#analysis-tags");
  const elOutRecs = $("#analysis-recs");

  const elInputPhoto = $("#photo-input");
  const elBtnPhoto = $("#btn-photo");
  const elTextarea = $("#textcontent");
  const elBtnSubmitText = $("#btn-submit-text");

  const elBtnLogin = $("#btn-login");
  const elBtnRegister = $("#btn-register");
  const elBtnLogout = $("#btn-logout");
  const elBtnPurchase = $("#btn-purchase");

  const elUserLabel = $("#user-label");
  const elUserState = $("#user-state");

  // Atualiza ano
  if (elYear) elYear.textContent = new Date().getFullYear();

  // -----------------------------
  // Persistência e auth
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
    const token = getToken();
    return token ? { Authorization: "Bearer " + token } : {};
  }

  function setUserState(label, color = "#6aa8ff") {
    if (elUserLabel) elUserLabel.textContent = label;
    if (elUserState) {
      const circle = elUserState.querySelector("circle");
      if (circle) circle.setAttribute("fill", color);
    }
  }

  function updateAuthUI() {
    const token = getToken();
    const logged = !!token;
    $("#btn-open-auth").style.display = logged ? "none" : "";
    elBtnLogout.style.display = logged ? "" : "none";
    if (logged) setUserState("Logado", "#00e676");
    else setUserState("Convidado", "#6aa8ff");
  }

  elBtnLogout?.addEventListener("click", () => {
    clearToken();
    updateAuthUI();
    updateCreditsLabel();
  });

  // -----------------------------
  // Funções auxiliares
  // -----------------------------
  function setFeedback(msg) {
    if (elFeedback) elFeedback.textContent = msg || "";
  }

  function showAnalysis(analysis) {
    const score = typeof analysis.score_risk === "number" ? analysis.score_risk : "—";
    const tags = Array.isArray(analysis.tags) ? analysis.tags.join(", ") : "—";
    const recs = Array.isArray(analysis.recommendations) ? analysis.recommendations : [];

    elOutSummary.textContent = analysis.summary || "Análise concluída.";
    elOutScore.textContent = String(score);
    elOutTags.textContent = tags;

    elOutRecs.innerHTML = "";
    recs.slice(0, 3).forEach((r) => {
      const li = document.createElement("li");
      li.textContent = r;
      elOutRecs.appendChild(li);
    });

    elOut.style.display = "block";
  }

  async function updateCreditsLabel() {
    try {
      const res = await fetch("/credits_status", {
        headers: authHeaders(),
      });
      const json = await res.json();
      if (!json.ok) return;
      const data = json.data || {};
      const s = data.session ?? "—";
      const u = data.user ?? "—";
      if (elCredits) elCredits.textContent = `Sessão: ${s} | Usuário: ${u}`;
    } catch (_) {}
  }

  // -----------------------------
  // Compressão básica de imagem
  // -----------------------------
  async function compressImage(file, maxW = 1920, maxH = 1920, quality = 0.7) {
    const img = await loadImage(file);
    const ratio = Math.min(maxW / img.width, maxH / img.height, 1);
    const canvas = document.createElement("canvas");
    canvas.width = img.width * ratio;
    canvas.height = img.height * ratio;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) =>
      canvas.toBlob(
        (b) => resolve(new File([b], file.name, { type: "image/jpeg" })),
        "image/jpeg",
        quality
      )
    );
  }

  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  // -----------------------------
  // Envio de imagem
  // -----------------------------
  elBtnPhoto?.addEventListener("click", () => elInputPhoto.click());
  elInputPhoto?.addEventListener("change", async () => {
    if (!elInputPhoto.files || !elInputPhoto.files[0]) return;
    const original = elInputPhoto.files[0];
    setFeedback("Compactando imagem...");
    const compressed = await compressImage(original);
    const fd = new FormData();
    fd.append("photo", compressed);

    setFeedback("Enviando para análise...");
    try {
      const res = await fetch("/analyze_photo", {
        method: "POST",
        headers: authHeaders(),
        body: fd,
      });
      const json = await res.json();
      if (json.ok) {
        showAnalysis(json.analysis);
        setFeedback("Análise concluída.");
      } else {
        setFeedback(json.error || "Falha na análise.");
      }
    } catch {
      setFeedback("Erro de rede.");
    }
    updateCreditsLabel();
  });

  // -----------------------------
  // Envio de texto
  // -----------------------------
  elBtnSubmitText?.addEventListener("click", async () => {
    const text = (elTextarea.value || "").trim();
    if (!text) return setFeedback("Digite um texto primeiro.");
    setFeedback("Analisando texto...");
    try {
      const res = await fetch("/analyze_text", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify({ text }),
      });
      const json = await res.json();
      if (json.ok) {
        showAnalysis(json.analysis);
        setFeedback("Análise concluída.");
      } else setFeedback(json.error || "Falha na análise.");
    } catch {
      setFeedback("Erro de rede.");
    }
    updateCreditsLabel();
  });

  // -----------------------------
  // Login e Registro
  // -----------------------------
  async function loginOrRegister(isRegister = false) {
    const email = $("#auth-email").value.trim().toLowerCase();
    const password = $("#auth-password").value;
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
        setFeedback(isRegister ? "Conta criada!" : "Login bem-sucedido!");
        $("#auth-modal")?.classList.remove("show");
        $("#auth-backdrop")?.classList.remove("show");
        updateAuthUI();
        updateCreditsLabel();
      } else {
        setFeedback(json.error || "Falha na autenticação.");
      }
    } catch {
      setFeedback("Erro de rede.");
    }
  }

  elBtnLogin?.addEventListener("click", () => loginOrRegister(false));
  elBtnRegister?.addEventListener("click", () => loginOrRegister(true));

  // -----------------------------
  // Compra mock
  // -----------------------------
  elBtnPurchase?.addEventListener("click", async () => {
    setFeedback("Solicitando compra...");
    try {
      const res = await fetch("/purchase", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify({ package: 10 }),
      });
      const json = await res.json();
      if (json.ok) {
        setFeedback("Créditos adicionados (mock).");
        updateCreditsLabel();
      } else {
        setFeedback(json.error || "Falha na compra.");
      }
    } catch {
      setFeedback("Erro de rede.");
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
