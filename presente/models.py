from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from taggit.managers import TaggableManager
from django.db.models import Case, When, Value, IntegerField

User = get_user_model()


class Network(models.Model):
    name = models.CharField(
        _("Nome"),
        max_length=100,
        unique=True,
        help_text=_("Nome identificador da rede (ex: 'Campus Natal Central')"),
    )
    description = models.TextField(
        _("Descrição"),
        blank=True,
        help_text=_("Descrição opcional da rede"),
    )
    ip_addresses = models.TextField(
        _("Endereços IP/Redes"),
        help_text=_(
            "IPs ou redes permitidas (um por linha). "
            "Exemplo: 192.168.1.0/24 ou 10.0.0.1"
        ),
    )
    is_active = models.BooleanField(
        _("Ativo"),
        default=True,
        help_text=_("Desmarque para desativar temporariamente esta rede"),
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Rede")
        verbose_name_plural = _("Redes")
        ordering = ["name"]


class ActivityQuerySet(models.QuerySet):
    def with_status_order(self):
        now = timezone.now()
        return self.annotate(
            status_order=Case(
                When(end_time__lt=now, then=Value(3)),
                When(start_time__gt=now, then=Value(1)),
                When(is_enabled=False, then=Value(2)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )


class ActivityManager(models.Manager):
    def get_queryset(self):
        return ActivityQuerySet(self.model, using=self._db).with_status_order()


class Activity(models.Model):
    owners = models.ManyToManyField(
        User,
        related_name="owned_activities",
        verbose_name=_("Responsáveis"),
    )
    title = models.CharField(_("Título"), max_length=100)
    tags = TaggableManager(
        verbose_name=_("Tags"),
        help_text=_(
            "Tags para organizar as atividades (ex: 'Workshop 2024', 'Python')"
        ),
        blank=True,
    )
    start_time = models.DateTimeField(_("Início"))
    end_time = models.DateTimeField(_("Término"))
    is_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Habilitar?"),
        help_text=_("Habilitar o registro de presença."),
    )
    qr_timeout = models.IntegerField(
        _("Timeout do QR Code (segundos)"),
        default=0,
        help_text=_(
            'Tempo de validade de cada QR Code para registro de presença (em segundos). Use "0" para desabilitar.'
        ),
    )
    restrict_ip = models.BooleanField(
        _("Restringir por IP"),
        default=False,
        help_text=_("Ativar restrição de acesso por endereço IP"),
    )
    allowed_networks = models.ManyToManyField(
        Network,
        verbose_name=_("Redes permitidas"),
        blank=True,
        help_text=_("Selecione as redes que podem acessar esta atividade"),
    )
    trilha = models.ForeignKey(
        "TrilhaGamificacao",
        on_delete=models.CASCADE,
        related_name="activities",
        verbose_name=_("Trilha"),
    )
    gamificacao = models.ForeignKey(
        "Gamificacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
        verbose_name=_("Gamificação associada"),
        help_text=_("Gamificação concedida ao registrar presença nesta atividade."),
    )
    evento = models.ForeignKey(
        "Evento",
        on_delete=models.CASCADE,
        related_name="activities",
        verbose_name=_("Evento"),
        null=True,
        blank=True,
    )
    area = models.ForeignKey(
        "Area",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
        verbose_name=_("Área"),
        help_text=_("Área temática desta atividade"),
    )
    created_at = models.DateTimeField(
        _("Criação"), auto_now_add=True, null=True, blank=True
    )
    modified_at = models.DateTimeField(
        _("Modificação"), auto_now=True, null=True, blank=True
    )

    objects = ActivityManager()

    def clean(self):
        if self.gamificacao and self.trilha:
            if self.gamificacao.trilha != self.trilha:
                raise ValidationError(
                    _("A gamificação deve pertencer à mesma trilha da atividade.")
                )
        if self.evento and self.start_time and self.end_time:
            if self.start_time < self.evento.data_inicio:
                raise ValidationError(
                    _("A atividade não pode iniciar antes do evento.")
                )
            if self.end_time > self.evento.data_fim:
                raise ValidationError(
                    _("A atividade não pode terminar após o evento.")
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def status(self):
        if timezone.now() > self.end_time:
            return "expired"
        elif timezone.now() < self.start_time:
            return "not_started"
        elif not self.is_enabled:
            return "not_enabled"
        else:
            return "active"

    def is_ip_allowed(self, client_ip):
        if not self.restrict_ip:
            return True

        active_networks = self.allowed_networks.filter(is_active=True)

        if not active_networks.exists():
            return False

        from ipaddress import ip_address, ip_network

        try:
            client_addr = ip_address(client_ip)
            for network_config in active_networks:
                ip_list = [
                    ip.strip()
                    for ip in network_config.ip_addresses.split("\n")
                    if ip.strip()
                ]
                for ip_entry in ip_list:
                    try:
                        if "/" in ip_entry:
                            network_obj = ip_network(ip_entry, strict=False)
                            if client_addr in network_obj:
                                return True
                        else:
                            ip_addr = ip_address(ip_entry)
                            if client_addr == ip_addr:
                                return True
                    except ValueError:
                        continue
            return False
        except ValueError:
            return False

    class Meta:
        verbose_name = _("Atividade")
        verbose_name_plural = _("Atividades")


class Attendance(models.Model):
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="attendances",
        verbose_name=_("Atividade"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="attendances",
        verbose_name=_("Usuário"),
    )
    checked_in_at = models.DateTimeField(_("Registrado em"), auto_now_add=True)
    ip_address = models.GenericIPAddressField(
        _("Endereço IP"),
        blank=True,
        null=True,
        help_text=_("Endereço IP do usuário no momento do check-in"),
    )

    def __str__(self):
        return f"{self.user} - {self.activity}"

    def get_network_name(self):
        if not self.ip_address:
            return "-"

        from ipaddress import ip_address, ip_network

        try:
            client_addr = ip_address(self.ip_address)
            for network_config in Network.objects.filter(is_active=True):
                ip_list = [
                    ip.strip()
                    for ip in network_config.ip_addresses.split("\n")
                    if ip.strip()
                ]
                for ip_entry in ip_list:
                    try:
                        if "/" in ip_entry:
                            network_obj = ip_network(ip_entry, strict=False)
                            if client_addr in network_obj:
                                return network_config.name
                        else:
                            ip_addr = ip_address(ip_entry)
                            if client_addr == ip_addr:
                                return network_config.name
                    except ValueError:
                        continue
            return self.ip_address
        except ValueError:
            return self.ip_address

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            from .services import PointService
            PointService.process_event("attendance.created", attendance=self)

    class Meta:
        verbose_name = _("Presença")
        verbose_name_plural = _("Presenças")
        unique_together = [["activity", "user"]]
        ordering = ["-checked_in_at"]


class AttendanceRemovalLog(models.Model):
    """
    Auditoria de remoções de presença feitas por responsáveis.
    Preserva um snapshot dos dados da presença mesmo após a deleção.
    """
    removed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="attendance_removals",
        verbose_name=_("Removido por"),
    )
    removed_at = models.DateTimeField(_("Removido em"), auto_now_add=True)
    justificativa = models.TextField(
        _("Justificativa"),
        help_text=_("Motivo da remoção da presença."),
    )
    activity = models.ForeignKey(
        "Activity",
        on_delete=models.SET_NULL,
        null=True,
        related_name="removal_logs",
        verbose_name=_("Atividade"),
    )
    attendance_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="removal_logs",
        verbose_name=_("Usuário da presença"),
    )
    checked_in_at_snapshot = models.DateTimeField(
        _("Registrado em (original)"),
        help_text=_("Data/hora original do check-in, preservada para histórico."),
    )

    class Meta:
        verbose_name = _("Log de Remoção de Presença")
        verbose_name_plural = _("Logs de Remoção de Presença")
        ordering = ["-removed_at"]

    def __str__(self):
        return (
            f"Remoção de {self.attendance_user} em "
            f"{self.activity} por {self.removed_by}"
        )


class Area(models.Model):
    nome = models.CharField(
        _("Nome"),
        max_length=100,
        unique=True,
        help_text=_("Ex: Informática, Jogos, EBM"),
    )
    descricao = models.TextField(_("Descrição"), blank=True)

    class Meta:
        verbose_name = _("Área")
        verbose_name_plural = _("Áreas")
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class MarcosDiversidade(models.Model):
    areas_necessarias = models.PositiveIntegerField(
        _("Áreas necessárias"),
        help_text=_("Quantidade de áreas diferentes no mesmo dia para ganhar o bônus"),
    )
    gamificacao_bonus = models.ForeignKey(
        "Gamificacao",
        on_delete=models.CASCADE,
        related_name="marcos_diversidade",
        verbose_name=_("Gamificação de bônus"),
        help_text=_("Gamificação concedida ao atingir este marco"),
    )
    descricao = models.TextField(
        _("Descrição"),
        blank=True,
        help_text=_("Ex: Participou de 3 áreas diferentes no mesmo dia"),
    )

    class Meta:
        verbose_name = _("Marco de Diversidade")
        verbose_name_plural = _("Marcos de Diversidade")
        ordering = ["areas_necessarias"]

    def __str__(self):
        return f"{self.areas_necessarias} áreas → {self.gamificacao_bonus}"


class TrilhaGamificacao(models.Model):
    name = models.CharField(_("Nome"), max_length=100, default="Trilha de Entrada")
    descricao = models.TextField(
        _("Descrição"),
        blank=True,
        help_text=_("Descrição da trilha"),
    )
    minimo_atividades = models.PositiveIntegerField(
        _("Mínimo de atividades para completar"),
        default=1,
        help_text=_("Quantidade mínima de presenças na trilha para ganhar o bônus"),
    )
    gamificacao_bonus = models.ForeignKey(
        "Gamificacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trilhas_bonus",
        verbose_name=_("Gamificação de bônus"),
        help_text=_("Gamificação concedida ao completar a trilha."),
    )

    class Meta:
        verbose_name = _("Trilha")
        verbose_name_plural = _("Trilhas")
        ordering = ["name"]

    def __str__(self):
        return self.name


class TipoGamificacao(models.Model):
    class Tipo(models.TextChoices):
        BADGE = "BDG", _("Badge")
        TROFEU = "TRF", _("Troféu")
        MEDALHA = "MDL", _("Medalha")

    trilha = models.ForeignKey(
        TrilhaGamificacao, on_delete=models.CASCADE, related_name="tipos"
    )
    tipo = models.CharField(_("Tipo"), max_length=3, choices=Tipo.choices)
    icone = models.ImageField(
        _("Ícone"), upload_to="gamificacao/icones/", blank=True, null=True
    )
    descricao = models.TextField(_("Descrição"), blank=True)

    class Meta:
        verbose_name = _("Tipo de gamificação")
        verbose_name_plural = _("Tipos de gamificação")
        constraints = [
            models.UniqueConstraint(
                fields=["trilha", "tipo"], name="unique_tipo_por_trilha"
            )
        ]
        ordering = ["tipo"]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.trilha.name}"


