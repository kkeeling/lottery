# Generated by Django 2.2 on 2022-05-23 12:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configuration', '0002_backgroundtask_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='backgroundtask',
            name='pct_complete',
            field=models.FloatField(default=0.0),
        ),
    ]
