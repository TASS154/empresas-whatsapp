"""Coleta dados públicos de empresas com WhatsApp divulgado.

Fontes: OpenStreetMap (tag contact:whatsapp) e a página pública do site
da empresa. Não usa API do Google e não busca dado pessoal sensível.
"""

from __future__ import annotations

import json
import re
import time
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "empresas-whatsapp-demo/0.1 (coleta publica; contato local)"
OVERPASS_URLS = (
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)

CIDADES = (
    ("São Paulo", -23.5505, -46.6333),
    ("Rio de Janeiro", -22.9068, -43.1729),
    ("Belo Horizonte", -19.9167, -43.9345),
    ("Curitiba", -25.4284, -49.2733),
    ("Porto Alegre", -30.0346, -51.2177),
    ("Salvador", -12.9777, -38.5016),
    ("Recife", -8.0476, -34.8770),
    ("Fortaleza", -3.7172, -38.5433),
    ("Brasília", -15.7939, -47.8828),
    ("Florianópolis", -27.5954, -48.5480),
    ("Campinas", -22.9099, -47.0626),
    ("Goiânia", -16.6869, -49.2648),
)

CATEGORIA = {
    "restaurant": "Restaurante",
    "cafe": "Café",
    "fast_food": "Lanchonete",
    "bar": "Bar",
    "pub": "Bar",
    "pharmacy": "Farmácia",
    "clinic": "Clínica",
    "doctors": "Consultório",
    "dentist": "Dentista",
    "hospital": "Hospital",
    "veterinary": "Clínica veterinária",
    "bank": "Banco",
    "fuel": "Posto",
    "school": "Escola",
    "kindergarten": "Escola infantil",
    "college": "Faculdade",
    "university": "Universidade",
    "hotel": "Hotel",
    "guest_house": "Pousada",
    "apartment": "Apart-hotel",
    "hostel": "Hostel",
    "motel": "Motel",
    "supermarket": "Supermercado",
    "bakery": "Padaria",
    "clothes": "Loja de roupas",
    "hairdresser": "Salão de beleza",
    "beauty": "Estética",
    "car_repair": "Oficina",
    "car": "Loja de veículos",
    "electronics": "Eletrônicos",
    "furniture": "Móveis",
    "hardware": "Ferragens",
    "florist": "Floricultura",
    "butcher": "Açougue",
    "greengrocer": "Hortifruti",
    "convenience": "Conveniência",
    "optician": "Ótica",
    "bed": "Loja de colchões",
    "tattoo": "Estúdio de tatuagem",
    "jewelry": "Joalheria",
    "shoes": "Calçados",
    "books": "Livraria",
    "travel_agency": "Agência de viagens",
    "estate_agent": "Imobiliária",
    "insurance": "Seguros",
    "lawyer": "Escritório de advocacia",
    "accountant": "Contabilidade",
    "company": "Empresa",
    "yes": "Comércio",
}

PULAR_AMENITY = {
    "toilets",
    "fountain",
    "bench",
    "waste_basket",
    "recycling",
    "parking",
    "parking_space",
    "bicycle_parking",
    "drinking_water",
    "post_box",
    "telephone",
    "clock",
    "hunting_stand",
    "waste_disposal",
    "grit_bin",
    "public_bookcase",
    "shelter",
    "atm",
}

COZINHA = {
    "brazilian": "brasileira",
    "international": "internacional",
    "pizza": "pizza",
    "regional": "regional",
    "vegetarian": "vegetariana",
    "vegan": "vegana",
    "steak_house": "churrascaria",
    "coffee_shop": "cafeteria",
    "sushi": "japonesa",
    "burger": "hambúrguer",
}

DIAS = {
    "Mo": "seg",
    "Tu": "ter",
    "We": "qua",
    "Th": "qui",
    "Fr": "sex",
    "Sa": "sáb",
    "Su": "dom",
    "PH": "feriados",
}

CNPJ_RE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
WA_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\d{10,15})", re.I)
CPF_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )
    return s


def _consulta_cidade(lat: float, lon: float) -> str:
    return (
        "[out:json][timeout:25];\n"
        f'(nwr["contact:whatsapp"]["name"](around:9000,{lat},{lon}););\n'
        "out tags center 15;"
    )


