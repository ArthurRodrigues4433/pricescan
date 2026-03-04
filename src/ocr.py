"""
src/ocr.py
Módulo de OCR para leitura de cartazes de preço.

Funções públicas:
    checar_qualidade(caminho) -> (ok: bool, motivo: str)
    extrair_texto(caminho)    -> str
    parsear_cartaz(texto)     -> dict
"""

from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from django.conf import settings
from PIL import Image, ImageOps


# 1. Checagem de qualidade

RESOLUCAO_MINIMA = 640  # px (largura ou altura)
BRILHO_MIN = 40  # histograma médio muito escuro
BRILHO_MAX = 220  # histograma médio superexposto
VARIANCIA_LAPLACIANO_MIN = 10  # baixo para aceitar fotos de tela em testes


def checar_qualidade(
    caminho: str | Path, checar_resolucao: bool = True
) -> tuple[bool, str]:
    """
    Verifica se a imagem tem qualidade suficiente para OCR.
    Retorna (True, "") se aprovada, ou (False, "mensagem") se reprovada.
    """
    caminho = str(caminho)

    # --- Resolução mínima (Pillow) ---
    if checar_resolucao:
        with Image.open(caminho) as img:
            largura, altura = img.size

        if largura < RESOLUCAO_MINIMA or altura < RESOLUCAO_MINIMA:
            return (
                False,
                f"Foto muito pequena ({largura}×{altura}px). "
                "Aproxime mais o celular do cartaz.",
            )

    # --- Brilho médio (Pillow) ---
    with Image.open(caminho) as img:
        cinza = ImageOps.grayscale(img)
        pixels = list(cinza.getdata())
    brilho_medio = sum(pixels) / len(pixels)

    if brilho_medio < BRILHO_MIN:
        return (False, "Foto muito escura. Melhore a iluminação e tente novamente.")
    if brilho_medio > BRILHO_MAX:
        return (False, "Foto muito clara / com reflexo. Evite luz direta no cartaz.")

    # --- Desfoque — variância do Laplaciano (OpenCV) ---
    # cv2.imread falha com caminhos não-ASCII no Windows; usamos PIL + numpy
    try:
        with Image.open(caminho) as _img_pil:
            img_cv = cv2.cvtColor(np.array(_img_pil.convert("RGB")), cv2.COLOR_RGB2GRAY)
    except Exception:
        return (False, "Não foi possível ler a imagem. Tente novamente.")
    if img_cv is None:
        return (False, "Não foi possível ler a imagem. Tente novamente.")

    variancia = float(cv2.Laplacian(img_cv, cv2.CV_64F).var())
    if variancia < VARIANCIA_LAPLACIANO_MIN:
        return (False, "Foto borrada. Segure o celular mais firme e tente novamente.")

    return (True, "")


# ---------------------------------------------------------------------------
# 2. Extração de texto via OCR
# ---------------------------------------------------------------------------


def extrair_texto(caminho: str | Path) -> str:
    """
    Pré-processa a imagem e executa o Tesseract com dois passes:
      - PSM 6 (bloco uniforme): captura texto denso small/médio
      - PSM 11 (texto esparso): captura números grandes isolados (preços)
    Retorna a concatenação dos dois resultados.
    """
    lang = getattr(settings, "TESSERACT_LANG", "por")

    with Image.open(str(caminho)) as img:
        cinza = ImageOps.grayscale(img)

        # Redimensiona para no mínimo 2400px de largura
        # (2400px necessário para ler texto pequeno como "CX 12 RS 110,16")
        w, h = cinza.size
        if w < 2400:
            fator = 2400 / w
            cinza = cinza.resize((int(w * fator), int(h * fator)), Image.LANCZOS)

        cinza = ImageOps.autocontrast(cinza)

        arr = np.array(cinza)
        _, binarizada = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        img_proc = Image.fromarray(binarizada)

    # Passo 1 — bloco uniforme: texto denso pequeno/médio (labels, nome, CX...)
    t1 = pytesseract.image_to_string(img_proc, lang=lang, config="--oem 3 --psm 6")
    # Passo 2 — layout automático: captura texto em colunas/tamanhos mistos
    t2 = pytesseract.image_to_string(img_proc, lang=lang, config="--oem 3 --psm 3")
    # Passo 3 — texto esparso: captura números grandes isolados (ex: "9,18" enorme)
    t3 = pytesseract.image_to_string(img_proc, lang=lang, config="--oem 3 --psm 11")

    # Combina os três passes, evitando duplicar linhas idênticas
    linhas_vistas: set = set()
    linhas_finais = []
    for linha in (t1 + "\n" + t2 + "\n" + t3).splitlines():
        s = linha.strip()
        if s and s not in linhas_vistas:
            linhas_vistas.add(s)
            linhas_finais.append(s)

    return "\n".join(linhas_finais)


