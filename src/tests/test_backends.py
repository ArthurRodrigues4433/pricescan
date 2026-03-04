from django.contrib.auth.models import User
from django.test import TestCase

from src.backends import EmailBackend


class EmailBackendTest(TestCase):
    """Testa o backend de autenticação por e-mail."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="SenhaSegura123!",
        )
        self.backend = EmailBackend()

    def test_autenticar_email_e_senha_validos(self):
        """Retorna o usuário quando e-mail e senha estão corretos."""
        result = self.backend.authenticate(
            None, username="user@example.com", password="SenhaSegura123!"
        )
        self.assertEqual(result, self.user)

    def test_autenticar_senha_errada_retorna_none(self):
        """Senha incorreta → None."""
        result = self.backend.authenticate(
            None, username="user@example.com", password="senhaerrada"
        )
        self.assertIsNone(result)

    def test_autenticar_email_inexistente_retorna_none(self):
        """E-mail sem cadastro → None."""
        result = self.backend.authenticate(
            None, username="naoexiste@example.com", password="qualquer"
        )
        self.assertIsNone(result)

    def test_autenticar_usuario_inativo_retorna_none(self):
        """Usuário com is_active=False → None."""
        self.user.is_active = False
        self.user.save()
        result = self.backend.authenticate(
            None, username="user@example.com", password="SenhaSegura123!"
        )
        self.assertIsNone(result)

    def test_autenticar_email_case_insensitive(self):
        """E-mail em maiúsculas também autentica (iexact)."""
        result = self.backend.authenticate(
            None, username="USER@EXAMPLE.COM", password="SenhaSegura123!"
        )
        self.assertEqual(result, self.user)
