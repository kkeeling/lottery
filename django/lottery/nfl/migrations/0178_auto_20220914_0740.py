# Generated by Django 2.2 on 2022-09-14 07:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0177_auto_20220913_1347'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slateplayerprojection',
            name='in_play',
            field=models.BooleanField(default=False),
        ),
    ]
