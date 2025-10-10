# INFLUE (MVP)

Portal para analisar **imagens e textos** antes de publicar em redes sociais.

## Estrutura

Mantemos os arquivos originais (`app.py`, `templates/`, `static/`) e **estendemos** com:
- `db/` (SQLite + DDL + helpers)
- `services/` (cliente de IA **stub** + créditos)
- `payments/` (mock + stub PagSeguro)
- `utils/` (segurança + rate limit)
- `tests/` (pytest básico)

## Rodando localmente

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # preencha se necessário
python -c "from db import init_db; init_db()"
flask --app app run
