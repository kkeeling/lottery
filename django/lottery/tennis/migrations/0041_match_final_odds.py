# Generated by Django 2.2 on 2023-01-12 15:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0040_match'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='final_odds',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
