# Generated by Django 2.2 on 2021-06-15 10:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0018_stackconstructionrule'),
    ]

    operations = [
        migrations.AddField(
            model_name='backtest',
            name='stack_construction',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='backtests', to='nfl.StackConstructionRule'),
        ),
    ]
