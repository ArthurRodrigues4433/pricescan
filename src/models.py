from django.db import models
from django.contrib.auth.models import User


class Compra(models.Model):
    STATUS_CHOICES = [('ativa', 'Ativa'), ('finalizada', 'Finalizada')]
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    data = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativa')

    def total(self):
        return sum(item.preco_total() for item in self.itens.all())


class ItemCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name="itens")
    nome = models.CharField(max_length=200)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    foto = models.ImageField(upload_to="produtos/")

    def preco_total(self):
        return self.preco_unitario * self.quantidade
