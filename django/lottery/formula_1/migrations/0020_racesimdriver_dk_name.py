# Generated by Django 2.2 on 2022-04-06 13:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('formula_1', '0019_auto_20220323_1253'),
    ]

    operations = [
        migrations.AddField(
            model_name='racesimdriver',
            name='dk_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]