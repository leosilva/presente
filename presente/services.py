from django.db.models import Sum
from .models import (
    Gamificacao,
    TrilhaGamificacao,
    UsuarioGamificacao,
    Activity,
    Attendance,
    MarcosDiversidade,
    
)

class PointService:
    
    @classmethod
    def debit_gamificacao(cls, user, gamificacao):
        deleted, _ = UsuarioGamificacao.objects.filter(user=user, gamificacao=gamificacao).delete() # Deleta a gamificacao do usuário e armazena dentro de deleted
        return deleted > 0 #.delete é praticamente um booleano, então se ele retorna 1 o delete funcionou. Se retorna 0, o delete não funcionou

    @classmethod
    def credit_gamificacao(cls, user, gamificacao):
        obj, created = UsuarioGamificacao.objects.get_or_create(
            # O get_or_create já garante se há duplicatas.
            # Pois caso o User já tenha a gamificação, ele
            # utiliza o get, caso não, ele utiliza o create
            user=user,
            gamificacao=gamificacao
        )
        return created

    @classmethod
    def get_user_gamificacoes(cls, user):
        user_gamificacao = UsuarioGamificacao.objects.filter(user=user).select_related('gamificacao') # Acessa o banco de dados e pega todas as gamificações associadas ao usuário
        return user_gamificacao

    @classmethod
    def _on_attendance_canceled(cls, attendance):   
        if not attendance.activity: # Verifica se há atividade registrada na presença
            return
        if not attendance.activity.gamificacao: # Verifica se o usuário recebeu a pontuação
            return
        user = attendance.user
        gamificacao = attendance.activity.gamificacao
        cls.debit_gamificacao(user, gamificacao) # Chama o método debit_gamificacao

    @classmethod
    def _on_attendance_created(cls, attendance):
        if not attendance.activity: # Verifica se há atividade registrada na presença
            return
        if not attendance.activity.gamificacao: # Verifica se tem alguma gamificação associada ao usuário
            return
        user = attendance.user
        gamificacao = attendance.activity.gamificacao
        cls.credit_gamificacao(user, gamificacao) # Chama o método credit_gamificacao
         # Verifica bônus de trilha
        if attendance.activity.trilha:
            cls._check_trilha_bonus(user, attendance.activity.trilha)

        # Verifica bônus de diversidade
        data_checkin = attendance.checked_in_at.date()
        cls._check_diversidade_bonus(user, data_checkin)

    @classmethod
    def calculate_user_point(cls, user):
        total_pontos = UsuarioGamificacao.objects.filter(user=user).aggregate(total=Sum('gamificacao__pontos'))
        '''Acessa o banco de dados e pega todas as 
        gamificações associadas ao usuário e usa o aggregate para navegar pelas
        tabelas e somar os pontos usando Sum
        '''
        return total_pontos.get('total') or 0 # Retorna o total de pontos. caso não tenha pontos, retorna 0

    @classmethod
    def _on_user_created(cls, user):
        user_gamificacao = Gamificacao.objects.filter(titulo="Boas-vindas").first()
        if not user_gamificacao:
            return 
        cls.credit_gamificacao(user, user_gamificacao)

    @classmethod
    def process_event(cls, event_name, **kwargs):
        handlers = {
            "user.created": cls._on_user_created,
            "attendance.created": cls._on_attendance_created,
            "attendance.canceled": cls._on_attendance_canceled,
        }
        handler = handlers.get(event_name)
        if not handler:
            raise ValueError(f"Evento Desconhecido: {event_name}")
        return handler (**kwargs)
    
    @classmethod
    def _check_trilha_bonus(cls, user, trilha):
        # Guard: trilha precisa ter bônus configurado
        if not trilha.gamificacao_bonus:
            return
        if not trilha.minimo_atividades:
            return

        # Evita conceder o bônus mais de uma vez
        ja_tem_bonus = UsuarioGamificacao.objects.filter(
            user=user,
            gamificacao=trilha.gamificacao_bonus
        ).exists()
        if ja_tem_bonus:
            return

        # Conta presenças do usuário em atividades desta trilha
        presencas_na_trilha = Attendance.objects.filter(
            user=user,
            activity__trilha=trilha
        ).count()

        if presencas_na_trilha >= trilha.minimo_atividades:
            cls.credit_gamificacao(user, trilha.gamificacao_bonus)
    @classmethod
    def _check_diversidade_bonus(cls, user, data):
        # Pega todas as áreas distintas em que o usuário participou no dia
        areas_no_dia = (
            Attendance.objects.filter(
                user=user,
                checked_in_at__date=data,
                activity__area__isnull=False  # ignora atividades sem área
            )
            .values_list("activity__area", flat=True)
            .distinct()
        )
        total_areas = areas_no_dia.count()

        if total_areas == 0:
            return

        # Verifica todos os marcos que o usuário pode ter atingido
        marcos = MarcosDiversidade.objects.filter(
            areas_necessarias__lte=total_areas  # marcos que o usuário já atingiu
        ).select_related("gamificacao_bonus")

        for marco in marcos:
            ja_tem_bonus = UsuarioGamificacao.objects.filter(
                user=user,
                gamificacao=marco.gamificacao_bonus
            ).exists()
            if not ja_tem_bonus:
                cls.credit_gamificacao(user, marco.gamificacao_bonus)
