from django.db import migrations


def backfill_evento(apps, schema_editor):
    """
    Melhor esforço: preenche PointHistory.evento nos registros existentes
    cuja gamificação está ligada a exatamente um evento (via Activity).
    Registros ambíguos (gamificação usada em mais de um evento) ou sem
    gamificação (ex: boas-vindas, trocas na loja) ficam com evento nulo.
    """
    PointHistory = apps.get_model("presente", "PointHistory")

    historico = PointHistory.objects.filter(
        evento__isnull=True, gamificacao__isnull=False
    ).select_related("gamificacao")

    for registro in historico:
        eventos = list(
            registro.gamificacao.activities.order_by()
            .values_list("evento", flat=True)
            .distinct()
        )
        if len(eventos) == 1 and eventos[0] is not None:
            registro.evento_id = eventos[0]
            registro.save(update_fields=["evento"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("presente", "0035_pointhistory_evento"),
    ]

    operations = [
        migrations.RunPython(backfill_evento, noop_reverse),
    ]
