# Generated by Django 2.2 on 2022-03-17 12:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('formula_1', '0003_racesimdriver_dk_salary_cpt'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='racesimdriver',
            name='q_outcomes',
        ),
    ]
