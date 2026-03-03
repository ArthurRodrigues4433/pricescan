from django.urls import path
from .views import (
    adicionar_produto,
    criar_compra,
    painel_compras,
    lista_compra,
    remover_item,
    finalizar_compra,
    excluir_compra,
    register,
)

app_name = "src"

urlpatterns = [
    path("", painel_compras, name="painel_compras"),
    path("compras/nova/", criar_compra, name="criar_compra"),
    path(
        "compras/<int:compra_id>/adicionar/",
        adicionar_produto,
        name="adicionar_produto",
    ),
    path("compras/<int:compra_id>/", lista_compra, name="lista_compra"),
    path(
        "compras/<int:compra_id>/remover-item/<int:item_id>/",
        remover_item,
        name="remover_item",
    ),
    path(
        "compras/<int:compra_id>/finalizar/", finalizar_compra, name="finalizar_compra"
    ),
    path("compras/<int:compra_id>/excluir/", excluir_compra, name="excluir_compra"),
    path("accounts/register/", register, name="register"),
]
