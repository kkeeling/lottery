# Generated by Django 2.2 on 2021-08-27 22:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0053_contestprize'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='play_order',
            field=models.IntegerField(default=1),
        ),
    ]