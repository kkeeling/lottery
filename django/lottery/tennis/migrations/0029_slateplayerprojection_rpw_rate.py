# Generated by Django 2.2 on 2022-02-08 07:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0028_auto_20220208_0633'),
    ]

    operations = [
        migrations.AddField(
            model_name='slateplayerprojection',
            name='rpw_rate',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=5),
        ),
    ]