"""Arquivo dos ciclos: cada lote novo ignora o que já foi salvo."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from coletor import atribuicao, chave_empresa, coletar

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "data"
ARQUIVO = SAIDA / "arquivo.json"
LOTE = 40
FUSO = timezone(timedelta(hours=-3))


def _ler_empresas(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if isinstance(dados, dict):
        return list(dados.get("empresas") or [])
    if isinstance(dados, list):
        return dados
    return []


def _juntar(destino: list[dict], origem: list[dict]) -> None:
    vistas = {chave_empresa(item) for item in destino}
    for empresa in origem:
        chave = chave_empresa(empresa)
        if not chave or chave in vistas:
            continue
        vistas.add(chave)
        destino.append(empresa)


def carregar() -> dict:
    if ARQUIVO.exists():
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        dados.setdefault("empresas", [])
        dados.setdefault("ciclos", [])
        return dados
    empresas: list[dict] = []
    _juntar(empresas, _ler_empresas(SAIDA / "empresas.json"))
    _juntar(empresas, _ler_empresas(SAIDA / "mensagens.json"))
    return {"atribuicao": atribuicao(), "empresas": empresas, "ciclos": []}


def salvar(dados: dict) -> None:
    SAIDA.mkdir(exist_ok=True)
    dados["atribuicao"] = atribuicao()
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def rodar_ciclo(tamanho: int = LOTE) -> dict:
    dados = carregar()
    ignorar = {chave_empresa(empresa) for empresa in dados["empresas"]}
    novas = coletar(tamanho, ignorar=ignorar)
    numero = len(dados["ciclos"]) + 1
    quando = datetime.now(FUSO).strftime("%Y-%m-%d %H:%M")
    for empresa in novas:
        empresa["ciclo"] = numero
    dados["empresas"].extend(novas)
    dados["ciclos"].append({"numero": numero, "quando": quando, "quantidade": len(novas)})
    salvar(dados)
    return {
        "numero": numero,
        "quando": quando,
        "quantidade": len(novas),
        "total": len(dados["empresas"]),
        "empresas": novas,
    }
