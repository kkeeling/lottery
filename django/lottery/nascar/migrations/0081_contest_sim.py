# Generated by Django 2.2 on 2022-05-05 14:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0080_contestentry_sim_scores'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='sim',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contests', to='nascar.RaceSim'),
        ),
    ]