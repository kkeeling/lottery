# Generated by Django 2.2 on 2022-01-24 15:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Alias',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dk_name', models.CharField(blank=True, max_length=255, null=True)),
                ('fd_name', models.CharField(blank=True, max_length=255, null=True)),
                ('ma_name', models.CharField(blank=True, max_length=255, null=True)),
                ('nascar_name', models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                'verbose_name': 'Alias',
                'verbose_name_plural': 'Aliases',
            },
        ),
        migrations.CreateModel(
            name='Driver',
            fields=[
                ('driver_id', models.BigIntegerField(db_index=True, primary_key=True, serialize=False, unique=True)),
                ('nascar_driver_id', models.IntegerField(db_index=True, unique=True)),
                ('first_name', models.CharField(max_length=50, null=True)),
                ('last_name', models.CharField(max_length=50, null=True)),
                ('full_name', models.CharField(max_length=50, null=True)),
                ('badge', models.CharField(max_length=5, null=True)),
                ('badge_image', models.URLField(null=True)),
                ('manufacturer_image', models.URLField(null=True)),
                ('team', models.CharField(max_length=100, null=True)),
                ('driver_image', models.URLField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='MissingAlias',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('player_name', models.CharField(blank=True, max_length=255, null=True)),
                ('site', models.CharField(choices=[('draftkings', 'DraftKings'), ('fanduel', 'Fanduel'), ('ma', 'Motorsports Analytics'), ('nascar', 'Nascar.com')], default='draftkings', max_length=50)),
                ('alias_1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hint_1', to='nascar.Alias')),
                ('alias_2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hint_2', to='nascar.Alias')),
                ('alias_3', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hint_3', to='nascar.Alias')),
            ],
            options={
                'verbose_name': 'Missing Alias',
                'verbose_name_plural': 'Missing Aliases',
            },
        ),
    ]
