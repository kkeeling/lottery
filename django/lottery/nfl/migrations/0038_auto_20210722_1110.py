# Generated by Django 2.2 on 2021-07-22 11:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0037_slatebuild_elapsed_time'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slatebuild',
            name='backtest',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='builds', to='nfl.BacktestSlate'),
        ),
    ]
