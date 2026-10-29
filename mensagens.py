"""Mensagem de primeiro contato, personalizada com o Gemini.

Usa só o que a coleta já deixou público: se há site, se ele respondeu e o estado.
Não envia a mensagem. Devolve o texto e um link wa.me para a pessoa abrir e mandar.
"""

from __future__ import annotations

import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from coletor import _marcar_presenca

MODELO_PADRAO = "gemini-3.5-flash-lite"
MODELOS_RESERVA = ("gemini-3.1-flash-lite", "gemini-2.5-flash-lite")
FUSO = timezone(timedelta(hours=-3))
URL_MODELO = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

INSTRUCAO = """Você escreve a primeira mensagem de WhatsApp para uma empresa, em português do Brasil.

Regras:
- Devolva só o texto da mensagem, sem aspas, sem título e sem comentário.
- Duas a quatro frases curtas. Tom cordial, de primeiro contato.
- Use apenas os fatos recebidos. Não invente promoção, preço, prazo, avaliação ou urgência.
- Se "tem site" for não, não fale de site.
- Se "site respondeu" for não, não diga que visitou o site e ignore a descrição.
- Se "site respondeu" for sim, cite um detalhe concreto do texto recebido, sem dizer que ele veio de uma descrição, de um site ou de uma ficha.
- Se houver estado, mencione o estado com naturalidade.
- Não peça documento, senha ou dado pessoal. Não repita telefone, e-mail nem CNPJ.
- Não diga que a mensagem foi gerada por inteligência artificial.
- Não use as expressões "descrição pública", "dados recebidos" ou "ficha".
"""


def carregar_env(caminho: Path | None = None) -> None:
    arquivo = caminho or Path(__file__).resolve().parent / ".env"
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if chave and chave not in os.environ:
            os.environ[chave] = valor


def chave_api() -> str:
    carregar_env()
    chave = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    if not chave.strip():
        raise RuntimeError(
            "Falta a chave do Gemini. Coloque GEMINI_API_KEY no ambiente ou no arquivo .env."
        )
    return chave.strip()


def modelo_configurado() -> str:
    carregar_env()
    return (os.environ.get("GEMINI_MODEL") or MODELO_PADRAO).strip()


def horario_sugerido(agora: datetime | None = None, gerador: random.Random | None = None) -> str:
    agora = agora or datetime.now(FUSO)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=FUSO)
    inicio = agora.replace(hour=6, minute=30, second=0, microsecond=0)
    fim = agora.replace(hour=22, minute=30, second=0, microsecond=0)
    if agora >= fim:
        inicio += timedelta(days=1)
        fim += timedelta(days=1)
    minutos = int((fim - inicio).total_seconds() // 60)
    sorteio = gerador.randrange(minutos) if gerador else random.randrange(minutos)
    marcado = inicio + timedelta(minutes=sorteio)
    return marcado.strftime("%Y-%m-%d %H:%M")


def ficha_publica(empresa: dict) -> str:
    _marcar_presenca(empresa)
    descricao = (empresa.get("descricao") or "").strip()
    if not empresa.get("site_respondeu"):
        descricao = ""
    linhas = [
        f"Nome: {empresa.get('nome') or ''}",
        f"Categoria: {empresa.get('categoria') or ''}",
        f"Cidade: {empresa.get('cidade') or ''}",
        f"Estado: {empresa.get('estado') or ''}",
        f"Endereço público: {empresa.get('endereco') or ''}",
        f"Horário publicado: {empresa.get('horario') or ''}",
        f"Tem site: {'sim' if empresa.get('tem_site') else 'não'}",
        f"Site respondeu: {'sim' if empresa.get('site_respondeu') else 'não'}",
        f"O que se sabe: {descricao}",
    ]
    return "\n".join(linhas)


def _texto_da_resposta(corpo: dict) -> str:
    candidatos = corpo.get("candidates") or []
    if not candidatos:
        motivo = (corpo.get("promptFeedback") or {}).get("blockReason") or "resposta vazia"
        raise RuntimeError(f"Gemini não devolveu texto ({motivo}).")
    partes = (candidatos[0].get("content") or {}).get("parts") or []
    trechos = [parte.get("text", "") for parte in partes if parte.get("text") and not parte.get("thought")]
    texto = "\n".join(trecho.strip() for trecho in trechos if trecho.strip()).strip()
    if texto.startswith(("\"", "“")) and texto.endswith(("\"", "”")):
        texto = texto[1:-1].strip()
    if not texto:
        raise RuntimeError("Gemini devolveu uma mensagem vazia.")
    return texto[:700]


def _pedir(session: requests.Session, modelo: str, chave: str, ficha: str) -> str:
    url = URL_MODELO.format(modelo=modelo)
    pedido = {
        "systemInstruction": {"parts": [{"text": INSTRUCAO}]},
        "contents": [{"role": "user", "parts": [{"text": ficha}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 320,
        },
    }
    resposta = session.post(url, params={"key": chave}, json=pedido, timeout=40)
    if resposta.status_code >= 400:
        detalhe = resposta.text[:300].replace("\n", " ")
        raise RuntimeError(f"Gemini HTTP {resposta.status_code}: {detalhe}")
    return _texto_da_resposta(resposta.json())


def gerar_mensagem(empresa: dict, session: requests.Session | None = None, chave: str | None = None) -> str:
    sessao = session or requests.Session()
    segredo = chave or chave_api()
    ficha = ficha_publica(empresa)
    modelos = [modelo_configurado(), *[item for item in MODELOS_RESERVA if item != modelo_configurado()]]
    ultimo_erro = "sem tentativa"
    for indice, modelo in enumerate(modelos):
        try:
            return _pedir(sessao, modelo, segredo, ficha)
        except RuntimeError as exc:
            ultimo_erro = str(exc)
            if "HTTP 404" not in ultimo_erro and indice == 0:
                raise
            if "HTTP 404" not in ultimo_erro:
                raise
    raise RuntimeError(ultimo_erro)


def link_pronto(empresa: dict, mensagem: str) -> str:
    base = (empresa.get("whatsapp_link") or "").strip()
    if not base or not mensagem:
        return base
    return f"{base}?text={quote(mensagem)}"


def preparar(empresa: dict, session: requests.Session, chave: str, gerador: random.Random | None = None) -> dict:
    _marcar_presenca(empresa)
    mensagem = gerar_mensagem(empresa, session=session, chave=chave)
    return {
        "mensagem": mensagem,
        "horario_sugerido": horario_sugerido(gerador=gerador),
        "link_pronto": link_pronto(empresa, mensagem),
    }


def preparar_lote(empresas: list[dict], pausa_segundos: float = 1.2) -> list[dict]:
    chave = chave_api()
    sessao = requests.Session()
    sessao.headers["User-Agent"] = "empresas-whatsapp-demo/0.1"
    prontas = []
    for indice, empresa in enumerate(empresas, start=1):
        print(f"mensagem {indice}/{len(empresas)}: {empresa.get('nome')}", flush=True)
        try:
            extras = preparar(empresa, sessao, chave)
            empresa.update(extras)
        except RuntimeError as exc:
            empresa["mensagem"] = ""
            empresa["horario_sugerido"] = ""
            empresa["link_pronto"] = empresa.get("whatsapp_link") or ""
            empresa["erro_mensagem"] = str(exc)
            print(f"  falhou: {exc}", flush=True)
        prontas.append(empresa)
        if indice < len(empresas):
            time.sleep(pausa_segundos)
    return prontas
