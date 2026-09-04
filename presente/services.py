from django.db.models import Sum
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import (
    Gamificacao,
    TrilhaGamificacao,
    UsuarioGamificacao,
    Activity,
    Attendance,
    MarcosDiversidade,
    PointHistory,
    Nivel,
    PerfilGamificado,
    Brinde,
    Troca,
    ItemRecompensa,
)


class PointService:

    # ──────────────────────────────────────────────────────────────
    # Operações atômicas de crédito / débito
    # ──────────────────────────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def debit_gamificacao(cls, user, gamificacao, motivo=""):
        deleted, _ = UsuarioGamificacao.objects.filter(
            user=user, gamificacao=gamificacao
        ).delete()

        if deleted > 0:
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
    @transaction.atomic
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
        # PointHistory é a fonte única de saldo — soma todos os créditos
        # (positivos) e débitos (negativos) registrados para o usuário.
        total = PointHistory.objects.filter(user=user).aggregate(
            total=Sum("pontos")
        ).get("total") or 0
        return total

    # ──────────────────────────────────────────────────────────────
    # Handlers de eventos
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def _on_user_created(cls, user):
        PerfilGamificado.objects.update_or_create(
            user=user,
            defaults={"nivel": None, "titulo": None},
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

        if attendance.activity.trilha:
            cls._check_trilha_bonus(user, attendance.activity.trilha)

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

        if activity.gamificacao:
            cls.debit_gamificacao(user, activity.gamificacao, motivo=base_motivo)

        if activity.trilha:
            cls._check_trilha_bonus_reversal(user, activity.trilha, base_motivo)

        data_checkin = attendance.checked_in_at.date()
        cls._check_diversidade_bonus_reversal(user, data_checkin, base_motivo)

    @classmethod
    @transaction.atomic #faz o Django tratar tudo dentro da função como uma transação de banco única: ou todas as operações de escrita são commitadas, ou, se qualquer exceção for levantada em qualquer ponto, todas são revertidas (rollback) — nenhuma fica parcialmente aplicada.
    def _on_gamificacao_updated(cls, gamificacao, pontos_anterior):
        if pontos_anterior == gamificacao.pontos:
            return

        tem_atividade_ativa = Activity.objects.filter(
            gamificacao=gamificacao,
            start_time__lte=timezone.now(),
            end_time__gte=timezone.now(),
        ).exists()
        if not tem_atividade_ativa:
            return

        usuarios = UsuarioGamificacao.objects.filter(
            gamificacao=gamificacao
        ).select_related("user")

        for ug in usuarios:
            PointHistory.objects.create(
                user=ug.user,
                gamificacao=gamificacao,
                tipo=PointHistory.TipoMovimento.DEBITO,
                pontos=-pontos_anterior,
                motivo=f"Ajuste de pontuação — {gamificacao.titulo} (valor anterior removido)",
            )
            PointHistory.objects.create(
                user=ug.user,
                gamificacao=gamificacao,
                tipo=PointHistory.TipoMovimento.CREDITO,
                pontos=gamificacao.pontos,
                motivo=f"Ajuste de pontuação — {gamificacao.titulo} (novo valor aplicado)",
            )
            cls._update_user_level(ug.user)

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
        nivel = (
            Nivel.objects.filter(pontos_minimos__lte=total_pontos)
            .order_by("-pontos_minimos")
            .first()
        )
        PerfilGamificado.objects.update_or_create(
            user=user, defaults={"nivel": nivel}
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
            "gamificacao.updated": cls._on_gamificacao_updated,
        }
        handler = handlers.get(event_name)
        if not handler:
            raise ValueError(f"Evento desconhecido: {event_name}")
        return handler(**kwargs)


class TrocaService:
    """
    Serviço responsável pela lógica de troca de pontos por brindes.
    Suporta múltiplos itens por troca (carrinho).
    Segue o mesmo padrão do PointService.
    """

    # ──────────────────────────────────────────────────────────────
    # Operação principal de troca
    # ──────────────────────────────────────────────────────────────

    @classmethod
    @transaction.atomic
    def realizar_troca(cls, user, itens):
        """
        Realiza a troca de pontos por brindes.

        Parâmetros:
            user: usuário que está realizando a troca
            itens: lista de dicts com {'brinde': <Brinde>, 'quantidade': <int>}

        Fluxo:
            1. Bloqueia os brindes com select_for_update (evita race condition)
            2. Valida cada brinde (ativo, estoque, validade)
            3. Valida se o usuário tem pontos suficientes para o total
            4. Cria a Troca e os ItemRecompensa
            5. Decrementa o estoque de cada brinde
            6. Registra o débito no PointHistory
        """
        if not itens:
            raise ValidationError(_("Nenhum item informado para a troca."))

        # Bloqueia todos os brindes da troca de uma vez para evitar race condition
        ids_brindes = [item["brinde"].pk for item in itens]
        brindes_locked = {
        b.pk: b
        for b in Brinde.objects.filter(pk__in=ids_brindes)
    }

        # Substitui os brindes do input pelos registros bloqueados do banco
        itens_validados = [
            {"brinde": brindes_locked[item["brinde"].pk], "quantidade": item["quantidade"]}
            for item in itens
        ]

        # Valida cada item individualmente
        for item in itens_validados:
            cls._validar_brinde_disponivel(item["brinde"], item["quantidade"])

        # Calcula o total de pontos necessários para toda a troca
        total_pontos = sum(
            item["brinde"].pontos_necessarios * item["quantidade"]
            for item in itens_validados
        )

        cls._validar_pontos_suficientes(user, total_pontos)

        # Cria o cabeçalho da troca
        troca = Troca.objects.create(
            usuario=user,
            pontos_gastos=total_pontos,
        )

        # Cria os itens e decrementa o estoque de cada brinde
        for item in itens_validados:
            brinde = item["brinde"]
            quantidade = item["quantidade"]

            ItemRecompensa.objects.create(
                troca=troca,
                brinde=brinde,
                quantidade=quantidade,
                pontos_unitarios=brinde.pontos_necessarios,
            )

            brinde.quantidade_disponivel -= quantidade
            brinde.save(update_fields=["quantidade_disponivel"])

        # Registra o débito total no PointHistory e atualiza o nível
        cls._debitar_pontos(user, troca)

        return troca

    # ──────────────────────────────────────────────────────────────
    # Validações
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def _validar_brinde_disponivel(cls, brinde, quantidade):
        """
        Verifica se o brinde pode ser trocado na quantidade solicitada.
        Checa ativo, estoque suficiente e data de validade.
        """
        if not brinde.ativo:
            raise ValidationError(
                _(f"O brinde '{brinde.nome}' não está mais disponível.")
            )

        if brinde.quantidade_disponivel < quantidade:
            raise ValidationError(
                _(
                    f"Estoque insuficiente para '{brinde.nome}'. "
                    f"Disponível: {brinde.quantidade_disponivel}, solicitado: {quantidade}."
                )
            )

        if (
            brinde.data_validade
            and brinde.data_validade < timezone.now().date()
        ):
            raise ValidationError(
                _(f"O prazo para trocar o brinde '{brinde.nome}' expirou.")
            )

    @classmethod
    def _validar_pontos_suficientes(cls, user, total_pontos):
        """
        Verifica se o usuário possui pontos suficientes para o total da troca.
        """
        pontos_usuario = PointService.calculate_user_point(user)

        if pontos_usuario < total_pontos:
            raise ValidationError(
                _(
                    f"Pontos insuficientes. Você possui {pontos_usuario} pts "
                    f"e esta troca custa {total_pontos} pts."
                )
            )

    # ──────────────────────────────────────────────────────────────
    # Débito de pontos
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def _debitar_pontos(cls, user, troca):
        """
        Registra o débito total da troca no PointHistory e recalcula o nível.
        gamificacao=None pois o débito origina de uma troca, não de uma gamificação.
        """
        nomes = ", ".join(
            f"{item.quantidade}x {item.brinde.nome}"
            for item in troca.itens.select_related("brinde").all()
        )

        PointHistory.objects.create(
            user=user,
            gamificacao=None,
            tipo=PointHistory.TipoMovimento.DEBITO,
            pontos=-troca.pontos_gastos,
            motivo=f"Troca #{troca.pk}: {nomes}",
        )
        PointService._update_user_level(user)

    # ──────────────────────────────────────────────────────────────
    # Consultas
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def get_trocas_usuario(cls, user):
        """
        Retorna todas as trocas realizadas por um usuário,
        com os itens e brindes carregados em uma única query.
        """
        return (
            Troca.objects.filter(usuario=user)
            .prefetch_related("itens__brinde")
            .order_by("-data")
        )

    @classmethod
    def get_brindes_disponiveis(cls, evento):
        """
        Retorna todos os brindes disponíveis para troca em um evento,
        filtrando ativos, com estoque e dentro da validade.
        """
        from django.db.models import Q

        return Brinde.objects.filter(
            evento=evento,
            ativo=True,
            quantidade_disponivel__gt=0,
        ).filter(
            Q(data_validade__isnull=True)
            | Q(data_validade__gte=timezone.now().date())
        ).order_by("pontos_necessarios")

    # ──────────────────────────────────────────────────────────────
    # Dispatcher de eventos
    # ──────────────────────────────────────────────────────────────

    @classmethod
    def process_event(cls, event_name, **kwargs):
        """
        Dispatcher de eventos do TrocaService.
        """
        handlers = {
            "troca.realizada": cls.realizar_troca,
        }

        handler = handlers.get(event_name)

        if not handler:
            raise ValueError(f"Evento desconhecido: {event_name}")

        return handler(**kwargs)