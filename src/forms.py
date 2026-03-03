from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import ItemCompra


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "seu@email.com"}),
    )

    class Meta:
        model = User
        fields = ["email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Senha"
        self.fields["password1"].help_text = (
            "Mínimo 8 caracteres. Não pode ser muito parecida com o e-mail. "
            "Não pode ser uma senha muito comum."
        )
        self.fields["password2"].label = "Confirme a senha"
        self.fields["password2"].help_text = "Digite a mesma senha para confirmar."

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("As senhas não coincidem.")
        return password2

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].lower()
        # usa o e-mail como username (aceita até 150 chars)
        user.username = user.email
        if commit:
            user.save()
        return user


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
