from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Attendance, Gamificacao
from .services import PointService

User = get_user_model()

@receiver(post_save, sender=User)
def dar_trilha_inicial(sender, instance, created, **kwargs):
    if created:
        PointService.process_event("user.created", user=instance)


@receiver(post_delete, sender=Attendance)
def debit_pontos(sender, instance, **kwargs):
    if getattr(instance, "_skip_point_reversal", False):
        return
    PointService.process_event("attendance.canceled", attendance=instance)


@receiver(pre_save, sender=Gamificacao)
def guardar_pontos_anterior(sender, instance, **kwargs):
    if instance.pk:
        instance._pontos_anterior = (
            Gamificacao.objects.filter(pk=instance.pk)
            .values_list("pontos", flat=True)
            .first()
        )
    else:
        instance._pontos_anterior = None


@receiver(post_save, sender=Gamificacao)
def atualizar_pontuacao(sender, instance, created, **kwargs):
    pontos_anterior = getattr(instance, "_pontos_anterior", None)
    if not created and pontos_anterior is not None and pontos_anterior != instance.pontos:
        PointService.process_event(
            "gamificacao.updated",
            gamificacao=instance,
            pontos_anterior=pontos_anterior,
        )