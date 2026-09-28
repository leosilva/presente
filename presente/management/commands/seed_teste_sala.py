import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from presente.models import (
    Activity,
    Area,
    Campus,
    Evento,
    Gamificacao,
    TipoGamificacao,
    TrilhaGamificacao,
)

User = get_user_model()

EVENTO_NOME = "Aulas - INFO 2 Vespertino (piloto)"

TRILHAS = ["Exatas", "Propedeuticas/Tecnicas", "Humanas", "Programacao", "Geral"]
AREAS = ["Exatas", "Propedeuticas/Tecnicas", "Humanas", "Programacao"]

# (data ISO, hora inicio, hora fim, materia, professor(a), trilha)
# Horario de INFO 2 Vespertino; terca-feira ja corrigida (Ingles e Arte
# estavam trocados no horario original). Educacao Fisica nao se encaixa nas
# 4 trilhas tematicas, entao usa a trilha "Geral" e fica sem Area (nao conta
# pro bonus de diversidade de nenhuma trilha).
AULAS = [
    ("2026-09-29", "13:00", "14:30", "Ingles I", "Tito Matias", "Humanas"),
    ("2026-09-29", "14:50", "16:20", "Arte III", "Cristina Tapuya", "Humanas"),
    ("2026-09-29", "16:30", "18:00", "Matematica II", "Suzany Medeiros", "Exatas"),
    ("2026-09-30", "13:00", "14:30", "Filosofia II", "Stanley Kreiter", "Humanas"),
    ("2026-09-30", "14:50", "16:20", "Redes de Computadores", "Diogo Cortez", "Propedeuticas/Tecnicas"),
    ("2026-09-30", "16:30", "18:00", "Organizacao e Montagem de Computadores", "Lennedy Soares", "Propedeuticas/Tecnicas"),
    ("2026-10-01", "13:00", "14:30", "Eletronica", "Thales Ramos", "Propedeuticas/Tecnicas"),
    ("2026-10-01", "14:50", "16:20", "Projeto de Banco de Dados", "Keylly Santos", "Programacao"),
    ("2026-10-01", "16:30", "18:00", "Organizacao e Montagem de Computadores", "Lennedy Soares", "Propedeuticas/Tecnicas"),
    ("2026-10-02", "13:00", "14:30", "Projeto de Banco de Dados", "Keylly Santos", "Programacao"),
    ("2026-10-02", "14:50", "16:20", "Matematica II", "Suzany Medeiros", "Exatas"),
    ("2026-10-02", "16:30", "18:00", "Educacao Fisica II", "Monica Lima", "Geral"),
]


class Command(BaseCommand):
    help = (
        "Cria o evento, trilhas, gamificacoes e atividades do piloto de "
        "sala de aula (INFO 2 Vespertino, 29/09 a 02/10/2026). Rode "
        "reset_teste_sala antes se quiser comecar do zero."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner-email",
            help=(
                "Email de um usuario ja existente para adicionar como "
                "responsavel (owner) em todas as atividades criadas."
            ),
        )
        parser.add_argument(
            "--pontos", type=int, default=10, help="Pontos por atividade (padrao: 10)."
        )
        parser.add_argument(
            "--qr-timeout",
            type=int,
            default=60,
            help="Timeout do QR Code em segundos (padrao: 60).",
        )

    def handle(self, *args, **options):
        if Evento.objects.filter(nome=EVENTO_NOME).exists():
            self.stderr.write(
                self.style.ERROR(
                    f'Ja existe um evento "{EVENTO_NOME}". Rode reset_teste_sala '
                    "antes (ou apague manualmente) para evitar duplicar dados."
                )
            )
            return

        owner = None
        if options["owner_email"]:
            owner = User.objects.filter(email=options["owner_email"]).first()
            if not owner:
                self.stdout.write(
                    self.style.WARNING(
                        f"Usuario com email {options['owner_email']} nao encontrado - "
                        "seguindo sem adicionar responsavel."
                    )
                )

        tz = timezone.get_current_timezone()
        primeiro_dia = datetime.date.fromisoformat(AULAS[0][0])
        ultimo_dia = datetime.date.fromisoformat(AULAS[-1][0])
        data_inicio = timezone.make_aware(
            datetime.datetime.combine(primeiro_dia, datetime.time(0, 0)), tz
        )
        data_fim = timezone.make_aware(
            datetime.datetime.combine(ultimo_dia, datetime.time(23, 59)), tz
        )

        evento = Evento.objects.create(
            nome=EVENTO_NOME,
            tipo=Evento.TipoEvento.OUTRO,
            data_inicio=data_inicio,
            data_fim=data_fim,
            descricao="Piloto de gamificacao com a turma de Informatica 2o ano vespertino.",
        )
        campi = Campus.objects.all()
        if campi.exists():
            evento.campus.set(campi)

        for nome_area in AREAS:
            Area.objects.get_or_create(nome=nome_area)
        areas_by_name = {a.nome: a for a in Area.objects.filter(nome__in=AREAS)}

        trilhas = {}
        tipos = {}
        for nome_trilha in TRILHAS:
            trilha, _ = TrilhaGamificacao.objects.get_or_create(name=nome_trilha)
            trilhas[nome_trilha] = trilha
            tipo, _ = TipoGamificacao.objects.get_or_create(
                trilha=trilha, tipo=TipoGamificacao.Tipo.BADGE
            )
            tipos[nome_trilha] = tipo

        criadas = 0
        for data_str, hora_ini, hora_fim, materia, professor, nome_trilha in AULAS:
            dia = datetime.date.fromisoformat(data_str)
            inicio = timezone.make_aware(
                datetime.datetime.combine(dia, datetime.time.fromisoformat(hora_ini)), tz
            )
            fim = timezone.make_aware(
                datetime.datetime.combine(dia, datetime.time.fromisoformat(hora_fim)), tz
            )
            trilha = trilhas[nome_trilha]

            gamificacao = Gamificacao.objects.create(
                titulo=f"Presenca - {materia} ({dia.strftime('%d/%m')})",
                tipo=tipos[nome_trilha],
                trilha=trilha,
                pontos=options["pontos"],
            )

            activity = Activity.objects.create(
                title=f"{materia} - {professor} ({dia.strftime('%d/%m')}, {hora_ini}-{hora_fim})",
                start_time=inicio,
                end_time=fim,
                is_enabled=True,
                qr_timeout=options["qr_timeout"],
                trilha=trilha,
                gamificacao=gamificacao,
                evento=evento,
                area=areas_by_name.get(nome_trilha),
            )
            if owner:
                activity.owners.add(owner)
            criadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Evento "{evento.nome}" criado com {criadas} atividades, '
                f"{len(trilhas)} trilhas e {len(tipos)} tipos de gamificacao."
            )
        )
