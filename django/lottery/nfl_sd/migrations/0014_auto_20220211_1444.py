# Generated by Django 2.2 on 2022-02-11 14:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl_sd', '0013_slate_num_contest_entries'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slatebuildlineup',
            name='ownership_projection',
            field=models.DecimalField(decimal_places=9, default=0.0, max_digits=10),
        ),
    ]