# Generated by Django 2.2 on 2022-10-11 20:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0185_auto_20221011_1419'),
    ]

    operations = [
        migrations.AddField(
            model_name='sheetcolumnheaders',
            name='use_for_data_feed',
            field=models.BooleanField(default=False),
        ),
    ]