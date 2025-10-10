/* INFLUE — Frontend Controller (mobile-first)
 * - Compressão de imagem (canvas -> JPEG q=0.7)
 * - Chamadas aos endpoints: /analyze_photo e /analyze_text
 * - Exibição do resultado (score/tags/recomendações)
 * - Atualização do contador de créditos via /credits_status
 */

(function () {
  "use strict";

  // -----------------------------
  // Utilidades
  // -----------------------------
  const $ = (sel) => document.querySelector(sel);

  const elYear = $("#year");
  const elFeedback = $("#feedback");
  const elCredits = $("#credits-left");

  const elBtnPhoto = $("#btn-photo");
  const elInputPhoto = $("#photo-input");
  const elFormPhoto = $("#form-photo");

  const elBtnText = $("#btn-text");
  const elFormText = $("#form-text");
  const elTextarea = $("#textcontent");
  const elBtnSubmitText = $("#btn-submit-text");

  const elOut = $("#analysis-output");
  const elOutSummary = $("#analysis-summary");
  const elOutScore = $("#analysis-score");
  const elOutTags = $("#analysis-tags");
  const elOutRecs = $("#analysis-recs");

  // Atualiza ano do rodapé
  if (elYear) elYear.textContent = new Date().getFullYear();

  function setFeedback(msg) {
    if (!elFeedback) return;
    elFeedback.textContent = msg || "";
  }

  function showAnalysis(analysis) {
    if (!elOut) return;
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

    elOut.style.display = "block";
  }

  async function updateCreditsLabel() {
    try {
      const res = await fetch("/credits_status", { method: "GET" });
      const json = await res.json();
      if (!json || !json.ok) return;

      const data = json.data || {};
      const s = (data.session ?? "—");
      const u = (data.user ?? "—");

      if (elCredits) {
        // Exibe de forma clara: Sessão | Usuário
        elCredits.textContent = `Sessão: ${s} | Usuário: ${u}`;
        elCredits.dataset.credits = String(s);
      }
    } catch (_) {
      // silencioso: não quebra UX
    }
  }

  // -----------------------------
  // Compressão de imagem (canvas)
  // -----------------------------
  // Polyfill minimalista de toBlob para navegadores antigos
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

      // Calcula dimensões mantendo proporção
      let { width, height } = img;
      const ratio = Math.min(maxW / width, maxH / height, 1); // não aumenta
      const targetW = Math.max(1, Math.round(width * ratio));
      const targetH = Math.max(1, Math.round(height * ratio));

      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      canvas.width = targetW;
      canvas.height = targetH;
      ctx.drawImage(img, 0, 0, targetW, targetH);

      const blob = await new Promise((resolve) =>
        canvas.toBlob((b) => resolve(b), "image/jpeg", quality)
      );

      // Se falhou, retorna o original
      if (!blob) return file;

      const compressedFile = new File([blob], renameToJpeg(file.name), { type: "image/jpeg" });
      return compressedFile;
    } catch {
      // Se der erro (ex.: HEIC não suportado), usa original
      return file;
    }
  }

  function renameToJpeg(filename) {
    const i = filename.lastIndexOf(".");
    const base = i > -1 ? filename.slice(0, i) : filename;
    return `${base}.jpg`;
  }

  // -----------------------------
  // Envio para /analyze_photo
  // -----------------------------
  async function handlePhotoSelected() {
    if (!elInputPhoto.files || !elInputPhoto.files[0]) return;
    const original = elInputPhoto.files[0];

    setFeedback("Compactando imagem...");
    const compressed = await compressImage(original, 1920, 1920, 0.7);

    const fd = new FormData();
    fd.append("photo", compressed, compressed.name);

    setFeedback("Enviando foto para análise…");
    try {
      const res = await fetch("/analyze_photo", { method: "POST", body: fd });
      const json = await res.json();

      if (json.ok && json.analysis) {
        setFeedback("Análise concluída.");
        showAnalysis(json.analysis);
      } else {
        setFeedback(json.error || "Falha na análise da foto.");
      }
    } catch (e) {
      setFeedback("Erro de rede ao enviar foto.");
    } finally {
      elInputPhoto.value = "";
      await updateCreditsLabel();
    }
  }

  // -----------------------------
  // Envio para /analyze_text
  // -----------------------------
  async function handleSubmitText() {
    const text = (elTextarea && elTextarea.value || "").trim();
    if (!text) {
      setFeedback("Digite um texto para analisar.");
      return;
    }
    setFeedback("Enviando texto para análise…");

    try {
      const res = await fetch("/analyze_text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const json = await res.json();

      if (json.ok && json.analysis) {
        setFeedback("Análise concluída.");
        showAnalysis(json.analysis);
      } else {
        setFeedback(json.error || "Falha na análise do texto.");
      }
    } catch (e) {
      setFeedback("Erro de rede ao enviar texto.");
    } finally {
      await updateCreditsLabel();
    }
  }

  // -----------------------------
  // Listeners (UI)
  // -----------------------------
  if (elBtnPhoto && elInputPhoto) {
    elBtnPhoto.addEventListener("click", () => elInputPhoto.click());
    elInputPhoto.addEventListener("change", handlePhotoSelected);
  }

  // Botão “Enviar texto/legenda” foca o textarea (UX)
  if (elBtnText && elTextarea) {
    elBtnText.addEventListener("click", () => elTextarea.focus());
  }

  if (elBtnSubmitText) {
    elBtnSubmitText.addEventListener("click", handleSubmitText);
  }

  // -----------------------------
  // Boot
  // -----------------------------
  // Traz créditos reais (sessão/usuário) ao carregar
  document.addEventListener("DOMContentLoaded", updateCreditsLabel);
})();
