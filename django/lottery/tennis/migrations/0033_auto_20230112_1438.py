# Generated by Django 2.2 on 2023-01-12 14:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0032_slate_input_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='player_id',
            field=models.CharField(max_length=50),
        ),
    ]