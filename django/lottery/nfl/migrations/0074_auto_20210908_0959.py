# Generated by Django 2.2 on 2021-09-08 09:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0073_slateplayerownershipprojectionsheet_projection_site'),
    ]

    operations = [
        migrations.AddField(
            model_name='alias',
            name='awesemo_ownership_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='missingalias',
            name='site',
            field=models.CharField(choices=[('draftkings', 'DraftKings'), ('fanduel', 'Fanduel'), ('yahoo', 'Yahoo'), ('4for4', '4For4'), ('awesemo', 'Awesemo'), ('awesemo_own', 'Awesemo Ownership'), ('etr', 'Establish The Run'), ('tda', 'The Daily Average'), ('rg', 'Rotogrinders'), ('fc', 'Fantasy Cruncher'), ('rts', 'Run The Sims')], default='fanduel', max_length=50),
        ),
        migrations.AlterField(
            model_name='sheetcolumnheaders',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4'), ('awesemo', 'Awesemo'), ('awesemo_own', 'Awesemo Ownership'), ('etr', 'Establish The Run'), ('tda', 'The Daily Average'), ('rg', 'Rotogrinders'), ('fc', 'Fantasy Cruncher'), ('rts', 'Run The Sims')], default='4for4', max_length=255),
        ),
        migrations.AlterField(
            model_name='slateplayerownershipprojectionsheet',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4'), ('awesemo', 'Awesemo'), ('awesemo_own', 'Awesemo Ownership'), ('etr', 'Establish The Run'), ('tda', 'The Daily Average'), ('rg', 'Rotogrinders'), ('fc', 'Fantasy Cruncher'), ('rts', 'Run The Sims')], default='awesemo', max_length=255),
        ),
        migrations.AlterField(
            model_name='slateplayerrawprojection',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4'), ('awesemo', 'Awesemo'), ('awesemo_own', 'Awesemo Ownership'), ('etr', 'Establish The Run'), ('tda', 'The Daily Average'), ('rg', 'Rotogrinders'), ('fc', 'Fantasy Cruncher'), ('rts', 'Run The Sims')], default='4for4', max_length=255),
        ),
        migrations.AlterField(
            model_name='slateprojectionsheet',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4'), ('awesemo', 'Awesemo'), ('awesemo_own', 'Awesemo Ownership'), ('etr', 'Establish The Run'), ('tda', 'The Daily Average'), ('rg', 'Rotogrinders'), ('fc', 'Fantasy Cruncher'), ('rts', 'Run The Sims')], default='4for4', max_length=255),
        ),
    ]