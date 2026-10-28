"""Demo: 10 empresas com WhatsApp público e o máximo de dado público em volta."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from coletor import atribuicao, coletar

SAIDA = Path(__file__).resolve().parent / "data"


def _acesso(valor: str) -> str:
    return {"yes": "sim", "no": "não", "limited": "parcial"}.get(valor, valor or "—")


def _html(empresas: list[dict]) -> str:
    cards = []
    for indice, empresa in enumerate(empresas, start=1):
        redes = "".join(
            f'<a href="{escape(url)}">{escape(nome)}</a>'
            for nome, url in (empresa.get("redes") or {}).items()
        )
        emails = ", ".join(escape(e) for e in empresa.get("emails_publicos") or [])
        telefones = ", ".join(escape(t) for t in empresa.get("telefones") or [])
        mapa = empresa.get("mapa") or ""
        site = empresa.get("site") or ""
        wa = empresa.get("whatsapp_link") or ""
        cards.append(
            f"""
            <article>
              <p class="indice">{indice:02d}</p>
              <h2>{escape(empresa["nome"])}</h2>
              <p class="categoria">{escape(empresa.get("categoria") or "")}</p>
              <p>{escape(empresa.get("descricao") or "Sem descrição pública adicional.")}</p>
              <dl>
                <dt>WhatsApp</dt><dd><a href="{escape(wa)}">{escape(empresa.get("whatsapp") or "")}</a></dd>
                <dt>Telefones</dt><dd>{telefones or "—"}</dd>
                <dt>E-mail público</dt><dd>{emails or "—"}</dd>
                <dt>Endereço</dt><dd>{escape(empresa.get("endereco") or "—")}</dd>
                <dt>Horário</dt><dd>{escape(empresa.get("horario") or "—")}</dd>
                <dt>Marca</dt><dd>{escape(empresa.get("marca") or "—")}</dd>
                <dt>Acessibilidade</dt><dd>{escape(_acesso(empresa.get("acessibilidade") or ""))}</dd>
                <dt>CNPJ publicado</dt><dd>{escape(empresa.get("cnpj_publico") or "—")}</dd>
                <dt>Site</dt><dd>{f'<a href="{escape(site)}">{escape(site)}</a>' if site else "—"}</dd>
                <dt>Redes</dt><dd class="redes">{redes or "—"}</dd>
                <dt>Mapa</dt><dd>{f'<a href="{escape(mapa)}">ver no OpenStreetMap</a>' if mapa else "—"}</dd>
              </dl>
              <p class="fonte">Fonte do mapa: <a href="{escape(empresa.get("fonte_mapa") or "")}">{escape(empresa.get("fonte_mapa") or "")}</a></p>
            </article>
            """
        )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Demo — empresas com WhatsApp público</title>
  <style>
    :root {{ color-scheme: light; font-family: Georgia, "Iowan Old Style", serif; }}
    body {{ margin: 0; background: #f4f0e6; color: #1c1915; }}
    header, main {{ max-width: 880px; margin: 0 auto; padding: 32px 20px; }}
    header {{ padding-bottom: 0; }}
    h1 {{ font-weight: 600; letter-spacing: -0.03em; margin-bottom: 8px; }}
    .nota {{ color: #5c564c; line-height: 1.5; }}
    article {{ background: #fffdf8; border: 1px solid #e3dccb; border-radius: 16px; padding: 22px 22px 8px; margin: 16px 0; }}
    .indice {{ color: #8a8172; letter-spacing: 0.12em; margin: 0; }}
    h2 {{ margin: 4px 0; }}
    .categoria {{ color: #6d5b3a; margin-top: 0; }}
    dl {{ display: grid; grid-template-columns: 140px 1fr; gap: 6px 12px; }}
    dt {{ color: #6f685c; }}
    dd {{ margin: 0; }}
    a {{ color: #0f6b4c; }}
    .redes a {{ margin-right: 10px; }}
    .fonte {{ color: #8a8172; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <header>
    <h1>10 empresas com WhatsApp público</h1>
    <p class="nota">Coleta de demonstração, só com dado publicado: mapa aberto e site da própria empresa. Sem API do Google e sem documento pessoal.</p>
    <p class="nota">{escape(atribuicao())}</p>
  </header>
  <main>
    {"".join(cards)}
  </main>
</body>
</html>
"""


def main() -> None:
    empresas = coletar(10)
    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "empresas.json").write_text(
        json.dumps({"atribuicao": atribuicao(), "empresas": empresas}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (SAIDA / "demo.html").write_text(_html(empresas), encoding="utf-8")
    print(f"{len(empresas)} empresas salvas em {SAIDA}")
    for indice, empresa in enumerate(empresas, start=1):
        print(f"{indice:02d}. {empresa['nome']} | {empresa['categoria']} | {empresa['whatsapp']} | {empresa.get('cidade') or empresa.get('endereco')}")


if __name__ == "__main__":
    main()
