# Generated by Django 2.2 on 2022-07-27 12:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0108_auto_20220727_1215'),
    ]

    operations = [
        migrations.CreateModel(
            name='SlateBuildLineupMatchup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('win_rate', models.FloatField(db_index=True, default=0.0)),
                ('build', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='matchups', to='nascar.SlateBuild', verbose_name='Build')),
                ('field_lineup', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='matchups', to='nascar.SlateBuildFieldLineup')),
                ('slate_lineup', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='matchups', to='nascar.SlateLineup')),
            ],
            options={
                'verbose_name': 'Lineup Matchup',
                'verbose_name_plural': 'Lineup Matchups',
                'ordering': ['-win_rate'],
            },
        ),
    ]
