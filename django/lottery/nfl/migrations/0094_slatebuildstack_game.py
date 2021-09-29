# Generated by Django 2.2 on 2021-09-23 07:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0093_slategame_avg_stack_ceiling'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildstack',
            name='game',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stacks', to='nfl.SlateGame'),
        ),
    ]