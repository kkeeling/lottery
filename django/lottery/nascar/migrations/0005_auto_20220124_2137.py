# Generated by Django 2.2 on 2022-01-24 21:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0004_auto_20220124_2134'),
    ]

    operations = [
        migrations.AlterField(
            model_name='track',
            name='track_name',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
