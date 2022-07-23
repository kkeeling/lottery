# Generated by Django 2.2 on 2022-07-21 14:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0103_auto_20220720_1135'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='slatebuildlineup',
            name='sim_scores',
        ),
        migrations.AddField(
            model_name='slatebuildlineup',
            name='win_rate',
            field=models.FloatField(db_index=True, default=0.0),
        ),
    ]