# Generated by Django 2.2 on 2022-02-11 11:37

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nfl_sd', '0009_auto_20220211_1118'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='slateplayerprojection',
            name='adjusted_opportunity',
        ),
        migrations.RemoveField(
            model_name='slateplayerprojection',
            name='ao_zscore',
        ),
        migrations.RemoveField(
            model_name='slateplayerprojection',
            name='ceiling_zscore',
        ),
        migrations.RemoveField(
            model_name='slateplayerprojection',
            name='zscore',
        ),
    ]