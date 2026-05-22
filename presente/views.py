from multiprocessing import context
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.views.generic.base import TemplateView,View
from django.views.generic import ListView
from django.views.generic.edit import FormView
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import get_object_or_404,render,redirect
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.http import Http404
from django.urls import reverse, reverse_lazy
from django_filters.views import FilterView
from django_weasyprint import WeasyTemplateResponseMixin
from django.core.exceptions import ValidationError
from core.mixins import PageTitleMixin, SuperuserRequiredMixin
from core.views import (
    CoreListView,
    CoreCreateView,
    CoreDetailView,
    CoreUpdateView,
    CoreDeleteView,
    CoreFilterView,
)
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
import os
import csv
from django.conf import settings
from django.http import HttpResponse
from .models import (
    Activity,
    Attendance,
    Network,
    Evento,
    UsuarioGamificacao,
    AttendanceRemovalLog,
    PointHistory,
    Brinde,
    Troca
    )
from .services import PointService,TrocaService
from .tables import (
    ActivityTable,
    AttendanceTable,
    ActivityAttendanceTable,
    NetworkTable,
    EventoTable,
)
from .forms import ActivityForm, AttendancePrintConfigForm, NetworkForm, EventoForm,AttendanceDeleteForm
from .filters import ActivityFilter, AttendanceFilter, ActivityAttendanceFilter
from .mixins import ActivityOwnerMixin
from .utils import (
    get_client_ip,
    encode_activity_id,
    decode_activity_id,
    generate_checkin_token,
    verify_checkin_token,
)

User = get_user_model()


class IndexView(LoginRequiredMixin, PageTitleMixin, TemplateView): # view da página inicial
    from .models import UsuarioGamificacao
    template_name = "presente/index.html"
    page_title = _("Dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_superuser:
            context["activities"] = Activity.objects.count()
        else:
            context["activities"] = Activity.objects.filter(
                owners=self.request.user
            ).count()
        context["my_attendances_count"] = Attendance.objects.filter(
            user=self.request.user
        ).count()
        context["recent_attendances"] = (
            Attendance.objects.filter(user=self.request.user)
            .select_related("activity")
            .order_by("-checked_in_at")[:5]
        )
        context["my_points"] = PointService.calculate_user_point(self.request.user)

        return context


class ActivityListView(CoreFilterView):
    page_title = _("Minhas Atividades")
    model = Activity
    table_class = ActivityTable
    filterset_class = ActivityFilter
    permission_required = []

    def get_queryset(self):
        return Activity.objects.filter(is_enabled=True).order_by(
            "-modified_at", "-start_time"
    )


class AdminActivitiesView(SuperuserRequiredMixin, CoreFilterView):
    page_title = _("Atividades")
    model = Activity
    table_class = ActivityTable
    filterset_class = ActivityFilter

    def get_queryset(self):
        return Activity.objects.all().order_by("-modified_at", "-start_time")


class ActivityCreateView(CoreCreateView):
    model = Activity
    page_title = _("Atividades")
    form_class = ActivityForm

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.owners.add(self.request.user)
        return response


class ActivityDetailView(CoreDetailView):
    model = Activity
    page_title = _("Atividades")
    template_name = "presente/activity_detail.html"

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Activity.objects.all()
        return Activity.objects.filter(owners=self.request.user)

    def get_fields(self):
        fields = super().get_fields()
        # Add owners to the fields list
        owners_list = ", ".join(
            [owner.get_full_name() or owner.email for owner in self.object.owners.all()]
        )
        fields.append(
            {
                "label": _("Responsáveis"),
                "value": owners_list if owners_list else "-",
                "safe": False,
            }
        )
        return fields

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["attendances"] = self.object.attendances.select_related("user").all()
        context["attendance_count"] = self.object.attendances.count()
        context["encoded_id"] = encode_activity_id(self.object.id)
        return context


class ActivityUpdateView(CoreUpdateView):
    model = Activity
    page_title = _("Atividades")
    form_class = ActivityForm

    def get_success_url(self):
        return reverse_lazy("presente:activity_view", kwargs={"pk": self.kwargs["pk"]})

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Activity.objects.all()
        return Activity.objects.filter(owners=self.request.user)


class ActivityDeleteView(CoreDeleteView):
    model = Activity

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Activity.objects.all()
        return Activity.objects.filter(owners=self.request.user)


# Public views for attendance


class PublicActivityView(TemplateView):
    template_name = "presente/public_activity.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        encoded_id = kwargs.get("encoded_id")

        activity_id = decode_activity_id(encoded_id)
        if not activity_id:
            raise Http404("Activity not found")

        activity = get_object_or_404(Activity, id=activity_id, is_enabled=True)

        context["activity"] = activity
        context["encoded_id"] = encoded_id

        return context


class ActivityQRCodeView(TemplateView):
    template_name = "presente/includes/qr_content.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        encoded_id = kwargs.get("encoded_id")
        now = timezone.now()

        context["server_time"] = now.isoformat()
        context["encoded_id"] = encoded_id

        activity_id = decode_activity_id(encoded_id)
        if activity_id:
            activity = get_object_or_404(Activity, id=activity_id)
            context["activity"] = activity

            # Pre-calculate countdown for not_started activities
            if activity.status == "not_started":
                seconds_until_start = int((activity.start_time - now).total_seconds())
                context["seconds_until_start"] = max(0, seconds_until_start)

            if activity.status == "active":
                checkin_token = generate_checkin_token(activity.id, activity.qr_timeout)
                checkin_path = reverse(
                    "presente:checkin", kwargs={"token": checkin_token}
                )
                checkin_url = self.request.build_absolute_uri(checkin_path)

                # Generate QR code server-side
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=10,
                    border=1,
                )
                qr.add_data(checkin_url)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                qr_data_url = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"

                context.update(
                    {
                        "checkin_url": checkin_url,
                        "qr_data_url": qr_data_url,
                        "timeout": activity.qr_timeout,
                    }
                )

        return context


