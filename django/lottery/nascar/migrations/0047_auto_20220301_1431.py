# Generated by Django 2.2 on 2022-03-01 14:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0046_buildplayerprojection_starting_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='racesimdriver',
            name='dk_salary',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='racesimdriver',
            name='fd_salary',
            field=models.IntegerField(default=0),
        ),
    ]