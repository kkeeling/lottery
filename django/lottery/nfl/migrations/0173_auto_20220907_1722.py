# Generated by Django 2.2 on 2022-09-07 17:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0172_auto_20220907_1621'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slateplayerprojection',
            name='floor',
            field=models.FloatField(db_index=True, default=0.0),
        ),
    ]