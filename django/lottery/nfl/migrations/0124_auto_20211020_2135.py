# Generated by Django 2.2 on 2021-10-20 21:35

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0123_slatebuildtopstack'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='slatebuildtopstack',
            options={'ordering': ['-times_used', '-projection'], 'verbose_name': 'Top Stack', 'verbose_name_plural': 'Top Stacks'},
        ),
        migrations.RemoveField(
            model_name='slatebuildtopstack',
            name='gto',
        ),
    ]