# Generated by Django 2.2 on 2021-09-01 14:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0055_auto_20210901_1329'),
    ]

    operations = [
        migrations.AlterField(
            model_name='backtest',
            name='total_optimals',
            field=models.PositiveIntegerField(default=0, verbose_name='TO'),
        ),
    ]
