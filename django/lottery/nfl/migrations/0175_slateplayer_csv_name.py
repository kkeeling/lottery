# Generated by Django 2.2 on 2022-09-07 18:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0174_auto_20220907_1806'),
    ]

    operations = [
        migrations.AddField(
            model_name='slateplayer',
            name='csv_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
