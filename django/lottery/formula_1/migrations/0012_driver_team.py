# Generated by Django 2.2 on 2022-03-18 14:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('formula_1', '0011_auto_20220318_1407'),
    ]

    operations = [
        migrations.AddField(
            model_name='driver',
            name='team',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='drivers', to='formula_1.Constructor'),
        ),
    ]
