# Generated by Django 2.2 on 2021-06-11 10:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0010_playerselectioncriteria'),
    ]

    operations = [
        migrations.CreateModel(
            name='LineupConstructionRule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('site', models.CharField(choices=[('draftkings', 'DraftKings'), ('fanduel', 'Fanduel'), ('yahoo', 'Yahoo')], default='fanduel', max_length=50)),
            ],
            options={
                'verbose_name': 'Lineup Construction Rule',
                'verbose_name_plural': 'Lineup Construction Rules',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='GroupCreationRule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('allow_rb', models.BooleanField(default=False)),
                ('allow_wr', models.BooleanField(default=False)),
                ('allow_te', models.BooleanField(default=False)),
                ('at_least', models.PositiveSmallIntegerField(default=0, help_text='At least X players meeting threshold, where X is the number you input')),
                ('at_least_threshold', models.TextField(blank=True, help_text='Forumla for limit threshold', null=True)),
                ('construction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='groups', to='nfl.LineupConstructionRule')),
            ],
            options={
                'verbose_name': 'Group Creation Rule',
                'verbose_name_plural': 'Group Creation Rules',
                'ordering': ['name'],
            },
        ),
    ]
