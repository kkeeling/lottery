# Generated by Django 2.2 on 2022-09-02 10:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0167_slate_in_play_criteria'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='slate',
            name='dst_threshold',
        ),
        migrations.RemoveField(
            model_name='slate',
            name='qb_threshold',
        ),
        migrations.RemoveField(
            model_name='slate',
            name='rb_threshold',
        ),
        migrations.RemoveField(
            model_name='slate',
            name='te_threshold',
        ),
        migrations.RemoveField(
            model_name='slate',
            name='wr_threshold',
        ),
    ]
