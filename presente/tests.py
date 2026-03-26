from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (
    Activity,
    Attendance,
    TrilhaGamificacao,
    TipoGamificacao,
    Gamificacao,
    UsuarioGamificacao,
)
from .services import PointService


User = get_user_model()


class PointServiceTests(TestCase):
    def setUp(self):
        # Garante estado predefinido limpo para testes de regras de evento
        TrilhaGamificacao.objects.filter(name=PointService.DEFAULT_ENTRY_TRILHA_NAME).delete()

        self.user = User.objects.create_user(username="testuser", email="testuser@example.com", password="pass")
        self.trilha = TrilhaGamificacao.objects.create(name=PointService.DEFAULT_ENTRY_TRILHA_NAME)
        self.tipo = TipoGamificacao.objects.create(trilha=self.trilha, tipo=TipoGamificacao.Tipo.BADGE)
        self.gamificacao = Gamificacao.objects.create(
            titulo="Boas-vindas",
            trilha=self.trilha,
            tipo=self.tipo,
            pontos=20,
        )

    def test_credit_and_debit_gamificacao(self):
        obj, created = PointService.credit_gamificacao(self.user, self.gamificacao)
        self.assertTrue(created)
        self.assertEqual(obj.user, self.user)
        self.assertEqual(obj.gamificacao, self.gamificacao)

        self.assertEqual(PointService.calculate_user_points(self.user), 20)

        removed = PointService.debit_gamificacao(self.user, self.gamificacao)
        self.assertTrue(removed)
        self.assertEqual(PointService.calculate_user_points(self.user), 0)

    def test_get_user_gamificacoes(self):
        PointService.credit_gamificacao(self.user, self.gamificacao)
        gamificacoes = PointService.get_user_gamificacoes(self.user)
        self.assertEqual(gamificacoes.count(), 1)
        self.assertEqual(gamificacoes.first().gamificacao, self.gamificacao)

    def test_process_event_user_created_credit(self):
        self.assertEqual(PointService.calculate_user_points(self.user), 0)

        PointService.process_event("user.created", user=self.user)

        self.assertEqual(PointService.calculate_user_points(self.user), 20)

    def test_process_event_attendance_created_credit(self):
        now = timezone.now()
        activity = Activity.objects.create(
            title="Atividade Teste",
            start_time=now,
            end_time=now + timezone.timedelta(hours=1),
            is_enabled=True,
            qr_timeout=0,
            restrict_ip=False,
            trilha=self.trilha,
            gamificacao=self.gamificacao,
        )
        activity.owners.add(self.user)

        attendance = Attendance.objects.create(activity=activity, user=self.user)
        self.assertEqual(PointService.calculate_user_points(self.user), 20)

        # Ainda deve existir apenas uma presenca única por usuario/atividade
        self.assertEqual(Attendance.objects.filter(activity=activity, user=self.user).count(), 1)
