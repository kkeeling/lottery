# Generated by Django 2.2 on 2021-07-19 13:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0035_backtest_elapsed_time'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slatebuild',
            name='total_lineups',
            field=models.PositiveIntegerField(default=0, verbose_name='total'),
        ),
    ]