class Gamificacao(models.Model):
    titulo = models.CharField(
        _("Título"),
        max_length=150,
        help_text=_("Nome da gamificação ou conquista"),
    )
    tipo = models.ForeignKey(
        "TipoGamificacao",
        on_delete=models.PROTECT,
        related_name="gamificacoes",
        verbose_name=_("Tipo"),
    )
    trilha = models.ForeignKey(
        "TrilhaGamificacao",
        on_delete=models.CASCADE,
        related_name="gamificacoes",
        verbose_name=_("Trilha"),
    )
    pontos = models.PositiveIntegerField(
        _("Pontos"),
        default=0,
        help_text=_("Quantidade de pontos concedidos"),
    )

    def clean(self):
        if self.tipo.trilha != self.trilha:
            raise ValidationError(
                _("O tipo de gamificação deve pertencer à mesma trilha.")
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Gamificação")
        verbose_name_plural = _("Gamificações")
        ordering = ["titulo"]

    def __str__(self):
        return f"{self.titulo} — {self.trilha.name}"


class UsuarioGamificacao(models.Model):
    """
    Registro de posse de conquistas do usuário.
    NÃO representa saldo de pontos — o saldo é calculado exclusivamente
    pelo PointHistory.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="gamificacoes_recebidas",
        verbose_name=_("Usuário"),
    )
    gamificacao = models.ForeignKey(
        Gamificacao,
        on_delete=models.CASCADE,
        related_name="usuarios",
        verbose_name=_("Gamificação"),
    )
    data_concedida = models.DateTimeField(_("Data concedida"), auto_now_add=True)

    class Meta:
        unique_together = ["user", "gamificacao"]


class Campus(models.Model):
    nome = models.CharField(_("Nome"), max_length=100, unique=True)

    class Meta:
        verbose_name = _("Campus")
        verbose_name_plural = _("Campi")
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Evento(models.Model):
    class TipoEvento(models.TextChoices):
        EXPOTEC = "EXP", _("EXPOTEC")
        SEMADEC = "SEM", _("SEMADEC")
        OUTRO = "OUT", _("Outro")

    nome = models.CharField(_("Nome"), max_length=150)
    campus = models.ManyToManyField(Campus, verbose_name=_("Campus"), related_name="eventos")
    tipo = models.CharField(_("Tipo"), max_length=3, choices=TipoEvento.choices)
    data_inicio = models.DateTimeField(_("Data de Início"))
    data_fim = models.DateTimeField(_("Data de Fim"))
    descricao = models.TextField(_("Descrição"), blank=True)

    class Meta:
        verbose_name = _("Evento")
        verbose_name_plural = _("Eventos")
        ordering = ["-data_inicio"]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

    def clean(self):
        if self.data_inicio and self.data_fim:
            if self.data_fim < self.data_inicio:
                raise ValidationError(
                    _("A data de fim não pode ser anterior à data de início.")
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class PointHistory(models.Model):
    """
    Registro imutável de cada crédito ou débito de pontuação.
    É a fonte única de verdade para o saldo de pontos do usuário.
    """
    class TipoMovimento(models.TextChoices):
        CREDITO = "CRD", _("Crédito")
        DEBITO = "DEB", _("Débito")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="point_history",
        verbose_name=_("Usuário"),
    )
    gamificacao = models.ForeignKey(
        "Gamificacao",
        on_delete=models.CASCADE,
        related_name="point_history",
        verbose_name=_("Gamificação"),
        null=True,
        blank=True,
    )
    tipo = models.CharField(_("Tipo"), max_length=3, choices=TipoMovimento.choices)
    pontos = models.IntegerField(
        _("Pontos"),
        help_text=_("Positivo para crédito, negativo para débito."),
    )
    motivo = models.TextField(
        _("Motivo"),
        blank=True,
        help_text=_("Descrição automática do motivo do movimento."),
    )
    criado_em = models.DateTimeField(_("Criado em"), auto_now_add=True)

    class Meta:
        verbose_name = _("Histórico de Pontos")
        verbose_name_plural = _("Histórico de Pontos")
        ordering = ["-criado_em"]

    def __str__(self):
        sinal = "+" if self.tipo == self.TipoMovimento.CREDITO else "-"
        gamificacao_str = self.gamificacao or "Troca de brinde"
        return f"{self.user} | {sinal}{self.pontos}pts | {gamificacao_str}"


class Nivel(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome")
    pontos_minimos = models.PositiveIntegerField(
        _("Pontos mínimos"),
        default=0,
        unique=True,
        help_text="Quantidade de pontos mínimos para estar nesse nível",
    )

    def __str__(self):
        return self.nome

    class Meta:
        ordering = ["pontos_minimos"]
        verbose_name = "Nível"
        verbose_name_plural = "Níveis"


class PerfilGamificado(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil_gamificado",
        verbose_name=_("Usuário"),
    )
    nivel = models.ForeignKey(
        Nivel,
        on_delete=models.SET_NULL,
        related_name="nivel_perfil",
        verbose_name=_("Nível"),
        null=True,
        blank=True,
    )
    titulo = models.CharField(
        max_length=155, verbose_name=_("Titulo"), blank=True, null=True
    )

    def __str__(self):
        return f"{self.user} - {self.nivel}"

    class Meta:
        verbose_name = "Perfil Gamificado"
        verbose_name_plural = "Perfis Gamificados"


class Brinde(models.Model):
    """
    Representa um brinde disponível na loja de recompensas de um evento.
    O estoque é controlado numericamente por quantidade_disponivel.
    """
    evento = models.ForeignKey(
        "Evento",
        on_delete=models.CASCADE,
        related_name="brindes",
        verbose_name=_("Evento"),
        help_text=_("Evento ao qual este brinde pertence."),
    )
    nome = models.CharField(_("Nome"), max_length=255)
    descricao = models.TextField(_("Descrição"), blank=True)
    pontos_necessarios = models.PositiveIntegerField(
        _("Pontos necessários"),
        help_text=_("Custo em pontos por unidade deste brinde."),
    )
    quantidade_disponivel = models.PositiveIntegerField(
        _("Quantidade disponível"),
        help_text=_("Estoque total disponível para troca."),
    )
    data_validade = models.DateField(_("Data de validade"), null=True, blank=True)
    ativo = models.BooleanField(_("Ativo"), default=True)
    criado_em = models.DateTimeField(_("Criado em"), auto_now_add=True)

    @property
    def disponivel(self):
        """Verifica se o brinde pode ser trocado no momento."""
        if not self.ativo or self.quantidade_disponivel <= 0:
            return False
        if self.data_validade and self.data_validade < timezone.now().date():
            return False
        return True

    class Meta:
        verbose_name = _("Brinde")
        verbose_name_plural = _("Brindes")
        ordering = ["pontos_necessarios"]

    def __str__(self):
        return f"{self.nome} ({self.pontos_necessarios} pts/un)"


class Troca(models.Model):
    """
    Cabeçalho de uma transação de troca de pontos por brindes.
    Agrupa um ou mais itens trocados de uma só vez pelo usuário.
    """
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="trocas",
        verbose_name=_("Usuário"),
    )
    pontos_gastos = models.PositiveIntegerField(
        _("Pontos gastos"),
        help_text=_("Total de pontos gastos nesta troca (soma de todos os itens)."),
    )
    data = models.DateTimeField(_("Data da troca"), auto_now_add=True)

    class Meta:
        verbose_name = _("Troca")
        verbose_name_plural = _("Trocas")
        ordering = ["-data"]

    def __str__(self):
        return f"Troca #{self.pk} — {self.usuario} ({self.pontos_gastos} pts)"


class ItemRecompensa(models.Model):
    """
    Representa cada linha de uma troca — um brinde específico e sua quantidade.
    É o registro de débito no estoque do brinde.
    Uma troca pode ter múltiplos itens (brindes diferentes ou quantidades > 1).
    """
    troca = models.ForeignKey(
        Troca,
        on_delete=models.CASCADE,
        related_name="itens",
        verbose_name=_("Troca"),
    )
    brinde = models.ForeignKey(
        Brinde,
        on_delete=models.PROTECT,
        related_name="itens",
        verbose_name=_("Brinde"),
    )
    quantidade = models.PositiveIntegerField(
        _("Quantidade"),
        default=1,
        help_text=_("Quantidade de unidades deste brinde nesta troca."),
    )
    pontos_unitarios = models.PositiveIntegerField(
        _("Pontos unitários"),
        help_text=_("Snapshot do custo por unidade no momento da troca."),
    )

    @property
    def pontos_total(self):
        """Total de pontos gastos neste item (quantidade × pontos unitários)."""
        return self.quantidade * self.pontos_unitarios

    class Meta:
        verbose_name = _("Item de Recompensa")
        verbose_name_plural = _("Itens de Recompensa")

    def __str__(self):
        return f"{self.quantidade}x {self.brinde.nome} — Troca #{self.troca.pk}"


class Conquista(models.Model):
    class TipoRegra(models.TextChoices):
        NUMERO_PRESENCAS = "NUMERO_PRESENCAS", _("Número de Presenças")
        NUMERO_AREAS_DIFERENTES = "NUMERO_AREAS_DIFERENTES", _("Número de Áreas Diferentes")
        NUMERO_ATIVIDADES = "NUMERO_ATIVIDADES", _("Número de Atividades")
        PRIMEIRA_PRESENCA = "PRIMEIRA_PRESENCA", _("Primeira Presença")

    nome = models.CharField(
        _("Nome Conquista"),
        max_length=155    
    )
    descricao = models.TextField(
        _("Descrição"),
        blank=True,
        help_text=_("Descrição da Conquista")
    )
    icone = models.ImageField(
        _("Ícone"),
        upload_to="gamificacao/icones/",
        blank=True,
        null=True
    )
    tipo_regra = models.CharField(
        _("Tipo da Regra"), 
        max_length=155, 
        choices=TipoRegra.choices,
        default=TipoRegra.PRIMEIRA_PRESENCA,
    )
    valor_necessario = models.PositiveIntegerField(
        _("Valor necessário"),
        default=1,
        help_text=_("Valor necessário para alcançar a conquista")
    )    
    pontos = models.PositiveIntegerField(
        _("Pontos"),
        default=0,
        help_text=_("Quantidade de pontos da conquista")
    )
    status = models.BooleanField(
        _("Ativo"),
        default=True
    )

# Modelo que representa usuário, conquista e data em que foi desbloqueada
class ConquistaUsuario(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("Usuário")
    )

    conquista = models.ForeignKey(
        Conquista,
        on_delete=models.CASCADE,
        verbose_name=_("Conquista do Usuário")
    )

    evento = models.ForeignKey(
        Evento,
        on_delete=models.CASCADE,
        verbose_name=_("Evento da conquista")
    )

    data_desbloqueio = models.DateField(
        _("Data de desbloqueio da conquista"),
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "conquista"],
                name="unique_usuario_conquista"
            )
        ]