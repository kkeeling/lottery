# Generated by Django 2.2 on 2021-06-21 14:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0025_auto_20210616_0916'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuild',
            name='stack_cutoff',
            field=models.SmallIntegerField(default=0),
        ),
    ]
