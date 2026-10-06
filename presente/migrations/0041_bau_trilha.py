from django.db import migrations, models

BONUS_POR_ATIVIDADE = 10


def dar_bau_as_trilhas_sem_bonus(apps, schema_editor):
    Trilha = apps.get_model("presente", "TrilhaGamificacao")
    TipoGamificacao = apps.get_model("presente", "TipoGamificacao")
    Gamificacao = apps.get_model("presente", "Gamificacao")
    UsuarioGamificacao = apps.get_model("presente", "UsuarioGamificacao")
    PointHistory = apps.get_model("presente", "PointHistory")
    Attendance = apps.get_model("presente", "Attendance")
    InscricaoTrilha = apps.get_model("presente", "InscricaoTrilha")

    for trilha in Trilha.objects.filter(gamificacao_bonus__isnull=True):
        minimo = max(1, trilha.minimo_atividades or 1)
        tipo, _ = TipoGamificacao.objects.get_or_create(trilha=trilha, tipo="TRF")
        bonus = Gamificacao.objects.create(
            titulo=f"Trilha concluída: {trilha.name}"[:150],
            tipo=tipo,
            trilha=trilha,
            pontos=minimo * BONUS_POR_ATIVIDADE,
        )
        trilha.gamificacao_bonus = bonus
        trilha.save(update_fields=["gamificacao_bonus"])

        # Quem já tinha completado a trilha recebe o baú agora (fechado, para abrir).
        presencas = Attendance.objects.filter(activity__trilha=trilha)
        if trilha.evento_id:
            inscritos = InscricaoTrilha.objects.filter(trilha=trilha).values_list("user_id", flat=True)
            presencas = presencas.filter(user_id__in=inscritos)
        contagem = {}
        for user_id in presencas.values_list("user_id", flat=True):
            contagem[user_id] = contagem.get(user_id, 0) + 1

        for user_id, total in contagem.items():
            if total < minimo:
                continue
            UsuarioGamificacao.objects.create(user_id=user_id, gamificacao=bonus)
            PointHistory.objects.create(
                user_id=user_id,
                gamificacao=bonus,
                evento_id=trilha.evento_id,
                tipo="CRD",
                categoria="GANHO",
                pontos=bonus.pontos,
                motivo=f"Bônus de trilha atingido: {trilha.name}",
            )


class Migration(migrations.Migration):

    dependencies = [
        ('presente', '0040_pointhistory_categoria'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuariogamificacao',
            name='bau_aberto_em',
            field=models.DateTimeField(blank=True, help_text='Para bônus de trilha: quando o aluno abriu o baú. Os pontos já são creditados ao concluir.', null=True, verbose_name='Baú aberto em'),
        ),
        migrations.RunPython(dar_bau_as_trilhas_sem_bonus, migrations.RunPython.noop),
    ]
