import django_tables2
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from .models import Activity, Attendance, Network,Evento


class CoreTable(django_tables2.Table):
    actions = django_tables2.TemplateColumn(
        template_name="core/includes/actions.html",
        orderable=False,
        verbose_name=_("Ações"),
        exclude_from_export=True,
    )


class ActivityTable(CoreTable):
    status = django_tables2.Column(
        verbose_name=_("Status"),
        orderable=True,
        order_by="status_order",
        empty_values=(),
    )
    tags_list = django_tables2.TemplateColumn(
        template_name="presente/includes/tags_column.html",
        verbose_name=_("Tags"),
        orderable=True,
        order_by="tags__name",
        exclude_from_export=True,
    )
    evento = django_tables2.Column(
    verbose_name=_("Evento"),
    accessor="evento",
    orderable=True,
)

    def render_status(self, record):
        status_map = {
            "active": '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Ativa</span>',
            "not_started": '<span class="badge bg-warning text-dark"><i class="bi bi-hourglass-split"></i> Não Iniciada</span>',
            "expired": '<span class="badge bg-secondary"><i class="bi bi-clock-history"></i> Encerrada</span>',
            "not_enabled": '<span class="badge bg-danger"><i class="bi bi-x-circle"></i> Desabilitada</span>',
        }
        return mark_safe(status_map.get(record.status, ""))

    class Meta:
        model = Activity
        fields = ("title", "evento", "tags_list", "start_time", "end_time", "status")


class AttendanceTable(django_tables2.Table):
    activity_title = django_tables2.Column(
        accessor="activity__title",
        verbose_name=_("Atividade"),
        orderable=True,
    )
    activity_tags = django_tables2.TemplateColumn(
        template_name="presente/includes/tags_column_attendance.html",
        verbose_name=_("Tags"),
        orderable=False,
    )
    activity_start = django_tables2.DateTimeColumn(
        accessor="activity__start_time",
        verbose_name=_("Início da Atividade"),
        format="d/m/Y H:i",
        orderable=True,
    )
    activity_end = django_tables2.DateTimeColumn(
        accessor="activity__end_time",
        verbose_name=_("Término da Atividade"),
        format="d/m/Y H:i",
        orderable=True,
    )
    checked_in_at = django_tables2.DateTimeColumn(
        verbose_name=_("Presença Registrada em"),
        format="d/m/Y H:i:s",
        orderable=True,
    )

    class Meta:
        model = Attendance
        fields = (
            "activity_title",
            "activity_tags",
            "activity_start",
            "activity_end",
            "checked_in_at",
        )
        order_by = "-checked_in_at"


class ActivityAttendanceTable(django_tables2.Table):
    user_name = django_tables2.Column(
        accessor="user",
        verbose_name=_("Nome"),
        orderable=True,
        order_by=("user__full_name_normalized", "user__full_name"),
    )
    user_type = django_tables2.Column(
        accessor="user__type",
        verbose_name=_("Tipo"),
        orderable=True,
    )
    user_curso = django_tables2.Column(
        accessor="user__curso",
        verbose_name=_("Curso"),
        orderable=True,
    )
    user_periodo_referencia = django_tables2.Column(
        accessor="user__periodo_referencia",
        verbose_name=_("Período de Referência"),
        orderable=True,
    )
    checked_in_at = django_tables2.DateTimeColumn(
        verbose_name=_("Presença Registrada em"),
        format="d/m/Y H:i:s",
        orderable=True,
    )
    actions = django_tables2.TemplateColumn(
        template_name="presente/includes/attendance_actions.html",
        orderable=False,
        verbose_name=_("Ações"),
        exclude_from_export=True,
    )

    def render_user_name(self, record):
        return record.user.get_full_name()

    def render_user_curso(self, record):
        return record.user.curso or "-"

    def render_user_periodo_referencia(self, record):
        return record.user.periodo_referencia or "-"

    class Meta:
        model = Attendance
        fields = (
            "user_name",
            "user_type",
            "user_curso",
            "user_periodo_referencia",
            "checked_in_at",
        )
        order_by = "-checked_in_at"


class NetworkTable(CoreTable):
    class Meta:
        model = Network
        fields = ("name", "description", "is_active")
        attrs = {"class": "table table-striped"}
class EventoTable(django_tables2.Table):
    atividades = django_tables2.TemplateColumn(
    template_code="""
        <a href="{% url 'presente:evento-atividades' record.pk %}"
           class="btn btn-sm btn-outline-primary">
           Ver Atividades
        </a>
    """,
    verbose_name="Atividades",
    orderable=False,
)
    class Meta:
        model = Evento
        fields = ("nome", "tipo", "data_inicio", "data_fim","atividades")

