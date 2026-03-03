from django import forms
from .models import ItemCompra


class ItemCompraForm(forms.ModelForm):
    class Meta:
        model = ItemCompra
        fields = ["nome", "preco_unitario", "quantidade", "foto"]

    def clean_preco_unitario(self):
        preco = self.cleaned_data.get("preco_unitario")

        if preco is not None and preco <= 0:
            raise forms.ValidationError("O preço deve ser maior que zero.")

        return preco

    def clean_quantidade(self):
        quantidade = self.cleaned_data.get("quantidade")

        if quantidade is not None and quantidade <= 0:
            raise forms.ValidationError("A quantidade deve ser maior que zero.")

        return quantidade
