# Generated by Django 2.2 on 2021-10-09 03:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0112_auto_20211009_0320'),
    ]

    operations = [
        migrations.AddField(
            model_name='buildplayerprojection',
            name='max_exposure',
            field=models.IntegerField(default=100, verbose_name='Min'),
        ),
        migrations.AddField(
            model_name='buildplayerprojection',
            name='min_exposure',
            field=models.IntegerField(default=0, verbose_name='Min'),
        ),
    ]