def buscar_osm(session: requests.Session, minimo: int = 18) -> list[dict[str, Any]]:
    elementos: list[dict[str, Any]] = []
    vistos: set[tuple[str, int]] = set()
    erros: list[str] = []
    for cidade, lat, lon in CIDADES:
        if len(elementos) >= minimo:
            break
        print(f"buscando em {cidade}...", flush=True)
        consulta = _consulta_cidade(lat, lon)
        conseguiu = False
        for url in OVERPASS_URLS:
            try:
                resposta = session.post(url, data={"data": consulta}, timeout=35)
            except requests.RequestException as exc:
                erros.append(f"{cidade}: {exc.__class__.__name__}")
                continue
            if resposta.status_code != 200 or not resposta.text.lstrip().startswith("{"):
                erros.append(f"{cidade}: HTTP {resposta.status_code}")
                continue
            try:
                lote = resposta.json().get("elements", [])
            except ValueError:
                erros.append(f"{cidade}: resposta inválida")
                continue
            for elemento in lote:
                chave = (str(elemento.get("type")), int(elemento.get("id") or 0))
                if chave in vistos:
                    continue
                vistos.add(chave)
                elementos.append(elemento)
            print(f"  {len(lote)} pontos, {len(elementos)} no total", flush=True)
            conseguiu = True
            break
        if conseguiu:
            time.sleep(1.0)
    if not elementos:
        detalhe = "; ".join(erros[-4:]) or "sem resposta"
        raise RuntimeError(f"OpenStreetMap não respondeu ({detalhe})")
    return elementos


def _primeiro(*valores: str | None) -> str:
    for valor in valores:
        if valor and str(valor).strip():
            return str(valor).strip()
    return ""


def _lista_contato(valor: str | None) -> list[str]:
    if not valor:
        return []
    partes = re.split(r"[;|,]", valor)
    return [p.strip() for p in partes if p.strip()]


def _digitos_whatsapp(valor: str) -> str:
    bruto = valor.strip()
    match = WA_RE.search(bruto)
    if match:
        return match.group(1)
    digitos = re.sub(r"\D", "", bruto)
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if digitos.startswith("0"):
        digitos = digitos[1:]
    if not digitos.startswith("55") and len(digitos) in (10, 11):
        digitos = "55" + digitos
    return digitos


def _parece_brasil(numero: str) -> bool:
    digitos = _digitos_whatsapp(numero)
    return digitos.startswith("55") and 12 <= len(digitos) <= 13


def _formatar_whatsapp(numero: str) -> str:
    digitos = _digitos_whatsapp(numero)
    if digitos.startswith("55") and len(digitos) >= 12:
        ddd = digitos[2:4]
        resto = digitos[4:]
        if len(resto) == 9:
            return f"+55 ({ddd}) {resto[:5]}-{resto[5:]}"
        if len(resto) == 8:
            return f"+55 ({ddd}) {resto[:4]}-{resto[4:]}"
    return numero.strip()


def _link_whatsapp(numero: str) -> str:
    digitos = _digitos_whatsapp(numero)
    if len(digitos) < 12:
        return ""
    return f"https://wa.me/{digitos}"


def _categoria(tags: dict[str, str]) -> str:
    for chave in ("shop", "amenity", "tourism", "office", "craft", "healthcare"):
        valor = tags.get(chave)
        if not valor:
            continue
        if chave == "amenity" and valor in PULAR_AMENITY:
            continue
        nome = CATEGORIA.get(valor, valor.replace("_", " ").capitalize())
        cozinha = tags.get("cuisine")
        if cozinha and chave == "amenity":
            partes = []
            for item in cozinha.split(";"):
                item = item.strip()
                if not item:
                    continue
                partes.append(COZINHA.get(item, item.replace("_", " ")))
            if partes:
                return f"{nome} ({', '.join(partes)})"
        return nome
    if tags.get("brand"):
        return "Comércio"
    return "Estabelecimento"


def _e_empresa(tags: dict[str, str]) -> bool:
    amenity = tags.get("amenity", "")
    if amenity in PULAR_AMENITY:
        return False
    chaves = ("shop", "office", "craft", "healthcare", "brand", "company")
    if any(tags.get(chave) for chave in chaves):
        return True
    if amenity and amenity not in PULAR_AMENITY:
        return True
    if tags.get("tourism") in {"hotel", "guest_house", "apartment", "hostel", "motel", "chalet"}:
        return True
    return False


