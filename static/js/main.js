(function(){
  const yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  const creditsEl = document.getElementById('credits-left');
  const feedback = document.getElementById('feedback');

  const btnPhoto = document.getElementById('btn-photo');
  const inputPhoto = document.getElementById('photo-input');
  const formPhoto = document.getElementById('form-photo');

  const btnText = document.getElementById('btn-text');
  const inputTextfile = document.getElementById('textfile-input');
  const formText = document.getElementById('form-text');

  function setFeedback(msg){ if (feedback) { feedback.textContent = msg || ''; } }

  // Foto
  if (btnPhoto && inputPhoto && formPhoto){
    btnPhoto.addEventListener('click', () => inputPhoto.click());
    inputPhoto.addEventListener('change', async () => {
      if (!inputPhoto.files || !inputPhoto.files[0]) return;
      setFeedback('Enviando foto para análise…');
      const fd = new FormData(formPhoto);
      try {
        const res = await fetch(formPhoto.action, { method: 'POST', body: fd });
        const json = await res.json();
        if (json.ok){
          setFeedback('Foto recebida. A análise de IA será integrada em seguida.');
          if (creditsEl){
            const n = Math.max(0, (parseInt(creditsEl.dataset.credits || '0', 10) - 1));
            creditsEl.dataset.credits = String(n);
            creditsEl.textContent = String(n);
          }
        } else {
          setFeedback(json.error || 'Falha ao enviar a foto.');
        }
      } catch (e){
        setFeedback('Erro de rede ao enviar foto.');
      } finally {
        inputPhoto.value = '';
      }
    });
  }

  // Texto — por arquivo (MVP). Campo de texto livre será adicionado na próxima etapa
  if (btnText && inputTextfile && formText){
    btnText.addEventListener('click', () => inputTextfile.click());
    inputTextfile.addEventListener('change', async () => {
      if (!inputTextfile.files || !inputTextfile.files[0]) return;
      setFeedback('Enviando texto para análise…');
      const fd = new FormData(formText);
      try {
        const res = await fetch(formText.action, { method: 'POST', body: fd });
        const json = await res.json();
        if (json.ok){
          setFeedback('Texto recebido. A análise de IA será integrada em seguida.');
          if (creditsEl){
            const n = Math.max(0, (parseInt(creditsEl.dataset.credits || '0', 10) - 1));
            creditsEl.dataset.credits = String(n);
            creditsEl.textContent = String(n);
          }
        } else {
          setFeedback(json.error || 'Falha ao enviar o texto.');
        }
      } catch (e){
        setFeedback('Erro de rede ao enviar texto.');
      } finally {
        inputTextfile.value = '';
      }
    });
  }
})();
