from django import template
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def to_percent(obj, sigdigits):
    if obj:
        return "{0:.{sigdigits}%}".format(obj, sigdigits=sigdigits)
    else: return obj


@register.simple_tag
def rb_matrix(build):
    html = '''
        <div class="table">
            <div class="row">
                <div class="cell">&nbsp;</div>
                <div class="cell value">Salary</div>
                <div class="cell value">Projection</div>
                <div class="cell value">Opportunity</div>
                <div class="cell value">OP</div>
                <div class="cell value">Exposure</div>
    '''

    for player in build.projections.filter(slate_player__site_pos='RB', in_play=True):
        html += '''
                <div class="cell">{}</div>
        '''.format(player.name)
            
    html += '''
            </div>
    '''

    for player in build.projections.filter(slate_player__site_pos='RB', in_play=True):
        html += '''
            <div class="row">
                <div class="cell">{}</div>
                <div class="cell value">{}</div>
                <div class="cell value">{:.2f}</div>
                <div class="cell value">{:.2f}</div>
                <div class="cell value">{:.2f}%</div>
                <div class="cell value">{:.2f}%</div>
        '''.format(player.name, player.salary, player.projection, player.adjusted_opportunity, player.ownership_projection * 100, player.exposure * 100)

        for player2 in build.projections.filter(slate_player__site_pos='RB', in_play=True):
            html += '''
                <div class="cell">{:.2f}%</div>
            '''.format(player.compare(player2) * 100)
        
        html += '''
            </div>
        '''

    html += '''
        </div>
    '''

    return mark_safe(html)
