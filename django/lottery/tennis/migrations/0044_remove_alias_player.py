# Generated by Django 2.2 on 2023-01-18 15:24

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0043_auto_20230118_1433'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='alias',
            name='player',
        ),
    ]
