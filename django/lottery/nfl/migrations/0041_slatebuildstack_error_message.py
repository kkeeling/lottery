# Generated by Django 2.2 on 2021-07-24 13:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0040_slatebuildstack_lineups_created'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildstack',
            name='error_message',
            field=models.TextField(blank=True, null=True),
        ),
    ]
