# Generated by Django 2.2 on 2021-10-01 14:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0102_auto_20211001_1340'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='slate',
            name='player_contest',
        ),
        migrations.AddField(
            model_name='contest',
            name='outcomes',
            field=models.FileField(blank=True, null=True, upload_to='uploads/sims'),
        ),
    ]