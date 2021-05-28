import subprocess

from fabric import Connection
from invoke import task, run


@task
def cleanstart(ctx):
    run('docker-compose -p lottery -f ../compose/dev.yml down')
    run('docker-compose -p lottery -f ../compose/dev.yml kill')
    run('docker-compose -p lottery -f ../compose/dev.yml rm -v --force')
    run('docker-compose -p lottery -f ../compose/dev.yml up --build --force-recreate')

@task
def start(ctx):
    if 'container' in ctx.config:
        run('docker-compose -p lottery -f ../compose/dev.yml up {}'.format(ctx.config.container))
    else:
        run('docker-compose -p lottery -f ../compose/dev.yml up')

@task
def stop(ctx):
    run('docker container stop lottery_dev_django')
    run('docker container stop lottery_dev_db')
    run('docker container stop lottery_dev_celery')
    run('docker container stop lottery_dev_redis')
    run('docker container stop lottery_dev_grafana')


@task
def dev(ctx):
    ctx.config.runner = run
    ctx.config.target = 'dev'
    ctx.config.path = 'lottery'
    ctx.config.containers = {
        'django': 'lottery_dev_django',
        'db': 'lottery_dev_db',
        'redis': 'lottery_dev_redis',
        'celery': 'lottery_dev_celery',
        'grafana': 'lottery_dev_grafana',
    }

@task
def production(ctx):
    ctx.config.target = 'production'
    ctx.config.host = '167.99.234.248'  # change this to new server
    ctx.config.user = 'lottery'
    ctx.config.connection = Connection(host=ctx.config.host, user=ctx.config.user)
    ctx.config.runner = ctx.config.connection.run
    ctx.config.path = 'lottery-docker'
    ctx.config.containers = {
        'django': 'lottery_production_django',
        'db': 'lottery_production_db',
        'redis': 'lottery_production_redis',
        'celery': 'lottery_production_celery',
        'nginx': 'lottery_production_nginx',
        'grafana': 'lottery_production_grafana',
    }

@task
def django(ctx):
    ctx.config.container = 'django'

@task
def db(ctx):
    ctx.config.container = 'db'

@task
def redis(ctx):
    ctx.config.container = 'redis'

@task
def celery(ctx):
    ctx.config.container = 'celery'

@task
def nginx(ctx):
    ctx.config.container = 'nginx'

@task
def rebuild(ctx):
    if ctx.config.path:
        with ctx.config.connection.cd(ctx.config.path):
            ctx.config.runner('git pull')
            ctx.config.runner('docker-compose -p lottery -f compose/{}.yml down'.format(ctx.config.target))
            ctx.config.runner('docker-compose -p lottery -f compose/{}.yml build --no-cache'.format(ctx.config.target))
            ctx.config.runner('docker-compose -p lottery -f compose/{}.yml up -d'.format(ctx.config.target))
    else:
        print('Can not rebuild local')

@task
def deploy(ctx):
    if ctx.config.path:
        with ctx.config.connection.cd(ctx.config.path):
            ctx.config.runner('git pull')
            ctx.config.runner('docker-compose -p lottery -f compose/{}.yml down'.format(ctx.config.target))
            ctx.config.runner('docker-compose -p lottery -f compose/{}.yml up -d'.format(ctx.config.target))
    else:
        print('Can not deploy local')

@task
def shell(ctx):
    if not hasattr(ctx.config, 'container'):
        subprocess.call(['ssh {}@{}'.format(ctx.config.user, ctx.config.host)], shell=True)
    else:
        container = ctx.config.containers[ctx.config.container]
        if hasattr(ctx.config, 'user') and hasattr(ctx.config, 'host'):
            subprocess.call(["ssh -t {}@{} 'docker exec -e TERM=xterm-256color -it {} /bin/bash'".format(
                ctx.config.user,
                ctx.config.host,
                container)], shell=True)
        else:
            subprocess.call(["docker exec -e TERM=xterm-256color -it {} /bin/bash".format(container)], shell=True)        

@task
def logs(ctx):
    if not hasattr(ctx.config, 'container'):
        print('Must target a container')
    else:
        container = ctx.config.containers[ctx.config.container]
        ctx.config.runner('docker logs {} -f --tail 50'.format(container), pty=True)


@task
def restart(ctx):
    if not hasattr(ctx.config, 'container'):
        print('Must target a container')
    else:
        container = ctx.config.containers[ctx.config.container]
        ctx.config.runner('docker restart {}'.format(container), pty=True)