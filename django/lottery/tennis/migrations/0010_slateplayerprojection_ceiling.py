# Generated by Django 2.2 on 2022-01-10 19:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0009_slateplayerprojection_sim_win_pct'),
    ]

    operations = [
        migrations.AddField(
            model_name='slateplayerprojection',
            name='ceiling',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=5, verbose_name='Proj'),
        ),
    ]