class CheckInView(LoginRequiredMixin, TemplateView):
    template_name = "presente/checkin_done.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = kwargs.get("token")
        context["success"] = False

        activity_id = verify_checkin_token(token, 300) #

        if not activity_id:
            context["error"] = _("QR Code inválido ou expirado.")
        else:
            activity = get_object_or_404(Activity, id=activity_id) #
            client_ip = get_client_ip(self.request)

            context["activity"] = activity
            context["encoded_id"] = encode_activity_id(activity.id)

            if not activity.is_ip_allowed(client_ip):
                context["error"] = _(
                    "Acesso negado. Seu IP ({ip}) não tem permissão para registrar presença nesta atividade."
                ).format(ip=client_ip)
                context["client_ip"] = client_ip
            elif activity.status == "not_started":
                context["error"] = _(
                    "Esta atividade ainda não começou. Não é possível registrar presença."
                )
            elif activity.status == "expired":
                context["error"] = _(
                    "Esta atividade já encerrou. Não é mais possível registrar presença."
                )
            elif activity.status == "not_enabled":
                context["error"] = _("Esta atividade não está aceitando presenças.")
            elif not verify_checkin_token(token, activity.qr_timeout):
                context["error"] = _("QR Code expirado. Solicite um novo código.")
            else:
                attendance, created = Attendance.objects.get_or_create(
                    activity=activity,
                    user=self.request.user,
                    defaults={"ip_address": client_ip},
                )
                context.update(
                    {
                        "success": True,
                        "attendance": attendance,
                        "created": created,
                    }
                )

        return context


class MyAttendancesView(CoreFilterView):
    page_title = _("Minhas Presenças")
    model = Attendance
    table_class = AttendanceTable
    filterset_class = AttendanceFilter
    table_pagination = {"per_page": 20}
    actions = []
    permission_required = []

    def get_queryset(self):
        return (
            Attendance.objects.filter(user=self.request.user)
            .select_related("activity")
            .prefetch_related("activity__tags")
            .order_by("-checked_in_at")
        )
