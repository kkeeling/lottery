# Generated by Django 2.2 on 2023-01-12 15:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0036_auto_20230112_1503'),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='country',
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='player',
            name='first_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='player',
            name='last_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
