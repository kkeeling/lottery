# Generated by Django 2.2 on 2021-11-09 15:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fanduel', '0002_auto_20211109_1507'),
    ]

    operations = [
        migrations.AddField(
            model_name='contestentry',
            name='entry_id',
            field=models.CharField(default='1', max_length=50),
            preserve_default=False,
        ),
    ]