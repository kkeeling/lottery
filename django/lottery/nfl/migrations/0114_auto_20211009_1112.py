# Generated by Django 2.2 on 2021-10-09 11:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0113_auto_20211009_0324'),
    ]

    operations = [
        migrations.AddField(
            model_name='buildplayerprojection',
            name='balanced_value',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=5, verbose_name='BV'),
        ),
        migrations.AlterField(
            model_name='buildplayerprojection',
            name='max_exposure',
            field=models.IntegerField(default=100, verbose_name='Max'),
        ),
    ]
