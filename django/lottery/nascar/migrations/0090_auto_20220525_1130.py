# Generated by Django 2.2 on 2022-05-25 11:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0089_auto_20220524_1354'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='contestbacktestentry',
            name='amounts_won',
        ),
        migrations.AddField(
            model_name='contestbacktestentry',
            name='amount_won',
            field=models.FloatField(default=0.0),
        ),
    ]