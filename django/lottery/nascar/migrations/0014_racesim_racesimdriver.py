# Generated by Django 2.2 on 2022-01-27 12:49

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0013_racedriverlap'),
    ]

    operations = [
        migrations.CreateModel(
            name='RaceSim',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('iterations', models.IntegerField(default=10000)),
                ('race', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sims', to='nascar.Race')),
            ],
        ),
        migrations.CreateModel(
            name='RaceSimDriver',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fp_outcomes', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(default=0), blank=True, null=True, size=None)),
                ('ll_outcomes', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(default=0), blank=True, null=True, size=None)),
                ('fl_outcomes', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(default=0), blank=True, null=True, size=None)),
                ('driver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outcomes', to='nascar.Driver')),
                ('sim', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outcomes', to='nascar.RaceSim')),
            ],
        ),
    ]