# Generated by Django 2.2 on 2022-01-10 11:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0004_missingalias_slatematch'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatematch',
            name='surface',
            field=models.CharField(choices=[('Hard', 'Hard'), ('Clay', 'Clay'), ('Grass', 'Grass')], default='Hard', max_length=255),
        ),
        migrations.AlterField(
            model_name='slatematch',
            name='slate',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='matches', to='tennis.Slate'),
        ),
    ]
