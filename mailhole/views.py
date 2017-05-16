from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.http import (
    HttpResponseBadRequest, HttpResponse, HttpResponseNotFound,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, FormView
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import AccessMixin

from mailhole.models import (
    Mailbox, Message, SentMessage,
)
from mailhole.forms import (
    AuthenticationForm, SubmitForm, MessageListForm, MessageDetailForm,
)


class MailboxRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.mailboxes = list(request.user.mailbox_set.all())
        if not self.mailboxes and not request.user.is_superuser:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class SingleMailboxRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.is_superuser:
            qs = Mailbox.objects.all()
        else:
            qs = request.user.mailbox_set.all()
        try:
            self.mailbox = qs.get(email=kwargs['mailbox'])
        except Mailbox.DoesNotExist:
            return HttpResponseNotFound()
        return super().dispatch(request, *args, **kwargs)


class MailboxList(MailboxRequiredMixin, TemplateView):
    template_name = 'mailhole/mailbox_list.html'

    def get(self, request, *args, **kwargs):
        # TODO make self.mailboxes available in dispatch
        if len(self.mailboxes) == 1:
            mailbox, = self.mailboxes
            return redirect('mailbox_message_list', mailbox=mailbox.email,
                            status=Message.INBOX)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['object_list'] = self.mailboxes
        return context_data


class MailboxDetail(SingleMailboxRequiredMixin, TemplateView):
    template_name = 'mailhole/mailbox_detail.html'

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data['mailbox'] = self.mailbox
        return context_data


class MailboxMessageList(SingleMailboxRequiredMixin, FormView):
    template_name = 'mailhole/message_list.html'
    form_class = MessageListForm

    def get_queryset(self):
        return self.mailbox.message_set.filter(status=self.kwargs['status'])

    def get_form_kwargs(self, **kwargs):
        kwargs = super().get_form_kwargs(**kwargs)
        kwargs['queryset'] = self.get_queryset()
        return kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        form = context_data['form']
        context_data['mailbox'] = self.mailbox
        context_data['status'] = Message.status_display(self.kwargs['status'])
        context_data['inbox'] = self.kwargs['status'] == Message.INBOX
        context_data['object_list'] = form.messages
        return context_data

    def form_valid(self, form):
        form.save(self.request.user)
        return redirect(self.request.path)


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
        return dict(recipient=self.get_object().rcpt_to)

    def form_valid(self, form):
        fresh_form = MessageDetailForm()
        message = self.get_object()
        if form.cleaned_data['send']:
            recipient = form.cleaned_data['recipient']
            SentMessage.create_and_send(message=message,
                                        user=self.request.user,
                                        recipient=recipient)
            return self.render_to_response(
                self.get_context_data(sent=True, form=fresh_form))

        return_to = message.status
        if form.cleaned_data['trash']:
            message.status = Message.TRASH
            message.save()
            return redirect('mailbox_message_list', mailbox=self.mailbox.email,
                            status=return_to)
        if form.cleaned_data['spam']:
            message.status = Message.SPAM
            message.save()
            return redirect('mailbox_message_list', mailbox=self.mailbox.email,
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
        return HttpResponseBadRequest(form.errors.as_json())

    def form_valid(self, form):
        try:
            form.cleaned_data['message_bytes'].open('rb')
            message_bytes = form.cleaned_data['message_bytes'].read()
            Message.create(peer=form.cleaned_data['peer'],
                           mail_from=form.cleaned_data['mail_from'],
                           rcpt_to=form.cleaned_data['rcpt_to'],
                           message_bytes=message_bytes)
        except ValidationError as exn:
            form.add_error(exn)
            return self.form_invalid(form)
        return HttpResponse('250 OK')
