# Generated by Django 2.2 on 2022-09-02 15:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0169_findwinnerbuild'),
    ]

    operations = [
        migrations.CreateModel(
            name='WinningLineup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('win_rate', models.FloatField(db_index=True, default=0.0)),
                ('median', models.FloatField(db_index=True, default=0.0)),
                ('s75', models.FloatField(db_index=True, default=0.0)),
                ('s90', models.FloatField(db_index=True, default=0.0)),
                ('build', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='winning_lineups', to='nfl.FindWinnerBuild', verbose_name='Build')),
                ('slate_lineup', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='winner_builds', to='nfl.SlateLineup', verbose_name='Lineup')),
            ],
            options={
                'verbose_name': 'Lineup',
                'verbose_name_plural': 'Lineups',
                'ordering': ['-median'],
            },
        ),
    ]
