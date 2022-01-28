# Generated by Django 2.2 on 2022-01-11 13:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0016_auto_20220111_1245'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slatebuildconfig',
            name='clean_lineups_by',
            field=models.CharField(choices=[('implied_win_pct', 'Implied Win %'), ('sim_win_pct', 'Simulated Win %'), ('projection', 'Median Projection'), ('s90', 'Ceiling Projection')], default='implied_win_pct', max_length=15),
        ),
        migrations.AlterField(
            model_name='slatebuildconfig',
            name='optimize_by',
            field=models.CharField(choices=[('implied_win_pct', 'Implied Win %'), ('sim_win_pct', 'Simulated Win %'), ('projection', 'Median Projection'), ('s90', 'Ceiling Projection')], default='implied_win_pct', max_length=50),
        ),
        migrations.CreateModel(
            name='SlateBuildPlayerExposure',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exposure', models.DecimalField(decimal_places=4, default=0.0, max_digits=5)),
                ('build', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exposures', to='tennis.SlateBuild')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exposures', to='tennis.SlatePlayerProjection')),
            ],
        ),
    ]