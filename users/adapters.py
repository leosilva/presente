import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import user_email, user_field
from django.conf import settings

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return settings.OPEN_FOR_SIGNUP or False


class SuapSocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        # Extra data in: sociallogin.account.extra_data
        user = sociallogin.user
        extra_data = sociallogin.account.extra_data

        # Basic user fields
        user_email(user, data.get("email") or "")
        user_field(user, "first_name", data.get("first_name"))
        user_field(user, "last_name", data.get("last_name"))

        # Full name - respect nome_social if available
        nome_completo = extra_data.get("nome_registro", "")
        if nome_social := extra_data.get("nome_social"):
            nome_completo = nome_social
        if nome_completo:
            user.full_name = nome_completo

        # User type from tipo_usuario
        tipo_usuario = extra_data.get("tipo_usuario", "")
        if "Servidor" in tipo_usuario:
            user.type = "SERVIDOR"
        elif "Aluno" in tipo_usuario:
            user.type = "ALUNO"

        # Avatar URL from foto
        foto = extra_data.get("foto")
        if foto:
            user.avatar_url = foto

        # Campus
        campus = extra_data.get("campus")
        if campus:
            user.campus = campus

        # Mark as SUAP user
        user.is_suap_user = True

        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)

        # Update user data from SUAP on every login
        extra_data = sociallogin.account.extra_data

        # Update email (in case it changed)
        email = extra_data.get("email", "")
        if email:
            user.email = email

        # Update basic fields
        user.first_name = extra_data.get("primeiro_nome", "")
        user.last_name = extra_data.get("ultimo_nome", "")

        # Update full name - respect nome_social if available
        nome_completo = extra_data.get("nome_registro", "")
        if nome_social := extra_data.get("nome_social"):
            nome_completo = nome_social
        if nome_completo:
            user.full_name = nome_completo

        # Update user type (in case it changed - e.g., student became staff)
        tipo_usuario = extra_data.get("tipo_usuario", "")
        if "Servidor" in tipo_usuario:
            user.type = "SERVIDOR"
        elif "Aluno" in tipo_usuario:
            user.type = "ALUNO"

        # Update avatar URL
        foto = extra_data.get("foto")
        if foto:
            user.avatar_url = foto

        # Update campus
        campus = extra_data.get("campus")
        if campus:
            user.campus = campus

        # Mark as SUAP user
        user.is_suap_user = True

        # Fetch additional student data for ALUNO users
        if user.type == "ALUNO":
            try:
                import requests

                # Get SUAP_URL from the provider configuration
                suap_url = settings.SOCIALACCOUNT_PROVIDERS.get("suap", {}).get(
                    "SUAP_URL", "https://suap.ifrn.edu.br"
                )
                token = sociallogin.token.token
                headers = {"Authorization": f"Bearer {token}"}
                response = requests.get(
                    f"{suap_url}/api/ensino/meus-dados-aluno/",
                    headers=headers,
                    timeout=10,
                )
                if response.status_code == 200:
                    student_data = response.json()
                    user.curso = student_data.get("curso", "")
                    user.periodo_referencia = student_data.get("periodo_referencia", "")
            except Exception:
                # If the API call fails, just continue without the student data
                pass
        else:
            # Clear student data if user is not ALUNO anymore
            user.curso = ""
            user.periodo_referencia = ""

        user.save()
        return user

    def is_open_for_signup(self, request, sociallogin):
        return settings.OPEN_FOR_SIGNUP or False

    def on_authentication_error(
        self,
        request,
        provider,
        error=None,
        exception=None,
        extra_context=None,
    ):
        logger.error(
            "Erro de autenticação social (provider=%s, error=%s): %s",
            provider,
            error,
            exception,
            exc_info=exception,
        )
        return super().on_authentication_error(
            request,
            provider,
            error=error,
            exception=exception,
            extra_context=extra_context,
        )
