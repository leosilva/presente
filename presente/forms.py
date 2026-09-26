from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from taggit.models import Tag
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, HTML
from .models import Activity, Network, Evento, Gamificacao, TrilhaGamificacao

User = get_user_model()


class TagsMultipleChoiceField(forms.MultipleChoiceField):
    def validate(self, value):
        # Skip validation - allow any values (existing or new tags)
        pass


class TrilhaSelect(forms.Select):
    """Expõe evento e bônus de cada trilha para o filtro e a prévia no navegador."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        trilha = getattr(value, "instance", None)
        if trilha is not None:
            bonus = trilha.gamificacao_bonus
            option["attrs"].update({
                "data-evento": trilha.evento_id or "",
                "data-minimo": trilha.minimo_atividades,
                "data-bonus": bonus.pontos if bonus else 0,
            })
        return option


def _secao(icone, titulo, texto):
    return HTML(
        f'<div class="form-section"><div class="form-section-title"><i class="bi bi-{icone}"></i> {titulo}</div>'
        f'<p class="form-section-help">{texto}</p></div>'
    )


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
    pontos = forms.IntegerField(
        label=_("Pontos pela presença"),
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "5"}),
        help_text=_("Quantos pontos cada participante ganha ao registrar presença. Use 0 para não dar pontos."),
    )

    class Meta:
        model = Activity
        fields = [
            "evento",
            "title",
            "descricao",
            "local",
            "ministrante",
            "area",
            "trilha",
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
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "local": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex: Bloco B — Laboratório 3"}
            ),
            "ministrante": forms.TextInput(attrs={"class": "form-control"}),
            "area": forms.Select(attrs={"class": "form-control"}),
            "trilha": TrilhaSelect(attrs={"class": "form-control"}),
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
            "is_enabled": forms.CheckboxInput(
                attrs={"class": "form-check-input", "role": "switch"}
            ),
            "restrict_ip": forms.CheckboxInput(
                attrs={"class": "form-check-input", "role": "switch"}
            ),
            "allowed_networks": forms.CheckboxSelectMultiple(
                attrs={"class": "form-check-input"}
            ),
            "owners": forms.SelectMultiple(
                attrs={"class": "form-control", "data-tom-select": "users"}
            ),
        }
        help_texts = {
            "area": _("Opcional. Participar de áreas diferentes no mesmo dia rende bônus de diversidade."),
        }

    class Media:
        js = ("js/activity_form.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_time"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["end_time"].input_formats = ["%Y-%m-%dT%H:%M"]

        self.fields["trilha"].queryset = (
            TrilhaGamificacao.objects.select_related("gamificacao_bonus").order_by("name")
        )
        self.fields["trilha"].empty_label = _("Nenhuma trilha")
        self.fields["area"].empty_label = _("Nenhuma área")

        gamificacao = self.instance.gamificacao if self.instance.pk else None
        self.fields["pontos"].initial = gamificacao.pontos if gamificacao else (0 if self.instance.pk else 10)

        # Populate owners field with all users
        self.fields["owners"].queryset = User.objects.all().order_by("email")

        def _owner_label(obj):
            name = obj.full_name or f"{obj.first_name} {obj.last_name}".strip()
            return f"{name} - {obj.email}" if name else obj.email

        self.fields["owners"].label_from_instance = _owner_label

        # Populate tags field with all existing tags
        all_tags = Tag.objects.all().order_by("name")
        tag_choices = [(tag.name, tag.name) for tag in all_tags]
        self.fields["tags"].choices = tag_choices

        # Set initial tags if editing
        if self.instance and self.instance.pk:
            self.fields["tags"].initial = [tag.name for tag in self.instance.tags.all()]

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            _secao(
                "person-lines-fill",
                _("Informações para o participante"),
                _("É isso que os alunos veem ao tocar na atividade dentro da trilha: onde é, quando e o que vão encontrar."),
            ),
            Row(
                Column("evento", css_class="col-md-6"),
                Column("title", css_class="col-md-6"),
            ),
            "descricao",
            Row(
                Column("local", css_class="col-md-6"),
                Column("ministrante", css_class="col-md-6"),
            ),
            Row(
                Column("start_time", css_class="col-md-6"),
                Column("end_time", css_class="col-md-6"),
            ),
            "tags",
            _secao(
                "stars",
                _("Gamificação"),
                _(
                    "Defina o que o participante ganha. Tudo aqui é opcional. "
                    "<a href=\"{% url 'presente:como_funciona' %}\" target=\"_blank\" rel=\"noopener\">"
                    "Como funciona a gamificação?</a>"
                ),
            ),
            Row(
                Column("pontos", css_class="col-md-4"),
                Column("trilha", css_class="col-md-4"),
                Column("area", css_class="col-md-4"),
            ),
            HTML(
                '<div class="gm-form-preview" id="gamificacao-preview" aria-live="polite">'
                '<div class="gm-form-preview-title"><i class="bi bi-eye"></i> O participante vai ver</div>'
                '<ul class="mb-0"></ul></div>'
            ),
            _secao(
                "qr-code",
                _("Registro de presença"),
                _("Controle de quando e de onde os alunos podem registrar presença pelo QR Code."),
            ),
            Row(
                Column("qr_timeout", css_class="col-md-4"),
                Column(
                    Field("is_enabled", wrapper_class="form-switch"),
                    css_class="col-md-4 d-flex align-items-center",
                ),
                Column(
                    Field("restrict_ip", wrapper_class="form-switch"),
                    css_class="col-md-4 d-flex align-items-center",
                ),
            ),
            "allowed_networks",
            _secao(
                "people",
                _("Responsáveis"),
                _("Quem pode ver a lista de presença e editar esta atividade."),
            ),
            "owners",
        )

    def clean(self):
        cleaned = super().clean()
        trilha = cleaned.get("trilha")
        evento = cleaned.get("evento")
        if trilha and evento and trilha.evento_id and trilha.evento_id != evento.pk:
            self.add_error("trilha", _("Esta trilha pertence a outro evento."))
        return cleaned

    def _sincronizar_gamificacao(self, instance, pontos):
        atual = instance.gamificacao
        if not pontos:
            # Só desvincula: apagar a gamificação apagaria o histórico de pontos.
            instance.gamificacao = None
            return

        titulo = f"Presença — {instance.title}"[:150]
        if atual is not None and not atual.automatica:
            compativel = atual.trilha_id in (None, instance.trilha_id)
            if atual.pontos == pontos and compativel:
                return
            atual = None

        if atual is None:
            instance.gamificacao = Gamificacao.objects.create(
                titulo=titulo, pontos=pontos, trilha=instance.trilha
            )
            return

        # Mudanças de título/trilha sem disparar o recálculo de pontos do signal.
        Gamificacao.objects.filter(pk=atual.pk).update(titulo=titulo, trilha=instance.trilha)
        atual.titulo, atual.trilha = titulo, instance.trilha
        if atual.pontos != pontos:
            atual.pontos = pontos
            atual.save()

    def save(self, commit=True):
        tags_data = self.cleaned_data.get("tags", "")
        pontos = self.cleaned_data.get("pontos") or 0

        instance = super().save(commit=False)
        self._sincronizar_gamificacao(instance, pontos)

        if commit:
            instance.save()
            self.save_m2m()

        if instance.pk:
            if tags_data:
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
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-check-input", "role": "switch"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            Row(
                Column("name", css_class="col-md-8"),
                Column(
                    Field("is_active", wrapper_class="form-switch"),
                    css_class="col-md-4 d-flex align-items-center",
                ),
            ),
            "description",
            "ip_addresses",
        )


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = "__all__"
        widgets = {
            "data_inicio": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "data_fim": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "campus": forms.SelectMultiple(
                attrs={"class": "form-control", "data-tom-select": "multi"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            Row(
                Column("nome", css_class="col-md-8"),
                Column("tipo", css_class="col-md-4"),
            ),
            "campus",
            Row(
                Column("data_inicio", css_class="col-md-6"),
                Column("data_fim", css_class="col-md-6"),
            ),
            "descricao",
        )

class AttendanceDeleteForm(forms.Form):
    justificativa = forms.CharField(
        label=_("Justificativa"),
        widget=forms.Textarea(attrs={
            "rows": 4,
            "class": "form-control",
            "placeholder": _("Descreva o motivo da remoção desta presença..."),
        }),
        min_length=10,
        max_length=500,
        help_text=_("Informe o motivo da remoção (mínimo 10 caracteres)."),
        error_messages={
            "min_length": _("A justificativa deve ter pelo menos 10 caracteres."),
            "required": _("A justificativa é obrigatória para remover uma presença."),
        },
    )