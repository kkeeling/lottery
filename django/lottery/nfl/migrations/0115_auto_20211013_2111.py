# Generated by Django 2.2 on 2021-10-13 21:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0114_auto_20211009_1112'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildactualslineup',
            name='std',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name='slatebuildlineup',
            name='std',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='buildplayerprojection',
            name='value',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=5, verbose_name='V'),
        ),
    ]
