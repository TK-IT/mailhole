"""mailhole URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import url
import django.views.static
from django.contrib import admin
import mailhole.views
from mailhole.models import Message

urlpatterns = [
    url(r'^admin/', admin.site.urls),

    url(r'^$', mailhole.views.MailboxList.as_view(), name='mailbox_list'),
    url(r'^login/$', mailhole.views.LoginView.as_view(), name='login'),
    url(r'^api/submit/$', mailhole.views.Submit.as_view(), name='submit'),
    url(r'^(?P<mailbox>[^/]+@[^/]+)/$',
        mailhole.views.MailboxDetail.as_view(), name='mailbox_detail'),
    url(r'^all/(?P<status>inbox|spam|trash)/$',
        mailhole.views.MessageList.as_view(), name='message_list'),
    url(r'^(?P<mailbox>[^/]+@[^/]+)/(?P<status>inbox|spam|trash)/$',
        mailhole.views.MailboxMessageList.as_view(), name='mailbox_message_list'),
    url(r'^(?P<mailbox>[^/]+@[^/]+)/(?P<pk>\d+)/$',
        mailhole.views.MessageDetail.as_view(), name='message_detail'),
]

if settings.DEBUG:
    # Temporary media (user uploaded static files)
    # serving from dev server
    urlpatterns.append(
        url(r'^uploads/(?P<path>.*)$',
            django.views.static.serve,
            {'document_root': settings.MEDIA_ROOT}))