def _endereco(tags: dict[str, str]) -> str:
    rua = tags.get("addr:street", "")
    numero = tags.get("addr:housenumber", "")
    bairro = tags.get("addr:suburb") or tags.get("addr:neighbourhood") or ""
    cidade = tags.get("addr:city", "")
    uf = tags.get("addr:state", "")
    cep = tags.get("addr:postcode", "")
    linha = " ".join(p for p in (rua, numero) if p).strip()
    if linha and bairro:
        linha = f"{linha}, {bairro}"
    elif bairro:
        linha = bairro
    cidade_uf = " - ".join(p for p in (cidade, uf) if p)
    if cep:
        cidade_uf = f"{cidade_uf}, {cep}".strip(", ")
    return ", ".join(p for p in (linha, cidade_uf) if p)


def _horario_legivel(bruto: str) -> str:
    if not bruto:
        return ""
    texto = bruto
    for codigo, nome in DIAS.items():
        texto = re.sub(rf"\b{codigo}\b", nome, texto)
    texto = texto.replace("off", "fechado").replace(";", "; ").replace(",", ", ")
    return re.sub(r"\s+", " ", texto).strip()


def _rede_util(rotulo: str, url: str) -> bool:
    caminho = urlparse(url).path.lower()
    if rotulo == "instagram" and any(parte in caminho for parte in ("/p/", "/reel/", "/tv/", "/stories/")):
        return False
    return True


def _redes(tags: dict[str, str]) -> dict[str, str]:
    redes: dict[str, str] = {}
    for chave, rotulo in (
        ("contact:instagram", "instagram"),
        ("contact:facebook", "facebook"),
        ("contact:twitter", "twitter"),
        ("contact:youtube", "youtube"),
        ("contact:linkedin", "linkedin"),
    ):
        valor = tags.get(chave, "").strip()
        if not valor:
            continue
        if valor.startswith("http"):
            url = valor.split(";")[0].strip()
            if _rede_util(rotulo, url):
                redes[rotulo] = url
        elif rotulo == "instagram":
            redes[rotulo] = "https://www.instagram.com/" + valor.strip("@/")
        elif rotulo == "facebook":
            redes[rotulo] = "https://www.facebook.com/" + valor.strip("/")
        else:
            redes[rotulo] = valor
    return redes


def _osm_url(elemento: dict[str, Any]) -> str:
    tipo = elemento.get("type", "node")
    return f"https://www.openstreetmap.org/{tipo}/{elemento.get('id')}"


def _site(tags: dict[str, str]) -> str:
    return _primeiro(tags.get("website"), tags.get("contact:website"), tags.get("url"))


def montar_base(elemento: dict[str, Any]) -> dict[str, Any] | None:
    tags = elemento.get("tags") or {}
    if not _e_empresa(tags):
        return None
    whatsapp_bruto = _primeiro(tags.get("contact:whatsapp"))
    if not whatsapp_bruto or not _parece_brasil(whatsapp_bruto):
        return None
    nome = tags.get("name", "").strip()
    if not nome:
        return None
    lat = elemento.get("lat") or (elemento.get("center") or {}).get("lat")
    lon = elemento.get("lon") or (elemento.get("center") or {}).get("lon")
    emails = _lista_contato(_primeiro(tags.get("contact:email"), tags.get("email")))
    telefones = _lista_contato(_primeiro(tags.get("contact:phone"), tags.get("phone"), tags.get("mobile")))
    whatsapp_fmt = _formatar_whatsapp(whatsapp_bruto)
    telefones_fmt = []
    for telefone in telefones:
        formatado = _formatar_whatsapp(telefone) if _parece_brasil(telefone) else telefone
        if formatado and formatado != whatsapp_fmt and formatado not in telefones_fmt:
            telefones_fmt.append(formatado)
    return {
        "nome": nome,
        "categoria": _categoria(tags),
        "descricao": _primeiro(tags.get("description"), tags.get("description:pt")),
        "whatsapp": whatsapp_fmt,
        "whatsapp_link": _link_whatsapp(whatsapp_bruto),
        "telefones": telefones_fmt,
        "emails_publicos": emails,
        "site": _site(tags),
        "endereco": _endereco(tags),
        "cidade": tags.get("addr:city", ""),
        "horario": _horario_legivel(tags.get("opening_hours", "")),
        "redes": _redes(tags),
        "acessibilidade": tags.get("wheelchair", ""),
        "marca": tags.get("brand", ""),
        "coordenadas": {"lat": lat, "lon": lon} if lat is not None and lon is not None else None,
        "mapa": (
            f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}"
            if lat is not None and lon is not None
            else ""
        ),
        "cnpj_publico": "",
        "fonte_mapa": _osm_url(elemento),
        "fonte_site": "",
        "paginas_lidas": [],
    }


