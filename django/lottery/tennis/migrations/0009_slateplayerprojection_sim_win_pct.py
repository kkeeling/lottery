# Generated by Django 2.2 on 2022-01-10 16:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0008_slateplayerprojection_slate_match'),
    ]

    operations = [
        migrations.AddField(
            model_name='slateplayerprojection',
            name='sim_win_pct',
            field=models.DecimalField(decimal_places=4, default=0.0, max_digits=5, verbose_name='sim_win'),
        ),
    ]