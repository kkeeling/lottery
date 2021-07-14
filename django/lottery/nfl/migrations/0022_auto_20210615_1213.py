# Generated by Django 2.2 on 2021-06-15 12:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0021_auto_20210615_1125'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuild',
            name='in_play_criteria',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='builds', to='nfl.PlayerSelectionCriteria'),
        ),
        migrations.AddField(
            model_name='slatebuild',
            name='lineup_construction',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='builds', to='nfl.LineupConstructionRule'),
        ),
        migrations.AddField(
            model_name='slatebuild',
            name='stack_construction',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='builds', to='nfl.StackConstructionRule'),
        ),
    ]
