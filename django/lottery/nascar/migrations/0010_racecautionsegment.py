# Generated by Django 2.2 on 2022-01-26 12:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0009_auto_20220125_2017'),
    ]

    operations = [
        migrations.CreateModel(
            name='RaceCautionSegment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_lap', models.IntegerField(default=0)),
                ('end_lap', models.IntegerField(default=0)),
                ('reason', models.CharField(blank=True, max_length=255, null=True)),
                ('comment', models.TextField(blank=True, null=True)),
                ('race', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cautions', to='nascar.Race')),
            ],
        ),
    ]