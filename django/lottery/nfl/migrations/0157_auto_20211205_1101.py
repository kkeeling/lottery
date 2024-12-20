# Generated by Django 2.2 on 2021-12-05 11:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0156_auto_20211204_2252'),
    ]

    operations = [
        migrations.AlterField(
            model_name='buildplayerprojection',
            name='balanced_projection',
            field=models.DecimalField(blank=True, decimal_places=4, default=0.0, max_digits=7, null=True, verbose_name='BP'),
        ),
        migrations.AlterField(
            model_name='buildplayerprojection',
            name='balanced_value',
            field=models.DecimalField(db_index=True, decimal_places=4, default=0.0, max_digits=7, verbose_name='BV'),
        ),
    ]
