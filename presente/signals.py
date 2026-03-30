from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Attendance
from .services import PointService

User = get_user_model()

@receiver(post_save, sender=User)
def dar_trilha_inicial(sender, instance, created, **kwargs):
    if created:
        PointService.process_event("user.created", user=instance)

@receiver(post_delete, sender=Attendance)
def debit_pontos(sender, instance, **kwargs):
    PointService.process_event("attendance.canceled", attendance=instance)