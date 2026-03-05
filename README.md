# PriceScan

Sistema web para controle de compras de feira com leitura automática de cartazes de preço via OCR. O usuário tira uma foto do cartaz, o sistema preenche nome, peso, preço unitário e regra de atacado automaticamente; basta confirmar, corrigir se necessário e informar a quantidade.

## Funcionalidades

- **Autenticação**: cadastro e login com e-mail (Django auth nativo)
- **Painel de feiras**:
  - Cards de resumo: total de feiras, feiras ativas e valor em aberto
  - Lista de feiras com status, contagem de itens e data relativa ("há 2 horas")
  - Cards (mobile) e linhas da tabela (desktop) clicáveis — navegam diretamente para a feira
- **Criar feira**: abre nova feira via modal de confirmação — bloqueado se já houver uma feira ativa (deve finalizar antes)
- **Escanear cartaz** *(fluxo OCR)*:
  1. Upload da foto do cartaz → validação de qualidade (resolução, brilho, desfoque)
  2. OCR em 3 passes (Tesseract PSM 6 / 3 / 11) com pré-processamento via OpenCV
  3. **Etapa 1** — confirmar dados: nome, peso/volume, preço unitário, regra de atacado
  4. **Etapa 2** — informar quantidade com preview do total em tempo real
- **Adicionar produto manualmente**: formulário clássico sem OCR
- **Lista da compra**:
  - Itens com foto, preço total por item (respeita regra de atacado) e total geral
  - Clicar em qualquer item abre modal de detalhes com foto do cartaz, preços e texto bruto do OCR — útil para conferência no caixa
- **Remover item**: remove produto da feira ativa
- **Editar quantidade**: altera a quantidade de um item já adicionado
- **Editar orçamento**: renomeia a feira
- **Perfil**: página do usuário logado
- **Finalizar feira**: confirmação via modal antes de mudar status para `finalizada`, bloqueando edições
- **Excluir feira**: remove permanentemente feiras finalizadas com confirmação via modal
- **Navegação**: botão "Voltar" visível em todas as páginas internas
- **Regra de negócio**: não é possível criar nova feira enquanto houver uma ativa
- **Layout responsivo**: mobile-first com Bootstrap 5.3.3

## Tecnologias

| Camada               | Tecnologia                          |
|----------------------|-------------------------------------|
| Backend              | Django 6.0.2                        |
| Banco (produção)     | PostgreSQL 16                       |
| Banco (dev local)    | SQLite (fallback automático)        |
| Frontend             | Bootstrap 5.3.3 (CDN)              |
| OCR                  | Tesseract + pytesseract             |
| Visão computacional  | OpenCV (`opencv-python-headless`)   |
| Imagens              | Pillow + ImageField                 |
| Armazenamento        | DigitalOcean Spaces (S3-compatible) |
| Auth                 | Django built-in auth                |
| Rate limiting        | django-ratelimit                    |
| Servidor WSGI        | Gunicorn                            |
| Proxy reverso        | Nginx                               |
| Containerização      | Docker + Docker Compose             |

## Modelos

```
Compra
  usuario           FK → User
  data              DateTimeField (auto_now_add)
  status            CharField: "ativa" | "finalizada"
  nome_orcamento    CharField(200)
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

| Método   | URL                                                | View                  | Descrição                            |
|----------|----------------------------------------------------|---------------------- |--------------------------------------|
| GET      | `/`                                                | `painel_compras`      | Painel de feiras                     |
| POST     | `/compras/nova/`                                   | `criar_compra`        | Cria nova feira                      |
| GET/POST | `/compras/<id>/adicionar/`                         | `adicionar_produto`   | Adiciona item manualmente            |
| GET      | `/compras/<id>/`                                   | `lista_compra`        | Detalhe da feira                     |
| POST     | `/compras/<id>/remover-item/<item_id>/`            | `remover_item`        | Remove um item                       |
| POST     | `/compras/<id>/itens/<item_id>/editar-quantidade/` | `editar_quantidade`   | Altera quantidade de um item         |
| POST     | `/compras/<id>/editar-orcamento/`                  | `editar_orcamento`    | Renomeia a feira                     |
| POST     | `/compras/<id>/finalizar/`                         | `finalizar_compra`    | Finaliza a feira                     |
| POST     | `/compras/<id>/excluir/`                           | `excluir_compra`      | Exclui feira finalizada              |
| GET/POST | `/compras/<id>/escanear/`                          | `escanear_cartaz`     | Upload e análise do cartaz           |
| POST     | `/compras/<id>/confirmar/`                         | `confirmar_produto`   | Etapa 1: revisar dados do OCR        |
| POST     | `/compras/<id>/quantidade/`                        | `informar_quantidade` | Etapa 2: informar quantidade e salvar|
| GET/POST | `/accounts/register/`                              | `register`            | Cadastro                             |
| GET/POST | `/accounts/login/`                                 | *(Django auth)*       | Login                                |
| GET      | `/perfil/`                                         | `perfil`              | Página do perfil do usuário          |

## Estrutura do projeto

```
PriceScan/
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── nginx.conf
├── .env.example
├── .gitignore
├── .dockerignore
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
    ├── ocr.py                  ← módulo OCR (ver README_OCR.md)
    ├── migrations/
    ├── static/
    │   └── css/style.css
    ├── templates/
    │   ├── painel_compras.html
    │   ├── lista_compra.html
    │   ├── adicionar_produto.html
    │   ├── escanear_cartaz.html
    │   ├── confirmar_produto.html
    │   ├── informar_quantidade.html
    │   ├── perfil.html
    │   └── registration/
    │       ├── login.html
    │       └── register.html
    └── tests/
        ├── test_models.py
        ├── test_views.py
        ├── test_forms.py
        ├── test_backends.py
        └── test_ocr.py
