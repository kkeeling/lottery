# Generated by Django 2.2 on 2021-06-11 09:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0009_auto_20210611_0922'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlayerSelectionCriteria',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('site', models.CharField(choices=[('draftkings', 'DraftKings'), ('fanduel', 'Fanduel'), ('yahoo', 'Yahoo')], default='fanduel', max_length=50)),
                ('qb_threshold', models.TextField(blank=True, help_text='Forumla for picking qbs in play', null=True)),
                ('rb_threshold', models.TextField(blank=True, help_text='Forumla for picking qbs in play', null=True)),
                ('wr_threshold', models.TextField(blank=True, help_text='Forumla for picking qbs in play', null=True)),
                ('te_threshold', models.TextField(blank=True, help_text='Forumla for picking qbs in play', null=True)),
                ('dst_threshold', models.TextField(blank=True, help_text='Forumla for picking qbs in play', null=True)),
            ],
            options={
                'verbose_name': 'In-Play Criteria',
                'verbose_name_plural': 'In-Play Criteria',
                'ordering': ['name'],
            },
        ),
    ]
