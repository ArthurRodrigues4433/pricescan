from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailBackend(ModelBackend):
    """Permite autenticação com e-mail no lugar do username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
