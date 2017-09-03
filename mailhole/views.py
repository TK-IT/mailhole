import logging

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.conf import settings
from django.utils.decorators import method_decorator
from django.http import (
    HttpResponseBadRequest, HttpResponse, HttpResponseNotFound,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    TemplateView, FormView, View, UpdateView,
)
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import AccessMixin

from mailhole.models import (
    Mailbox, Message, SentMessage,
)
from mailhole.forms import (
    AuthenticationForm, SubmitForm, MessageListForm, MessageDetailForm,
)


logger = logging.getLogger('mailhole')


class MailboxRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.mailboxes = list(Mailbox.owned_by_user(request.user))
        if not self.mailboxes and not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class SingleMailboxRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        qs = Mailbox.visible_to_user(request.user)
        try:
            self.mailbox = qs.get(name=kwargs['mailbox'])
        except Mailbox.DoesNotExist:
            return HttpResponseNotFound()
        return super().dispatch(request, *args, **kwargs)


class SuperuserRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class MailboxList(MailboxRequiredMixin, TemplateView):
    template_name = 'mailhole/mailbox_list.html'

    def get(self, request, *args, **kwargs):
        # TODO make self.mailboxes available in dispatch
        if len(self.mailboxes) == 1:
            mailbox, = self.mailboxes
            return redirect('mailbox_message_list', mailbox=mailbox.name,
                            status=Message.INBOX)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['object_list'] = self.mailboxes
        context_data['all_folders'] = [
            (key, label, reverse('message_list', kwargs=dict(status=key)),
             Message.objects.filter(mailbox__in=self.mailboxes,
                                    status=key))
            for key, label in Message.STATUS
        ]
        return context_data


class MailboxDetail(SingleMailboxRequiredMixin, TemplateView):
    template_name = 'mailhole/mailbox_detail.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['mailbox'] = self.mailbox
        return context_data


class MessageListBase(FormView):
    template_name = 'mailhole/message_list.html'
    form_class = MessageListForm

    def get_queryset(self):
        raise NotImplementedError

    def get_form_kwargs(self, **kwargs):
        kwargs = super().get_form_kwargs(**kwargs)
        kwargs['queryset'] = self.get_queryset()
        return kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        form = context_data['form']
        context_data['status'] = Message.status_display(self.kwargs['status'])
        context_data['inbox'] = self.kwargs['status'] == Message.INBOX
        context_data['object_list'] = form.messages
        return context_data

    def form_valid(self, form):
        # form.save logs the action(s)
        form.save(self.request.user)
        return redirect(self.request.path)


class MessageList(MailboxRequiredMixin, MessageListBase):
    def get_queryset(self):
        return Message.objects.filter(status=self.kwargs['status'],
                                      mailbox__in=self.mailboxes)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['all'] = True
        return context_data


class MailboxMessageList(SingleMailboxRequiredMixin, MessageListBase):
    def get_queryset(self):
        return self.mailbox.message_set.filter(status=self.kwargs['status'])

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['mailbox'] = self.mailbox
        return context_data


class MessageDetail(SingleMailboxRequiredMixin, FormView):
    form_class = MessageDetailForm
    template_name = 'mailhole/message_detail.html'

    def get_object(self):
        return get_object_or_404(
            self.mailbox.message_set, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['mailbox'] = self.mailbox
        context_data['message'] = self.get_object()
        return context_data

    def get_initial(self):
        return dict(recipient=self.get_object().recipients()[0])

    def form_valid(self, form):
        user = self.request.user
        fresh_form = MessageDetailForm()
        message = self.get_object()
        if form.cleaned_data['send']:
            # SentMessage.create_and_send logs the action
            recipient = form.cleaned_data['recipient']
            SentMessage.create_and_send(message=message,
                                        user=user,
                                        recipient=recipient)
            return self.render_to_response(
                self.get_context_data(sent=True, form=fresh_form))

        return_to = message.status
        if form.cleaned_data['trash']:
            logger.info('user:%s (%s) message:%s marked trash',
                        user.pk, user.username, message.pk)
            message.set_status(Message.TRASH, user=user)
            message.save()
            return redirect('mailbox_message_list', mailbox=self.mailbox.name,
                            status=return_to)
        if form.cleaned_data['spam']:
            logger.info('user:%s (%s) message:%s marked spam',
                        user.pk, user.username, message.pk)
            message.set_status(Message.SPAM, user=user)
            message.save()
            return redirect('mailbox_message_list', mailbox=self.mailbox.name,
                            status=return_to)
        return HttpResponseBadRequest(
            'Du skal trykke enten Send, Trash eller Spam')


class LoginView(auth_views.LoginView):
    template_name = 'mailhole/login.html'
    form_class = AuthenticationForm


class Submit(FormView):
    form_class = SubmitForm

    def get(self, request, *args, **kwargs):
        return HttpResponseBadRequest()

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        json_errors = form.errors.as_json()
        logger.warning('Submit.form_invalid(): %s', json_errors)
        return HttpResponseBadRequest(json_errors)

    def form_valid(self, form):
        try:
            # form.save() logs the action
            messages = form.save()
        except ValidationError as exn:
            # form_invalid logs the error
            form.add_error(None, exn)
            return self.form_invalid(form)
        for message in messages:
            message.filter_incoming()
        return HttpResponse('250 OK')


class Log(SuperuserRequiredMixin, View):
    def get(self, request):
        filename = settings.LOGGING['handlers']['file']['filename']
        with open(filename, encoding='utf8') as fp:
            s = fp.read()
        return HttpResponse(s, content_type='text/plain; charset=utf8')


class DefaultActionUpdate(SingleMailboxRequiredMixin, UpdateView):
    template_name = 'mailhole/default_action_update.html'
    model = Mailbox
    fields = ('default_action',)

    def get_object(self):
        return self.mailbox

    def get_success_url(self):
        return reverse('mailbox_list')
