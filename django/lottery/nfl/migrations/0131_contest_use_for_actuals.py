# Generated by Django 2.2 on 2021-10-25 21:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0130_auto_20211025_2146'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='use_for_actuals',
            field=models.BooleanField(default=True),
        ),
    ]
