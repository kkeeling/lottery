# Generated by Django 2.2 on 2021-11-03 14:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0134_remove_stackconstructionrule_lock_top_pc'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildconfig',
            name='use_leverage',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='slatebuildconfig',
            name='use_mini_stacks',
            field=models.BooleanField(default=False),
        ),
    ]
