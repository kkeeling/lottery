# Generated by Django 2.2 on 2021-10-29 20:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0133_stackconstructionrule_criteria'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='stackconstructionrule',
            name='lock_top_pc',
        ),
    ]