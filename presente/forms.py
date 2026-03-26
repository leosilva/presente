from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from taggit.models import Tag
from .models import Activity, Network, Evento

User = get_user_model()


class TagsMultipleChoiceField(forms.MultipleChoiceField):
    def validate(self, value):
        # Skip validation - allow any values (existing or new tags)
        pass


class ActivityForm(forms.ModelForm):
    tags = TagsMultipleChoiceField(
        required=False,
        label="Tags",
        choices=[],
        widget=forms.SelectMultiple(
            attrs={"class": "form-control", "data-tom-select": "tags"}
        ),
        help_text="Tags para organizar as atividades (ex: 'Workshop 2024', 'Python')",
    )

    class Meta:
        model = Activity
        fields = [
            "evento",
            "title",
            "start_time",
            "end_time",
            "qr_timeout",
            "restrict_ip",
            "is_enabled",
            "allowed_networks",
            "owners",
        ]
        widgets = {
            "evento": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "start_time": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "end_time": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "qr_timeout": forms.NumberInput(
                attrs={"class": "form-control", "min": "0"}
            ),
            "is_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "restrict_ip": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "allowed_networks": forms.CheckboxSelectMultiple(
                attrs={"class": "form-check-input"}
            ),
            "owners": forms.SelectMultiple(
                attrs={"class": "form-control", "data-tom-select": "users"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_time"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["end_time"].input_formats = ["%Y-%m-%dT%H:%M"]

        # Populate owners field with SERVIDOR users only
        self.fields["owners"].queryset = User.objects.filter(type="SERVIDOR").order_by(
            "email"
        )
        self.fields["owners"].label_from_instance = (
            lambda obj: obj.get_full_name() or obj.email
        )

        # Populate tags field with all existing tags
        all_tags = Tag.objects.all().order_by("name")
        tag_choices = [(tag.name, tag.name) for tag in all_tags]
        self.fields["tags"].choices = tag_choices

        # Set initial tags if editing
        if self.instance and self.instance.pk:
            self.fields["tags"].initial = [tag.name for tag in self.instance.tags.all()]

        # Set field order
        self.order_fields(
            [
                "evento",
                "title",
                "tags",
                "start_time",
                "end_time",
                "qr_timeout",
                "is_enabled",
                "restrict_ip",
                "allowed_networks",
                "owners",
            ]
        )

    def save(self, commit=True):
        # Save the tags data before calling super() since tags is not a model field
        tags_data = self.cleaned_data.get("tags", "")

        # Call parent save
        instance = super().save(commit=commit)

        # Handle tags only after instance is saved (requires pk)
        if instance.pk:
            if tags_data:
                # Tags can be a list (from select) or string (if using create with delimiter)
                if isinstance(tags_data, str):
                    tag_list = [
                        tag.strip() for tag in tags_data.split(",") if tag.strip()
                    ]
                else:
                    tag_list = tags_data
                instance.tags.set(tag_list)
            else:
                instance.tags.clear()

        return instance


class AttendancePrintConfigForm(forms.Form):
    COLUMN_CHOICES = [
        ("number", _("Número")),
        ("name", _("Nome")),
        ("email", _("Email")),
        ("matricula", _("Matrícula")),
        ("type", _("Tipo")),
        ("curso", _("Curso")),
        ("periodo", _("Período")),
        ("checked_in_at", _("Data/Hora de Registro")),
        ("ip_address", _("Endereço IP")),
    ]

    SORT_CHOICES = [
        ("name", _("Nome (A-Z)")),
        ("-name", _("Nome (Z-A)")),
        ("checked_in_at", _("Data de Registro (Mais Antiga)")),
        ("-checked_in_at", _("Data de Registro (Mais Recente)")),
        ("type", _("Tipo (A-Z)")),
        ("-type", _("Tipo (Z-A)")),
        ("curso", _("Curso (A-Z)")),
        ("-curso", _("Curso (Z-A)")),
        ("periodo", _("Período (A-Z)")),
        ("-periodo", _("Período (Z-A)")),
    ]

    columns = forms.MultipleChoiceField(
        choices=COLUMN_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label=_("Colunas a Exibir"),
        initial=["number", "name", "matricula", "checked_in_at"],
        required=False,
    )

    sort_by = forms.ChoiceField(
        choices=SORT_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Ordenar Por"),
        initial="name",
        required=False,
    )

    def clean_columns(self):
        columns = self.cleaned_data.get("columns")
        if not columns:
            # Default columns if none selected
            return ["number", "name", "matricula", "checked_in_at"]
        return columns


class NetworkForm(forms.ModelForm):
    class Meta:
        model = Network
        fields = ["name", "description", "ip_addresses", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "ip_addresses": forms.Textarea(
                attrs={
                    "class": "form-control font-monospace",
                    "rows": 10,
                    "placeholder": "200.137.2.62\n192.168.1.0/24\n10.0.0.1",
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        
class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = "__all__"
        widgets = {
            "data_inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "data_fim": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
