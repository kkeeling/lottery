# Generated by Django 2.2 on 2022-01-05 13:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0162_delete_slatefieldoutcome'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildconfig',
            name='lineup_pool_per_stack',
            field=models.SmallIntegerField(default=20),
        ),
    ]