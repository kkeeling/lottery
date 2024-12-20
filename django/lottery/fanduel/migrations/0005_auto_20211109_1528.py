# Generated by Django 2.2 on 2021-11-09 15:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fanduel', '0004_auto_20211109_1522'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='contest_id',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='contest',
            name='cost',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='contest',
            name='name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='contest',
            name='url',
            field=models.URLField(default='https://api.fanduel.com/contests/63955-248463555', help_text='https://api.fanduel.com/contests/63955-248463555'),
            preserve_default=False,
        ),
    ]