```

## Instalação (desenvolvimento local)

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

# Copiar e preencher variáveis de ambiente
copy .env.example .env        # Windows
cp .env.example .env          # Linux/macOS
# Edite o .env — preencha SECRET_KEY e TESSERACT_CMD (Windows)

# Aplicar migrações (usa SQLite automaticamente se POSTGRES_DB não estiver definido)
python manage.py migrate

# Criar usuário administrador
python manage.py createsuperuser

# Iniciar servidor de desenvolvimento
python manage.py runserver
```

Acesse em: http://127.0.0.1:8000/

### 3. Variáveis de ambiente

Veja o arquivo `.env.example` para a lista completa. As principais para desenvolvimento:

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `SECRET_KEY` | Sim | Chave secreta do Django |
| `DEBUG` | Não | `true` para dev (padrão), `false` para produção |
| `TESSERACT_CMD` | Windows | Caminho do executável do Tesseract |
| `TESSERACT_LANG` | Não | Idioma OCR (padrão: `por`) |

> Sem `POSTGRES_DB`, o sistema usa SQLite automaticamente.  
> Sem `DO_SPACES_BUCKET`, uploads ficam em memória (sem persistência em dev).

## Deploy com Docker (produção)

### Pré-requisitos

- Docker e Docker Compose instalados no servidor
- Conta na DigitalOcean com Spaces configurado (ou outro S3-compatible)

### 1. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com valores de produção:

```env
SECRET_KEY=<chave-segura-gerada>
DEBUG=false
ALLOWED_HOSTS=seu-dominio.com
CSRF_TRUSTED_ORIGINS=https://seu-dominio.com

POSTGRES_DB=pricescan
POSTGRES_USER=pricescan
POSTGRES_PASSWORD=<senha-forte>
POSTGRES_HOST=db

DO_SPACES_KEY=<sua-key>
DO_SPACES_SECRET=<seu-secret>
DO_SPACES_BUCKET=<nome-do-bucket>
DO_SPACES_ENDPOINT=https://sfo3.digitaloceanspaces.com
```

### 2. Subir os containers

```bash
docker compose up -d --build
```

Isso inicia três serviços:

| Serviço | Descrição |
|---------|-----------|
| `db` | PostgreSQL 16 com healthcheck |
| `web` | Django + Gunicorn (porta 8000 interna) |
| `nginx` | Proxy reverso na porta 80, serve arquivos estáticos |

O `entrypoint.sh` aguarda o banco ficar disponível, roda as migrações e inicia o Gunicorn automaticamente.

### 3. Criar superusuário (primeira vez)

```bash
docker compose exec web python manage.py createsuperuser
```

### 4. Logs e manutenção

```bash
docker compose logs -f web       # logs da aplicação
docker compose restart web       # reiniciar sem rebuild
docker compose down              # parar tudo
docker compose up -d --build     # rebuild após alterações
```

## Segurança

- **Headers de segurança** (produção): HSTS, cookies seguros, CSP, X-Frame-Options
- **Rate limiting**: registro (10/min por IP), escanear cartaz (20/min por usuário)
- **Upload**: máximo 10 MB por imagem (validado no form e no Nginx)
- **Armazenamento**: fotos enviadas para DigitalOcean Spaces — nada fica no filesystem local
- **Credenciais**: todas em `.env`, nunca commitadas (`.gitignore` protege)

## Pós-deploy — o que falta configurar

### Domínio + DNS
- Registrar um domínio e apontar o **A record** para o IP do servidor
- Atualizar `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` no `.env`
- Reiniciar: `docker compose restart web`

### HTTPS / SSL
- **Opção A**: Certbot direto no servidor:
  ```bash
  sudo apt install certbot python3-certbot-nginx
  sudo certbot --nginx -d seu-dominio.com
  ```
- **Opção B**: Load balancer da DigitalOcean com SSL termination (mais simples)
- Depois de ativar HTTPS, as configs de segurança do Django (HSTS, secure cookies, SSL redirect) ativam automaticamente com `DEBUG=false`

### Criar superusuário
```bash
docker compose exec web python manage.py createsuperuser
```

### Opcional: Email SMTP
Hoje usa console backend (emails só aparecem nos logs). Para envio real (reset de senha etc.), configurar no `.env`:
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu@email.com
EMAIL_HOST_PASSWORD=sua-app-password
```

### Opcional: Redis
Hoje usa cache em memória local. Para cache distribuído + rate limiting mais robusto, adicionar Redis no `docker-compose.yml` e no `.env`:
```env
REDIS_URL=redis://redis:6379/1
```

## Testes

```bash
python manage.py test src.tests
```

122 testes cobrindo models, views, forms, backends e OCR.

## Licença

MIT — veja o arquivo [LICENSE](LICENSE).
