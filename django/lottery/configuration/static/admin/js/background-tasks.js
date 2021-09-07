(function($) {
  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
  }

  function getMessages() {
    var $messages = $(".messagelist");
    if ($messages.length == 0) {
      $messages = $('<ul class="messagelist"></ul>')
      $("#content").before($messages);
    }
    return $messages;
  }

  function fetchBackgroundTasks() {
    $.getJSON('/api/backgroundtask/')
    .done(function(tasks) {
      tryAgain = false
      if (tasks.count > 0) {
        if ($('#busy').length == 0) {
          $('#user-tools').prepend('<img id="busy" src="/static/admin/media/busy.gif" alt="busy background task" style="width:25px;margin:0px 5px -10px 0px;"/>');
        }
        tasks.results.forEach(function(task) {
          if (task.status !== 'processing') {
            if (task.status === 'download') {
              $messages = getMessages()
              $message = $('<li class="success">Your file is ready and has automatically started downloading. If it hasn\'t, click <a href="'+task.content+'" download>here</a>.</li>');
              $messages.append($message);
              $message.hide();
              $message.slideDown();

              var link = document.createElement("a");
              link.download = '';
              link.href = task.content;
              link.click();
              link.remove();
            } else {
              $messages = getMessages()
              if (task.link == null) {
                $message = $('<li class="' + task.status + '">' + task.content + '</li>');
              } else {
                $message = $('<li class="' + task.status + '">' + task.content + ' <a target="_blank" href="' + task.link + '">Review here</a>.</li>');
              }
              $messages.append($message);
              $message.hide();
              $message.slideDown();
            }

            $.ajax({
              url: '/api/backgroundtask/' + task.id + '/',
              type: 'DELETE',
            });
          } else {
            tryAgain = true;
          }
        });
        
        if (tryAgain) {
          setTimeout(fetchBackgroundTasks, 2000);
        } else {
          $('#busy').remove();
        }
      } else {
        $('#busy').remove();
      }
    });
  }
  function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
  }

  var csrftoken = getCookie('csrftoken');
  $.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
    }
  });

  fetchBackgroundTasks();
})(jQuery);