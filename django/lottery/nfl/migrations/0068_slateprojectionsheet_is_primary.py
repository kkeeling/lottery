# Generated by Django 2.2 on 2021-09-07 11:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0067_sheetcolumnheaders_column_team'),
    ]

    operations = [
        migrations.AddField(
            model_name='slateprojectionsheet',
            name='is_primary',
            field=models.BooleanField(default=True),
        ),
    ]
