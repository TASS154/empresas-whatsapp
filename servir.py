"""Painel local: um botão puxa o próximo ciclo de 40 empresas novas."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape

from ciclos import LOTE, carregar, rodar_ciclo
from coletor import atribuicao

PORTA = 8765
_ciclo = threading.Lock()


def _cartao(empresa: dict, indice: int) -> str:
    cidade = empresa.get("cidade") or "cidade não informada"
    estado = empresa.get("estado") or ""
    whatsapp = empresa.get("whatsapp_link") or ""
    return f"""
    <article>
      <p class="indice">{indice:02d}</p>
      <h2>{escape(empresa.get("nome") or "")}</h2>
      <p class="categoria">{escape(empresa.get("categoria") or "")} · {escape(cidade)} {escape(estado)}</p>
      <p><a href="{escape(whatsapp)}">{escape(empresa.get("whatsapp") or "")}</a></p>
      <p class="fonte">{escape(empresa.get("endereco") or "")}</p>
    </article>
    """


def pagina(aviso: str = "") -> str:
    dados = carregar()
    empresas = dados.get("empresas") or []
    ciclos = dados.get("ciclos") or []
    ultimo = ciclos[-1]["numero"] if ciclos else 0
    lista = "".join(_cartao(empresa, i) for i, empresa in enumerate(empresas[-LOTE:], start=1))
    if not lista:
        lista = "<p>Nenhum ciclo novo ainda. O arquivo já guarda as empresas coletadas antes.</p>"
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ciclos de coleta</title>
  <style>
    body {{ margin: 0; background: #f4f0e6; color: #1c1915; font-family: Georgia, serif; }}
    header, main {{ max-width: 760px; margin: 0 auto; padding: 28px 18px; }}
    button {{ background: #0f6b4c; color: #fff; border: 0; border-radius: 999px; padding: 12px 18px; font: inherit; cursor: pointer; }}
    button:disabled {{ background: #8a8172; cursor: wait; }}
    #status {{ color: #6f685c; min-height: 1.4em; }}
    article {{ background: #fffdf8; border: 1px solid #e3dccb; border-radius: 16px; padding: 16px 18px; margin: 12px 0; }}
    .indice, .fonte, .categoria {{ color: #6f685c; }}
    a {{ color: #0f6b4c; }}
  </style>
</head>
<body>
  <header>
    <h1>Próximo ciclo</h1>
    <p>Cada clique busca {LOTE} empresas com WhatsApp público e pula as que já estão no arquivo.</p>
    <p id="resumo">No arquivo: {len(empresas)}. Ciclos novos: {len(ciclos)}. Último: {ultimo}.</p>
    <p><form id="form-ciclo" method="post" action="/ciclo"><button id="buscar" type="submit">Buscar mais {LOTE}</button></form></p>
    <p id="status">{escape(aviso)}</p>
    <p>{escape(atribuicao())}</p>
  </header>
  <main id="lista">
    {lista}
  </main>
  <script>
    const botao = document.getElementById("buscar");
    const status = document.getElementById("status");
    const formulario = document.getElementById("form-ciclo");
    formulario.addEventListener("submit", async (evento) => {{
      evento.preventDefault();
      botao.disabled = true;
      status.textContent = "Buscando {LOTE} empresas que ainda não foram coletadas…";
      try {{
        const resposta = await fetch("/ciclo", {{ method: "POST", headers: {{ "Accept": "application/json" }} }});
        const dados = await resposta.json();
        if (!resposta.ok) throw new Error(dados.erro || "Falha no ciclo");
        status.textContent = "Ciclo " + dados.numero + ": " + dados.quantidade + " empresas novas. Arquivo agora tem " + dados.total + ".";
        document.getElementById("resumo").textContent = "No arquivo: " + dados.total + ". Último ciclo: " + dados.numero + ".";
        const lista = document.getElementById("lista");
        lista.innerHTML = "";
        dados.empresas.forEach((empresa, indice) => {{
          const artigo = document.createElement("article");
          artigo.innerHTML = "<p class='indice'>" + String(indice + 1).padStart(2, "0") + "</p>"
            + "<h2></h2><p class='categoria'></p><p><a></a></p><p class='fonte'></p>";
          artigo.querySelector("h2").textContent = empresa.nome || "";
          artigo.querySelector(".categoria").textContent = (empresa.categoria || "") + " · " + (empresa.cidade || "cidade não informada") + " " + (empresa.estado || "");
          const link = artigo.querySelector("a");
          link.href = empresa.whatsapp_link || "#";
          link.textContent = empresa.whatsapp || "";
          artigo.querySelector(".fonte").textContent = empresa.endereco || "";
          lista.appendChild(artigo);
        }});
      }} catch (erro) {{
        status.textContent = erro.message;
      }} finally {{
        botao.disabled = false;
      }}
    }});
  </script>
</body>
</html>
"""


class Painel(BaseHTTPRequestHandler):
    def _json(self, codigo: int, corpo: dict) -> None:
        bruto = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(bruto)))
        self.end_headers()
        self.wfile.write(bruto)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] not in {"/", "/index.html"}:
            self.send_error(404)
            return
        bruto = pagina().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(bruto)))
        self.end_headers()
        self.wfile.write(bruto)

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/ciclo":
            self.send_error(404)
            return
        if not _ciclo.acquire(blocking=False):
            self._json(409, {"erro": "Já existe um ciclo em andamento."})
            return
        try:
            resultado = rodar_ciclo(LOTE)
        except RuntimeError as exc:
            self._json(502, {"erro": str(exc)})
            return
        finally:
            _ciclo.release()
        if "application/json" in self.headers.get("Accept", ""):
            self._json(200, resultado)
            return
        aviso = (
            f"Ciclo {resultado['numero']}: {resultado['quantidade']} empresas novas. "
            f"Arquivo agora tem {resultado['total']}."
        )
        bruto = pagina(aviso).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(bruto)))
        self.end_headers()
        self.wfile.write(bruto)

    def log_message(self, formato: str, *args) -> None:
        print(formato % args, flush=True)


def main() -> None:
    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), Painel)
    print(f"Painel em http://127.0.0.1:{PORTA}", flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
