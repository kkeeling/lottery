# Generated by Django 2.2 on 2021-09-02 15:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0057_auto_20210902_1428'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildlineup',
            name='rating',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5),
        ),
    ]
