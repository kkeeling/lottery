# Generated by Django 2.2 on 2022-04-25 15:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('formula_1', '0021_remove_racesim_ll_mean'),
    ]

    operations = [
        migrations.AddField(
            model_name='racesim',
            name='optimal_lineups_per_iteration',
            field=models.IntegerField(default=1, verbose_name='num_lineups'),
        ),
        migrations.AddField(
            model_name='racesim',
            name='run_with_gto',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='racesim',
            name='run_with_lineup_rankings',
            field=models.BooleanField(default=False),
        ),
    ]
