# Generated by Django 2.2 on 2021-09-30 14:52

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0098_slatebuildconfig_use_super_stacks'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildstack',
            name='mini_player_1',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='mini_1_stacks', to='nfl.BuildPlayerProjection'),
        ),
        migrations.AddField(
            model_name='slatebuildstack',
            name='mini_player_2',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='mini_2_stacks', to='nfl.BuildPlayerProjection'),
        ),
    ]