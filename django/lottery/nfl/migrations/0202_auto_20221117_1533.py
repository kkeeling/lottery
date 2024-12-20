# Generated by Django 2.2 on 2022-11-17 15:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0201_auto_20221117_1523'),
    ]

    operations = [
        migrations.AddField(
            model_name='winninglineup',
            name='rating_2',
            field=models.FloatField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='winninglineup',
            name='win_count_2',
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='winninglineup',
            name='win_rate_2',
            field=models.FloatField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='winningsdlineup',
            name='rating_2',
            field=models.FloatField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='winningsdlineup',
            name='win_count_2',
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='winningsdlineup',
            name='win_rate_2',
            field=models.FloatField(blank=True, db_index=True, null=True),
        ),
    ]
