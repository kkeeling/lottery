# Generated by Django 2.2 on 2021-09-13 07:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0083_slateplayerprojection_sim_scores'),
    ]

    operations = [
        migrations.AddField(
            model_name='slate',
            name='fc_actuals_sheet',
            field=models.FileField(blank=True, null=True, upload_to='uploads/actuals', verbose_name='FC Actuals CSV'),
        ),
    ]
