# Generated by Django 2.2 on 2022-11-29 14:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0202_auto_20221117_1533'),
    ]

    operations = [
        migrations.AddField(
            model_name='alias',
            name='etr_all_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='marketprojections',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4 Main'), ('4for4_thu_mon', '4for4 Thu-Mon'), ('4for4_sun_mon', '4for4 Sun-Mon'), ('4for4_early', '4for4 1pm Only'), ('4for4_afternoon', '4for4 Afternoon Only'), ('4for4_turbo', '4for4 Turbo'), ('4for4_primetime', '4for4 Primetime'), ('4for4_mon_thu', '4for4 Mon-Thu'), ('awesemo', 'Awesemo Main'), ('awesemo_own', 'Awesemo Main Ownership'), ('awesemo_thu_mon', 'Awesemo Thu-Mon'), ('awesemo_own_thu_mon', 'Awesemo Thu-Mon Ownership'), ('awesemo_sun_mon', 'Awesemo Sun-Mon'), ('awesemo_own_sun_mon', 'Awesemo Sun-Mon Ownership'), ('awesemo_early', 'Awesemo 1pm Only'), ('awesemo_own_early', 'Awesemo 1pm Only Ownership'), ('awesemo_afternoon', 'Awesemo Afternoon Only'), ('awesemo_own_afternoon', 'Awesemo Afternoon Only Ownership'), ('awesemo_turbo', 'Awesemo Turbo'), ('awesemo_own_turbo', 'Awesemo Turbo Ownership'), ('awesemo_primetime', 'Awesemo Primetime'), ('awesemo_own_primetime', 'Awesemo Primetime Ownership'), ('awesemo_mon_thu', 'Awesemo Mon-Thu'), ('awesemo_own_mon_thu', 'Awesemo Mon-Thu Ownership'), ('awesemo_sd', 'Awesemo Showdown'), ('awesemo_own_sd', 'Awesemo Showdown Ownership'), ('etr', 'Establish The Run Main'), ('etr_all', 'Establish The Run All'), ('etr_sd', 'Establish The Run DK Showdown'), ('etr_sg', 'Establish The Run FD Single Game'), ('rg', 'Rotogrinders Main'), ('rg_all', 'Rotogrinders All'), ('rg_thu_mon', 'Rotogrinders Thu-Mon'), ('rg_sun_mon', 'Rotogrinders Sun-Mon'), ('rg_early', 'Rotogrinders 1pm Only'), ('rg_afternoon', 'Rotogrinders Afternoon Only'), ('rg_turbo', 'Rotogrinders Turbo'), ('rg_primetime', 'Rotogrinders Primetime'), ('rg_mon_thu', 'Rotogrinders Mon-Thu'), ('rg_sd', 'Rotogrinders Showdown')], default='4for4', max_length=255),
        ),
        migrations.AlterField(
            model_name='marketprojections',
            name='site',
            field=models.CharField(choices=[('draftkings', 'DK'), ('fanduel', 'FD'), ('yahoo', 'YH')], default='draftkings', max_length=50),
        ),
        migrations.AlterField(
            model_name='missingalias',
            name='site',
            field=models.CharField(choices=[('draftkings', 'DK'), ('fanduel', 'FD'), ('yahoo', 'YH'), ('4for4', '4For4 Main'), ('4for4_thu_mon', '4for4 Thu-Mon'), ('4for4_sun_mon', '4for4 Sun-Mon'), ('4for4_early', '4for4 1pm Only'), ('4for4_afternoon', '4for4 Afternoon Only'), ('4for4_turbo', '4for4 Turbo'), ('4for4_primetime', '4for4 Primetime'), ('4for4_mon_thu', '4for4 Mon-Thu'), ('awesemo', 'Awesemo Main'), ('awesemo_own', 'Awesemo Main Ownership'), ('awesemo_thu_mon', 'Awesemo Thu-Mon'), ('awesemo_own_thu_mon', 'Awesemo Thu-Mon Ownership'), ('awesemo_sun_mon', 'Awesemo Sun-Mon'), ('awesemo_own_sun_mon', 'Awesemo Sun-Mon Ownership'), ('awesemo_early', 'Awesemo 1pm Only'), ('awesemo_own_early', 'Awesemo 1pm Only Ownership'), ('awesemo_afternoon', 'Awesemo Afternoon Only'), ('awesemo_own_afternoon', 'Awesemo Afternoon Only Ownership'), ('awesemo_turbo', 'Awesemo Turbo'), ('awesemo_own_turbo', 'Awesemo Turbo Ownership'), ('awesemo_primetime', 'Awesemo Primetime'), ('awesemo_own_primetime', 'Awesemo Primetime Ownership'), ('awesemo_mon_thu', 'Awesemo Mon-Thu'), ('awesemo_own_mon_thu', 'Awesemo Mon-Thu Ownership'), ('awesemo_sd', 'Awesemo Showdown'), ('awesemo_own_sd', 'Awesemo Showdown Ownership'), ('etr', 'Establish The Run Main'), ('etr_all', 'Establish The Run All'), ('etr_sd', 'Establish The Run DK Showdown'), ('etr_sg', 'Establish The Run FD Single Game'), ('rg', 'Rotogrinders Main'), ('rg_all', 'Rotogrinders All'), ('rg_thu_mon', 'Rotogrinders Thu-Mon'), ('rg_sun_mon', 'Rotogrinders Sun-Mon'), ('rg_early', 'Rotogrinders 1pm Only'), ('rg_afternoon', 'Rotogrinders Afternoon Only'), ('rg_turbo', 'Rotogrinders Turbo'), ('rg_primetime', 'Rotogrinders Primetime'), ('rg_mon_thu', 'Rotogrinders Mon-Thu'), ('rg_sd', 'Rotogrinders Showdown')], default='fanduel', max_length=50),
        ),
        migrations.AlterField(
            model_name='sheetcolumnheaders',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4 Main'), ('4for4_thu_mon', '4for4 Thu-Mon'), ('4for4_sun_mon', '4for4 Sun-Mon'), ('4for4_early', '4for4 1pm Only'), ('4for4_afternoon', '4for4 Afternoon Only'), ('4for4_turbo', '4for4 Turbo'), ('4for4_primetime', '4for4 Primetime'), ('4for4_mon_thu', '4for4 Mon-Thu'), ('awesemo', 'Awesemo Main'), ('awesemo_own', 'Awesemo Main Ownership'), ('awesemo_thu_mon', 'Awesemo Thu-Mon'), ('awesemo_own_thu_mon', 'Awesemo Thu-Mon Ownership'), ('awesemo_sun_mon', 'Awesemo Sun-Mon'), ('awesemo_own_sun_mon', 'Awesemo Sun-Mon Ownership'), ('awesemo_early', 'Awesemo 1pm Only'), ('awesemo_own_early', 'Awesemo 1pm Only Ownership'), ('awesemo_afternoon', 'Awesemo Afternoon Only'), ('awesemo_own_afternoon', 'Awesemo Afternoon Only Ownership'), ('awesemo_turbo', 'Awesemo Turbo'), ('awesemo_own_turbo', 'Awesemo Turbo Ownership'), ('awesemo_primetime', 'Awesemo Primetime'), ('awesemo_own_primetime', 'Awesemo Primetime Ownership'), ('awesemo_mon_thu', 'Awesemo Mon-Thu'), ('awesemo_own_mon_thu', 'Awesemo Mon-Thu Ownership'), ('awesemo_sd', 'Awesemo Showdown'), ('awesemo_own_sd', 'Awesemo Showdown Ownership'), ('etr', 'Establish The Run Main'), ('etr_all', 'Establish The Run All'), ('etr_sd', 'Establish The Run DK Showdown'), ('etr_sg', 'Establish The Run FD Single Game'), ('rg', 'Rotogrinders Main'), ('rg_all', 'Rotogrinders All'), ('rg_thu_mon', 'Rotogrinders Thu-Mon'), ('rg_sun_mon', 'Rotogrinders Sun-Mon'), ('rg_early', 'Rotogrinders 1pm Only'), ('rg_afternoon', 'Rotogrinders Afternoon Only'), ('rg_turbo', 'Rotogrinders Turbo'), ('rg_primetime', 'Rotogrinders Primetime'), ('rg_mon_thu', 'Rotogrinders Mon-Thu'), ('rg_sd', 'Rotogrinders Showdown')], default='4for4', max_length=255),
        ),
        migrations.AlterField(
            model_name='slateplayerownershipprojectionsheet',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4 Main'), ('4for4_thu_mon', '4for4 Thu-Mon'), ('4for4_sun_mon', '4for4 Sun-Mon'), ('4for4_early', '4for4 1pm Only'), ('4for4_afternoon', '4for4 Afternoon Only'), ('4for4_turbo', '4for4 Turbo'), ('4for4_primetime', '4for4 Primetime'), ('4for4_mon_thu', '4for4 Mon-Thu'), ('awesemo', 'Awesemo Main'), ('awesemo_own', 'Awesemo Main Ownership'), ('awesemo_thu_mon', 'Awesemo Thu-Mon'), ('awesemo_own_thu_mon', 'Awesemo Thu-Mon Ownership'), ('awesemo_sun_mon', 'Awesemo Sun-Mon'), ('awesemo_own_sun_mon', 'Awesemo Sun-Mon Ownership'), ('awesemo_early', 'Awesemo 1pm Only'), ('awesemo_own_early', 'Awesemo 1pm Only Ownership'), ('awesemo_afternoon', 'Awesemo Afternoon Only'), ('awesemo_own_afternoon', 'Awesemo Afternoon Only Ownership'), ('awesemo_turbo', 'Awesemo Turbo'), ('awesemo_own_turbo', 'Awesemo Turbo Ownership'), ('awesemo_primetime', 'Awesemo Primetime'), ('awesemo_own_primetime', 'Awesemo Primetime Ownership'), ('awesemo_mon_thu', 'Awesemo Mon-Thu'), ('awesemo_own_mon_thu', 'Awesemo Mon-Thu Ownership'), ('awesemo_sd', 'Awesemo Showdown'), ('awesemo_own_sd', 'Awesemo Showdown Ownership'), ('etr', 'Establish The Run Main'), ('etr_all', 'Establish The Run All'), ('etr_sd', 'Establish The Run DK Showdown'), ('etr_sg', 'Establish The Run FD Single Game'), ('rg', 'Rotogrinders Main'), ('rg_all', 'Rotogrinders All'), ('rg_thu_mon', 'Rotogrinders Thu-Mon'), ('rg_sun_mon', 'Rotogrinders Sun-Mon'), ('rg_early', 'Rotogrinders 1pm Only'), ('rg_afternoon', 'Rotogrinders Afternoon Only'), ('rg_turbo', 'Rotogrinders Turbo'), ('rg_primetime', 'Rotogrinders Primetime'), ('rg_mon_thu', 'Rotogrinders Mon-Thu'), ('rg_sd', 'Rotogrinders Showdown')], default='awesemo', max_length=255),
        ),
        migrations.AlterField(
            model_name='slateplayerrawprojection',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4 Main'), ('4for4_thu_mon', '4for4 Thu-Mon'), ('4for4_sun_mon', '4for4 Sun-Mon'), ('4for4_early', '4for4 1pm Only'), ('4for4_afternoon', '4for4 Afternoon Only'), ('4for4_turbo', '4for4 Turbo'), ('4for4_primetime', '4for4 Primetime'), ('4for4_mon_thu', '4for4 Mon-Thu'), ('awesemo', 'Awesemo Main'), ('awesemo_own', 'Awesemo Main Ownership'), ('awesemo_thu_mon', 'Awesemo Thu-Mon'), ('awesemo_own_thu_mon', 'Awesemo Thu-Mon Ownership'), ('awesemo_sun_mon', 'Awesemo Sun-Mon'), ('awesemo_own_sun_mon', 'Awesemo Sun-Mon Ownership'), ('awesemo_early', 'Awesemo 1pm Only'), ('awesemo_own_early', 'Awesemo 1pm Only Ownership'), ('awesemo_afternoon', 'Awesemo Afternoon Only'), ('awesemo_own_afternoon', 'Awesemo Afternoon Only Ownership'), ('awesemo_turbo', 'Awesemo Turbo'), ('awesemo_own_turbo', 'Awesemo Turbo Ownership'), ('awesemo_primetime', 'Awesemo Primetime'), ('awesemo_own_primetime', 'Awesemo Primetime Ownership'), ('awesemo_mon_thu', 'Awesemo Mon-Thu'), ('awesemo_own_mon_thu', 'Awesemo Mon-Thu Ownership'), ('awesemo_sd', 'Awesemo Showdown'), ('awesemo_own_sd', 'Awesemo Showdown Ownership'), ('etr', 'Establish The Run Main'), ('etr_all', 'Establish The Run All'), ('etr_sd', 'Establish The Run DK Showdown'), ('etr_sg', 'Establish The Run FD Single Game'), ('rg', 'Rotogrinders Main'), ('rg_all', 'Rotogrinders All'), ('rg_thu_mon', 'Rotogrinders Thu-Mon'), ('rg_sun_mon', 'Rotogrinders Sun-Mon'), ('rg_early', 'Rotogrinders 1pm Only'), ('rg_afternoon', 'Rotogrinders Afternoon Only'), ('rg_turbo', 'Rotogrinders Turbo'), ('rg_primetime', 'Rotogrinders Primetime'), ('rg_mon_thu', 'Rotogrinders Mon-Thu'), ('rg_sd', 'Rotogrinders Showdown')], default='4for4', max_length=255),
        ),
        migrations.AlterField(
            model_name='slateprojectionimport',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4 Main'), ('4for4_thu_mon', '4for4 Thu-Mon'), ('4for4_sun_mon', '4for4 Sun-Mon'), ('4for4_early', '4for4 1pm Only'), ('4for4_afternoon', '4for4 Afternoon Only'), ('4for4_turbo', '4for4 Turbo'), ('4for4_primetime', '4for4 Primetime'), ('4for4_mon_thu', '4for4 Mon-Thu'), ('awesemo', 'Awesemo Main'), ('awesemo_own', 'Awesemo Main Ownership'), ('awesemo_thu_mon', 'Awesemo Thu-Mon'), ('awesemo_own_thu_mon', 'Awesemo Thu-Mon Ownership'), ('awesemo_sun_mon', 'Awesemo Sun-Mon'), ('awesemo_own_sun_mon', 'Awesemo Sun-Mon Ownership'), ('awesemo_early', 'Awesemo 1pm Only'), ('awesemo_own_early', 'Awesemo 1pm Only Ownership'), ('awesemo_afternoon', 'Awesemo Afternoon Only'), ('awesemo_own_afternoon', 'Awesemo Afternoon Only Ownership'), ('awesemo_turbo', 'Awesemo Turbo'), ('awesemo_own_turbo', 'Awesemo Turbo Ownership'), ('awesemo_primetime', 'Awesemo Primetime'), ('awesemo_own_primetime', 'Awesemo Primetime Ownership'), ('awesemo_mon_thu', 'Awesemo Mon-Thu'), ('awesemo_own_mon_thu', 'Awesemo Mon-Thu Ownership'), ('awesemo_sd', 'Awesemo Showdown'), ('awesemo_own_sd', 'Awesemo Showdown Ownership'), ('etr', 'Establish The Run Main'), ('etr_all', 'Establish The Run All'), ('etr_sd', 'Establish The Run DK Showdown'), ('etr_sg', 'Establish The Run FD Single Game'), ('rg', 'Rotogrinders Main'), ('rg_all', 'Rotogrinders All'), ('rg_thu_mon', 'Rotogrinders Thu-Mon'), ('rg_sun_mon', 'Rotogrinders Sun-Mon'), ('rg_early', 'Rotogrinders 1pm Only'), ('rg_afternoon', 'Rotogrinders Afternoon Only'), ('rg_turbo', 'Rotogrinders Turbo'), ('rg_primetime', 'Rotogrinders Primetime'), ('rg_mon_thu', 'Rotogrinders Mon-Thu'), ('rg_sd', 'Rotogrinders Showdown')], default='4for4', max_length=255),
        ),
        migrations.AlterField(
            model_name='slateprojectionsheet',
            name='projection_site',
            field=models.CharField(choices=[('4for4', '4For4 Main'), ('4for4_thu_mon', '4for4 Thu-Mon'), ('4for4_sun_mon', '4for4 Sun-Mon'), ('4for4_early', '4for4 1pm Only'), ('4for4_afternoon', '4for4 Afternoon Only'), ('4for4_turbo', '4for4 Turbo'), ('4for4_primetime', '4for4 Primetime'), ('4for4_mon_thu', '4for4 Mon-Thu'), ('awesemo', 'Awesemo Main'), ('awesemo_own', 'Awesemo Main Ownership'), ('awesemo_thu_mon', 'Awesemo Thu-Mon'), ('awesemo_own_thu_mon', 'Awesemo Thu-Mon Ownership'), ('awesemo_sun_mon', 'Awesemo Sun-Mon'), ('awesemo_own_sun_mon', 'Awesemo Sun-Mon Ownership'), ('awesemo_early', 'Awesemo 1pm Only'), ('awesemo_own_early', 'Awesemo 1pm Only Ownership'), ('awesemo_afternoon', 'Awesemo Afternoon Only'), ('awesemo_own_afternoon', 'Awesemo Afternoon Only Ownership'), ('awesemo_turbo', 'Awesemo Turbo'), ('awesemo_own_turbo', 'Awesemo Turbo Ownership'), ('awesemo_primetime', 'Awesemo Primetime'), ('awesemo_own_primetime', 'Awesemo Primetime Ownership'), ('awesemo_mon_thu', 'Awesemo Mon-Thu'), ('awesemo_own_mon_thu', 'Awesemo Mon-Thu Ownership'), ('awesemo_sd', 'Awesemo Showdown'), ('awesemo_own_sd', 'Awesemo Showdown Ownership'), ('etr', 'Establish The Run Main'), ('etr_all', 'Establish The Run All'), ('etr_sd', 'Establish The Run DK Showdown'), ('etr_sg', 'Establish The Run FD Single Game'), ('rg', 'Rotogrinders Main'), ('rg_all', 'Rotogrinders All'), ('rg_thu_mon', 'Rotogrinders Thu-Mon'), ('rg_sun_mon', 'Rotogrinders Sun-Mon'), ('rg_early', 'Rotogrinders 1pm Only'), ('rg_afternoon', 'Rotogrinders Afternoon Only'), ('rg_turbo', 'Rotogrinders Turbo'), ('rg_primetime', 'Rotogrinders Primetime'), ('rg_mon_thu', 'Rotogrinders Mon-Thu'), ('rg_sd', 'Rotogrinders Showdown')], default='4for4', max_length=255),
        ),
    ]
