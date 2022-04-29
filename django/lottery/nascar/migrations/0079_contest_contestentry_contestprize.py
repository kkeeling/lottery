# Generated by Django 2.2 on 2022-04-27 13:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0078_auto_20220405_2044'),
    ]

    operations = [
        migrations.CreateModel(
            name='Contest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cost', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('num_entries', models.PositiveIntegerField(default=0)),
                ('entries_file', models.FileField(blank=True, null=True, upload_to='uploads/entries')),
                ('slate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contests', to='nascar.Slate')),
            ],
        ),
        migrations.CreateModel(
            name='ContestPrize',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('min_rank', models.IntegerField(default=1)),
                ('max_rank', models.IntegerField(default=1)),
                ('prize', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('contest', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prizes', to='nascar.Contest')),
            ],
        ),
        migrations.CreateModel(
            name='ContestEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entry_id', models.CharField(max_length=50)),
                ('entry_name', models.CharField(blank=True, max_length=255, null=True)),
                ('lineup_str', models.TextField(blank=True, null=True)),
                ('contest', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='nascar.Contest')),
                ('player_1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contest_entry_as_player_1', to='nascar.SlatePlayer')),
                ('player_2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contest_entry_as_player_2', to='nascar.SlatePlayer')),
                ('player_3', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contest_entry_as_player_3', to='nascar.SlatePlayer')),
                ('player_4', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contest_entry_as_player_4', to='nascar.SlatePlayer')),
                ('player_5', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contest_entry_as_player_5', to='nascar.SlatePlayer')),
                ('player_6', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='contest_entry_as_player_6', to='nascar.SlatePlayer')),
            ],
        ),
    ]
