## ─── services.py COMPLETO (substitui o arquivo atual) ───────────────────────

from django.db.models import Sum
from django.utils import timezone
from .models import (
    Gamificacao,
    TrilhaGamificacao,
    UsuarioGamificacao,
    Activity,
    Attendance,
    MarcosDiversidade,
    PointHistory,
    Nivel,
    PerfilGamificado
)


class PointService:

    # ──────────────────────────────────────────────────────────────
    # Operações atômicas de crédito / débito
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def debit_gamificacao(cls, user, gamificacao, motivo=""):
        deleted, _ = UsuarioGamificacao.objects.filter(
            user=user, gamificacao=gamificacao
        ).delete()

        if deleted > 0:
            # Grava histórico mesmo após a deleção
            PointHistory.objects.create(
                user=user,
                gamificacao=gamificacao,
                tipo=PointHistory.TipoMovimento.DEBITO,
                pontos=-gamificacao.pontos,
                motivo=motivo or f"Estorno automático — {gamificacao.titulo}",
            )
            cls._update_user_level(user)

        return deleted > 0

    @classmethod
    def credit_gamificacao(cls, user, gamificacao, motivo=""):
        obj, created = UsuarioGamificacao.objects.get_or_create(
            user=user,
            gamificacao=gamificacao,
        )

        if created:
            PointHistory.objects.create(
                user=user,
                gamificacao=gamificacao,
                tipo=PointHistory.TipoMovimento.CREDITO,
                pontos=gamificacao.pontos,
                motivo=motivo or f"Concessão automática — {gamificacao.titulo}",
            )
            cls._update_user_level(user)

        return created

    # ──────────────────────────────────────────────────────────────
    # Consultas
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def get_user_gamificacoes(cls, user):
        return UsuarioGamificacao.objects.filter(user=user).select_related(
            "gamificacao"
        )

    @classmethod
    def calculate_user_point(cls, user):
        total = UsuarioGamificacao.objects.filter(user=user).aggregate(
            total=Sum("gamificacao__pontos")
        )
        return total.get("total") or 0

    # ──────────────────────────────────────────────────────────────
    # Handlers de eventos
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def _on_user_created(cls, user):
        PerfilGamificado.objects.update_or_create(
            user=user,
            defaults={'nivel': None, 'titulo': None}
        )
        boas_vindas = Gamificacao.objects.filter(titulo="Boas-vindas").first()
        if not boas_vindas:
            return
        cls.credit_gamificacao(user, boas_vindas, motivo="Boas-vindas ao sistema")

    @classmethod
    def _on_attendance_created(cls, attendance):
        if not attendance.activity:
            return
        if not attendance.activity.gamificacao:
            return

        user = attendance.user
        gamificacao = attendance.activity.gamificacao
        motivo = f"Presença registrada em: {attendance.activity.title}"
        cls.credit_gamificacao(user, gamificacao, motivo=motivo)

        # Verifica bônus de trilha
        if attendance.activity.trilha:
            cls._check_trilha_bonus(user, attendance.activity.trilha)

        # Verifica bônus de diversidade
        cls._check_diversidade_bonus(user, attendance.checked_in_at.date())

    @classmethod
    def _on_attendance_canceled(cls, attendance, justificativa=""):
        """
        Reverte TODOS os pontos relacionados à presença removida:
          1. Gamificação direta da atividade
          2. Bônus de trilha (se o usuário perder o mínimo de presenças)
          3. Bônus de diversidade (se o usuário perder o mínimo de áreas no dia)
        """
        if not attendance.activity:
            return

        user = attendance.user
        activity = attendance.activity
        base_motivo = (
            f"Presença removida em: {activity.title}"
            + (f" — {justificativa}" if justificativa else "")
        )

        # 1. Estorna gamificação direta
        if activity.gamificacao:
            cls.debit_gamificacao(
                user,
                activity.gamificacao,
                motivo=base_motivo,
            )

        # 2. Estorna bônus de trilha se o usuário ficou abaixo do mínimo
        if activity.trilha:
            cls._check_trilha_bonus_reversal(user, activity.trilha, base_motivo)

        # 3. Estorna bônus de diversidade se o usuário ficou abaixo do mínimo
        data_checkin = attendance.checked_in_at.date()
        cls._check_diversidade_bonus_reversal(user, data_checkin, base_motivo)

    @classmethod
    def _on_gamificacao_updated(cls, gamificacao):
        atividades = Activity.objects.filter(
            gamificacao=gamificacao,
            start_time__lte=timezone.now(),
            end_time__gte=timezone.now()
            )
        for atividade in atividades:
            usuarios = UsuarioGamificacao.objects.filter(
                gamificacao=gamificacao
            )
            for ug in usuarios:
                cls.debit_gamificacao(ug.user, gamificacao)
                cls.credit_gamificacao(ug.user, gamificacao)

    # ──────────────────────────────────────────────────────────────
    # Bônus de trilha
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def _check_trilha_bonus(cls, user, trilha):
        if not trilha.gamificacao_bonus or not trilha.minimo_atividades:
            return

        ja_tem_bonus = UsuarioGamificacao.objects.filter(
            user=user, gamificacao=trilha.gamificacao_bonus
        ).exists()
        if ja_tem_bonus:
            return

        presencas_na_trilha = Attendance.objects.filter(
            user=user, activity__trilha=trilha
        ).count()

        if presencas_na_trilha >= trilha.minimo_atividades:
            motivo = f"Bônus de trilha atingido: {trilha.name}"
            cls.credit_gamificacao(user, trilha.gamificacao_bonus, motivo=motivo)

    @classmethod
    def _check_trilha_bonus_reversal(cls, user, trilha, base_motivo=""):
        """
        Remove o bônus de trilha se, após a remoção da presença,
        o usuário ficar abaixo do mínimo exigido.
        Nota: a contagem é feita ANTES do delete (o signal post_delete
        já removeu a presença), então o count já reflete o estado pós-remoção.
        """
        if not trilha.gamificacao_bonus or not trilha.minimo_atividades:
            return

        presencas_restantes = Attendance.objects.filter(
            user=user, activity__trilha=trilha
        ).count()

        if presencas_restantes < trilha.minimo_atividades:
            motivo = (
                f"Estorno de bônus de trilha '{trilha.name}' — "
                f"presenças insuficientes após remoção. {base_motivo}"
            )
            cls.debit_gamificacao(user, trilha.gamificacao_bonus, motivo=motivo)

    # ──────────────────────────────────────────────────────────────
    # Bônus de diversidade
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def _check_diversidade_bonus(cls, user, data):
        areas_no_dia = (
            Attendance.objects.filter(
                user=user,
                checked_in_at__date=data,
                activity__area__isnull=False,
            )
            .values_list("activity__area", flat=True)
            .distinct()
        )
        total_areas = areas_no_dia.count()

        if total_areas == 0:
            return

        marcos = MarcosDiversidade.objects.filter(
            areas_necessarias__lte=total_areas
        ).select_related("gamificacao_bonus")

        for marco in marcos:
            ja_tem_bonus = UsuarioGamificacao.objects.filter(
                user=user, gamificacao=marco.gamificacao_bonus
            ).exists()
            if not ja_tem_bonus:
                motivo = (
                    f"Bônus de diversidade: {marco.areas_necessarias} "
                    f"áreas no dia {data}"
                )
                cls.credit_gamificacao(user, marco.gamificacao_bonus, motivo=motivo)

    @classmethod
    def _check_diversidade_bonus_reversal(cls, user, data, base_motivo=""):
        """
        Remove bônus de diversidade cujo requisito de áreas não é mais
        satisfeito após a remoção da presença.
        """
        areas_restantes = (
            Attendance.objects.filter(
                user=user,
                checked_in_at__date=data,
                activity__area__isnull=False,
            )
            .values_list("activity__area", flat=True)
            .distinct()
            .count()
        )

        # Busca marcos que o usuário NÃO atinge mais
        marcos_excedentes = MarcosDiversidade.objects.filter(
            areas_necessarias__gt=areas_restantes
        ).select_related("gamificacao_bonus")

        for marco in marcos_excedentes:
            motivo = (
                f"Estorno de bônus de diversidade — "
                f"áreas insuficientes no dia {data}. {base_motivo}"
            )
            cls.debit_gamificacao(user, marco.gamificacao_bonus, motivo=motivo)

    # ──────────────────────────────────────────────────────────────
    # Atualização de nível
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def _update_user_level(cls, user):
        total_pontos = cls.calculate_user_point(user)
        nivel = Nivel.objects.filter(pontos_minimos__lte=total_pontos).order_by('-pontos_minimos').first()
        PerfilGamificado.objects.update_or_create(
            user=user,
            defaults={'nivel': nivel}
        )

    # ──────────────────────────────────────────────────────────────
    # Dispatcher de eventos
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def process_event(cls, event_name, **kwargs):
        handlers = {
            "user.created": cls._on_user_created,
            "attendance.created": cls._on_attendance_created,
            "attendance.canceled": cls._on_attendance_canceled,
            "gamificacao.updated": cls._on_gamificacao_updated
        }
        handler = handlers.get(event_name)
        if not handler:
            raise ValueError(f"Evento desconhecido: {event_name}")
        return handler(**kwargs)
