# Generated by Django 2.2 on 2021-09-13 08:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0085_slate_is_complete'),
    ]

    operations = [
        migrations.AddField(
            model_name='sheetcolumnheaders',
            name='column_ownership',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='sheetcolumnheaders',
            name='column_score',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