def _pode_buscar(session: requests.Session, url: str, cache: dict[str, RobotFileParser]) -> bool:
    partes = urlparse(url)
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        return False
    base = f"{partes.scheme}://{partes.netloc}"
    if base not in cache:
        parser = RobotFileParser()
        parser.set_url(base + "/robots.txt")
        try:
            resposta = session.get(base + "/robots.txt", timeout=8)
            if resposta.status_code == 200 and "text" in resposta.headers.get("content-type", "text/plain"):
                parser.parse(resposta.text.splitlines())
            else:
                parser.parse([])
        except requests.RequestException:
            parser.parse([])
        cache[base] = parser
    return cache[base].can_fetch(USER_AGENT, url)


def _extrair_jsonld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    achados: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        if "@graph" in node:
            walk(node["@graph"])
        achados.append(node)
        for valor in node.values():
            if isinstance(valor, (dict, list)):
                walk(valor)

    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        bruto = script.string or script.get_text() or ""
        bruto = bruto.strip()
        if not bruto:
            continue
        try:
            walk(json.loads(bruto))
        except json.JSONDecodeError:
            continue
    return achados


def _texto_endereco_ld(endereco: Any) -> str:
    if isinstance(endereco, str):
        return endereco.strip()
    if isinstance(endereco, list):
        return ", ".join(_texto_endereco_ld(item) for item in endereco if item)
    if not isinstance(endereco, dict):
        return ""
    partes = [
        endereco.get("streetAddress") or "",
        endereco.get("addressLocality") or "",
        endereco.get("addressRegion") or "",
        endereco.get("postalCode") or "",
    ]
    return ", ".join(str(p).strip() for p in partes if str(p).strip())


def _horario_ld(node: dict[str, Any]) -> str:
    bruto = node.get("openingHours") or node.get("openingHoursSpecification")
    if isinstance(bruto, str):
        return _horario_legivel(bruto)
    if isinstance(bruto, list) and bruto and isinstance(bruto[0], str):
        return _horario_legivel("; ".join(bruto))
    if isinstance(bruto, list):
        linhas = []
        for item in bruto:
            if not isinstance(item, dict):
                continue
            dias = item.get("dayOfWeek") or ""
            if isinstance(dias, list):
                dias = ", ".join(str(d).split("/")[-1] for d in dias)
            elif isinstance(dias, str):
                dias = dias.split("/")[-1]
            abre = item.get("opens", "")
            fecha = item.get("closes", "")
            if dias and abre:
                linhas.append(f"{dias} {abre}-{fecha}".strip("-"))
        return "; ".join(linhas)
    return ""


def _aplicar_jsonld(empresa: dict[str, Any], nodes: list[dict[str, Any]]) -> None:
    for node in nodes:
        tipos = node.get("@type") or ""
        if isinstance(tipos, list):
            tipo_txt = " ".join(str(t) for t in tipos).lower()
        else:
            tipo_txt = str(tipos).lower()
        interessante = any(
            p in tipo_txt
            for p in ("localbusiness", "organization", "store", "restaurant", "foodestablishment", "place")
        )
        if not interessante and not node.get("telephone") and not node.get("address"):
            continue
        if not empresa["descricao"]:
            descricao = node.get("description")
            if isinstance(descricao, str):
                empresa["descricao"] = _limpar(descricao)
        telefone = node.get("telephone") or node.get("telephone")
        if isinstance(telefone, list):
            for item in telefone:
                if isinstance(item, str):
                    _adicionar_telefone(empresa, item)
        elif isinstance(telefone, str):
            _adicionar_telefone(empresa, telefone)
        email = node.get("email")
        if isinstance(email, str):
            _adicionar_email(empresa, email)
        if not empresa["endereco"]:
            empresa["endereco"] = _texto_endereco_ld(node.get("address"))
        if not empresa["horario"]:
            empresa["horario"] = _horario_ld(node)
        same = node.get("sameAs") or []
        if isinstance(same, str):
            same = [same]
        if isinstance(same, list):
            for url in same:
                if isinstance(url, str):
                    _adicionar_rede(empresa, url)
        if not empresa["site"]:
            url = node.get("url")
            if isinstance(url, str) and url.startswith("http"):
                empresa["site"] = url


