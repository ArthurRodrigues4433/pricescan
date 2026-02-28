from django import forms
from .models import ItemCompra


class ItemCompraForm(forms.ModelForm):
    class Meta:
        model = ItemCompra
        fields = ["nome", "preco_unitario", "quantidade", "foto"]
