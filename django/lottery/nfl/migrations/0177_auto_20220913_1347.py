# Generated by Django 2.2 on 2022-09-13 13:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0176_slatelineup_sim_scores'),
    ]

    operations = [
        migrations.AddField(
            model_name='slate',
            name='lineups_per_cycle',
            field=models.IntegerField(default=1000),
        ),
        migrations.AddField(
            model_name='slate',
            name='num_cycles',
            field=models.IntegerField(default=10),
        ),
    ]
