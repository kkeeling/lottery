# Generated by Django 2.2 on 2021-09-13 07:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0084_slate_fc_actuals_sheet'),
    ]

    operations = [
        migrations.AddField(
            model_name='slate',
            name='is_complete',
            field=models.BooleanField(default=False),
        ),
    ]