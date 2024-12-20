# Generated by Django 2.2 on 2021-10-09 03:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0110_auto_20211008_1342'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slatebuildstack',
            name='actual',
            field=models.DecimalField(blank=True, db_index=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AlterField(
            model_name='slatebuildstack',
            name='build_order',
            field=models.PositiveIntegerField(db_index=True, default=1),
        ),
        migrations.AlterField(
            model_name='slatebuildstack',
            name='contains_top_pc',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AlterField(
            model_name='slatebuildstack',
            name='count',
            field=models.PositiveIntegerField(db_index=True, default=0, help_text='# of lineups in which this stack should appear'),
        ),
        migrations.AlterField(
            model_name='slatebuildstack',
            name='projection',
            field=models.DecimalField(db_index=True, decimal_places=2, max_digits=5),
        ),
        migrations.AlterField(
            model_name='slatebuildstack',
            name='projection_zscore',
            field=models.DecimalField(db_index=True, decimal_places=4, default=0.0, max_digits=6, verbose_name='Z-Score'),
        ),
        migrations.AlterField(
            model_name='slatebuildstack',
            name='rank',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='slatebuildstack',
            name='salary',
            field=models.PositiveIntegerField(db_index=True),
        ),
        migrations.AlterField(
            model_name='slatebuildstack',
            name='times_used',
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
    ]
