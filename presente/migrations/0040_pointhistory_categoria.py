from django.db import migrations, models


def classificar(apps, schema_editor):
    PointHistory = apps.get_model("presente", "PointHistory")
    debitos = PointHistory.objects.filter(tipo="DEB")
    # Trocas na loja são os únicos débitos sem gamificação vinculada.
    debitos.filter(gamificacao__isnull=True).update(categoria="TROCA")
    debitos.filter(gamificacao__isnull=False).update(categoria="ESTORNO")


class Migration(migrations.Migration):

    dependencies = [
        ('presente', '0039_gamificacao_opcional'),
    ]

    operations = [
        migrations.AddField(
            model_name='pointhistory',
            name='categoria',
            field=models.CharField(choices=[('GANHO', 'Ganho'), ('ESTORNO', 'Estorno'), ('TROCA', 'Troca na loja')], db_index=True, default='GANHO', help_text='Trocas na loja reduzem o saldo, mas não os pontos ganhos (ranking e nível).', max_length=10, verbose_name='Categoria'),
        ),
        migrations.RunPython(classificar, migrations.RunPython.noop),
    ]