# ---------------------------------------------------------------------------
# 3. Parser — extrai campos estruturados do texto bruto
# ---------------------------------------------------------------------------

# Padrões
_RE_PRECO = re.compile(
    r"(?<!\d)R?\$?\s*(\d{1,3}[.,]\s*\d{2})(?!\d)",
    re.IGNORECASE,
)
_RE_PESO = re.compile(
    r"(\d+[,.]?\d*)\s*(kg|g(?![r])|gr|ml|l(?![t])|lt|un|unid)",
    re.IGNORECASE,
)
_RE_ATACADO_QTD = re.compile(
    # Formato normal: "A PARTIR DE 12" / "LEVE 3" / "APARTIR DE 5"
    r"(?:leve|a\s*partir\s*de|acima\s*de|com|apartir\s*de)\s*(\d+)"
    # OCR funde tudo: "APARTIRDES5" / "APARTIRDE12"
    r"|apartirdes?\s*(\d+)"
    # "A PARTIR" truncado: "PARTIR DE 12" ou "PARTIR 12"
    r"|partir\s*(?:de\s*)?(\d+)"
    # "/" seguido de 2+ dígitos (OCR garble de "A PARTIR DE 12" → "/12"; ignora "/2" solto)
    r"|\/\s*(\d{2,3})\b",
    re.IGNORECASE,
)
_RE_ATACADO_PRECO = re.compile(
    r"(?:leve|a\s*partir\s*de|acima\s*de|com|apartir\s*de)[^\d]*"
    r"(?:r?\$)?\s*(\d{1,3}[.,]\d{2})",
    re.IGNORECASE,
)

# Linhas que contêm preços de contexto (total de caixa, preço por KG, datas)
# → devem ser ignoradas na extração de preço unitário
_RE_LINHA_CONTEXTO = re.compile(
    r"\bcx\b.*\d"  # "CX 30 R$ 302,70"
    r"|\bequi[vl]"  # "EQUIVALENTE" / "EQUIV" / "EQUIL" (OCR)
    r"|\bequ[iíl]v"  # variações OCR de EQUIV
    r"|eq[uü][iíl]v"  # mais variações
    r"|\bpor\s+k[g6]\b"  # "POR KG" / "POR K6" (OCR misread)
    r"|/\s*k[g6]\b"  # "/KG" "/K6"
    r"|\bk[g6]\b"  # linha terminando em KG ou K6
    r"|\d{1,2}/\d{1,2}/\d{2,4}"  # datas "19/02/26"
    r"|\bpartir\b"  # "A PARTIR DE 30 UNID."
    r"|\bunid\b"  # "UNID." / "UNIDADE" — quantidade, não peso
    r"|\bpor\s+litro\b"  # "PRECO POR LITRO RS 5,99" / "POR LITRO RS"
    r"|\bpor\s+pacote\b"  # "PRECO POR PACOTE"
    r"|prec[o0]\s+e"  # "PRECO E..." (PRECO EQUIVALENTE / EQIV)
    r"|\d{4,}\.\d{2}"  # números com 4+ dígitos antes do ponto (ex: 1371.00)
    r"|\d{6,}"  # 6+ dígitos seguidos = código de barras / PLU / EAN
    r"|\d%",  # número seguido de % = percentagem (ex: "R$2,36%/kg") — não é preço
    re.IGNORECASE,
)


