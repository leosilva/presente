from django.shortcuts import get_object_or_404
from django.http import Http404
from .models import Activity


class ActivityOwnerMixin:
    def get_activity(self):
        activity = get_object_or_404(Activity, pk=self.kwargs["pk"])

        if (
            not self.request.user.is_superuser
            and not activity.owners.filter(pk=self.request.user.pk).exists()
        ):
            raise Http404("Você não tem permissão para acessar esta atividade")

        return activity
class BrindeAdminMixin:
    def get_allowed_actions(self):
        allowed_actions = super().get_allowed_actions()
        allowed_actions["list"] = "presente:admin_brindes"
        return allowed_actions