@login_required
def minhas_pontuacoes(request):
    historico = PointHistory.objects.filter(
        user=request.user
    ).select_related("gamificacao").order_by("-criado_em")

    total_pontos = PointService.calculate_user_point(request.user)

    context = {
        "historico": historico,
        "total_pontos": total_pontos,
    }
    return render(request, "presente/minhas_pontuacoes.html", context)
class RankingListView(ListView):
    model = User
    template_name = "presente/ranking.html"
    context_object_name = "ranking"

    def get_queryset(self):
        return (
            User.objects
            .annotate(
                total_pontos=Coalesce(
                    Sum("point_history__pontos"),
                    0
                )
            )
            .order_by("-total_pontos", "username")
        )

class ActivityAttendanceListView(ActivityOwnerMixin, CoreFilterView):
    model = Attendance
    table_class = ActivityAttendanceTable
    filterset_class = ActivityAttendanceFilter
    template_name = "presente/activity_attendance_list.html"
    table_pagination = {"per_page": 20}
    # context_object_name = "attendances"
    actions = ["delete"]
    permission_required = []

    def get_page_title(self):
        activity = self.get_activity()
        return _("Presenças - {}").format(activity.title)

    def get_queryset(self):
        activity = self.get_activity()
        qs = Attendance.objects.filter(activity=activity).select_related("user")
        return qs.order_by("-checked_in_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self.get_activity()
        context["activity"] = activity
        context["total_attendances"] = self.get_queryset().count()
        return context

    def get_allowed_actions(self):
        allowed_actions = {}
        allowed_actions["delete"] = "presente:attendance_delete"
        return allowed_actions


class AttendanceDeleteView(LoginRequiredMixin, FormView):
    """
    GET  → retorna fragmento HTML para o modal HTMX
    POST → processa o delete com justificativa e estorna pontos
    """

    form_class = AttendanceDeleteForm

    def get_template_names(self):
        # GET: fragmento para o modal
        # POST com erro: recarrega o fragmento com erros
        return ["presente/includes/attendance_delete_modal.html"]

    def get_activity(self):
        activity = get_object_or_404(Activity, pk=self.kwargs["activity_pk"])
        if (
            not self.request.user.is_superuser
            and not activity.owners.filter(pk=self.request.user.pk).exists()
        ):
            raise Http404("Você não tem permissão para remover presenças desta atividade")
        return activity

    def get_attendance(self):
        activity = self.get_activity()
        return get_object_or_404(Attendance, pk=self.kwargs["pk"], activity=activity)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["attendance"] = self.get_attendance()
        context["activity"] = self.get_activity()
        return context

    def form_valid(self, form):
        attendance = self.get_attendance()
        justificativa = form.cleaned_data["justificativa"]

        activity = attendance.activity
        user = attendance.user
        checked_in_at = attendance.checked_in_at

        # 1. Grava log ANTES de deletar (preserva snapshot)
        AttendanceRemovalLog.objects.create(
            removed_by=self.request.user,
            justificativa=justificativa,
            activity=activity,
            attendance_user=user,
            checked_in_at_snapshot=checked_in_at,
        )

        # 2. Deleta a presença (flag evita duplo débito no signal)
        attendance._skip_point_reversal = True
        attendance.delete()

        # 3. Estorna pontos DEPOIS do delete (contagem já reflete estado pós-remoção)
        PointService.process_event(
            "attendance.canceled",
            attendance=attendance,
            justificativa=justificativa,
        )

        messages.success(self.request, _("Presença removida com sucesso!"))

        # Retorna redirect via HTMX
        response = HttpResponse(status=204)
        response["HX-Redirect"] = reverse(
            "presente:activity_attendances",
            kwargs={"pk": self.kwargs["activity_pk"]},
        )
        return response

    def form_invalid(self, form):
        # Recarrega o modal com os erros de validação
        return self.render_to_response(self.get_context_data(form=form))
    
class EventoActivityListView(CoreFilterView):
    model = Activity
    table_class = ActivityTable
    filterset_class = ActivityFilter
    template_name = "core/list.html"
    table_pagination = {"per_page": 20}

    def get_queryset(self):
        evento = get_object_or_404(Evento, pk=self.kwargs["evento_pk"])
        return Activity.objects.filter(evento=evento)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["evento"] = get_object_or_404(
            Evento, pk=self.kwargs["evento_pk"]
        )
        return context

class ActivityAttendanceExportConfigView(
    ActivityOwnerMixin,
    LoginRequiredMixin,
    TemplateView,
):
    template_name = "presente/includes/attendance_export_config_modal.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self.get_activity()
        context["activity"] = activity
        context["form"] = AttendancePrintConfigForm()

        # Get current sort setting from page
        current_sort = self.request.GET.get("sort_by", "name")
        context["current_sort"] = current_sort

        # Convert GET params to dict for easier template iteration
        filter_params = {}
        for key, value in self.request.GET.items():
            if key not in ["columns", "sort_by"]:
                filter_params[key] = value
        context["filter_params"] = filter_params

        return context


class ActivityAttendancePDFView(
    WeasyTemplateResponseMixin,
    ActivityOwnerMixin,
    LoginRequiredMixin,
    FilterView,
):
    model = Attendance
    filterset_class = ActivityAttendanceFilter
    template_name = "presente/attendance_pdf.html"
    context_object_name = "attendances"
    pdf_filename = "relatorio_presencas.pdf"
    pdf_attachment = False  # Display inline in browser instead of downloading

    def get_pdf_filename(self):
        activity = self.get_activity()
        safe_title = "".join(
            c if c.isalnum() or c in (" ", "-", "_") else "" for c in activity.title
        ).replace(" ", "_")
        return f"presencas_{safe_title}.pdf"

    def get_queryset(self):
        activity = self.get_activity()

        # Get base queryset
        qs = Attendance.objects.filter(activity=activity).select_related("user")

        # Apply sorting from configuration
        sort_by = self.request.GET.get("sort_by", "name")
        if sort_by:
            # Map sort fields to actual model fields
            sort_mapping = {
                "name": "user__full_name_normalized",
                "-name": "-user__full_name_normalized",
                "type": "user__type",
                "-type": "-user__type",
                "curso": "user__curso",
                "-curso": "-user__curso",
                "periodo": "user__periodo_referencia",
                "-periodo": "-user__periodo_referencia",
                "checked_in_at": "checked_in_at",
                "-checked_in_at": "-checked_in_at",
            }
            sort_field = sort_mapping.get(sort_by, "user__full_name_normalized")
            qs = qs.order_by(sort_field)
        else:
            qs = qs.order_by("user__full_name_normalized")

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self.get_activity()
        context["activity"] = activity

        # Get the filtered queryset (after filters are applied) and apply sorting
        sort_by = self.request.GET.get("sort_by", "name")
        sort_mapping = {
            "name": "user__full_name_normalized",
            "-name": "-user__full_name_normalized",
            "type": "user__type",
            "-type": "-user__type",
            "curso": "user__curso",
            "-curso": "-user__curso",
            "periodo": "user__periodo_referencia",
            "-periodo": "-user__periodo_referencia",
            "checked_in_at": "checked_in_at",
            "-checked_in_at": "-checked_in_at",
        }
        sort_field = sort_mapping.get(sort_by, "user__full_name_normalized")

        # Apply sorting to the filtered queryset
        filtered_qs = context["filter"].qs.order_by(sort_field)

        # Store the sorted queryset for the template
        context["sorted_qs"] = filtered_qs
        context["total_attendances"] = filtered_qs.count()

        # Get column configuration
        columns = self.request.GET.getlist("columns")
        if not columns:
            columns = ["number", "name", "matricula", "checked_in_at"]
        context["columns"] = columns

        # Get sort configuration
        context["sort_by"] = self.request.GET.get("sort_by", "name")

        # Get filter information for display
        filter_info = []
        filter_data = self.request.GET

        if filter_data.get("user__full_name"):
            filter_info.append(f"Nome: {filter_data['user__full_name']}")
        if filter_data.get("user__type"):
            type_display = dict(User.UserType.choices).get(filter_data["user__type"])
            filter_info.append(f"Tipo: {type_display}")
        if filter_data.get("user__curso"):
            filter_info.append(f"Curso: {filter_data['user__curso']}")
        if filter_data.get("user__periodo_referencia"):
            filter_info.append(f"Período: {filter_data['user__periodo_referencia']}")

        context["filter_info"] = filter_info
        context["generated_at"] = timezone.now()

        # Add absolute paths for WeasyPrint
        logo_path = os.path.join(
            settings.BASE_DIR, "static", "img", "presente-icon.svg"
        )
        context["logo_path"] = logo_path

        # Add font paths
        context["source_sans_regular_path"] = os.path.join(
            settings.BASE_DIR, "static", "fonts", "SourceSans3-Regular.ttf"
        )
        context["source_sans_bold_path"] = os.path.join(
            settings.BASE_DIR, "static", "fonts", "SourceSans3-Bold.ttf"
        )

        return context


class ActivityAttendanceCSVExportView(
    ActivityOwnerMixin,
    LoginRequiredMixin,
    FilterView,
):
    model = Attendance
    filterset_class = ActivityAttendanceFilter

    def get_queryset(self):
        activity = self.get_activity()
        qs = Attendance.objects.filter(activity=activity).select_related("user")

        # Apply sorting
        sort_by = self.request.GET.get("sort_by", "name")
        sort_mapping = {
            "name": "user__full_name_normalized",
            "-name": "-user__full_name_normalized",
            "type": "user__type",
            "-type": "-user__type",
            "curso": "user__curso",
            "-curso": "-user__curso",
            "periodo": "user__periodo_referencia",
            "-periodo": "-user__periodo_referencia",
            "checked_in_at": "checked_in_at",
            "-checked_in_at": "-checked_in_at",
        }
        sort_field = sort_mapping.get(sort_by, "user__full_name_normalized")
        qs = qs.order_by(sort_field)

        return qs

    def get(self, request, *args, **kwargs):
        activity = self.get_activity()
        filterset = self.filterset_class(request.GET, queryset=self.get_queryset())
        queryset = filterset.qs

        # Reapply sorting to ensure it's maintained after filtering
        sort_by = request.GET.get("sort_by", "name")
        sort_mapping = {
            "name": "user__full_name_normalized",
            "-name": "-user__full_name_normalized",
            "type": "user__type",
            "-type": "-user__type",
            "curso": "user__curso",
            "-curso": "-user__curso",
            "periodo": "user__periodo_referencia",
            "-periodo": "-user__periodo_referencia",
            "checked_in_at": "checked_in_at",
            "-checked_in_at": "-checked_in_at",
        }
        sort_field = sort_mapping.get(sort_by, "user__full_name_normalized")
        queryset = queryset.order_by(sort_field)

        # Get column configuration
        columns = request.GET.getlist("columns")
        if not columns:
            columns = ["number", "name", "matricula", "checked_in_at"]

        # Generate filename
        safe_title = "".join(
            c if c.isalnum() or c in (" ", "-", "_") else "" for c in activity.title
        ).replace(" ", "_")
        filename = f"presencas_{safe_title}.csv"

        # Create CSV response
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)

        # Write header row
        header = []
        if "number" in columns:
            header.append("#")
        if "name" in columns:
            header.append("Nome")
        if "email" in columns:
            header.append("Email")
        if "matricula" in columns:
            header.append("Matrícula")
        if "type" in columns:
            header.append("Tipo")
        if "curso" in columns:
            header.append("Curso")
        if "periodo" in columns:
            header.append("Período")
        if "checked_in_at" in columns:
            header.append("Registrado em")
        if "ip_address" in columns:
            header.append("Rede")

        writer.writerow(header)

        # Write data rows
        for idx, attendance in enumerate(queryset, 1):
            row = []
            if "number" in columns:
                row.append(idx)
            if "name" in columns:
                row.append(attendance.user.get_full_name().upper())
            if "email" in columns:
                row.append(attendance.user.email or "-")
            if "matricula" in columns:
                row.append(attendance.user.matricula or "-")
            if "type" in columns:
                row.append(attendance.user.get_type_display())
            if "curso" in columns:
                row.append(attendance.user.curso or "-")
            if "periodo" in columns:
                row.append(attendance.user.periodo_referencia or "-")
            if "checked_in_at" in columns:
                row.append(attendance.checked_in_at.strftime("%d/%m/%Y %H:%M:%S"))
            if "ip_address" in columns:
                row.append(attendance.get_network_name())

            writer.writerow(row)

        return response