def parsear_cartaz(texto: str) -> dict:
    """
    Extrai campos estruturados de um texto de cartaz de atacarejo.

    Retorna dict com chaves:
        nome, peso_volume, preco_unitario, preco_atacado, qtd_min_atacado
    Campos não encontrados retornam string vazia "".
    'quantidade' nunca é extraída — o usuário informa na etapa 2.
    """
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]

    # --- Nome: linha de produto mais frequente no texto (OCR faz 3 passagens)
    # Estratégia: coleta candidatos com boa proporção de chars limpos e
    # escolhe o que mais se repete ao longo das linhas OCR.
    nome = ""
    _candidatos_nome: list[str] = []
    for linha in linhas:
        if len(linha) <= 4:
            continue
        if re.match(r"^[\d\s\.,R\$\/\|\-]+$", linha):
            continue
        chars_limpos = sum(
            1 for c in linha if c.isalnum() or c in " -áàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ"
        )
        ratio = chars_limpos / len(linha)
        num_alfa = sum(1 for c in linha if c.isalpha())
        if ratio >= 0.65 and num_alfa >= 4:
            trimmed = re.sub(r"^[^A-Za-zÀ-ÿ]+|[^A-Za-zÀ-ÿ\d\)]+$", "", linha).strip()
            if len(trimmed) >= 4:
                _candidatos_nome.append(trimmed)

    if _candidatos_nome:
        # Palavras e padrões que indicam que a linha NÃO é nome de produto
        _RE_LINHA_NAO_NOME = re.compile(
            r"\bvarejo\b|\batacado\b|\bpromo[cç][aã]o\b|\boferta\b|\bdesconto\b|\bimperd[ií]vel\b|\bpromo\b"
            r"|\bunidade\b|\bunid\b|\ba partir\b|\bapartir\b|\bleve\b|\bacima\b|\bcliente\b|\blimitado\b"
            r"|\bplu\b|\br\$|\brs\b|\bpre[cç]o\b|\bpre[cç]o\b|\bpre[cç]os\b|\bpre[cç]os?\b"
            r"|atacad|atacarejo|atacad[aã]o|atacadista|supermercado|mercado|hipermercado|comercial|distribuidor|distribuidora"
            r"|\bpor\s+cliente\b|\bpor\s+kg\b|\bpor\s+litro\b|\bpor\s+pacote\b|\bpor\s+unidade\b"
            r"|\bpre[cç]o\s+por\b|\bpre[cç]o\s+equivalente\b|\bequivalente\b|\bequiv\b|\bequ[iíl]v\b|eq[uü][iíl]v"
            r"|\bsite\b|\bwww\b|\.com\b|\.br\b|instagram|facebook|@|#|telefone|zap|whatsapp"
            r"|\bpromo[cç][aã]o\b|\boferta\b|\bdesconto\b|\bimperd[ií]vel\b|\bpre[cç]o\s+baixo\b|\bpre[cç]o\s+especial\b"
            r"|\baproveite\b|\bsomente\b|\bhoje\b|\bvalido\b|\bvalida\b|\bdata\b|\bvalidade\b|\bconfira\b|\bcompare\b"
            r"|\bparcelamos\b|\bcart[ãa]o\b|\bcrédito\b|\bdébito\b|\bvisa\b|\bmaster\b|\belite\b|\belo\b"
            r"|\bpre[cç]o\s+total\b|\bpre[cç]o\s+final\b|\bpre[cç]o\s+unit[áa]rio\b|\bpre[cç]o\s+atacado\b"
            r"|\bkg\b|\bg\b|\bml\b|\bl\b|\blt\b|\bpacote\b|\bcx\b|\bcaixa\b|\bfardo\b|\bdúzia\b"
            r"|\bpor\s+kg\b|\bpor\s+litro\b|\bpor\s+pacote\b|\bpor\s+unidade\b"
            r"|\d{4,}\.[0-9]{2}|\d{6,}|\d%",  # códigos, datas, percentuais
            re.IGNORECASE,
        )
        _candidatos_nome = [
            c for c in _candidatos_nome if not _RE_LINHA_NAO_NOME.search(c)
        ]

    if _candidatos_nome:

        def _score_nome(c: str) -> tuple:
            palavras = re.findall(r"[A-Za-zÀ-ÿ]{4,}", c)
            freq = (
                sum(
                    1
                    for l in linhas
                    if any(re.search(p, l, re.IGNORECASE) for p in palavras[:3])
                )
                if palavras
                else 0
            )
            # Tiebreaker: prefere nomes com unidade de medida ("140g" > "1408")
            has_unit = (
                1 if re.search(r"\d+\s*(g|ml|kg|l|lt|un)\b", c, re.IGNORECASE) else 0
            )
            return (freq, has_unit)

        _candidatos_nome.sort(key=_score_nome, reverse=True)
        # Remove letras/algarismos soltos nas bordas (artefatos OCR: "n BISCOITO ... i")
        _raw = _candidatos_nome[0]
        _raw = re.sub(r"^[A-Za-zÀ-ÿ]ú?\s+(?=[A-ZÀ-ß])", "", _raw).strip()
        _raw = re.sub(r"\s+[A-Za-zÀ-ÿ]$", "", _raw).strip()
        nome = _raw

    # --- Peso / volume ---
    # Busca linha a linha, ignorando linhas de contexto (por KG, equivalente, CX)
    # para não capturar "126,13 KG" de "PREÇO EQUIVALENTE A R$ 126,13 KG"
    peso_volume = ""
    for linha in linhas:
        if _RE_LINHA_CONTEXTO.search(linha):
            continue
        m = _RE_PESO.search(linha)
        if m:
            peso_volume = f"{m.group(1)}{m.group(2).lower()}"
            break

    # --- Helpers de preço ---
    def _to_float(p: str) -> float:
        """Converte string de preço BR para float (trata vírgula, ponto e espaços OCR)."""
        p = p.strip()
        # "10, 48" → "10,48" (espaço após separador decimal)
        p = re.sub(r"([,.])\s+(\d{2})$", r"\1\2", p)
        # "302 70" → "302.70" (espaço como separador decimal, sem vírgula/ponto)
        m_space = re.match(r"^(\d{1,4})\s+(\d{2})$", p)
        if m_space:
            p = m_space.group(1) + "." + m_space.group(2)
        if "," in p:
            return float(p.replace(".", "").replace(",", "."))
        if "." in p:
            partes = p.split(".")
            if len(partes) == 2 and len(partes[1]) == 2:
                return float(p)
            return float(p.replace(".", ""))
        return float(p)

    def _normaliza(p: str) -> str:
        # Remove espaços após separador ("10, 48" → "10,48") e converte ponto em vírgula
        p = re.sub(r"([,.])\s+(\d{2})$", r"\1\2", p.strip())
        return p.replace(".", ",")

    # Regex para números sem separador decimal que o OCR leu de preços grandes
    # Ex: "918" → 9,18 | "219" → 2,19
    # IMPORTANTE: só 3 dígitos — 4+ dígitos são quase sempre fragmentos de código
    # de barras (ex: "9343" de "7894545210987" → NÃO deve virar R$93,43)
    # Preços ≥ R$10 com vírgula ("22,50", "103,90") são capturados pela estratégia 1.
    # Exclui letras após o número para evitar "500g" → "5,00" ou "500ml" → "5,00"
    _RE_PRECO_SEM_VIRGULA = re.compile(r"(?<!\d)(\d{3})(?![,.\da-zA-ZÀ-ÿ])")

    def _precos_limpos() -> list:
        """
        Varre as linhas e retorna (float, str_normalizada) de cada preço,
        ignorando linhas de contexto (CX total, por KG, datas).

        Três estratégias em cascata:
          1. Preço com vírgula/ponto normal: "9,18" ou "10.09"
          2. Preço sem separador numa linha curta: "918" → "9,18"
          3. Preço partido em duas linhas: "9" / "18" → "9,18"
        """
        vistos: set = set()
        resultado = []

        def _adicionar(raw: str) -> None:
            s = _normaliza(raw)
            if s in vistos:
                return
            try:
                v = _to_float(raw)
                if 0.01 <= v <= 9999:
                    vistos.add(s)
                    resultado.append((v, s))
            except (ValueError, OverflowError):
                pass

        # Filtra linhas de contexto antes de qualquer análise
        linhas_uteis = [l for l in linhas if not _RE_LINHA_CONTEXTO.search(l)]

        # --- Estratégia 3 (pré-passo): preço partido em duas linhas consecutivas ---
        # Padrão: linha com só 1-3 dígitos seguida de linha com exatamente 2 dígitos
        # Ex: "9" → "18" = "9,18" | "10" → "09" = "10,09"
        _RE_INTEIROS = re.compile(r"^\d{1,3}$")
        _RE_CENTAVOS = re.compile(r"^\d{2}$")
        linhas_usadas_como_parte: set = set()
        for i in range(len(linhas_uteis) - 1):
            l1 = linhas_uteis[i].strip()
            l2 = linhas_uteis[i + 1].strip()
            if _RE_INTEIROS.match(l1) and _RE_CENTAVOS.match(l2):
                reconstruido = f"{l1},{l2}"
                _adicionar(reconstruido)
                linhas_usadas_como_parte.add(i)
                linhas_usadas_como_parte.add(i + 1)

        # --- Pré-passo B: dígito(s) numa linha + preço na linha seguinte ---
        # Ex: "1" / "4,90" → "14,90"  |  "14" / "90" já coberto pelo passo A acima
        _RE_PRECO_LINHA_PURA = re.compile(r"^(\d{1,3}[.,]\d{2})$")
        for i in range(len(linhas_uteis) - 1):
            l1 = linhas_uteis[i].strip()
            l2 = linhas_uteis[i + 1].strip()
            m_preco = _RE_PRECO_LINHA_PURA.match(l2)
            if _RE_INTEIROS.match(l1) and m_preco and i not in linhas_usadas_como_parte:
                reconstruido = l1 + l2  # "1" + "4,90" = "14,90"
                _adicionar(reconstruido)
                linhas_usadas_como_parte.add(i)
                # Não adiciona i+1 como usado, pois l2 sozinho também pode ser válido

        # --- RE auxiliar: preço com espaço inline, ex: "18 90" → 18,90 ---
        _RE_PRECO_ESPACADO_INLINE = re.compile(r"(?<!\d)(\d{1,3})\s+(\d{2})(?!\d)")

        # --- Estratégias 1, 2 e 3: linha por linha ---
        for idx, linha in enumerate(linhas_uteis):
            # Passo 1 — preços com vírgula/ponto (formato normal)
            achou_normal = False
            for m2 in _RE_PRECO.finditer(linha):
                _adicionar(m2.group(1))
                achou_normal = True

            if achou_normal:
                # Passo 1b — na mesma linha com preço normal, extrai também
                # números de 3 dígitos sem separador (ex: "149 1,79" → 1,49)
                for m3 in _RE_PRECO_SEM_VIRGULA.finditer(linha):
                    raw3 = m3.group(1)
                    reconstruido3 = raw3[0] + "," + raw3[1:]
                    _adicionar(reconstruido3)
                # Nota: NÃO aplica detecção espaço-separado aqui para evitar
                # falsos positivos tipo "22 50 23,90" → "50,23"
            else:
                # Passo 2 — fallback: extrai números de 3 dígitos em qualquer linha
                # sem preço com separador. Ex: "219 - 29" → 2,19 | "918 TEST" → 9,18
                # O regex exclui números seguidos de letras (evita "500g" → "5,00")
                # Guarda: ignora linhas com ≥2 palavras longas (provavelmente nome
                # do produto, ex: "BISCOTO RECHEADO 140" → não extrai "1,40")
                matched_3dig = False
                palavras_alfa = re.findall(r"[A-Za-zÀ-ÿ]{3,}", linha)
                if idx not in linhas_usadas_como_parte and len(palavras_alfa) <= 1:
                    for m3 in _RE_PRECO_SEM_VIRGULA.finditer(linha):
                        raw3 = m3.group(1)
                        reconstruido3 = raw3[:-2] + "," + raw3[-2:]
                        _adicionar(reconstruido3)
                        matched_3dig = True
                if not matched_3dig:
                    # Passo 3 — preço com espaço em qualquer linha sem price normal
                    # Ex: "27 90 UNIDADE" → 27,90  |  "27 90" → 27,90
                    for m4 in _RE_PRECO_ESPACADO_INLINE.finditer(linha):
                        reconstruido4 = m4.group(1) + "," + m4.group(2)
                        _adicionar(reconstruido4)

        return resultado

    def _filtrar_outliers(precos: list) -> list:
        """
        Remove preços que são > 20x o menor preço da lista.
        Exemplo: [4,49 ; 494,49] → [4,49]  (OCR juntou dígitos espúrios)
        """
        if len(precos) < 2:
            return precos
        min_p = min(v for v, _ in precos)
        limite = max(20 * min_p, 50.0)  # nunca filtra abaixo de R$50
        filtrado = [(v, s) for v, s in precos if v <= limite]
        return filtrado if filtrado else precos  # segurança: retorna original se vazio

    preco_unitario = ""
    preco_atacado = ""
    qtd_min_atacado = ""

    texto_lower = texto.lower()

    # Detecção de labels com tolerância a erros de OCR
    # "ATACADO" → "ATAGADO", "ATAC4DO", "ATAC ADO", etc.
    # "VAREJO"  → "VAREJORS", "VAREJO", "VARE]O", etc.
    _RE_LABEL_ATACADO = re.compile(
        r"at[a@][cgq][a@4]d[o0ãÃaoÃµ]"  # ATACADO / ATACADÃO (com ou sem ã)
        r"|at[a@]g[a@]d[o0]"  # ATAGADO (troca C→G)
        r"|at[a@]c\s*[a@]d[o0ãÃ]",  # ATA CADO (com espaço)
        re.IGNORECASE,
    )
    _RE_LABEL_VAREJO = re.compile(
        r"var[e3][j\]i][o0]",  # VAREJO com variações OCR
        re.IGNORECASE,
    )
    has_atacado = bool(_RE_LABEL_ATACADO.search(texto))
    has_varejo = bool(_RE_LABEL_VAREJO.search(texto))

    def _label_in_linha(linha: str, re_label: re.Pattern) -> bool:
        return bool(re_label.search(linha))

    def _precos_apos_label(label: re.Pattern, parar_em: re.Pattern = None) -> list:
        """
        Retorna lista de (float, str) dos preços encontrados nas até 6 linhas
        após a linha que contém `label`. Para ao encontrar `parar_em` (outro label).
        Quando a própria linha do label já contém os dois labels (lado a lado),
        começa a varredura a partir da linha seguinte.
        """
        _RE_PRECO_LINHA = re.compile(r"(?<!\d)(\d{1,3}[.,]\s*\d{2})(?!\d)")
        _RE_3DIG = re.compile(r"(?<!\d)(\d{3})(?![,.\da-zA-ZÀ-ÿ])")
        _RE_ESPACO_LABEL = re.compile(r"(?<!\d)(\d{1,3})\s+(\d{2})(?!\d)")

        def _add_res(raw: str) -> None:
            try:
                v = _to_float(raw)
                if 0.01 <= v <= 9999:
                    resultado.append((v, _normaliza(raw)))
            except (ValueError, OverflowError):
                pass

        resultado = []
        encontrou = False
        janela = 0
        for linha in linhas:
            if label.search(linha):
                encontrou = True
                janela = 0
                # Se a própria linha do label tem os dois labels juntos,
                # não busca preço nessa linha (os preços vêm nas próximas)
                continue
            if encontrou:
                janela += 1
                if janela > 6:
                    break
                # Para se encontrou o label do outro campo —
                # mas só se já temos algum preço OU passamos as primeiras 2 linhas.
                # Caso contrário os dois labels podem estar em linhas consecutivas
                # e ainda não chegamos aos preços.
                if parar_em and parar_em.search(linha):
                    if resultado or janela > 2:
                        break
                    # Labels consecutivos: continua procurando preços além do outro label
                    continue
                if _RE_LINHA_CONTEXTO.search(linha):
                    continue
                achou = False
                for m2 in _RE_PRECO_LINHA.finditer(linha):
                    _add_res(m2.group(1))
                    achou = True
                if achou:
                    # Inline 3-digit (ex: "149 1,79" → 1,49)
                    for m3 in _RE_3DIG.finditer(linha):
                        raw3 = m3.group(1)
                        _add_res(raw3[0] + "," + raw3[1:])
                    # Nota: NÃO aplica espaço-separado aqui para evitar
                    # "99 10" de "9,99 10,89" → "99,10" falso
                else:
                    # fallback: extrai números de 3 dígitos em qualquer linha sem preço
                    # Ex: "219 * 203" → 2,19 e 2,03 | "918 UNIDADE" → 9,18
                    # O regex exclui números seguidos de letras (evita "500g" → "5,00")
                    # Guarda: ignora linhas com ≥2 palavras longas (nomes de produto)
                    palavras_alfa = re.findall(r"[A-Za-zÀ-ÿ]{3,}", linha)
                    if len(palavras_alfa) <= 1:
                        for m3 in _RE_3DIG.finditer(linha):
                            raw = m3.group(1)
                            _add_res(raw[:-2] + "," + raw[-2:])
                    # Preço com espaço em qualquer linha sem price normal
                    # (ex: "27 90 UNIDADE" → 27,90)
                    for m4 in _RE_ESPACO_LABEL.finditer(linha):
                        cand = m4.group(1) + "," + m4.group(2)
                        _add_res(cand)
        return resultado

    limpos = _filtrar_outliers(_precos_limpos())

    if has_varejo and has_atacado:
        # Busca preços próximos a cada label, parando ao encontrar o outro label
        precos_varejo = _filtrar_outliers(
            _precos_apos_label(_RE_LABEL_VAREJO, parar_em=_RE_LABEL_ATACADO)
        )
        precos_atacado = _filtrar_outliers(
            _precos_apos_label(_RE_LABEL_ATACADO, parar_em=_RE_LABEL_VAREJO)
        )

        if precos_varejo and precos_atacado:
            pu_cand = sorted(precos_varejo, key=lambda x: x[0])[-1][1]
            pa_cand = sorted(precos_atacado, key=lambda x: x[0])[0][1]
            if pa_cand != pu_cand:
                preco_unitario = pu_cand
                preco_atacado = pa_cand
            else:
                # Ambos os labels encontraram o mesmo preço (label antes do preço)
                # → usa lista global de preços do cartaz
                sv = sorted(limpos, key=lambda x: x[0])
                if len(sv) >= 2:
                    preco_atacado = sv[0][1]
                    preco_unitario = sv[-1][1]
                elif sv:
                    preco_unitario = sv[0][1]
        else:
            # Labels na mesma linha ou preços antes dos labels → usa lista global
            # menor dos limpos = atacado; maior = varejo/unitário
            sv = sorted(limpos, key=lambda x: x[0])
            if len(sv) >= 2:
                preco_atacado = sv[0][1]
                preco_unitario = sv[-1][1]
            elif sv:
                preco_unitario = sv[0][1]

    elif has_atacado:
        # Tem label ATACADO mas OCR não leu "VAREJO"
        sv = sorted(limpos, key=lambda x: x[0])
        if len(sv) >= 2:
            # Dois preços: menor = atacado, maior = varejo (não rotulado)
            preco_atacado = sv[0][1]
            preco_unitario = sv[-1][1]
        elif sv:
            # Único preço + label ATACADO → é o preço de atacado; unidade fica vazia
            preco_atacado = sv[0][1]
            preco_unitario = ""

    elif has_varejo and limpos:
        sv = sorted(limpos, key=lambda x: x[0])
        if len(sv) >= 2:
            # Dois preços com label VAREJO: menor = atacado (implícito), maior = varejo
            preco_atacado = sv[0][1]
            preco_unitario = sv[-1][1]
        else:
            preco_unitario = sv[0][1]

    elif limpos:
        sv = sorted(limpos, key=lambda x: x[0])
        has_qty_context = bool(_RE_ATACADO_QTD.search(texto))
        if len(sv) >= 2:
            # Dois preços sem labels legíveis → padrão atacarejo: menor=atacado, maior=varejo.
            # Se há qty_context o menor certamente é atacado; sem qty ainda é a melhor inferência.
            preco_atacado = sv[0][1]
            preco_unitario = sv[-1][1]
        else:
            if has_qty_context:
                # Preço único + quantidade mínima → é preço de atacado; unitário não informado
                preco_atacado = sv[0][1]
                preco_unitario = ""
            else:
                # Preço único sem contexto → preço unitário
                preco_unitario = sv[0][1]

    # --- Quantidade mínima de atacado ---
    # "A PARTIR DE 30 UNID." / "LEVE 3" / fallbacks OCR
    m_qtd = _RE_ATACADO_QTD.search(texto)
    if m_qtd:
        # Regex tem múltiplos grupos alternativos — pega o primeiro não-nulo
        val_qtd = next((g for g in m_qtd.groups() if g is not None), None)
        if val_qtd:
            v_int = int(val_qtd)
            if v_int >= 2:
                qtd_min_atacado = val_qtd

    # Fallback: "N UNIDADE(S)" / "N PACOTE(S)" em linha sem preço
    # Ex: "6 UNIDADES" / "2 PACOTES" — mas NÃO casa "27 90 UNIDADE" (linha tem preço)
    if not qtd_min_atacado:
        _RE_QTD_UNID = re.compile(
            r"(?<![\d,.])(\d{1,3})\s*(?:unidade[s]?|unid\.?|pacote[s]?)\b",
            re.IGNORECASE,
        )
        _RE_TEM_PRECO = re.compile(
            r"\d{1,3}[.,]\d{2}"  # formato normal: 27,90
            r"|\b\d{1,3}\s+\d{2}\b"  # espaço-separado: 27 90
        )
        for _linha in linhas:
            if _RE_TEM_PRECO.search(_linha):
                continue  # linha com preço: UNIDADE é label de unidade, não qty
            m_u = _RE_QTD_UNID.search(_linha)
            if m_u:
                v_u = int(m_u.group(1))
                if 2 <= v_u <= 999:
                    qtd_min_atacado = str(v_u)
                    break

    # "CX 12 RS 110,16" → qtd_min=12, preco_atacado=110,16/12=9,18 (preço POR UNIDADE)
    _RE_CX = re.compile(
        r"\bcx\s+(\d+)\s+(?:r\$|rs|r\s*\$)?\s*(\d{1,3}(?:[.,]\s*\d{2}|\s\d{2}))",
        re.IGNORECASE,
    )
    m_cx_list = _RE_CX.findall(texto)
    if m_cx_list:
        # Pode haver múltiplas linhas CX no OCR (uma corrompida, outra certa)
        # Usa a que tiver o maior total — a correta será a mais alta
        melhor = max(m_cx_list, key=lambda m: _to_float(m[1]))
        qtd_cx = int(melhor[0])
        qtd_min_atacado = str(qtd_cx)
        # Calcula preço por unidade via CX quando atacado ainda não foi encontrado.
        # Mesmo com labels ATACADO/VAREJO, o OCR pode ter fragmentado o preço atacado
        # em múltiplas linhas (ex: "1","0","9" em vez de "10,09") → CX é mais confiável.
        # O max() já descarta linhas CX corrompidas (ex: "38 70" vs "302 70").
        if not preco_atacado and qtd_cx > 0:
            total_cx = _to_float(melhor[1])
            preco_unit_cx = total_cx / qtd_cx
            preco_atacado = f"{preco_unit_cx:.2f}".replace(".", ",")
    elif not qtd_min_atacado:
        # Fallback: CX sem preço
        m_cx_simples = re.search(r"\bcx\s+(\d+)\b", texto, re.IGNORECASE)
        if m_cx_simples:
            qtd_min_atacado = m_cx_simples.group(1)

    # Se o preço atacado for igual ao unitário, não há desconto → limpa os campos
    sem_desconto_atacado = False
    if preco_atacado and preco_unitario:
        try:
            if abs(_to_float(preco_atacado) - _to_float(preco_unitario)) < 0.005:
                preco_atacado = ""
                qtd_min_atacado = ""
                sem_desconto_atacado = True
        except (ValueError, TypeError):
            pass

    return {
        "nome": nome,
        "peso_volume": peso_volume,
        "preco_unitario": preco_unitario,
        "preco_atacado": preco_atacado,
        "qtd_min_atacado": qtd_min_atacado,
        "sem_desconto_atacado": sem_desconto_atacado,
    }
