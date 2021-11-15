# Generated by Django 2.2 on 2021-11-11 15:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0140_slatebuildlineup_median'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildconfig',
            name='lineup_removal_by',
            field=models.CharField(choices=[('projection', 'Projection'), ('sim_median', 'Median'), ('sim_ceiling', 'Ceiling')], default='projection', max_length=15),
        ),
    ]