# Generated by Django 2.2 on 2022-07-18 22:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0098_auto_20220718_2210'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatelineup',
            name='player_1',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='p1', to='nascar.SlatePlayer'),
        ),
        migrations.AddField(
            model_name='slatelineup',
            name='player_2',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='p2', to='nascar.SlatePlayer'),
        ),
        migrations.AddField(
            model_name='slatelineup',
            name='player_3',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='p3', to='nascar.SlatePlayer'),
        ),
        migrations.AddField(
            model_name='slatelineup',
            name='player_4',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='p4', to='nascar.SlatePlayer'),
        ),
        migrations.AddField(
            model_name='slatelineup',
            name='player_5',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='p5', to='nascar.SlatePlayer'),
        ),
        migrations.AddField(
            model_name='slatelineup',
            name='player_6',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='p6', to='nascar.SlatePlayer'),
        ),
        migrations.AddField(
            model_name='slatelineup',
            name='slate',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='possible_lineups', to='nascar.Slate'),
            preserve_default=False,
        ),
    ]
