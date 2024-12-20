# Generated by Django 2.2 on 2022-11-17 15:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0200_auto_20221114_1034'),
    ]

    operations = [
        migrations.AddField(
            model_name='findwinnerbuild',
            name='allow_two_tes',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='findwinnerbuild',
            name='field_lineup_creation_strategy',
            field=models.CharField(choices=[('optimize_by_ownership', 'Optimize by Ownership'), ('optimize_by_projection', 'Optimize by Projection')], default='optimize_by_ownership', max_length=50),
        ),
        migrations.AddField(
            model_name='findwinnerbuild',
            name='run_it_twice',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='findwinnerbuild',
            name='run_it_twice_count',
            field=models.IntegerField(default=3),
        ),
        migrations.AddField(
            model_name='findwinnerbuild',
            name='run_it_twice_strategy',
            field=models.CharField(choices=[('h2h', 'Head-to-Head'), ('se', 'Single Entry')], default='h2h', max_length=5),
        ),
    ]
