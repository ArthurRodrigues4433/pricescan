# PriceScan — Módulo OCR (`src/ocr.py`)

Referência técnica do módulo de leitura automática de cartazes de preço de atacarejo.

---

## Visão geral

O módulo expõe três funções públicas, executadas em sequência pelo fluxo de escaneamento:

```
foto → checar_qualidade() → extrair_texto() → parsear_cartaz() → dict de campos
```

---

## `checar_qualidade(caminho, checar_resolucao=True) → (bool, str)`

Valida se a imagem tem qualidade suficiente para OCR antes de chamar o Tesseract.

| Checagem | Critério de reprovação | Lib |
|---|---|---|
| Resolução mínima | Largura **ou** altura < 640 px | Pillow |
| Brilho médio | < 40 (muito escura) ou > 220 (superexposta) | Pillow |
| Desfoque (variância do Laplaciano) | < 10 | OpenCV |

Retorna `(True, "")` se aprovada, ou `(False, "mensagem")` se reprovada.

> O limiar de desfoque é propositalmente baixo (10) para aceitar fotos de tela usadas em testes.

---

## `extrair_texto(caminho) → str`

### Pipeline de pré-processamento

1. Abre com Pillow e converte para escala de cinza
2. Redimensiona para no mínimo **2400 px de largura** (necessário para texto pequeno)
3. Aplica `ImageOps.autocontrast`
4. Binarização Otsu via OpenCV (`THRESH_BINARY + THRESH_OTSU`)

### 3 passes OCR (Tesseract, idioma `por`)

| Passo | PSM | Foco |
|---|---|---|
| 1 | 6 (bloco uniforme) | Texto denso — nome, labels |
| 2 | 3 (layout automático) | Texto em colunas / tamanhos mistos |
| 3 | 11 (texto esparso) | Números grandes isolados (preços) |

As três saídas são concatenadas, eliminando linhas duplicadas.

---

## `parsear_cartaz(texto) → dict`

Retorna:

```python
{
    "nome": str,              # nome do produto
    "peso_volume": str,       # ex: "5kg", "900ml", "1,6kg"
    "preco_unitario": str,    # ex: "19,98"
    "preco_atacado": str,     # ex: "18,90"
    "qtd_min_atacado": str,   # ex: "6"
    "sem_desconto_atacado": bool,  # True quando os dois preços são iguais
}
```

Campos não encontrados retornam `""`. A `quantidade` **nunca é extraída** — o usuário informa na Etapa 2.

---

### Extração do nome

**Estratégia por frequência:**  
Coleta candidatos de linhas com ≥ 65 % de caracteres limpos e ≥ 4 letras, filtra por uma blocklist e escolhe o candidato que mais se repete entre os três passes — porque o nome do produto aparece 2–3× no OCR enquanto lixo aparece uma vez.

**Blocklist de linhas não-nome:**  
`varejo`, `atacado`, `promoção`, `unidade`, `unid`, `a partir`, `apartir`, `plu`, `r$`, `rs`, `preco`, `preço`, `atacad*`, `limitado`, `oferta`, `por cliente`

**Tiebreaker:** em caso de empate na frequência, prefere candidatos com unidade de medida (`140g`, `5KG`) sobre fragmentos numéricos (`1408`, `SKG`).

---

### Extração de peso/volume

Regex: `(\d+[,.]?\d*)\s*(kg|g|gr|ml|l|lt|un|unid)`  
Varre linha a linha, ignorando linhas de contexto (por KG, equivalente, CX, datas).

---

### Extração de preços

#### Linhas bloqueadas (`_RE_LINHA_CONTEXTO`)

Linhas com qualquer um destes padrões são ignoradas na extração de preço:

| Padrão | Exemplo |
|---|---|
| `\bcx\b.*\d` | `CX 30 R$ 302,70` |
| `equi[vl]` | `EQUIVALENTE`, `EQUIV` |
| `por\s+k[g6]`, `/\s*k[g6]`, `\bk[g6]\b` | `POR KG`, `/KG` |
| `\d{1,2}/\d{1,2}/\d{2,4}` | datas `19/02/26` |
| `\bpartir\b` | `A PARTIR DE 30 UNID.` |
| `\bunid\b` | `UNIDADE`, `UNID.` |
| `\bpor\s+litro\b` | `PRECO POR LITRO` |
| `\d{6,}` | código de barras / PLU / EAN |
| `\d%` | `2,36%/kg` — percentagem |

