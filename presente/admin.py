from django.contrib import admin
from .models import (
    Activity,
    Attendance,
    Network,
    TipoGamificacao,
    TrilhaGamificacao,
    Gamificacao,
    UsuarioGamificacao,
    Evento,
    Campus,
    Area,
    MarcosDiversidade,
    Nivel,
    PerfilGamificado,
    PointHistory,
    Recompensa,
    ResgateRecompensa
    )


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    fieldsets = (
        (None, {"fields": ("name", "description", "is_active")}),
        ("Endereços IP", {"fields": ("ip_addresses",)}),
    )


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "start_time",
        "end_time",
        "qr_timeout",
    ]
    list_filter = ["tags"]
    search_fields = ["title"]
    date_hierarchy = "start_time"
    filter_horizontal = ["owners", "allowed_networks"]


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ["user", "activity", "checked_in_at", "network_or_ip"]
    list_filter = ["activity", "checked_in_at"]
    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "activity__title",
        "ip_address",
    ]
    date_hierarchy = "checked_in_at"
    readonly_fields = ["checked_in_at", "ip_address", "network_display"]

    def network_or_ip(self, obj):
        return obj.get_network_name()

    network_or_ip.short_description = "Rede/IP"

    def network_display(self, obj):
        if not obj.ip_address:
            return "-"
        network_name = obj.get_network_name()
        if network_name != obj.ip_address:
            return f"{network_name} ({obj.ip_address})"
        return obj.ip_address

    network_display.short_description = "Rede"



@admin.register(TrilhaGamificacao)
class TrilhaGamificacaoAdmin(admin.ModelAdmin):
    search_fields = ("name",)
@admin.register(TipoGamificacao)
class TipoGamificacaoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "trilha")
    list_filter = ("tipo", "trilha")
@admin.register(Gamificacao)
class GamificacaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "trilha", "tipo", "pontos")
    list_filter = ("trilha", "tipo")
    search_fields = ("titulo",)

@admin.register(UsuarioGamificacao)
class UsuarioGamificacaoAdmin(admin.ModelAdmin):
    list_display = ("user", "gamificacao", "data_concedida")
    list_filter = ("gamificacao", "data_concedida")
    search_fields = ("user__username", "gamificacao__titulo")
    def pontos(self, obj):
        return obj.gamificacao.pontos

    pontos.short_description = "Pontos"
@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "data_inicio", "data_fim")
    list_filter = ("tipo", "campus")
    search_fields = ("nome",)

admin.site.register(Campus)

@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao']
    search_fields = ['nome']

@admin.register(MarcosDiversidade)
class MarcosDiversidadeAdmin(admin.ModelAdmin):
    list_display = ['areas_necessarias', 'gamificacao_bonus', 'descricao']
    ordering = ['areas_necessarias']

@admin.register(Nivel)
class NivelAdmin(admin.ModelAdmin):
    list_display = ("nome", "pontos_minimos")

@admin.register(PerfilGamificado)
class PerfilGamificadoAdmin(admin.ModelAdmin):
    list_display = ("user", "nivel", "titulo")
@admin.register(PointHistory)
class PointHistoryAdmin(admin.ModelAdmin):
    list_display = ["user", "tipo", "pontos", "gamificacao", "motivo", "criado_em"]
    list_filter = ["tipo", "criado_em"]
    search_fields = ["user__username", "motivo"]
    readonly_fields = ["user", "gamificacao", "tipo", "pontos", "motivo", "criado_em"]
    date_hierarchy = "criado_em"
@admin.register(Recompensa)
class RecompensaAdmin(admin.ModelAdmin):
    list_display = ["nome", "evento", "pontos_necessarios", "quantidade_disponivel", "data_validade", "ativo", "disponivel"]
    list_filter = ["ativo", "evento"]
    search_fields = ["nome"]

@admin.register(ResgateRecompensa)
class ResgateRecompensaAdmin(admin.ModelAdmin):
    list_display = ["usuario", "recompensa", "pontos_gastos", "resgatado_em"]
    list_filter = ["recompensa__evento"]
    search_fields = ["usuario__username", "recompensa__nome"]
    readonly_fields = ["usuario", "recompensa", "pontos_gastos", "resgatado_em"]
