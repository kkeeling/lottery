# Generated by Django 2.2 on 2021-06-15 09:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0016_auto_20210615_0940'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildstack',
            name='contains_top_pc',
            field=models.BooleanField(default=False),
        ),
    ]
