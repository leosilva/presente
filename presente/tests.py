from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (
    Activity,
    Attendance,
    Evento,
    TrilhaGamificacao,
    TipoGamificacao,
    Gamificacao,
    Missao,
    MissaoProgresso,
    UsuarioGamificacao,
)
from .services import PointService


User = get_user_model()


class PointServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="testuser@example.com", password="pass")
        self.trilha = TrilhaGamificacao.objects.create(name="Trilha de Teste")
        self.tipo = TipoGamificacao.objects.create(trilha=self.trilha, tipo=TipoGamificacao.Tipo.BADGE)
        self.gamificacao = Gamificacao.objects.create(
            titulo="Boas-vindas",
            trilha=self.trilha,
            tipo=self.tipo,
            pontos=20,
        )

    def test_credit_and_debit_gamificacao(self):
        created = PointService.credit_gamificacao(self.user, self.gamificacao)
        self.assertTrue(created)
        self.assertTrue(
            UsuarioGamificacao.objects.filter(user=self.user, gamificacao=self.gamificacao).exists()
        )
        # Crédito repetido não duplica
        self.assertFalse(PointService.credit_gamificacao(self.user, self.gamificacao))

        self.assertEqual(PointService.calculate_user_point(self.user), 20)

        removed = PointService.debit_gamificacao(self.user, self.gamificacao)
        self.assertTrue(removed)
        self.assertEqual(PointService.calculate_user_point(self.user), 0)

    def test_get_user_gamificacoes(self):
        PointService.credit_gamificacao(self.user, self.gamificacao)
        gamificacoes = PointService.get_user_gamificacoes(self.user)
        self.assertEqual(gamificacoes.count(), 1)
        self.assertEqual(gamificacoes.first().gamificacao, self.gamificacao)

    def test_process_event_user_created_credit(self):
        self.assertEqual(PointService.calculate_user_point(self.user), 0)

        PointService.process_event("user.created", user=self.user)

        self.assertEqual(PointService.calculate_user_point(self.user), 20)

    def test_process_event_attendance_created_credit(self):
        now = timezone.now()
        evento = Evento.objects.create(
            nome="Evento Teste",
            tipo=Evento.TipoEvento.OUTRO,
            data_inicio=now - timezone.timedelta(days=1),
            data_fim=now + timezone.timedelta(days=1),
        )
        activity = Activity.objects.create(
            title="Atividade Teste",
            evento=evento,
            start_time=now,
            end_time=now + timezone.timedelta(hours=1),
            is_enabled=True,
            qr_timeout=0,
            restrict_ip=False,
            trilha=self.trilha,
            gamificacao=self.gamificacao,
        )
        activity.owners.add(self.user)

        Attendance.objects.create(activity=activity, user=self.user)
        self.assertEqual(PointService.calculate_user_point(self.user), 20)

        # Ainda deve existir apenas uma presenca única por usuario/atividade
        self.assertEqual(Attendance.objects.filter(activity=activity, user=self.user).count(), 1)

    def test_missao_frequencia_concede_e_estorna(self):
        now = timezone.now()
        evento = Evento.objects.create(
            nome="Evento Missão",
            tipo=Evento.TipoEvento.OUTRO,
            data_inicio=now - timezone.timedelta(days=1),
            data_fim=now + timezone.timedelta(days=1),
        )
        activity = Activity.objects.create(
            title="Atividade Missão",
            evento=evento,
            start_time=now,
            end_time=now + timezone.timedelta(hours=1),
            is_enabled=True,
        )
        bonus = Gamificacao.objects.create(titulo="Bônus da missão", pontos=50)
        missao = Missao.objects.create(
            titulo="Primeira presença",
            tipo=Missao.Tipo.FREQUENCIA,
            meta=1,
            gamificacao=bonus,
        )

        attendance = Attendance.objects.create(activity=activity, user=self.user)
        progresso = MissaoProgresso.objects.get(user=self.user, missao=missao)
        self.assertTrue(progresso.concluida)
        self.assertEqual(PointService.calculate_user_point(self.user), 50)

        attendance.delete()
        progresso.refresh_from_db()
        self.assertFalse(progresso.concluida)
        self.assertEqual(PointService.calculate_user_point(self.user), 0)