def _limpar(texto: str) -> str:
    texto = unescape(re.sub(r"\s+", " ", texto)).strip()
    texto = CPF_RE.sub("", texto)
    return texto[:500]


def _adicionar_email(empresa: dict[str, Any], email: str) -> None:
    email = email.strip().lower().strip(".,;)")
    if not EMAIL_RE.fullmatch(email):
        return
    if email.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")):
        return
    if email not in empresa["emails_publicos"]:
        empresa["emails_publicos"].append(email)


def _adicionar_telefone(empresa: dict[str, Any], telefone: str) -> None:
    telefone = telefone.strip()
    if not telefone or len(re.sub(r"\D", "", telefone)) < 8:
        return
    formatado = _formatar_whatsapp(telefone) if _parece_brasil(telefone) else telefone
    if formatado not in empresa["telefones"] and formatado != empresa["whatsapp"]:
        empresa["telefones"].append(formatado)


def _adicionar_rede(empresa: dict[str, Any], url: str) -> None:
    baixo = url.lower()
    for rotulo, dominio in (
        ("instagram", "instagram.com"),
        ("facebook", "facebook.com"),
        ("youtube", "youtube.com"),
        ("linkedin", "linkedin.com"),
    ):
        if dominio in baixo and rotulo not in empresa["redes"] and _rede_util(rotulo, url):
            empresa["redes"][rotulo] = url.split("?")[0]


def _ler_pagina(session: requests.Session, url: str) -> tuple[str, BeautifulSoup] | None:
    try:
        resposta = session.get(url, timeout=10, allow_redirects=True)
    except requests.RequestException:
        return None
    tipo = resposta.headers.get("content-type", "")
    if resposta.status_code >= 400 or "html" not in tipo.lower():
        return None
    html = resposta.text[:1_500_000]
    return str(resposta.url), BeautifulSoup(html, "html.parser")


def enriquecer_site(
    session: requests.Session,
    empresa: dict[str, Any],
    robots_cache: dict[str, RobotFileParser],
) -> None:
    site = empresa.get("site") or ""
    if not site:
        return
    if not site.startswith("http"):
        site = "https://" + site
    if not _pode_buscar(session, site, robots_cache):
        empresa["fonte_site"] = "robots.txt não permitiu a leitura"
        return
    lido = _ler_pagina(session, site)
    if not lido:
        empresa["fonte_site"] = "site indisponível nesta coleta"
        return
    final_url, soup = lido
    empresa["paginas_lidas"].append(final_url)
    empresa["fonte_site"] = final_url
    _absorver_html(empresa, soup, final_url)

    contato = ""
    if not empresa["descricao"] or not empresa["emails_publicos"]:
        contato = _achar_contato(soup, final_url)
    if contato and contato.rstrip("/") != final_url.rstrip("/") and _pode_buscar(session, contato, robots_cache):
        time.sleep(0.6)
        extra = _ler_pagina(session, contato)
        if extra:
            url_extra, soup_extra = extra
            empresa["paginas_lidas"].append(url_extra)
            _absorver_html(empresa, soup_extra, url_extra)


def _achar_contato(soup: BeautifulSoup, base: str) -> str:
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        texto = (link.get_text(" ", strip=True) or "").lower()
        alvo = (href + " " + texto).lower()
        if any(p in alvo for p in ("contato", "contact", "fale-conosco", "faleconosco")):
            absoluto = urljoin(base, href)
            if urlparse(absoluto).netloc == urlparse(base).netloc:
                return absoluto
    return ""


