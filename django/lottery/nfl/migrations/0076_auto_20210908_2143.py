# Generated by Django 2.2 on 2021-09-08 21:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0075_auto_20210908_2131'),
    ]

    operations = [
        migrations.RenameField(
            model_name='groupcreationrule',
            old_name='at_least_threshold',
            new_name='threshold',
        ),
        migrations.RemoveField(
            model_name='groupcreationrule',
            name='at_most_threshold',
        ),
    ]
