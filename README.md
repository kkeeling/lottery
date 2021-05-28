# lottery - Docker Edition (Reef)

What you need to have to develop:
- Docker
- Docker Compose
- Python 3 (available as python3)

First, setup the tools:
```
./tools.sh bootstrap
```

Then, you can start your local setup like this:
```
./tools.sh start
```

In another shell you'll need to get into the django app container and make a super user:
```
./tools.sh dev django shell
./manage.py createsuperuser
```

You'll now be able to login at http://localhost:8000/admin/

To log into Grafana go to http://localhost:3000/

Initial username/password is admin/admin and you'll want to add a Postgres
datasource. The info for the datasource is:
```
Host: db:5432
Database: lottery
User: lottery
Password: lottery
SSL mode: disable
```

If you ever need to recreate the local containers:
```
./tools.sh cleanstart
```

To deploy:
```
./tools.sh production deploy
```

Note that production (host tbd) pulls from the production branch.

To ssh into specific containers on specific machines:
```
./tools.sh dev app shell
./tools.sh production redis shell
```
etc.

General notes about how things work:
The tools.sh shell script is mostly a pass-through to python scripts made using the Invoke and Fabric libraries. The bootstrap command to the tools.sh script just setups a virtualenv and installs Invoke and Fabric there. All other commands pass through to the tasks defined in tasks.py in the tools folder.

The servers were setup with Ubuntu 18.04, Docker and Docker Compose. Docker was installed via instructions from Digital Ocean and Docker Compose directly from its website.

The data directory is used specifically to pass data into the django and database containers. Contents of the directory are ignored by git.