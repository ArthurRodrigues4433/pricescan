from django.contrib.auth.models import User
from django.test import TestCase

from src.forms import RegisterForm, ItemCompraForm


class RegisterFormTest(TestCase):
    def _dados(self, **kwargs):
        base = {
            "nome": "Usuário Teste",
            "email": "novo@teste.com",
            "password1": "SenhaSegura123!",
            "password2": "SenhaSegura123!",
        }
        base.update(kwargs)
        return base

    def test_form_valido(self):
        form = RegisterForm(data=self._dados())
        self.assertTrue(form.is_valid())

    def test_senhas_divergentes(self):
        form = RegisterForm(data=self._dados(password2="Diferente123!"))
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_email_duplicado(self):
        User.objects.create_user(username="dup@t.com", email="dup@t.com", password="X")
        form = RegisterForm(data=self._dados(email="dup@t.com"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_email_obrigatorio(self):
        form = RegisterForm(data=self._dados(email=""))
        self.assertFalse(form.is_valid())

    def test_save_usa_email_como_username(self):
        form = RegisterForm(data=self._dados(email="Usuario@Teste.COM"))
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.username, "usuario@teste.com")
        self.assertEqual(user.email, "usuario@teste.com")


class ItemCompraFormTest(TestCase):
    def _dados(self, **kwargs):
        base = {
            "nome": "Arroz",
            "preco_unitario": "5.00",
            "quantidade": "2",
        }
        base.update(kwargs)
        return base

    def test_form_valido(self):
        form = ItemCompraForm(data=self._dados())
        self.assertTrue(form.is_valid())

    def test_preco_zero_invalido(self):
        form = ItemCompraForm(data=self._dados(preco_unitario="0"))
        self.assertFalse(form.is_valid())
        self.assertIn("preco_unitario", form.errors)

    def test_preco_negativo_invalido(self):
        form = ItemCompraForm(data=self._dados(preco_unitario="-1"))
        self.assertFalse(form.is_valid())
        self.assertIn("preco_unitario", form.errors)

    def test_quantidade_zero_invalida(self):
        form = ItemCompraForm(data=self._dados(quantidade="0"))
        self.assertFalse(form.is_valid())
        self.assertIn("quantidade", form.errors)

    def test_nome_obrigatorio(self):
        form = ItemCompraForm(data=self._dados(nome=""))
        self.assertFalse(form.is_valid())
        self.assertIn("nome", form.errors)
