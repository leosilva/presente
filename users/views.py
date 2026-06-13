from allauth.account.views import (
    PasswordResetFromKeyView,
    EmailView,
    PasswordChangeView,
)
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView
from django.views.generic.edit import UpdateView
from django.contrib.    auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.shortcuts import redirect
from core.mixins import PageTitleMixin
from core.views import (
    CoreCreateView,
    CoreDetailView,
    CoreUpdateView,
    CoreDeleteView,
    CoreFilterView,
)
from .tables import UserTable
from .filters import UserFilter
from presente.models import PerfilGamificado, UsuarioGamificacao, Nivel, TrilhaGamificacao
from presente.services import PointService

User = get_user_model() 


class ExcludeAdminMixin:
    admin_id = 1

    def get_queryset(self):
        base_qs = super().get_queryset()
        return base_qs.exclude(id=self.admin_id)


class CustomPasswordResetFromKeyView(PasswordResetFromKeyView):
    success_url = reverse_lazy("account_login")


class UserListView(ExcludeAdminMixin, CoreFilterView):
    page_title = _("Usuários")
    model = User
    table_class = UserTable
    filterset_class = UserFilter

    def get_queryset(self):
        queryset = super().get_queryset()
        # Prefetch social accounts to avoid N+1 queries when accessing matricula
        queryset = queryset.prefetch_related("socialaccount_set")
        return queryset


class UserCreateView(CoreCreateView):
    page_title = _("Usuários")
    model = User
    fields = ["email", "first_name", "last_name"]


class UserDetailView(ExcludeAdminMixin, CoreDetailView):
    page_title = _("Usuários")
    model = User
    context_object_name = "user_obj"
    fields = [
        "full_name",
        "email",
        "type",
        "curso",
        "periodo_referencia",
        "date_joined",
    ]


class UserUpdateView(ExcludeAdminMixin, CoreUpdateView):
    page_title = _("Usuários")
    model = User
    context_object_name = "user_obj"
    fields = ["email", "first_name", "last_name"]


class UserDeleteView(ExcludeAdminMixin, CoreDeleteView):
    model = User
    context_object_name = "user_obj"


class UserProfileView(LoginRequiredMixin, PageTitleMixin, TemplateView):
    page_title = _("Perfil")
    template_name = "presente/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
            
        # Prefetch social accounts for the current user
        user = User.objects.prefetch_related("socialaccount_set").get(
            pk=self.request.user.pk
        )

        context["user"] = user
        my_points = PointService.calculate_user_point(self.request.user)
        context["my_points"] = my_points
        perfil = PerfilGamificado.objects.filter(user=self.request.user).first()
        context["perfil"] = perfil
        nivel_atual = perfil.nivel if perfil else None
        
        if nivel_atual:
            proximo_nivel = Nivel.objects.filter(pontos_minimos__gt=nivel_atual.pontos_minimos).first()
        else:
            proximo_nivel=None

        context["proximo_nivel"] = proximo_nivel

        if not nivel_atual:
            percentual = 0
        elif not proximo_nivel:
            percentual = 100
        else:
            percentual = (my_points - nivel_atual.pontos_minimos) * 100 / (proximo_nivel.pontos_minimos - nivel_atual.pontos_minimos)
        
        context["percentual"] = percentual

        offset = round(408 * (1 - percentual / 100), 1)
        context["offset"] = str(offset).replace(",", ".")

        trilhas_completas = TrilhaGamificacao.objects.filter(gamificacao_bonus__usuarios__user=self.request.user)
        context["trilhas_completas"] = trilhas_completas

        context["total_badges"] = UsuarioGamificacao.objects.filter(
            user=self.request.user,
            gamificacao__tipo__tipo="BDG"
        ).count()

        context["total_trofeus"] = UsuarioGamificacao.objects.filter(
            user=self.request.user,
            gamificacao__tipo__tipo="TRF"
        ).count()

        context["total_medalhas"] = UsuarioGamificacao.objects.filter(
            user=self.request.user,
            gamificacao__tipo__tipo="MDL"
        ).count()

        context["conquistas"] = UsuarioGamificacao.objects.filter(
            user=self.request.user
        ).select_related('gamificacao', 'gamificacao__tipo', 'gamificacao__trilha')
        
        return context


class UserProfileUpdateView(LoginRequiredMixin, PageTitleMixin, UpdateView):
    page_title = _("Atualizar Perfil")
    model = User
    fields = ["first_name", "last_name", "email"]
    template_name = "presente/profile_edit.html"
    success_url = reverse_lazy("users:user_profile")

    def get_object(self, queryset=None):
        return self.request.user

    def dispatch(self, request, *args, **kwargs):
        # Prevent SUAP users from editing their profile
        if request.user.is_authenticated and request.user.is_suap_user:
            messages.warning(
                request,
                _(
                    "Seu perfil é gerenciado pelo SUAP e não pode ser editado manualmente. "
                    "Os dados são atualizados automaticamente a cada login."
                ),
            )
            return redirect("users:user_profile")
        return super().dispatch(request, *args, **kwargs)


class CustomEmailView(EmailView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_suap_user:
            messages.warning(
                request,
                _(
                    "Usuários SUAP não podem alterar o email. "
                    "Esta informação é gerenciada pelo SUAP."
                ),
            )
            return redirect("users:user_profile")
        return super().dispatch(request, *args, **kwargs)


class CustomPasswordChangeView(PasswordChangeView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_suap_user:
            messages.warning(
                request,
                _(
                    "Usuários SUAP não podem alterar a senha. "
                    "Use o sistema SUAP para gerenciar sua senha."
                ),
            )
            return redirect("users:user_profile")
        return super().dispatch(request, *args, **kwargs)
