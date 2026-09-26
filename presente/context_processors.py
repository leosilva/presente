from .models import PerfilGamificado
from .services import NivelService


def gamificacao_context(request):
    if not request.user.is_authenticated:
        return {}

    progresso = NivelService.progresso(request.user)
    return {
        "perfil": PerfilGamificado.objects.filter(user=request.user).first(),
        "my_points": progresso["pontos"],
        "nivel_atual": progresso["nivel_atual"],
        "proximo_nivel": progresso["proximo_nivel"],
        "percentual": progresso["percentual"],
        "pontos_faltando": progresso["pontos_faltando"],
        "progresso_nivel": progresso,
    }