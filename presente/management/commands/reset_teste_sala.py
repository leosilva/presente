from django.core.management.base import BaseCommand
from django.db import transaction

from presente.models import (
    Activity,
    Attendance,
    AttendanceRemovalLog,
    Brinde,
    ConquistaUsuario,
    Evento,
    Gamificacao,
    ItemRecompensa,
    PerfilGamificado,
    PointHistory,
    TipoGamificacao,
    Troca,
    TrilhaGamificacao,
    UsuarioGamificacao,
)


class Command(BaseCommand):
    help = (
        "Zera historico de gamificacao (pontos, presencas, trocas, "
        "eventos/atividades/trilhas antigos) para o piloto de sala de aula. "
        "Mantem usuarios, niveis, conquistas (regras), areas e bonus de "
        "diversidade. Por padrao so mostra as contagens (dry-run); use "
        "--apply para apagar de verdade."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Executa o apagamento. Sem essa flag, so mostra as contagens.",
        )

    def handle(self, *args, **options):
        counts = {
            "ItemRecompensa": ItemRecompensa.objects.count(),
            "Troca": Troca.objects.count(),
            "PointHistory": PointHistory.objects.count(),
            "AttendanceRemovalLog": AttendanceRemovalLog.objects.count(),
            "Attendance": Attendance.objects.count(),
            "Brinde": Brinde.objects.count(),
            "ConquistaUsuario": ConquistaUsuario.objects.count(),
            "Activity": Activity.objects.count(),
            "Evento": Evento.objects.count(),
            "UsuarioGamificacao": UsuarioGamificacao.objects.count(),
            "Gamificacao": Gamificacao.objects.count(),
            "TipoGamificacao": TipoGamificacao.objects.count(),
            "TrilhaGamificacao": TrilhaGamificacao.objects.count(),
        }

        self.stdout.write(self.style.WARNING("Contagens atuais (serao apagadas):"))
        for label, value in counts.items():
            self.stdout.write(f"  {label}: {value}")

        perfis_com_nivel = PerfilGamificado.objects.exclude(nivel=None).count()
        self.stdout.write(
            f"  PerfilGamificado com nivel/titulo a resetar: {perfis_com_nivel} "
            "(o perfil nao e apagado, so o nivel/titulo volta a vazio)"
        )

        self.stdout.write(
            self.style.WARNING(
                "\nMANTIDOS: usuarios/contas SUAP, niveis, conquistas (regras), "
                "areas e bonus de diversidade."
            )
        )

        if not options["apply"]:
            self.stdout.write(
                self.style.NOTICE(
                    "\nDry-run - nada foi apagado. Rode de novo com --apply para executar."
                )
            )
            return

        with transaction.atomic():
            # ItemRecompensa/Troca antes de Brinde: ItemRecompensa.brinde e
            # PROTECT, entao precisa sumir antes do Evento (que cascateia
            # Brinde) ser apagado.
            ItemRecompensa.objects.all().delete()
            Troca.objects.all().delete()

            # Nao sao 100% cobertos por cascata a partir de Evento/Trilha:
            # PointHistory tem gamificacao nullable (troca de brinde nao
            # tem gamificacao) e AttendanceRemovalLog usa SET_NULL.
            PointHistory.objects.all().delete()
            AttendanceRemovalLog.objects.all().delete()

            # Cascateia Activity, Attendance, Brinde, ConquistaUsuario.
            Evento.objects.all().delete()

            # Gamificacao antes de Trilha: Gamificacao.tipo e PROTECT, e o
            # Django nao garante que o cascade Trilha->Gamificacao seja
            # processado antes do cascade Trilha->TipoGamificacao (que essa
            # protecao bloquearia). Apagando Gamificacao primeiro, cascateia
            # UsuarioGamificacao; depois a Trilha cascateia TipoGamificacao
            # sem mais nada protegendo.
            Gamificacao.objects.all().delete()
            TrilhaGamificacao.objects.all().delete()

            PerfilGamificado.objects.update(nivel=None, titulo=None)

        self.stdout.write(self.style.SUCCESS("\nReset concluido."))
