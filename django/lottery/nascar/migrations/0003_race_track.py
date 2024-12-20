# Generated by Django 2.2 on 2022-01-24 21:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0002_auto_20220124_1541'),
    ]

    operations = [
        migrations.CreateModel(
            name='Track',
            fields=[
                ('track_id', models.IntegerField(db_index=True, primary_key=True, serialize=False, unique=True)),
                ('track_name', models.CharField(max_length=255)),
                ('track_type', models.IntegerField(choices=[(1, 'Large Oval'), (2, 'Flat Track'), (3, 'Short Track'), (4, 'Super Speedway'), (5, 'Road Course')], default=1)),
            ],
        ),
        migrations.CreateModel(
            name='Race',
            fields=[
                ('race_id', models.BigIntegerField(db_index=True, primary_key=True, serialize=False, unique=True)),
                ('series', models.IntegerField(choices=[(1, 'Nascar'), (2, 'Xfinity'), (3, 'Trucks')], default=1)),
                ('race_season', models.IntegerField(default=2022)),
                ('race_name', models.CharField(max_length=255)),
                ('race_type', models.IntegerField(choices=[(1, 'Points Race'), (2, 'Exhibition Race')], default=1)),
                ('restrictor_plate', models.BooleanField(default=False)),
                ('race_date', models.DateTimeField()),
                ('qualifying_date', models.DateTimeField(blank=True, null=True)),
                ('scheduled_distance', models.IntegerField(default=0)),
                ('scheduled_laps', models.IntegerField(default=0)),
                ('track', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='races', to='nascar.Track')),
            ],
        ),
    ]
