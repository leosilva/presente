from .models import PerfilGamificado, Nivel
from .services import PointService

def gamificacao_context(request):
    if not request.user.is_authenticated:
        return {}

    perfil = PerfilGamificado.objects.filter(user=request.user).first()
    my_points = PointService.calculate_user_point(request.user)
    nivel_atual = perfil.nivel if perfil else None

    if nivel_atual:
        proximo_nivel = Nivel.objects.filter(pontos_minimos__gt=nivel_atual.pontos_minimos).first()
    else:
        proximo_nivel = None

    if not nivel_atual:
        percentual = 0
    elif not proximo_nivel:
        percentual = 100
    else:
        percentual = (my_points - nivel_atual.pontos_minimos) * 100 / (proximo_nivel.pontos_minimos - nivel_atual.pontos_minimos)

    offset = round(408 * (1 - percentual / 100), 1)

    return {
        "perfil": perfil,
        "my_points": my_points,
        "nivel_atual": nivel_atual,
        "proximo_nivel": proximo_nivel,
        "percentual": percentual,
        "offset": str(offset).replace(",", "."),
    }