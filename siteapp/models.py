from django.db import models, transaction
from django.utils import timezone
from django.conf import settings

from jsonfield import JSONField

from .betteruser import UserBase, UserManagerBase
from questions import Module


class UserManager(UserManagerBase):
    def _get_user_class(self):
        return User

class User(UserBase):
    objects = UserManager()

    def __str__(self):
        from guidedmodules.models import TaskAnswer
        name = TaskAnswer.objects.filter(
            question__task=self.get_settings_task(),
            question__question_id="name").first()
        if name:
            return name.value #+ " <" + self.email + ">"
        else:
            return self.email

    def get_settings_task(self):
        from guidedmodules.models import Task
        return Task.objects.filter(
            editor=self,
            project=None,
            module_id="account_settings").first()

    def render_context_dict(self):
        return {
            "id": self.id,
            "name": str(self),
        }

class Project(models.Model):
    title = models.CharField(max_length=256, help_text="The title of this Project.")
    notes = models.TextField(blank=True, help_text="Notes about this Project for Project members.")

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)
    extra = JSONField(blank=True, help_text="Additional information stored with this object.")

    def __str__(self):
        # For the admin.
        return self.title + " [" + self.get_owner_domains() + "]"

    def __repr__(self):
        # For debugging.
        return "<Project %d %s>" % (self.id, self.title[0:30])

    def get_absolute_url(self):
        from django.utils.text import slugify
        return "/tasks/projects/%d/%s" % (self.id, slugify(self.title))

    def get_owner_domains(self):
        # Utility function for the admin/debugging to quickly see the domain
        # names in the email addresses of the admins of this project.
        return ", ".join(sorted(m.user.email.split("@", 1)[1] for m in ProjectMembership.objects.filter(project=self, is_admin=True)))

class ProjectMembership(models.Model):
    project = models.ForeignKey(Project, related_name="members", help_text="The Project this is defining membership for.")
    user = models.ForeignKey(User, help_text="The user that is a member of the Project.")
    is_admin = models.BooleanField(default=False, help_text="Is the user an administrator of the Project?")
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        unique_together = [('project', 'user')]


class Invitation(models.Model):
    # who is sending the invitation
    from_user = models.ForeignKey(User, related_name="invitations_sent", help_text="The User who sent the invitation.")
    from_project = models.ForeignKey(Project, related_name="invitations_sent", help_text="The Project within which the invitation exists.")
    
    # about what prompted the invitation
    prompt_task = models.ForeignKey('guidedmodules.Task', blank=True, null=True, related_name="invitations_prompted", help_text="The Task that prompted the invitation.")
    prompt_question_id = models.CharField(max_length=64, blank=True, null=True, help_text="The ID of the question that prompted the invitation.")

    # what is the recipient being invited to?
    into_project = models.BooleanField(default=False, help_text="Whether the user being invited is being invited to join from_project.")
    into_new_task_module_id = models.CharField(max_length=128, blank=True, null=True, help_text="The ID of the module that the recipient is being asked to complete, if any.")
    into_task_editorship = models.ForeignKey('guidedmodules.Task', blank=True, null=True, related_name="invitations_to_take_over", help_text="The Task that the recipient is being invited to take editorship over, if any.")
    into_discussion = models.ForeignKey('guidedmodules.Discussion', blank=True, null=True, related_name="invitations", help_text="The Discussion that the recipient is being invited to join, if any.")

    # who is the recipient of the invitation?
    to_user = models.ForeignKey(User, related_name="invitations_received", blank=True, null=True, help_text="The user who the invitation was sent to, if to an existing user.")
    to_email = models.CharField(max_length=256, blank=True, null=True, help_text="The email address the invitation was sent to, if to a non-existing user.")

    # personalization
    text = models.TextField(blank=True, help_text="The personalized text of the invitation.")

    # what state is this invitation in?
    sent_at = models.DateTimeField(blank=True, null=True, help_text="If the invitation has been sent by email, when it was sent.")
    accepted_at = models.DateTimeField(blank=True, null=True, help_text="If the invitation has been accepted, when it was accepted.")
    revoked_at = models.DateTimeField(blank=True, null=True, help_text="If the invitation has been revoked, when it was revoked.")

    # what resulted from this invitation?
    accepted_user = models.ForeignKey(User, related_name="invitations_accepted", blank=True, null=True, help_text="The user that accepted the invitation (i.e. if the invitation was by email address and an account was created).")
    accepted_task = models.ForeignKey('guidedmodules.Task', related_name="invitations_received", blank=True, null=True, help_text="The Task generated by accepting the invitation.")

    # random string to generate unique code for recipient
    email_invitation_code = models.CharField(max_length=64, blank=True, help_text="For emails, a unique verification code.")

    # bookkeeping
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)
    extra = JSONField(blank=True, help_text="Additional information stored with this object.")

    @staticmethod
    def generate_email_invitation_code():
        import random, string
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(24))

    @staticmethod
    def form_context_dict(user, project):
        from guidedmodules.models import ProjectMembership
        return {
            "project_id": project.id,
            "project_title": project.title,
            "users": [{ "id": pm.user.id, "name": str(pm.user) } for pm in ProjectMembership.objects.filter(project=project).exclude(user=user)],
        }

    def to_display(self):
        return str(self.to_user) if self.to_user else self.to_email

    def purpose(self):
        if self.into_new_task_module_id:
            return ("to edit a new module <%s>" % Module.load(self.into_new_task_module_id).title) \
                + (" and to join the project team" if self.into_project else "")
        elif self.into_task_editorship:
            return ("to take over editing <%s>" % self.into_task_editorship.title) \
                + (" and to join the project team" if self.into_project else "")
        elif self.into_discussion:
            return ("to join the discussion <%s>" % self.into_discussion.title) \
                + (" and to join the project team" if self.into_project else "")
        elif self.into_project:
            return "to join this project team"
        else:
            raise Exception()

    def get_acceptance_url(self):
        from django.core.urlresolvers import reverse
        return settings.SITE_ROOT_URL \
            + reverse('accept_invitation', kwargs={'code': self.email_invitation_code})

    @property
    def into_new_task_module_title(self):
        return Module.load(self.into_new_task_module_id).title

    def send(self):
        # Send and mark as sent.
        from htmlemailer import send_mail
        send_mail(
            "email/invitation",
            "GovReady Q <q@mg.govready.com>",
            [self.to_user.email if self.to_user else self.to_email],
            {
                'invitation': self,
            }
        )
        Invitation.objects.filter(id=self.id).update(sent_at=timezone.now())

    def is_expired(self):
        from datetime import timedelta
        return self.sent_at and timezone.now() > (self.sent_at + timedelta(days=10))
    is_expired.boolean = True

    def get_redirect_url(self):
        if self.accepted_task:
            return self.accepted_task.get_absolute_url() + "/start"
        elif self.into_task_editorship:
            return self.into_task_editorship.get_absolute_url() + "/start"
        elif self.into_discussion:
            return self.into_discussion.for_question.get_absolute_url()
        else:
            return "/"

