import django_filters
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from taggit.models import Tag
from .models import Activity, Attendance,Evento

User = get_user_model()


class ActivityFilter(django_filters.FilterSet):
    STATUS_CHOICES = [
        ("active", _("Ativa")),
        ("not_started", _("Não Iniciada")),
        ("expired", _("Encerrada")),
        ("not_enabled", _("Desabilitada")),
    ]

    title = django_filters.CharFilter(
        lookup_expr="icontains",
        label=_("Título"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    evento = django_filters.ModelChoiceFilter(
        queryset=Evento.objects.all(),
        label="Evento"
    )
    status = django_filters.ChoiceFilter(
        choices=STATUS_CHOICES,
        label=_("Status"),
        method="filter_status",
        empty_label="---------",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    tags = django_filters.ModelChoiceFilter(
        queryset=Tag.objects.all(),
        label=_("Tags"),
        field_name="tags",
        empty_label="---------",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    start_time__gte = django_filters.DateFilter(
        field_name="start_time",
        lookup_expr="gte",
        label=_("Data inicial (a partir de)"),
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    start_time__lte = django_filters.DateFilter(
        field_name="start_time",
        lookup_expr="lte",
        label=_("Data inicial (até)"),
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def filter_status(self, queryset, name, value):
        from django.utils import timezone

        now = timezone.now()

        if value == "active":
            return queryset.filter(
                start_time__lte=now, end_time__gte=now, is_enabled=True
            )
        elif value == "not_started":
            return queryset.filter(start_time__gt=now)
        elif value == "expired":
            return queryset.filter(end_time__lt=now)
        elif value == "not_enabled":
            return queryset.filter(is_enabled=False)
        return queryset

    class Meta:
        model = Activity
        fields = [
            "title",
            "evento",
            "status",
            "tags",
            "start_time__gte",
            "start_time__lte",
        ]


class AttendanceFilter(django_filters.FilterSet):
    activity__title = django_filters.CharFilter(
        lookup_expr="icontains",
        label=_("Atividade"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    activity__tags = django_filters.ModelChoiceFilter(
        queryset=Tag.objects.all(),
        label=_("Tags"),
        field_name="activity__tags",
        empty_label="---------",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    activity__start_time__gte = django_filters.DateFilter(
        field_name="activity__start_time",
        lookup_expr="gte",
        label=_("Início a partir de"),
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    activity__start_time__lte = django_filters.DateFilter(
        field_name="activity__start_time",
        lookup_expr="lte",
        label=_("Início até"),
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    class Meta:
        model = Attendance
        fields = [
            "activity__title",
            "activity__tags",
            "activity__start_time__gte",
            "activity__start_time__lte",
        ]


class ActivityAttendanceFilter(django_filters.FilterSet):
    user__full_name = django_filters.CharFilter(
        lookup_expr="icontains",
        label=_("Nome"),
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    user__type = django_filters.ChoiceFilter(
        choices=User.UserType.choices,
        label=_("Tipo"),
        empty_label="---------",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    user__campus = django_filters.ChoiceFilter(
        label=_("Campus"),
        empty_label="---------",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    user__curso = django_filters.ChoiceFilter(
        label=_("Curso"),
        widget=forms.Select(
            attrs={"class": "form-select", "data-tom-select": "simple"}
        ),
    )
    user__periodo_referencia = django_filters.ChoiceFilter(
        label=_("Período de Referência"),
        empty_label="---------",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get distinct values from the queryset
        if self.queryset is not None:
            # Campus choices
            campus_choices = [
                (campus, campus)
                for campus in self.queryset.exclude(user__campus__isnull=True)
                .exclude(user__campus="")
                .values_list("user__campus", flat=True)
                .distinct()
                .order_by("user__campus")
            ]
            self.filters["user__campus"].extra["choices"] = campus_choices

            # Curso choices
            curso_choices = [
                (curso, curso)
                for curso in self.queryset.exclude(user__curso__isnull=True)
                .exclude(user__curso="")
                .values_list("user__curso", flat=True)
                .distinct()
                .order_by("user__curso")
            ]
            self.filters["user__curso"].extra["choices"] = curso_choices

            # Periodo_referencia choices
            periodo_choices = [
                (periodo, periodo)
                for periodo in self.queryset.exclude(
                    user__periodo_referencia__isnull=True
                )
                .exclude(user__periodo_referencia="")
                .values_list("user__periodo_referencia", flat=True)
                .distinct()
                .order_by("user__periodo_referencia")
            ]
            self.filters["user__periodo_referencia"].extra["choices"] = periodo_choices

    class Meta:
        model = Attendance
        fields = [
            "user__full_name",
            "user__type",
            "user__campus",
            "user__curso",
            "user__periodo_referencia",
        ]
