# Generated by Django 2.2 on 2021-11-30 15:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0147_slate_end_datetime'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='buildplayerprojection',
            name='at_least_one_in_lineup',
        ),
        migrations.RemoveField(
            model_name='buildplayerprojection',
            name='at_least_two_in_lineup',
        ),
        migrations.RemoveField(
            model_name='buildplayerprojection',
            name='at_most_one_in_stack',
        ),
    ]
