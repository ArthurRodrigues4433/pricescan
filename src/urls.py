from django.urls import path
from .views import (
    adicionar_produto,
    criar_compra,
    lista_compra,
    remover_item,
    finalizar_compra,
)

urlpatterns = [
    path("", criar_compra, name="criar_compra"),
    path("compras/<int:compra_id>/adicionar/", adicionar_produto, name="adicionar_produto"),
    path("compras/<int:compra_id>/", lista_compra, name="lista_compra"),
    path("compras/<int:compra_id>/remover-item/<int:item_id>/", remover_item, name="remover_item"),
    path("compras/<int:compra_id>/finalizar/", finalizar_compra, name="finalizar_compra"),
]
