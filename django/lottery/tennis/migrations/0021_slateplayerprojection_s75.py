# Generated by Django 2.2 on 2022-01-19 11:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0020_slateplayerprojection_max_exposure'),
    ]

    operations = [
        migrations.AddField(
            model_name='slateplayerprojection',
            name='s75',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=5, verbose_name='s75'),
        ),
    ]
