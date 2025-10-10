# services/openai_client.py
# INFLUE — Cliente de IA (stub operacional + “switch” para produção)
# Foco: garantir que /analyze_photo e /analyze_text funcionem end-to-end AGORA,
# sem dependências extras. Quando formos ligar a IA real, ativamos via env.

from __future__ import annotations

import os
import re
import json
import math
import time
import hashlib
from typing import Any, Dict, List, Optional


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


class OpenAIClient:
    """
    Cliente de IA do INFLUE.

    MODO ATUAL (operacional / MVP):
      - Usa STUB determinístico para gerar:
        score_risk (0-100), tags, summary e recommendations.
      - Não requer biblioteca externa, nem altera requirements.txt.
      - Faz o portal “funcionar agora” com respostas coerentes.

    MODO PRODUÇÃO (planejado):
      - Quando quiser integrar com a OpenAI:
        * Definir OPENAI_USE_STUB=false
        * Adicionar SDK e/ou implementar chamada REST
        * Preencher OPENAI_API_KEY, OPENAI_MODEL_VISION, OPENAI_MODEL_TEXT
    """

    def __init__(self) -> None:
        # Switch de operação
        self.use_stub = _env_bool("OPENAI_USE_STUB", True)

        # Parâmetros pensados para produção (não usados no stub)
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.model_vision = os.environ.get("OPENAI_MODEL_VISION", "gpt-5-vision")
        self.model_text = os.environ.get("OPENAI_MODEL_TEXT", "gpt-5")
        self.timeout_s = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "12"))

    # ---------------------------------------------------------------------
    # PÚBLICO: analisadores chamados pelo app.py
    # ---------------------------------------------------------------------
    def analyze_image(self, file_path: str) -> Dict[str, Any]:
        """
        Analisa uma imagem e retorna um dicionário padronizado:
        {
          "ok": True,
          "score_risk": int 0..100,
          "tags": [str],
          "summary": str,
          "recommendations": [str, str, str]
        }
        """
        if self.use_stub:
            return self._stub_analyze_image(file_path)

        # Produção real (placeholder seguro até habilitarmos)
        return {
            "ok": False,
            "error": (
                "Integração OpenAI desativada neste build. "
                "Defina OPENAI_USE_STUB=true para usar o stub, ou implemente a chamada real."
            ),
        }

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analisa um texto/legenda e retorna o mesmo formato da imagem.
        """
        if self.use_stub:
            return self._stub_analyze_text(text)

        # Produção real (placeholder seguro até habilitarmos)
        return {
            "ok": False,
            "error": (
                "Integração OpenAI desativada neste build. "
                "Defina OPENAI_USE_STUB=true para usar o stub, ou implemente a chamada real."
            ),
        }

    # ---------------------------------------------------------------------
    # STUBS (operacional) — determinísticos e úteis para QA
    # ---------------------------------------------------------------------
    def _stub_analyze_image(self, file_path: str) -> Dict[str, Any]:
        """
        Heurísticas simples baseadas no nome do arquivo e hash do conteúdo
        para gerar respostas consistentes e úteis nos testes.
        """
        try:
            # Base determinística: hash do caminho
            h = hashlib.sha256(file_path.encode("utf-8", errors="ignore")).hexdigest()
            seed = int(h[:8], 16)

            # Tags por palavras-chave do nome do arquivo
            lname = file_path.lower()
            tags: List[str] = []
            keywords = [
                ("violencia", "violência"),
                ("sangue", "sangue"),
                ("arma", "arma"),
                ("bebida", "álcool"),
                ("cerveja", "álcool"),
                ("vinho", "álcool"),
                ("marca", "marca_em_foco"),
                ("logo", "marca_em_foco"),
                ("politica", "política"),
                ("campanha", "política"),
                ("corrupcao", "política"),
                ("dinheiro", "ostentação"),
                ("ostentacao", "ostentação"),
                ("biquini", "sensual"),
                ("praia", "contexto_praia"),
                ("animal", "animal"),
                ("silvestre", "animal_silvestre"),
            ]
            for k, tag in keywords:
                if k in lname and tag not in tags:
                    tags.append(tag)

            # Score baseia-se no seed + presença de tags sensíveis
            base = seed % 100
            risk = base

            # Penaliza (sobe risco) se houver tags sensíveis
            sensitive = {"violência", "arma", "sangue", "política", "álcool", "animal_silvestre"}
            bump = sum(10 for t in tags if t in sensitive)
            risk = max(0, min(100, risk // 2 + bump))

            # Classificação resumida
            label = self._risk_label(risk)

            # Resumo e recomendações
            summary = (
                f"A imagem apresenta {label} risco de interpretação negativa. "
                "Considere pequenos ajustes antes de publicar."
            )
            recs = self._recommendations_for_tags(tags, is_image=True)
            if not recs:
                recs = [
                    "Verifique iluminação e enquadramento para maior apelo visual.",
                    "Evite elementos de fundo que possam distrair ou comprometer sua imagem.",
                    "Inclua uma legenda objetiva que destaque o valor do post.",
                ]

            return {
                "ok": True,
                "score_risk": risk,
                "tags": tags,
                "summary": summary,
                "recommendations": recs[:3],
            }
        except Exception as e:
            return {"ok": False, "error": f"Falha no stub de imagem: {e}"}

    def _stub_analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Heurísticas simples no texto para identificar potenciais riscos reputacionais.
        """
        try:
            t = (text or "").strip()
            if not t:
                return {"ok": False, "error": "Texto vazio."}

            h = hashlib.sha256(t.encode("utf-8", errors="ignore")).hexdigest()
            seed = int(h[:8], 16)

            # Normaliza para análise
            ln = t.lower()

            # Regras básicas de risco
            patterns = {
                "ofensa": r"\b(burro|idiota|otário|imbecil|lixo|ódio|hater)\b",
                "álcool": r"\b(cerveja|vodka|whisky|tequila|bebida|cachaça|drinks?)\b",
                "política": r"\b(eleição|política|partido|campanha|corrupção|governo)\b",
                "sensível": r"\b(sangue|violência|arma|tiro|assalto|morte)\b",
                "marca_em_foco": r"[@#]?\b(nike|adidas|apple|samsung|coca[- ]?cola|heineken)\b",
                "ostentação": r"\b(luxo|ostentação|milionário|carro\s+caro|rolext?)\b",
            }

            tags: List[str] = []
            bump = 0
            for tag, rx in patterns.items():
                if re.search(rx, ln, flags=re.IGNORECASE):
                    tags.append(tag)
                    if tag in {"sensível", "política"}:
                        bump += 20
                    elif tag in {"ofensa", "álcool"}:
                        bump += 12
                    else:
                        bump += 6

            base = seed % 100
            risk = max(0, min(100, base // 2 + bump))

            label = self._risk_label(risk)
            summary = (
                f"O texto sugere {label} risco de reação negativa. "
                "Ajustes de tom e clareza podem melhorar a recepção."
            )

            recs = self._recommendations_for_tags(tags, is_image=False)
            if not recs:
                recs = [
                    "Prefira um tom empático e direto para evitar interpretações dúbias.",
                    "Evite termos que possam soar ofensivos ou polarizadores.",
                    "Inclua um call-to-action suave e relevante ao seu público.",
                ]

            return {
                "ok": True,
                "score_risk": risk,
                "tags": tags,
                "summary": summary,
                "recommendations": recs[:3],
            }
        except Exception as e:
            return {"ok": False, "error": f"Falha no stub de texto: {e}"}

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    @staticmethod
    def _risk_label(score: int) -> str:
        if score >= 70:
            return "ALTO"
        if score >= 40:
            return "MÉDIO"
        return "BAIXO"

    @staticmethod
    def _recommendations_for_tags(tags: List[str], is_image: bool) -> List[str]:
        recs: List[str] = []
        tagset = set(tags)

        # Recomendações específicas por risco
        if "álcool" in tagset:
            recs.append("Se houver bebidas, mantenha o foco no contexto e responsabilidade social.")
        if "política" in tagset:
            recs.append("Evite generalizações e frases categóricas; ofereça contexto para reduzir polarização.")
        if "violência" in tagset or "arma" in tagset or "sangue" in tagset or "sensível" in tagset:
            recs.append("Evite imagery/termos que sugiram violência explícita; considere suavizar a narrativa.")
        if "marca_em_foco" in tagset:
            recs.append("Cheque direitos de uso de marca e evite enquadramento que pareça endorsement indevido.")
        if "ostentação" in tagset:
            recs.append("Balanceie com uma mensagem de utilidade/valor para o público, evitando percepção de ostentação.")
        if "animal_silvestre" in tagset:
            recs.append("Evite interação direta com animal silvestre; destaque responsabilidade ambiental.")

        # Recomendações genéricas por tipo
        if is_image:
            recs.append("Ajuste iluminação e enquadramento; evite ruídos no fundo e preserve a nitidez.")
            recs.append("Use uma legenda que direcione a interpretação e reforce seu posicionamento.")
        else:
            recs.append("Releia buscando ambiguidade; substitua termos potentes por equivalentes neutros.")
            recs.append("Inclua 1 chamada clara (CTA) e evite parágrafos muito longos.")

        # Deduplicate mantendo ordem
        dedup: List[str] = []
        seen = set()
        for r in recs:
            if r not in seen:
                dedup.append(r)
                seen.add(r)
        return dedup
