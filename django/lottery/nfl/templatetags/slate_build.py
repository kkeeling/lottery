from django import template
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def rb_matrix(build):
    html = '''
        <div class="table">
            <div class="row">
                <div class="cell">&nbsp;</div>
                <div class="cell">Salary</div>
                <div class="cell">Projection</div>
                <div class="cell">Opportunity</div>
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
                <div class="cell">{}</div>
                <div class="cell">{:.2f}</div>
                <div class="cell">{:.2f}</div>
        '''.format(player.name, player.salary, player.projection, player.adjusted_opportunity)

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
