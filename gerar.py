"""Versão completa: coleta pública e mensagem personalizada pelo Gemini.

A mensagem fica pronta, com horário sugerido entre 6:30 e 22:30.
O envio continua manual, pelo link wa.me.
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

from coletor import _marcar_presenca, atribuicao, coletar
from mensagens import preparar_lote

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "data"


def carregar_cache() -> list[dict]:
    caminho = SAIDA / "empresas.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    empresas = dados.get("empresas") or []
    for empresa in empresas:
        _marcar_presenca(empresa)
    return empresas


def _html(empresas: list[dict]) -> str:
    cards = []
    for indice, empresa in enumerate(empresas, start=1):
        mensagem = escape(empresa.get("mensagem") or empresa.get("erro_mensagem") or "Sem mensagem.")
        link = empresa.get("link_pronto") or ""
        cards.append(
            f"""
            <article>
              <p class="indice">{indice:02d} · {escape(empresa.get("horario_sugerido") or "sem horário")}</p>
              <h2>{escape(empresa.get("nome") or "")}</h2>
              <p class="categoria">{escape(empresa.get("categoria") or "")} · {escape(empresa.get("cidade") or "cidade não informada")} {escape(empresa.get("estado") or "")}</p>
              <p class="sinais">Site: {"sim" if empresa.get("tem_site") else "não"} · Respondeu: {"sim" if empresa.get("site_respondeu") else "não"}</p>
              <blockquote>{mensagem}</blockquote>
              <p><a href="{escape(link)}">Abrir no WhatsApp</a></p>
              <p class="fonte">{escape(empresa.get("whatsapp") or "")}</p>
            </article>
            """
        )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mensagens personalizadas</title>
  <style>
    body {{ margin: 0; background: #f4f0e6; color: #1c1915; font-family: Georgia, serif; }}
    header, main {{ max-width: 760px; margin: 0 auto; padding: 28px 18px; }}
    article {{ background: #fffdf8; border: 1px solid #e3dccb; border-radius: 16px; padding: 18px 20px; margin: 14px 0; }}
    .indice, .sinais, .fonte {{ color: #6f685c; }}
    blockquote {{ margin: 12px 0; white-space: pre-wrap; }}
    a {{ color: #0f6b4c; }}
  </style>
</head>
<body>
  <header>
    <h1>Mensagens prontas para enviar</h1>
    <p>O horário é uma sugestão entre 6:30 e 22:30. O link abre o WhatsApp com o texto; o envio é seu.</p>
    <p>{escape(atribuicao())}</p>
  </header>
  <main>
    {"".join(cards)}
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera mensagens personalizadas com o Gemini.")
    parser.add_argument("--limite", type=int, default=10)
    parser.add_argument("--coletar", action="store_true", help="Busca empresas de novo em vez de usar o cache.")
    args = parser.parse_args()
    if args.coletar or not (SAIDA / "empresas.json").exists():
        empresas = coletar(args.limite)
    else:
        empresas = carregar_cache()[: args.limite]
    prontas = preparar_lote(empresas)
    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "mensagens.json").write_text(
        json.dumps({"atribuicao": atribuicao(), "empresas": prontas}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (SAIDA / "mensagens.html").write_text(_html(prontas), encoding="utf-8")
    print(f"{len(prontas)} mensagens em {SAIDA / 'mensagens.json'}")
    for empresa in prontas:
        estado = "ok" if empresa.get("mensagem") else "erro"
        print(f"- {empresa.get('nome')}: {estado} · {empresa.get('horario_sugerido') or ''}")


if __name__ == "__main__":
    main()
