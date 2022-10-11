# Generated by Django 2.2 on 2022-10-07 12:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0183_slateprojectionimport_content_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slateprojectionimport',
            name='content_type',
            field=models.CharField(choices=[('csv', 'CSV'), ('json', 'JSON')], default='csv', max_length=5),
        ),
    ]