# Network CRUD Views


class NetworkListView(SuperuserRequiredMixin, CoreListView):
    page_title = _("Redes")
    model = Network
    table_class = NetworkTable

class NetworkCreateView(SuperuserRequiredMixin, CoreCreateView):
    model = Network
    page_title = _("Redes")
    form_class = NetworkForm


class NetworkDetailView(SuperuserRequiredMixin, CoreDetailView):
    model = Network
    page_title = _("Redes")


class NetworkUpdateView(SuperuserRequiredMixin, CoreUpdateView):
    model = Network
    page_title = _("Redes")
    form_class = NetworkForm


class NetworkDeleteView(SuperuserRequiredMixin, CoreDeleteView):
    model = Network
    page_title = _("Redes")
# Evento CRUD Views

class EventoListView(SuperuserRequiredMixin, CoreListView):
    page_title = _("Eventos")
    model = Evento
    table_class = EventoTable
   


class EventoCreateView(SuperuserRequiredMixin, CoreCreateView):
    model = Evento
    page_title = _("Eventos")
    form_class = EventoForm


class EventoDetailView(SuperuserRequiredMixin, CoreDetailView):
    model = Evento
    page_title = _("Eventos")


class EventoUpdateView(SuperuserRequiredMixin, CoreUpdateView):
    model = Evento
    page_title = _("Eventos")
    form_class = EventoForm


