from celery import shared_task, chord, group, chain

from django.contrib import admin, messages
from django.shortcuts import redirect, get_object_or_404
from django.urls import path
from django.utils.html import mark_safe

from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter

from configuration.models import BackgroundTask
from . import models, tasks


class ContestPrizeInline(admin.TabularInline):
    model = models.ContestPrize


@admin.register(models.Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'cost',
        'num_entries',
        'num_iterations'
    )

    inlines = [
        ContestPrizeInline
    ]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.process_contest(request, obj)

    def process_contest(self, request, contest):
        tasks.process_contest.delay(
            contest.id,
            BackgroundTask.objects.create(
                name='Processing Contest',
                user=request.user
            ).id
        )
        messages.add_message(
            request,
            messages.WARNING,
            'Your contest is being processed. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once the contest is ready.')


@admin.register(models.ContestEntryPlayer)
class ContestEntryPlayerAdmin(admin.ModelAdmin):
    pass


@admin.register(models.ContestEntry)
class ContestEntryAdmin(admin.ModelAdmin):
    list_display = (
        'entry_name',
        'contest',
        'player_1',
        'player_2',
        'player_3',
        'player_4',
        'player_5',
        'player_6',
    )

    list_filter = [
        ('contest', RelatedDropdownFilter)
    ]

    search_fields = (
        'player_1__name',
        'player_2__name',
        'player_3__name',
        'player_4__name',
        'player_5__name',
        'player_6__name',
        'entry_name',
    )


@admin.register(models.ContestBacktest)
class ContestBacktestAdmin(admin.ModelAdmin):
    list_display = (
        'contest',
        'get_results_link',
        'run_button',
    )

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('backtest-run/<int:pk>/', self.run_backtest, name="admin_backtest_run"),
        ]
        return my_urls + urls

    def get_results_link(self, obj):
        if obj.entry_outcomes.all().count() > 0:
            return mark_safe('<a href="/admin/backtesting/contestbacktestentry/?backtest__id={}">Results</a>'.format(obj.id))
        return 'None'
    get_results_link.short_description = 'Results'

    def run_backtest(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        backtest = get_object_or_404(models.ContestBacktest, pk=pk)
        backtest.entry_outcomes.all().delete()
        
        tasks.start_contest_simulation.delay(
            backtest.id,
            BackgroundTask.objects.create(
                name='Simulate Contest ROI',
                user=request.user
            ).id
        )

        messages.add_message(
            request,
            messages.WARNING,
            f'Simulating ROI for {backtest}'
        )

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)


@admin.register(models.ContestBacktestEntry)
class ContestBacktestEntryAdmin(admin.ModelAdmin):
    list_display = (
        'entry',
        'get_amount_won',
        'get_roi',
        'get_lineup',
        'get_dup_count',
    )
    raw_id_fields = (
        'backtest',
        'entry',
    )
    search_fields = (
        'entry__entry_name',
    )

    def get_amount_won(self, obj):
        return '${:.2f}'.format(obj.amount_won)
    get_amount_won.short_description = 'amount_won'
    get_amount_won.admin_order_field = 'amount_won'

    def get_roi(self, obj):
        return '{:.2f}%'.format(obj.roi * 100)
    get_roi.short_description = 'roi'
    get_roi.admin_order_field = 'roi'

    def get_lineup(self, obj):
        return f'{obj.entry.lineup_str}'
    get_lineup.short_description = 'lineup'

    def get_dup_count(self, obj):
        lineup_str = obj.entry.lineup_str
        return models.ContestEntry.objects.filter(contest=obj.backtest.contest, lineup_str=lineup_str).count()
    get_dup_count.short_description = 'dup'
