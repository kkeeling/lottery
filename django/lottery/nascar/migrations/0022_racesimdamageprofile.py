# Generated by Django 2.2 on 2022-02-02 12:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0021_auto_20220201_1459'),
    ]

    operations = [
        migrations.CreateModel(
            name='RaceSimDamageProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('min_cars_involved', models.IntegerField(default=0)),
                ('max_cars_involved', models.IntegerField(default=2)),
                ('prob_no_damage', models.FloatField(default=0.05)),
                ('prob_minor_damage', models.FloatField(default=0.1)),
                ('prob_medium_damage', models.FloatField(default=0.1)),
                ('prob_dnf', models.FloatField(default=0.75)),
                ('sim', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='damage_profiles', to='nascar.RaceSim')),
            ],
        ),
    ]