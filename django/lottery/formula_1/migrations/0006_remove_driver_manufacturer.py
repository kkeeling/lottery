# Generated by Django 2.2 on 2022-03-17 12:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('formula_1', '0005_auto_20220317_1240'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='driver',
            name='manufacturer',
        ),
    ]