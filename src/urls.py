from django.urls import path
from .views import (
    adicionar_produto,
    criar_compra,
    painel_compras,
    lista_compra,
    remover_item,
    editar_quantidade,
    finalizar_compra,
    excluir_compra,
    register,
    perfil,
    escanear_cartaz,
    confirmar_produto,
    informar_quantidade,
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
        "compras/<int:compra_id>/itens/<int:item_id>/editar-quantidade/",
        editar_quantidade,
        name="editar_quantidade",
    ),
    path(
        "compras/<int:compra_id>/finalizar/", finalizar_compra, name="finalizar_compra"
    ),
    path("compras/<int:compra_id>/excluir/", excluir_compra, name="excluir_compra"),
    path("accounts/register/", register, name="register"),
    path("perfil/", perfil, name="perfil"),
    # OCR
    path("compras/<int:compra_id>/escanear/", escanear_cartaz, name="escanear_cartaz"),
    path(
        "compras/<int:compra_id>/confirmar/",
        confirmar_produto,
        name="confirmar_produto",
    ),
    path(
        "compras/<int:compra_id>/quantidade/",
        informar_quantidade,
        name="informar_quantidade",
    ),
]
