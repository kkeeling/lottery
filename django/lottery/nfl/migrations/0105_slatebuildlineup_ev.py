# Generated by Django 2.2 on 2021-10-02 11:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0104_auto_20211001_1446'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildlineup',
            name='ev',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
    ]
