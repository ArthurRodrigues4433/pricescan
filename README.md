# PriceScan - MVP

## Descrição
Sistema web simples para controle de compras em feiras e mercados. O usuário pode adicionar produtos com foto, nome, preço unitário e quantidade. O sistema calcula automaticamente o total individual e o total geral da compra, exibindo tudo em uma lista organizada.

## Funcionalidades
- Cadastro de produtos com foto, nome, preço unitário e quantidade
- Cálculo automático do total de cada item e do total geral
- Upload de imagens dos produtos
- Visualização da lista de compras com fotos e totais
- Interface simples e profissional

## Tecnologias Utilizadas
- Backend: Django
- Banco de dados: SQLite
- Frontend: Django Templates + CSS simples
- Upload de imagem: ImageField do Django

## Estrutura do Projeto
```
PriceScan/
├── db.sqlite3
├── manage.py
├── pricescan/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── src/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── forms.py
    ├── models.py
    ├── tests.py
    ├── views.py
    ├── urls.py
    ├── templates/
    │   ├── adicionar_produto.html
    │   └── lista_compra.html
    └── migrations/
        └── __init__.py
```

## Como rodar o projeto
1. Clone o repositório e acesse a pasta do projeto.
2. Crie e ative um ambiente virtual:
   ```
   python -m venv venv
   venv\Scripts\activate  # Windows
   # ou
   source venv/bin/activate  # Linux/Mac
   ```
3. Instale as dependências:
   ```
   pip install django pillow
   ```
4. Faça as migrações:
   ```
   python manage.py makemigrations
   python manage.py migrate
   ```
5. Crie um superusuário:
   ```
   python manage.py createsuperuser
   ```
6. Rode o servidor:
   ```
   python manage.py runserver
   ```
7. Acesse:
   - Admin: http://127.0.0.1:8000/admin
   - Adicionar produto: http://127.0.0.1:8000/adicionar/
   - Lista de compras: http://127.0.0.1:8000/lista/

## Observações
- O upload de imagens funciona apenas em modo DEBUG.
- O sistema está pronto para ser expandido com novas funcionalidades, como histórico de compras, login obrigatório, etc.

## Licença
Este projeto é open source, licenciado sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

## Contribuição
Contribuições são bem-vindas! Sinta-se à vontade para abrir issues, enviar pull requests ou sugerir melhorias.