class EventoDeleteView(SuperuserRequiredMixin, CoreDeleteView):
    model = Evento
    page_title = _("Eventos")
# ──────────────────────────────────────────────────────────────
# Helpers de carrinho (armazenado na sessão)
# ──────────────────────────────────────────────────────────────
 
def get_carrinho(request):
    """Retorna o carrinho da sessão como dict {brinde_pk: quantidade}."""
    return request.session.get("carrinho", {})
 
 
def set_carrinho(request, carrinho):
    """Salva o carrinho na sessão e marca como modificado."""
    request.session["carrinho"] = carrinho
    request.session.modified = True
 
 
def limpar_carrinho(request):
    """Remove o carrinho da sessão."""
    request.session.pop("carrinho", None)
    request.session.modified = True
 
 
def carrinho_para_itens(carrinho):
    """
    Converte o carrinho {brinde_pk: quantidade} em uma lista de objetos Brinde
    com a quantidade anotada, para uso no template e no TrocaService.
    Ignora brindes que não existem mais no banco.
    """
    pks = [int(pk) for pk in carrinho.keys()]
    brindes = {b.pk: b for b in Brinde.objects.filter(pk__in=pks)}
    itens = []
    for pk, quantidade in carrinho.items():
        brinde = brindes.get(int(pk))
        if brinde:
            itens.append({"brinde": brinde, "quantidade": quantidade})
    return itens
 
 
