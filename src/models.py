from django.db import models
from django.contrib.auth.models import User


class Compra(models.Model):
    STATUS_CHOICES = [("ativa", "Ativa"), ("finalizada", "Finalizada")]
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    data = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ativa")
    nome = models.CharField(max_length=100, blank=True, default="")
    orcamento = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def total(self):
        return sum(item.preco_total() for item in self.itens.all())  # type: ignore


class ItemCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name="itens")
    nome = models.CharField(max_length=200)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    foto = models.ImageField(upload_to="produtos/", blank=True)

    # Campos do módulo OCR
    peso_volume = models.CharField(max_length=50, blank=True, default="")
    preco_atacado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    qtd_min_atacado = models.PositiveIntegerField(null=True, blank=True)
    ocr_texto = models.TextField(blank=True, default="")  # texto bruto lido pelo OCR

    def preco_total(self):
        if self.preco_atacado and self.qtd_min_atacado:
            if self.quantidade >= self.qtd_min_atacado:
                return self.preco_atacado * self.quantidade
        return self.preco_unitario * self.quantidade

    def falta_para_atacado(self):
        if (
            self.preco_atacado
            and self.qtd_min_atacado
            and self.quantidade < self.qtd_min_atacado
        ):
            return self.qtd_min_atacado - self.quantidade
        return 0