#### Estratégias de detecção de preço (em cascata)

1. **Preço com vírgula/ponto:** `R?\$?\s*(\d{1,3}[.,]\s*\d{2})` — formato normal
2. **3 dígitos sem separador em linha sem palavras duplas:** `219` → `2,19`  
   O regex exclui números seguidos de letras (`500g` não vira `5,00`).  
   Linhas com ≥ 2 palavras longas (nomes de produto) são ignoradas.
3. **Preço com espaço inline (apenas quando nenhum preço normal foi encontrado na linha):**  
   `27 90 UNIDADE` → `27,90`  
   Não é aplicado quando a linha já tem preço com separador (evita `22 50 23,90` → `50,23`).
4. **Pré-passo A — preço partido em duas linhas:**  
   Linha com 1–3 dígitos + linha com exatamente 2 dígitos → `"9" + "18"` = `9,18`
5. **Pré-passo B — dígito + preço na linha seguinte:**  
   `"1"` + `"4,90"` = `14,90`

#### Filtro de outliers

Remove preços > 20× o menor preço da lista (elimina artefatos OCR como `494,49` quando o real é `4,49`). O filtro nunca descarta abaixo de R$ 50.

---

### Detecção de labels ATACADO / VAREJO

Os labels usam regex tolerante a erros OCR:

```
ATACADO → at[a@][cgq][a@4]d[o0ãÃaoÃµ] | at[a@]g[a@]d[o0] | at[a@]c\s*[a@]d[o0ãÃ]
VAREJO  → var[e3][j\]i][o0]
```

#### Lógica de atribuição dos preços

| Labels detectados | Preços encontrados | Resultado |
|---|---|---|
| ATACADO + VAREJO | 2 preços (um perto de cada label) | menor = atacado, maior = unitário |
| ATACADO + VAREJO | mesmo preço em ambos | usa lista global: menor = atacado, maior = unitário |
| Só ATACADO | 2 preços | menor = atacado, maior = unitário |
| Só ATACADO | 1 preço | → **preco_atacado** (unitário fica vazio) |
| Só VAREJO | 2 preços | menor = atacado implícito, maior = unitário |
| Só VAREJO | 1 preço | → **preco_unitario** |
| Sem labels + quantidade detectada | 2 preços | menor = atacado, maior = unitário |
| Sem labels + quantidade detectada | 1 preço | → **preco_atacado** (unitário fica vazio) |
| Sem labels, sem quantidade | qualquer | menor preço = unitário |

---

### Detecção de quantidade mínima

**Regex principal (`_RE_ATACADO_QTD`)** — tolerante a OCR garble:

```
(leve|a partir de|acima de|com) \d+
apartirdes? \d+
partir (?:de)? \d+
/\d{2,3}   ← OCR funde "A PARTIR DE 12" → "/12"
```

**Fallback: `N UNIDADE(S)` / `N PACOTE(S)`** em linhas sem preço.  
Linhas com preço são ignoradas para evitar `"27 90 UNIDADE"` → qtd=90.

**CX total:** `CX 30 R$ 302,70` → qtd_min=30 e preco_atacado=302,70/30=10,09.

---

## Script de teste

```bash
python testar_cartazes.py
```

Processa todas as imagens em `testes_cartaz/` e exibe para cada uma:
- Texto bruto consolidado do OCR
- Campos extraídos: nome, peso_volume, preco_unit, preco_atac, qtd_min

---

## Dependências

```bash
pip install -r requirements.txt
```

Binário externo: **Tesseract OCR** com pacote de idioma `por`  
→ https://github.com/UB-Mannheim/tesseract/wiki (Windows)  
→ `sudo apt install tesseract-ocr tesseract-ocr-por` (Linux)

> No deploy com Docker, o Tesseract e o pacote `por` já são instalados automaticamente pela imagem — veja o `Dockerfile`.
