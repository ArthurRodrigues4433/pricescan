# PriceScan

Sistema web para controle de compras de feira. Permite criar feiras, adicionar produtos com foto e valores, acompanhar o total em tempo real e finalizar ou excluir feiras.

## Funcionalidades

- **Autenticação**: login obrigatório em todas as rotas (Django auth nativo)
- **Painel de feiras**: lista todas as feiras do usuário com status, data e total
- **Criar feira**: abre uma nova feira com status `ativa`
- **Adicionar produtos**: formulário com nome, preço unitário, quantidade e foto (opcional)
- **Lista da compra**: exibe itens com foto, totais por item e total geral
- **Remover item**: remove um produto da feira ativa
- **Finalizar feira**: muda status para `finalizada`, bloqueando edições
- **Excluir feira**: remove permanentemente feiras finalizadas, com confirmação via modal
- **Feedback visual**: mensagem de sucesso ao adicionar cada produto
- **Layout responsivo**: mobile com lista scrollável e botão "Finalizar" fixo no rodapé; desktop com tabela

## Tecnologias

| Camada     | Tecnologia               |
|------------|--------------------------|
| Backend    | Django 4+                |
| Banco      | SQLite (desenvolvimento) |
| Frontend   | Bootstrap 5.3.3 (CDN)    |
| Imagens    | Pillow + ImageField       |
| Auth       | Django built-in auth     |

## Modelos

```
Compra
  usuario       FK → User
  data          DateTimeField (auto)
  status        CharField: ativa | finalizada
  total()       → soma dos preco_total() dos itens

ItemCompra
  compra        FK → Compra (related_name="itens")
  nome          CharField
  preco_unitario DecimalField
  quantidade    DecimalField
  foto          ImageField (upload_to="produtos/")
  preco_total() → preco_unitario × quantidade
```

## Rotas

| Método | URL                                          | View               | Descrição                        |
|--------|----------------------------------------------|--------------------|----------------------------------|
| GET    | `/`                                          | painel_compras     | Lista todas as feiras do usuário |
| POST   | `/compras/nova/`                             | criar_compra       | Cria nova feira                  |
| GET/POST | `/compras/<id>/adicionar/`               | adicionar_produto  | Formulário de item               |
| GET    | `/compras/<id>/`                             | lista_compra       | Detalhe de uma feira             |
| POST   | `/compras/<id>/remover-item/<item_id>/`      | remover_item       | Remove um item                   |
| POST   | `/compras/<id>/finalizar/`                   | finalizar_compra   | Finaliza a feira                 |
| POST   | `/compras/<id>/excluir/`                     | excluir_compra     | Exclui feira finalizada          |

## Estrutura

```
PriceScan/
├── manage.py
├── db.sqlite3
├── media/
│   └── produtos/          ← uploads de fotos
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
    ├── migrations/
    └── templates/
        ├── painel_compras.html
        ├── lista_compra.html
        ├── adicionar_produto.html
        └── registration/
            └── login.html
```

## Como rodar

```bash
# 1. Clone e entre na pasta
git clone <repo-url>
cd PriceScan

# 2. Crie e ative o ambiente virtual
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 3. Instale as dependências
pip install django pillow

# 4. Migrações
python manage.py migrate

# 5. Crie um usuário
python manage.py createsuperuser

# 6. Rode o servidor
python manage.py runserver
```

Acesse em: http://127.0.0.1:8000/

> **Nota:** o serviço de arquivos de mídia (`MEDIA_URL`) funciona apenas com `DEBUG = True`. Para produção, configure um servidor de arquivos estáticos adequado (ex: whitenoise, S3).

## Licença

MIT — veja o arquivo [LICENSE](LICENSE).
