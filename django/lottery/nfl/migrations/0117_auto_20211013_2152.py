# Generated by Django 2.2 on 2021-10-13 21:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0116_auto_20211013_2132'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slatebuildlineup',
            name='std',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=100),
        ),
    ]
