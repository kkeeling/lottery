# Generated by Django 2.2 on 2022-01-06 07:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BuildPlayerProjection',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pinnacle_odds', models.IntegerField(default=0)),
                ('implied_win_pct', models.DecimalField(decimal_places=4, default=0.0, max_digits=5, verbose_name='iwin')),
                ('game_total', models.DecimalField(decimal_places=1, default=0.0, max_digits=3, verbose_name='gt')),
                ('spread', models.DecimalField(decimal_places=1, default=0.0, max_digits=3)),
                ('projection', models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=5, verbose_name='Proj')),
                ('in_play', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Player Projection',
                'verbose_name_plural': 'Player Projections',
                'ordering': ['-slate_player__salary'],
            },
        ),
        migrations.CreateModel(
            name='PinnacleMatch',
            fields=[
                ('id', models.BigIntegerField(primary_key=True, serialize=False, unique=True)),
                ('event', models.CharField(default='foo', max_length=255)),
                ('home_participant', models.CharField(max_length=255)),
                ('away_participant', models.CharField(max_length=255)),
                ('start_time', models.DateTimeField()),
            ],
            options={
                'verbose_name': 'Pinnacle Match',
                'verbose_name_plural': 'Pinnacle Matches',
            },
        ),
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('player_id', models.CharField(max_length=15)),
                ('first_name', models.CharField(max_length=50)),
                ('last_name', models.CharField(max_length=50)),
                ('tour', models.CharField(choices=[('atp', 'ATP'), ('wta', 'WTA')], max_length=3)),
                ('hand', models.CharField(choices=[('r', 'R'), ('l', 'L'), ('u', 'U')], max_length=1)),
                ('dob', models.DateField(blank=True, null=True)),
                ('country', models.CharField(max_length=3)),
            ],
            options={
                'verbose_name': 'Player',
                'verbose_name_plural': 'Players',
            },
        ),
        migrations.CreateModel(
            name='Slate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datetime', models.DateTimeField()),
                ('name', models.CharField(max_length=255, verbose_name='Slate')),
                ('site', models.CharField(choices=[('draftkings', 'DraftKings'), ('fanduel', 'Fanduel')], default='draftkings', max_length=50)),
                ('is_main_slate', models.BooleanField(default=False)),
                ('last_match_datetime', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-name'],
            },
        ),
        migrations.CreateModel(
            name='SlateBuild',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('used_in_contests', models.BooleanField(default=False, verbose_name='Used')),
                ('lineup_start_number', models.IntegerField(default=1)),
                ('top_score', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='top')),
                ('total_lineups', models.PositiveIntegerField(default=0, verbose_name='total')),
                ('total_cashes', models.PositiveIntegerField(blank=True, null=True, verbose_name='cashes')),
                ('total_one_pct', models.PositiveIntegerField(blank=True, null=True, verbose_name='1%')),
                ('total_half_pct', models.PositiveIntegerField(blank=True, null=True, verbose_name='0.5%')),
                ('binked', models.BooleanField(default=False, help_text='Finished 1st, 2nd, or 3rd', verbose_name='bink')),
            ],
            options={
                'verbose_name': 'Slate Build',
                'verbose_name_plural': 'Slate Builds',
            },
        ),
        migrations.CreateModel(
            name='SlateBuildConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('site', models.CharField(choices=[('draftkings', 'DraftKings'), ('fanduel', 'Fanduel')], default='draftkings', max_length=50)),
                ('randomness', models.DecimalField(decimal_places=2, default=0.75, max_digits=2)),
                ('uniques', models.IntegerField(default=1)),
                ('min_salary', models.IntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Build Config',
                'verbose_name_plural': 'Build Configs',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='SlateBuildGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('max_from_group', models.PositiveIntegerField(default=1)),
                ('min_from_group', models.PositiveIntegerField(default=0)),
                ('active', models.BooleanField(default=True)),
                ('build', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='groups', to='tennis.SlateBuild')),
            ],
            options={
                'verbose_name': 'Group',
                'verbose_name_plural': 'Groups',
            },
        ),
        migrations.CreateModel(
            name='SlatePlayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slate_player_id', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
                ('surface', models.CharField(choices=[('Hard', 'Hard'), ('Clay', 'Clay'), ('Grass', 'Grass')], default='Hard', max_length=255)),
                ('best_of', models.IntegerField(default=3)),
                ('salary', models.IntegerField()),
                ('fantasy_points', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('ownership', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('withdrew', models.BooleanField(default=False)),
                ('is_replacement_player', models.BooleanField(default=False)),
                ('opponent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='slates_as_opponent', to='tennis.Player')),
                ('player', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='slates', to='tennis.Player')),
                ('slate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='players', to='tennis.Slate')),
            ],
            options={
                'ordering': ['-salary', 'name'],
            },
        ),
        migrations.CreateModel(
            name='SlatePlayerProjection',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pinnacle_odds', models.IntegerField(default=0)),
                ('implied_win_pct', models.DecimalField(decimal_places=4, default=0.0, max_digits=5, verbose_name='iwin')),
                ('game_total', models.DecimalField(decimal_places=1, default=0.0, max_digits=3, verbose_name='gt')),
                ('spread', models.DecimalField(decimal_places=1, default=0.0, max_digits=3)),
                ('projection', models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=5, verbose_name='Proj')),
                ('slate_player', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='projection', to='tennis.SlatePlayer')),
            ],
            options={
                'verbose_name': 'Player Projection',
                'verbose_name_plural': 'Player Projections',
                'ordering': ['-slate_player__salary'],
            },
        ),
        migrations.CreateModel(
            name='SlatePlayerImportSheet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sheet_type', models.CharField(choices=[('site', 'Salary File')], default='site', max_length=255)),
                ('sheet', models.FileField(upload_to='uploads/salaries')),
                ('slate', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='salaries', to='tennis.Slate')),
            ],
        ),
        migrations.CreateModel(
            name='SlateBuildLineup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_salary', models.IntegerField(default=0)),
                ('build', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lineups', to='tennis.SlateBuild', verbose_name='Build')),
                ('player_1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lineup_as_player_1', to='tennis.BuildPlayerProjection')),
                ('player_2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lineup_as_player_2', to='tennis.BuildPlayerProjection')),
                ('player_3', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lineup_as_player_3', to='tennis.BuildPlayerProjection')),
                ('player_4', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lineup_as_player_4', to='tennis.BuildPlayerProjection')),
                ('player_5', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lineup_as_player_5', to='tennis.BuildPlayerProjection')),
                ('player_6', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lineup_as_player_6', to='tennis.BuildPlayerProjection')),
            ],
            options={
                'verbose_name': 'Lineup',
                'verbose_name_plural': 'Lineups',
            },
        ),
        migrations.CreateModel(
            name='SlateBuildGroupPlayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='players', to='tennis.SlateBuildGroup')),
                ('slate_player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='groups', to='tennis.SlatePlayer')),
            ],
            options={
                'verbose_name': 'Player',
                'verbose_name_plural': 'Players',
            },
        ),
        migrations.AddField(
            model_name='slatebuild',
            name='configuration',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='builds', to='tennis.SlateBuildConfig', verbose_name='Config'),
        ),
        migrations.AddField(
            model_name='slatebuild',
            name='slate',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='builds', to='tennis.Slate'),
        ),
        migrations.CreateModel(
            name='RankingHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ranking_date', models.DateField()),
                ('ranking', models.PositiveIntegerField()),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ranking_history', to='tennis.Player')),
            ],
            options={
                'verbose_name': 'Ranking History',
                'verbose_name_plural': 'Ranking Histories',
            },
        ),
        migrations.CreateModel(
            name='PinnacleMatchOdds',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('create_at', models.DateTimeField()),
                ('home_price', models.IntegerField(default=0)),
                ('away_price', models.IntegerField(default=0)),
                ('home_spread', models.DecimalField(decimal_places=2, default=0.0, max_digits=4)),
                ('away_spread', models.DecimalField(decimal_places=2, default=0.0, max_digits=4)),
                ('match', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='odds', to='tennis.PinnacleMatch')),
            ],
        ),
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tourney_id', models.CharField(blank=True, max_length=255, null=True)),
                ('tourney_name', models.CharField(blank=True, max_length=255, null=True)),
                ('surface', models.CharField(blank=True, max_length=255, null=True)),
                ('draw_size', models.IntegerField(blank=True, null=True)),
                ('tourney_level', models.CharField(blank=True, max_length=255, null=True)),
                ('tourney_date', models.DateField(blank=True, null=True)),
                ('match_num', models.IntegerField(blank=True, null=True)),
                ('winner_seed', models.CharField(blank=True, max_length=255, null=True)),
                ('winner_entry', models.CharField(blank=True, max_length=255, null=True)),
                ('winner_name', models.CharField(blank=True, max_length=255, null=True)),
                ('winner_hand', models.CharField(blank=True, max_length=255, null=True)),
                ('winner_ht', models.IntegerField(blank=True, null=True)),
                ('winner_ioc', models.CharField(blank=True, max_length=255, null=True)),
                ('winner_age', models.DecimalField(blank=True, decimal_places=10, max_digits=15, null=True)),
                ('loser_seed', models.CharField(blank=True, max_length=255, null=True)),
                ('loser_entry', models.CharField(blank=True, max_length=255, null=True)),
                ('loser_name', models.CharField(blank=True, max_length=255, null=True)),
                ('loser_hand', models.CharField(blank=True, max_length=255, null=True)),
                ('loser_ht', models.IntegerField(blank=True, null=True)),
                ('loser_ioc', models.CharField(blank=True, max_length=255, null=True)),
                ('loser_age', models.DecimalField(blank=True, decimal_places=10, max_digits=15, null=True)),
                ('score', models.CharField(blank=True, max_length=255, null=True)),
                ('best_of', models.IntegerField(blank=True, null=True)),
                ('round', models.CharField(blank=True, max_length=255, null=True)),
                ('minutes', models.IntegerField(blank=True, null=True)),
                ('w_ace', models.IntegerField(blank=True, null=True)),
                ('w_df', models.IntegerField(blank=True, null=True)),
                ('w_svpt', models.IntegerField(blank=True, null=True)),
                ('w_1stIn', models.IntegerField(blank=True, null=True)),
                ('w_1stWon', models.IntegerField(blank=True, null=True)),
                ('w_2ndWon', models.IntegerField(blank=True, null=True)),
                ('w_SvGms', models.IntegerField(blank=True, null=True)),
                ('w_bpSaved', models.IntegerField(blank=True, null=True)),
                ('w_bpFaced', models.IntegerField(blank=True, null=True)),
                ('l_ace', models.IntegerField(blank=True, null=True)),
                ('l_df', models.IntegerField(blank=True, null=True)),
                ('l_svpt', models.IntegerField(blank=True, null=True)),
                ('l_1stIn', models.IntegerField(blank=True, null=True)),
                ('l_1stWon', models.IntegerField(blank=True, null=True)),
                ('l_2ndWon', models.IntegerField(blank=True, null=True)),
                ('l_SvGms', models.IntegerField(blank=True, null=True)),
                ('l_bpSaved', models.IntegerField(blank=True, null=True)),
                ('l_bpFaced', models.IntegerField(blank=True, null=True)),
                ('winner_rank', models.IntegerField(blank=True, null=True)),
                ('winner_rank_points', models.IntegerField(blank=True, null=True)),
                ('loser_rank', models.IntegerField(blank=True, null=True)),
                ('loser_rank_points', models.IntegerField(blank=True, null=True)),
                ('loser', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='losing_matches', to='tennis.Player')),
                ('winner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='winning_matches', to='tennis.Player')),
            ],
            options={
                'verbose_name': 'Match',
                'verbose_name_plural': 'Matches',
            },
        ),
        migrations.AddField(
            model_name='buildplayerprojection',
            name='build',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='projections', to='tennis.SlateBuild'),
        ),
        migrations.AddField(
            model_name='buildplayerprojection',
            name='slate_player',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='build_projection', to='tennis.SlatePlayer'),
        ),
        migrations.CreateModel(
            name='Alias',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dk_name', models.CharField(blank=True, max_length=255, null=True)),
                ('fd_name', models.CharField(blank=True, max_length=255, null=True)),
                ('pinn_name', models.CharField(blank=True, max_length=255, null=True)),
                ('player', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aliases', to='tennis.Player')),
            ],
            options={
                'verbose_name': 'Alias',
                'verbose_name_plural': 'Aliases',
            },
        ),
    ]
