# Generated by Django 2.2 on 2021-09-08 07:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0072_auto_20210907_1225'),
    ]

    operations = [
        migrations.AddField(
            model_name='slateplayerownershipprojectionsheet',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4'), ('awesemo', 'Awesemo'), ('etr', 'Establish The Run'), ('tda', 'The Daily Average'), ('rg', 'Rotogrinders'), ('fc', 'Fantasy Cruncher'), ('rts', 'Run The Sims')], default='awesemo', max_length=255),
        ),
    ]
