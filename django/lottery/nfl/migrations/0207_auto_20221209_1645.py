# Generated by Django 2.2 on 2022-12-09 16:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0206_auto_20221207_1038'),
    ]

    operations = [
        migrations.AlterField(
            model_name='marketprojections',
            name='week',
            field=models.ForeignKey(blank=True, default=125, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='market_projections', to='nfl.Week'),
        ),
    ]
