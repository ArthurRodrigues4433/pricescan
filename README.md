# PriceScan

Sistema web para controle de compras de feira com leitura automática de cartazes de preço via OCR. O usuário tira uma foto do cartaz, o sistema preenche nome, peso, preço unitário e regra de atacado automaticamente; basta confirmar, corrigir se necessário e informar a quantidade.

## Funcionalidades

- **Autenticação**: cadastro e login com e-mail (Django auth nativo)
- **Painel de feiras**: lista todas as feiras do usuário com status, data e total
- **Criar feira**: abre nova feira com status `ativa`
- **Escanear cartaz** *(fluxo OCR)*:
  1. Upload da foto do cartaz → validação de qualidade (resolução, brilho, desfoque)
  2. OCR em 3 passes (Tesseract PSM 6 / 3 / 11) com pré-processamento via OpenCV
  3. **Etapa 1** — confirmar dados: nome, peso/volume, preço unitário, regra de atacado
  4. **Etapa 2** — informar quantidade com preview do total em tempo real
- **Adicionar produto manualmente**: formulário clássico sem OCR
- **Lista da compra**: itens com foto, preço total por item (respeita regra de atacado) e total geral
- **Remover item**: remove produto da feira ativa
- **Finalizar feira**: muda status para `finalizada`, bloqueando edições
- **Excluir feira**: remove permanentemente feiras finalizadas com confirmação via modal
- **Layout responsivo**: mobile-first com Bootstrap 5

## Tecnologias

| Camada               | Tecnologia               |
|----------------------|--------------------------|
| Backend              | Django 5+                |
| Banco                | SQLite (desenvolvimento) |
| Frontend             | Bootstrap 5.3.3 (CDN)   |
| OCR                  | Tesseract + pytesseract  |
| Visão computacional  | OpenCV (`opencv-python`) |
| Imagens              | Pillow + ImageField      |
| Auth                 | Django built-in auth     |

## Modelos

```
Compra
  usuario           FK → User
  data              DateTimeField (auto_now_add)
  status            CharField: "ativa" | "finalizada"
  total()           → soma dos preco_total() dos itens

ItemCompra
  compra            FK → Compra (related_name="itens")
  nome              CharField(200)
  preco_unitario    DecimalField(10, 2)
  quantidade        DecimalField(10, 2)
  foto              ImageField (upload_to="produtos/")
  peso_volume       CharField(50)       ← preenchido pelo OCR
  preco_atacado     DecimalField        ← preenchido pelo OCR
  qtd_min_atacado   PositiveIntegerField← preenchido pelo OCR
  ocr_texto         TextField           ← texto bruto lido pelo Tesseract

  preco_total()     → se quantidade ≥ qtd_min_atacado: usa preco_atacado
                      caso contrário: usa preco_unitario
```

## Rotas

| Método   | URL                                                | View                | Descrição                            |
|----------|----------------------------------------------------|---------------------|--------------------------------------|
| GET      | `/`                                                | `painel_compras`    | Painel de feiras                     |
| POST     | `/compras/nova/`                                   | `criar_compra`      | Cria nova feira                      |
| GET/POST | `/compras/<id>/adicionar/`                         | `adicionar_produto` | Adiciona item manualmente            |
| GET      | `/compras/<id>/`                                   | `lista_compra`      | Detalhe da feira                     |
| POST     | `/compras/<id>/remover-item/<item_id>/`            | `remover_item`      | Remove um item                       |
| POST     | `/compras/<id>/finalizar/`                         | `finalizar_compra`  | Finaliza a feira                     |
| POST     | `/compras/<id>/excluir/`                           | `excluir_compra`    | Exclui feira finalizada              |
| GET/POST | `/compras/<id>/escanear/`                          | `escanear_cartaz`   | Upload e análise do cartaz           |
| POST     | `/compras/<id>/confirmar/`                         | `confirmar_produto` | Etapa 1: revisar dados do OCR        |
| POST     | `/compras/<id>/quantidade/`                        | `informar_quantidade`| Etapa 2: informar quantidade e salvar|
| GET/POST | `/accounts/register/`                              | `register`          | Cadastro                             |
| GET/POST | `/accounts/login/`                                 | *(Django auth)*     | Login                                |

## Estrutura do projeto

```
PriceScan/
├── manage.py
├── db.sqlite3
├── testar_cartazes.py          ← script de teste do OCR (desenvolvimento)
├── testes_cartaz/              ← imagens de teste (não vai para produção)
├── media/
│   ├── produtos/               ← uploads das fotos dos itens
│   └── tmp/                    ← imagens temporárias do OCR
├── pricescan/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py / asgi.py
└── src/
    ├── models.py
    ├── views.py
    ├── urls.py
    ├── forms.py
    ├── admin.py
    ├── backends.py
    ├── ocr.py                  ← módulo OCR
    ├── migrations/
    └── templates/
        ├── painel_compras.html
        ├── lista_compra.html
        ├── adicionar_produto.html
        ├── escanear_cartaz.html
        ├── confirmar_produto.html
        ├── informar_quantidade.html
        └── registration/
            ├── login.html
            └── register.html
```

## Instalação

### 1. Instalar o Tesseract (binário do sistema)

O Tesseract **não é** um pacote Python — é um programa externo instalado separadamente.

**Windows:** baixe o instalador em https://github.com/UB-Mannheim/tesseract/wiki  
Durante a instalação, selecione o pacote de idioma **Portuguese**.

```bash
# Linux (Ubuntu/Debian)
sudo apt install tesseract-ocr tesseract-ocr-por

# macOS
brew install tesseract
```

### 2. Clonar e configurar o projeto

```bash
git clone <repo-url>
cd PriceScan

# Criar e ativar ambiente virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

# Instalar dependências Python
pip install -r requirements.txt

# Configurar variáveis de ambiente
copy .env.example .env        # Windows
cp .env.example .env          # Linux/macOS
# Edite o .env e preencha SECRET_KEY e TESSERACT_CMD

# Aplicar migrações
python manage.py migrate

# Criar usuário administrador
python manage.py createsuperuser

# Iniciar servidor de desenvolvimento
python manage.py runserver
```

Acesse em: http://127.0.0.1:8000/

### 3. Configurar variáveis de ambiente

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/macOS
```

Edite o `.env` gerado:

```env
SECRET_KEY=<gere uma chave em https://djecrety.ir/>
DEBUG=True
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe   # somente Windows
TESSERACT_LANG=por
```

Em Linux/macOS, `TESSERACT_CMD` pode ficar em branco (o binário já está no PATH).

### 4. Testar o OCR (opcional)

Coloque fotos de cartazes na pasta `testes_cartaz/` e execute:

```bash
python testar_cartazes.py
```

O script processa cada imagem e exibe o texto bruto lido e os campos extraídos.

## Dependências Python

```
Django==6.0.2
Pillow==12.1.1
pytesseract==0.3.13
opencv-python==4.13.0.92
python-dotenv==1.2.2
```

> Instale com `pip install -r requirements.txt`.

> **Nota de produção:** `MEDIA_URL` só serve arquivos com `DEBUG = True`. Para produção, configure armazenamento de arquivos adequado (ex: whitenoise, AWS S3). O `db.sqlite3` deve ser substituído por PostgreSQL ou MySQL.

## Licença

MIT — veja o arquivo [LICENSE](LICENSE).
