# Generated by Django 2.2 on 2021-11-30 14:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0146_groupimportsheet'),
    ]

    operations = [
        migrations.AddField(
            model_name='slate',
            name='end_datetime',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
