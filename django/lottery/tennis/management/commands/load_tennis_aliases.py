import csv
import traceback

from django.core.management.base import BaseCommand

from tennis import models


class Command(BaseCommand):
    help = 'Import Aliases'

    def add_arguments(self, parser):
        parser.add_argument(
            '--alias-file',
            action='store',
            dest='alias_file',
            default=None,
        )

    def handle(self, *args, **options):
        alias_file = options.get('alias_file')
        print(alias_file)

        if alias_file is None:
            print('You must pass in a file to parse using --alias-file flag')
            return
        
        with open(alias_file, mode='r') as alias_csv:
            csv_reader = csv.reader(alias_csv, delimiter=',')
            missing_players = []
            row_count = 0

            for row in csv_reader:
                if row_count > 0:
                    full_name= row[1]
                    name_arr = full_name.split(" ", 1)
                    first = name_arr[0]
                    last = name_arr[1] if len(name_arr) > 1 else ""

                    (alias, created) = models.Alias.objects.get_or_create(
                        dk_name=row[0]
                    )
                    alias.fd_name=row[0]
                    alias.pinn_name=row[2]

                    try:
                        player = models.Player.objects.get(
                            first_name=first,
                            last_name=last
                        )
                        alias.player = player
                    except models.Player.DoesNotExist:
                        missing_players.append(full_name)

                    alias.save()
                    print(alias)

                row_count += 1
        
            print('Added {} aliases'.format(row_count))

        if len(missing_players) > 0:
            print()
            print('Missing players:')
            for p in missing_players:
                print(p)