def _absorver_html(empresa: dict[str, Any], soup: BeautifulSoup, url: str) -> None:
    if not empresa["descricao"]:
        meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        if not meta:
            meta = soup.find("meta", attrs={"property": re.compile("og:description", re.I)})
        if meta and meta.get("content"):
            empresa["descricao"] = _limpar(meta["content"])
    if soup.title and soup.title.string and not empresa["descricao"]:
        empresa["descricao"] = _limpar(soup.title.string)

    _aplicar_jsonld(empresa, _extrair_jsonld(soup))

    texto = soup.get_text(" ", strip=True)
    if CPF_RE.search(texto):
        texto = CPF_RE.sub("", texto)
    if not empresa["cnpj_publico"]:
        match = CNPJ_RE.search(texto)
        if match:
            empresa["cnpj_publico"] = match.group(0)

    for email in EMAIL_RE.findall(texto[:20000]):
        _adicionar_email(empresa, email)
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.lower().startswith("mailto:"):
            _adicionar_email(empresa, href.split(":", 1)[1].split("?")[0])
        match = WA_RE.search(href)
        if match and not empresa["whatsapp_link"]:
            empresa["whatsapp"] = _formatar_whatsapp(match.group(1))
            empresa["whatsapp_link"] = _link_whatsapp(match.group(1))
        if href.lower().startswith("tel:"):
            _adicionar_telefone(empresa, href.split(":", 1)[1])
        if href.startswith("http"):
            _adicionar_rede(empresa, href)

    if "whatsapp" in texto.lower() and not empresa["whatsapp_link"]:
        match = re.search(r"(?:\+?55\s*)?\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4}", texto)
        if match and "whatsapp" in texto.lower()[max(0, match.start() - 40) : match.end() + 40]:
            candidato = match.group(0)
            if _parece_brasil(candidato):
                empresa["whatsapp"] = _formatar_whatsapp(candidato)
                empresa["whatsapp_link"] = _link_whatsapp(candidato)


def pontuar(empresa: dict[str, Any]) -> int:
    pontos = 0
    for chave in ("descricao", "endereco", "cidade", "horario", "site", "cnpj_publico", "marca"):
        if empresa.get(chave):
            pontos += 2
    pontos += min(len(empresa.get("emails_publicos") or []), 2)
    pontos += min(len(empresa.get("telefones") or []), 2)
    pontos += min(len(empresa.get("redes") or {}), 3) * 2
    pontos += min(len(empresa.get("paginas_lidas") or []), 2) * 3
    return pontos


def coletar(limite: int = 10) -> list[dict[str, Any]]:
    session = _session()
    elementos = buscar_osm(session)
    bases: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for elemento in elementos:
        empresa = montar_base(elemento)
        if not empresa:
            continue
        chave = empresa["whatsapp_link"] or empresa["nome"].lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        bases.append(empresa)

    com_site = [e for e in bases if e["site"]]
    sem_site = [e for e in bases if not e["site"]]
    com_site.sort(key=pontuar, reverse=True)
    sem_site.sort(key=pontuar, reverse=True)
    fila = com_site[: limite + 6] + sem_site

    robots_cache: dict[str, RobotFileParser] = {}
    escolhidas: list[dict[str, Any]] = []
    visitas = 0
    for empresa in fila:
        if empresa["site"] and visitas < limite + 2:
            print(f"lendo site de {empresa['nome']}...", flush=True)
            enriquecer_site(session, empresa, robots_cache)
            visitas += 1
            time.sleep(0.4)
        escolhidas.append(empresa)
        if len(escolhidas) >= limite + 4:
            break

    if len(escolhidas) < limite:
        raise RuntimeError(f"Só encontrei {len(escolhidas)} empresas públicas com WhatsApp.")

    escolhidas.sort(key=pontuar, reverse=True)
    for empresa in escolhidas:
        empresa.pop("paginas_lidas", None)
        empresa["emails_publicos"] = empresa["emails_publicos"][:4]
        empresa["telefones"] = empresa["telefones"][:4]
    return escolhidas[:limite]


def atribuicao() -> str:
    return (
        "Dados de mapa © colaboradores do OpenStreetMap, licença ODbL. "
        "Demais campos vieram de páginas públicas dos próprios estabelecimentos."
    )
