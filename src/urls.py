from django.urls import path
from .views import adicionar_produto, lista_compra

urlpatterns = [
    path("adicionar/", adicionar_produto, name="adicionar_produto"),
    path("lista/", lista_compra, name="lista_compra"),
]
