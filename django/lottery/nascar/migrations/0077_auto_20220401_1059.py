# Generated by Django 2.2 on 2022-04-01 10:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0076_auto_20220331_1636'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildconfig',
            name='clean_by_direction',
            field=models.CharField(choices=[('ascending', 'Ascending'), ('descending', 'Descending')], default='descending', max_length=25),
        ),
        migrations.AddField(
            model_name='slatebuildconfig',
            name='clean_by_field',
            field=models.CharField(default='s90', max_length=25),
        ),
    ]
