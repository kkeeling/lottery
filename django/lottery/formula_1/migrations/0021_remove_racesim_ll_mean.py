# Generated by Django 2.2 on 2022-04-06 13:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('formula_1', '0020_racesimdriver_dk_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='racesim',
            name='ll_mean',
        ),
    ]
