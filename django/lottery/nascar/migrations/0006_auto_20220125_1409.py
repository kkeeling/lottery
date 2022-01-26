# Generated by Django 2.2 on 2022-01-25 14:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0005_auto_20220124_2137'),
    ]

    operations = [
        migrations.AlterField(
            model_name='track',
            name='track_type',
            field=models.IntegerField(choices=[(1, '550 HP'), (2, '750 HP'), (3, 'Super Speedway'), (4, 'Road Course')], default=1),
        ),
        migrations.CreateModel(
            name='RaceResult',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('finishing_position', models.IntegerField(default=0)),
                ('starting_position', models.IntegerField(default=0)),
                ('laps_led', models.IntegerField(default=0)),
                ('times_led', models.IntegerField(default=0)),
                ('laps_completed', models.IntegerField(default=0)),
                ('finishing_status', models.CharField(default='Running', max_length=50)),
                ('disqualified', models.BooleanField(default=False)),
                ('driver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='nascar.Driver')),
                ('race', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='nascar.Race')),
            ],
        ),
    ]