# ──────────────────────────────────────────────────────────────
# Loja — listagem de brindes disponíveis + carrinho lateral
# ──────────────────────────────────────────────────────────────
 
class LojaView(LoginRequiredMixin, TemplateView):
    template_name = "presente/loja.html"
 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
 
        # Filtra pelo evento ativo mais recente que tenha brindes
        evento = (
            Evento.objects.filter(brindes__ativo=True)
            .order_by("-data_inicio")
            .first()
        )
 
        brindes = []
        if evento:
            brindes = TrocaService.get_brindes_disponiveis(evento)
 
        carrinho = get_carrinho(self.request)
        itens_carrinho = carrinho_para_itens(carrinho)
        total_carrinho = sum(
            item["brinde"].pontos_necessarios * item["quantidade"]
            for item in itens_carrinho
        )
 
        context["evento"] = evento
        context["brindes"] = brindes
        context["itens_carrinho"] = itens_carrinho
        context["total_carrinho"] = total_carrinho
        context["total_pontos"] = PointService.calculate_user_point(self.request.user)
        context["pontos_apos_troca"] = context["total_pontos"] - total_carrinho
        return context
 
 
# ──────────────────────────────────────────────────────────────
# Adicionar brinde ao carrinho (HTMX ou redirect)
# ──────────────────────────────────────────────────────────────
 
