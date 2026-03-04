from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import ItemCompra


class RegisterForm(UserCreationForm):
    nome = forms.CharField(
        required=True,
        label="Nome",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Seu nome completo"}),
    )
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
        email = self.cleaned_data["email"].lower()
        user.email = email
        user.first_name = self.cleaned_data["nome"].strip()
        # username interno gerado a partir do e-mail (único por definição)
        user.username = email
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


# ---------------------------------------------------------------------------
# Formulários do módulo OCR
# ---------------------------------------------------------------------------


class EscanearCartazForm(forms.Form):
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

    foto = forms.ImageField(
        label="Foto do cartaz",
        widget=forms.ClearableFileInput(
            attrs={"accept": "image/*", "capture": "environment"}
        ),
    )

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        if foto and foto.size > self.MAX_UPLOAD_SIZE:
            raise forms.ValidationError(
                f"A imagem não pode exceder {self.MAX_UPLOAD_SIZE // (1024 * 1024)} MB."
            )
        return foto


class ConfirmarProdutoForm(forms.Form):
    """Etapa 1 — revisão dos dados extraídos pelo OCR."""

    nome = forms.CharField(
        max_length=200,
        label="Nome do produto",
        widget=forms.TextInput(attrs={"placeholder": "Ex: Arroz Tio João 5kg"}),
    )
    peso_volume = forms.CharField(
        max_length=50,
        required=False,
        label="Peso / Volume",
        widget=forms.TextInput(attrs={"placeholder": "Ex: 5kg, 500ml"}),
    )
    preco_unitario = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Preço unitário (R$)",
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "0,00"}),
    )
    preco_atacado = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        label="Preço atacado (R$)",
        widget=forms.NumberInput(
            attrs={"step": "0.01", "placeholder": "0,00 (opcional)"}
        ),
    )
    qtd_min_atacado = forms.IntegerField(
        min_value=1,
        required=False,
        label="Qtd. mínima para atacado",
        widget=forms.NumberInput(attrs={"placeholder": "Ex: 3 (opcional)"}),
    )
    # A imagem viaja como campo oculto (base64 não é prático; usamos o caminho
    # temporário salvo na sessão — o campo abaixo só carrega o arquivo original).
    foto = forms.ImageField(
        label="Foto do cartaz",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )


class InformarQuantidadeForm(forms.Form):
    """Etapa 2 — somente a quantidade comprada."""

    quantidade = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Quantidade",
        widget=forms.NumberInput(
            attrs={"step": "0.01", "placeholder": "Ex: 2", "autofocus": True}
        ),
    )
