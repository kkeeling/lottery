# Generated by Django 2.2 on 2022-03-22 12:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('formula_1', '0016_auto_20220322_1104'),
    ]

    operations = [
        migrations.CreateModel(
            name='RaceSimNumLeadersProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('leader_count', models.IntegerField(default=1)),
                ('probability', models.FloatField(default=0.0)),
                ('sim', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nl_profiles', to='formula_1.RaceSim')),
            ],
        ),
    ]
