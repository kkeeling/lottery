# Generated by Django 2.2 on 2022-01-06 16:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0002_auto_20220106_1114'),
    ]

    operations = [
        migrations.AddField(
            model_name='slate',
            name='salaries',
            field=models.FileField(blank=True, null=True, upload_to='uploads/salaries'),
        ),
        migrations.DeleteModel(
            name='SlatePlayerImportSheet',
        ),
    ]
