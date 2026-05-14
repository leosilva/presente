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
    Recompensa,
    ResgateRecompensa
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
class ResgateService:
    """
    Serviço responsável por toda a lógica de resgate de recompensas na loja.
    Segue o mesmo padrão do PointService: métodos de classe organizados
    em operações atômicas, consultas e handlers de eventos.
    """
 
    # ──────────────────────────────────────────────────────────────
    # Operação principal de resgate
    # ──────────────────────────────────────────────────────────────
 
    @classmethod
    @transaction.atomic                                    # Garante que todas as operações abaixo ocorram em uma única transação — se qualquer uma falhar, tudo é revertido
    def resgatar(cls, user, recompensa):
        """
        Realiza o resgate de uma recompensa para o usuário.
        Valida pontos, estoque e validade antes de confirmar.
        Lança ValidationError com mensagem descritiva em caso de falha.
        """
        recompensa = Recompensa.objects.select_for_update().get(pk=recompensa.pk)
 
        cls._validar_recompensa_disponivel(recompensa)     # Verifica se a recompensa está ativa, com estoque e dentro da validade
        cls._validar_pontos_suficientes(user, recompensa)  # Verifica se o usuário tem pontos suficientes para o resgate
        cls._validar_resgate_duplicado(user, recompensa)   # Verifica se o usuário ainda não resgatou esta recompensa
 
 
        resgate = ResgateRecompensa.objects.create(        # Cria o registro do resgate vinculando usuário e recompensa
            usuario=user,                                  # Usuário que está realizando o resgate
            recompensa=recompensa,                         # Recompensa que está sendo resgatada
            pontos_gastos=recompensa.pontos_necessarios,   # Snapshot dos pontos necessários no momento do resgate
        )
 
        recompensa.quantidade_disponivel -= 1              # Decrementa o estoque da recompensa em uma unidade
        recompensa.save(update_fields=["quantidade_disponivel"])  # Salva apenas o campo de estoque para evitar sobrescrita de outros campos
 
        cls._debitar_pontos(user, recompensa)              # Registra o débito dos pontos no PointHistory para manter o histórico completo
 
        return resgate                                     # Retorna o objeto de resgate criado para uso na view ou serializer
 
    # ──────────────────────────────────────────────────────────────
    # Validações
    # ──────────────────────────────────────────────────────────────
 
    @classmethod
    def _validar_recompensa_disponivel(cls, recompensa):
        """
        Verifica se a recompensa pode ser resgatada no momento.
        Checa ativo, estoque e data de validade.
        """
 
        if not recompensa.ativo:                           # Verifica se a recompensa está marcada como ativa no sistema
            raise ValidationError(                         # Lança erro de validação impedindo o resgate
                _("Esta recompensa não está mais disponível.")  # Mensagem traduzível exibida ao usuário
            )
 
        if recompensa.quantidade_disponivel <= 0:          # Verifica se ainda há unidades em estoque
            raise ValidationError(                         # Lança erro de validação impedindo o resgate
                _("Esta recompensa está esgotada.")        # Mensagem traduzível exibida ao usuário
            )
 
        if (                                               # Inicia verificação de validade apenas se a data foi preenchida
            recompensa.data_validade                       # Confere se o campo data_validade foi definido (não é nulo/blank)
            and recompensa.data_validade < timezone.now().date()  # Compara a data de validade com a data atual
        ):
            raise ValidationError(                         # Lança erro de validação impedindo o resgate
                _("O prazo para resgatar esta recompensa expirou.")  # Mensagem traduzível exibida ao usuário
            )
 
    @classmethod
    def _validar_pontos_suficientes(cls, user, recompensa):
        """
        Verifica se o usuário possui pontos suficientes para o resgate.
        """
 
        pontos_usuario = PointService.calculate_user_point(user)  # Calcula o total de pontos atual do usuário via PointService
 
        if pontos_usuario < recompensa.pontos_necessarios: # Compara os pontos do usuário com o custo da recompensa
            raise ValidationError(                         # Lança erro de validação impedindo o resgate
                _(
                    f"Pontos insuficientes. Você possui {pontos_usuario} pts "  # Mostra ao usuário quantos pontos ele tem
                    f"e esta recompensa custa {recompensa.pontos_necessarios} pts."  # Mostra ao usuário quantos pontos a recompensa custa
                )
            )
 
    @classmethod
    def _validar_resgate_duplicado(cls, user, recompensa):
        """
        Impede que o mesmo usuário resgate a mesma recompensa mais de uma vez.
        """
 
        ja_resgatou = ResgateRecompensa.objects.filter(    # Consulta o banco verificando se já existe um resgate para este par usuário/recompensa
            usuario=user,                                  # Filtra pelo usuário que está tentando resgatar
            recompensa=recompensa,                         # Filtra pela recompensa específica
        ).exists()                                         # Retorna True se já existir ao menos um registro
 
        if ja_resgatou:                                    # Se o usuário já resgatou esta recompensa anteriormente
            raise ValidationError(                         # Lança erro de validação impedindo novo resgate
                _("Você já resgatou esta recompensa.")     # Mensagem traduzível exibida ao usuário
            )
 
    # ──────────────────────────────────────────────────────────────
    # Débito de pontos
    # ──────────────────────────────────────────────────────────────
 
    @classmethod
    def _debitar_pontos(cls, user, recompensa):
        """
        Registra o débito dos pontos no PointHistory.
        Não remove UsuarioGamificacao — apenas cria um registro negativo
        no histórico, mantendo o saldo real calculado pela soma do histórico.
        """
 
        PointHistory.objects.create(                       # Cria um registro imutável de débito no histórico de pontos
            user=user,                                     # Usuário que teve os pontos debitados
            gamificacao=None,  # Débito de resgate não tem gamificação associada
            tipo=PointHistory.TipoMovimento.DEBITO,        # Define o tipo do movimento como débito
            pontos=-recompensa.pontos_necessarios,         # Valor negativo representando os pontos gastos no resgate
            motivo=f"Resgate de recompensa: {recompensa.nome}",  # Descrição automática do motivo do débito
        )
        PointService._update_user_level(user)
 
    # ──────────────────────────────────────────────────────────────
    # Consultas
    # ──────────────────────────────────────────────────────────────
 
    @classmethod
    def get_resgates_usuario(cls, user):
        """
        Retorna todos os resgates realizados por um usuário,
        com os dados da recompensa carregados em uma única query.
        """
 
        return ResgateRecompensa.objects.filter(           # Filtra os resgates pelo usuário informado
            usuario=user                                   # Parâmetro de filtro: usuário específico
        ).select_related("recompensa")                     # Carrega os dados da recompensa em JOIN para evitar queries N+1
 
    @classmethod
    def get_recompensas_disponiveis(cls, evento):
        """
        Retorna todas as recompensas disponíveis para resgate em um evento,
        filtrando ativas, com estoque e dentro da validade.
        """
 
        from django.db.models import Q                     # Importa Q para construir consultas complexas com OR/AND
 
        return Recompensa.objects.filter(                  # Filtra as recompensas do banco pelo evento informado
            evento=evento,                                 # Restringe ao evento específico
            ativo=True,                                    # Apenas recompensas marcadas como ativas
            quantidade_disponivel__gt=0,                   # Apenas recompensas com estoque maior que zero
        ).filter(                                          # Aplica segundo filtro para a lógica de validade
            Q(data_validade__isnull=True)                  # Inclui recompensas sem data de validade definida
            | Q(data_validade__gte=timezone.now().date())  # OU recompensas cuja validade ainda não expirou
        ).order_by("pontos_necessarios")                   # Ordena da recompensa mais barata para a mais cara
 
    # ──────────────────────────────────────────────────────────────
    # Dispatcher de eventos (mesmo padrão do PointService)
    # ──────────────────────────────────────────────────────────────
 
    @classmethod
    def process_event(cls, event_name, **kwargs):          # Método dispatcher que roteia eventos para seus handlers, igual ao PointService
        """
        Dispatcher de eventos do ResgateService.
        Permite desacoplar chamadas diretas ao serviço usando nomes de eventos.
        """
 
        handlers = {                                       # Dicionário mapeando nome do evento para o método handler correspondente
            "recompensa.resgatada": cls.resgatar,          # Evento disparado quando um usuário solicita um resgate
        }
 
        handler = handlers.get(event_name)                 # Busca o handler correspondente ao evento recebido
 
        if not handler:                                    # Se o evento não estiver registrado no dicionário
            raise ValueError(                              # Lança erro informando que o evento é desconhecido
                f"Evento desconhecido: {event_name}"       # Mensagem de erro com o nome do evento inválido
            )
 
        return handler(**kwargs)                           # Chama o handler passando os argumentos recebidos via kwargs
 