class CarrinhoAdicionarView(LoginRequiredMixin, View):
    def post(self, request):
        brinde_pk = request.POST.get("brinde_pk")
        if not brinde_pk:
            messages.error(request, _("Brinde não informado."))
            return redirect("presente:loja")
 
        brinde = get_object_or_404(Brinde, pk=brinde_pk)
 
        if not brinde.disponivel:
            messages.error(request, _(f"'{brinde.nome}' não está disponível."))
            return redirect("presente:loja")
 
        carrinho = get_carrinho(request)
        quantidade_atual = carrinho.get(str(brinde_pk), 0)
 
        # Verifica se ainda há estoque para adicionar mais uma unidade
        if quantidade_atual >= brinde.quantidade_disponivel:
            messages.warning(request, _(f"Estoque máximo atingido para '{brinde.nome}'."))
            return redirect("presente:loja")
 
        carrinho[str(brinde_pk)] = quantidade_atual + 1
        set_carrinho(request, carrinho)
 
        messages.success(request, _(f"'{brinde.nome}' adicionado ao carrinho."))
        return redirect("presente:loja")
 
 
# ──────────────────────────────────────────────────────────────
# Remover brinde do carrinho
# ──────────────────────────────────────────────────────────────
 
class CarrinhoRemoverView(LoginRequiredMixin, View):
    def post(self, request, brinde_pk):
        carrinho = get_carrinho(request)
 
        if str(brinde_pk) in carrinho:
            del carrinho[str(brinde_pk)]
            set_carrinho(request, carrinho)
            messages.success(request, _("Item removido do carrinho."))
        
        return redirect("presente:loja")
 
 
# ──────────────────────────────────────────────────────────────
# Confirmar troca
# ──────────────────────────────────────────────────────────────
 
class TrocaConfirmarView(LoginRequiredMixin, View):
    def post(self, request):
        carrinho = get_carrinho(request)
 
        if not carrinho:
            messages.error(request, _("Seu carrinho está vazio."))
            return redirect("presente:loja")
 
        itens = carrinho_para_itens(carrinho)
 
        try:
            troca = TrocaService.realizar_troca(user=request.user, itens=itens)
            limpar_carrinho(request)
            messages.success(
                request,
                _(f"Troca #{troca.pk} realizada com sucesso! {troca.pontos_gastos} pts descontados.")
            )
            return redirect("presente:troca_historico")
 
        except ValidationError as e:
            messages.error(request, e.message)
            return redirect("presente:loja")
 
 
# ──────────────────────────────────────────────────────────────
# Histórico de trocas do usuário
# ──────────────────────────────────────────────────────────────
 
class TrocaHistoricoView(LoginRequiredMixin, TemplateView):
    template_name = "presente/troca_historico.html"
 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["trocas"] = TrocaService.get_trocas_usuario(self.request.user)
        context["total_pontos"] = PointService.calculate_user_point(self.request.user)
        return context
 
