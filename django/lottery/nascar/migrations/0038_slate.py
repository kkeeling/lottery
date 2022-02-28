# Generated by Django 2.2 on 2022-02-25 14:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0037_racesim_laps_per_caution'),
    ]

    operations = [
        migrations.CreateModel(
            name='Slate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datetime', models.DateTimeField()),
                ('name', models.CharField(max_length=255, verbose_name='Slate')),
                ('site', models.CharField(choices=[('draftkings', 'DraftKings'), ('fanduel', 'Fanduel')], default='draftkings', max_length=50)),
                ('salaries', models.FileField(blank=True, null=True, upload_to='uploads/salaries')),
            ],
            options={
                'ordering': ['-name'],
            },
        ),
    ]
