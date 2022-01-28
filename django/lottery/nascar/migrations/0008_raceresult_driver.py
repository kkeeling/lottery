# Generated by Django 2.2 on 2022-01-25 20:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0007_auto_20220125_2011'),
    ]

    operations = [
        migrations.AddField(
            model_name='raceresult',
            name='driver',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='results', to='nascar.Driver'),
            preserve_default=False,
        ),
    ]