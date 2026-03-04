from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from src.models import Compra, ItemCompra


class ItemCompraPrecosTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u@t.com", password="pass1234")
        self.compra = Compra.objects.create(usuario=self.user, status="ativa")

    def _item(self, preco, qtd, preco_atacado=None, qtd_min=None):
        return ItemCompra.objects.create(
            compra=self.compra,
            nome="Produto Teste",
            preco_unitario=Decimal(str(preco)),
            quantidade=Decimal(str(qtd)),
            preco_atacado=Decimal(str(preco_atacado)) if preco_atacado else None,
            qtd_min_atacado=qtd_min,
        )

    def test_preco_total_sem_atacado(self):
        item = self._item(preco=5.00, qtd=3)
        self.assertEqual(item.preco_total(), Decimal("15.00"))

    def test_preco_total_atacado_aplicado(self):
        """Qtde >= mínimo → usa preço atacado."""
        item = self._item(preco=10.00, qtd=5, preco_atacado=8.00, qtd_min=3)
        self.assertEqual(item.preco_total(), Decimal("40.00"))

    def test_preco_total_atacado_nao_aplicado(self):
        """Qtde < mínimo → usa preço unitário."""
        item = self._item(preco=10.00, qtd=2, preco_atacado=8.00, qtd_min=3)
        self.assertEqual(item.preco_total(), Decimal("20.00"))

    def test_preco_total_atacado_exatamente_no_minimo(self):
        """Qtde == mínimo → usa preço atacado."""
        item = self._item(preco=10.00, qtd=3, preco_atacado=8.00, qtd_min=3)
        self.assertEqual(item.preco_total(), Decimal("24.00"))

    def test_compra_total_soma_itens(self):
        self._item(preco=5.00, qtd=2)
        self._item(preco=3.00, qtd=4)
        self.assertEqual(self.compra.total(), Decimal("22.00"))

    def test_compra_total_vazia(self):
        self.assertEqual(self.compra.total(), 0)
