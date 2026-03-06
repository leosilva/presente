from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _



class PresenteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "presente"
    verbose_name = _("Presente")
    def ready(self):
        from . import signals  