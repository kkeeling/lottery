# Generated by Django 2.2 on 2022-10-07 12:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0182_auto_20221007_0738'),
    ]

    operations = [
        migrations.AddField(
            model_name='slateprojectionimport',
            name='content_type',
            field=models.CharField(default='csv', max_length=5),
        ),
    ]
