# Generated by Django 2.2 on 2021-12-01 12:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0149_auto_20211130_1517'),
    ]

    operations = [
        migrations.AddField(
            model_name='alias',
            name='yahoo_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
