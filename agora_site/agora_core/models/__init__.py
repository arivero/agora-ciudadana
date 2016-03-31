import datetime
import unicodedata

from django.core.urlresolvers import reverse
from django.core.mail import (EmailMultiAlternatives, EmailMessage,
                              send_mass_mail)
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils import translation
from django.utils import simplejson as json
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import get_object_or_404

from userena.models import UserenaLanguageBaseProfile
from userena.utils import get_gravatar
from userena import settings as userena_settings
from guardian.shortcuts import *

from actstream.actions import follow, is_following
from actstream.signals import action

from agora_site.misc.utils import (JSONField, geolocate_ip, send_action,
                                   get_base_email_context)
from agora import Agora
from election import Election
from castvote import CastVote
from delegateelectioncount import DelegateElectionCount


class Profile(UserenaLanguageBaseProfile):
    '''
    Profile used together with django User class, and accessible via
    user.get_profile(), because  in settings we have configured:

    AUTH_PROFILE_MODULE = 'agora_site.agora_core.models.Profile'

    See https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-AUTH_PROFILE_MODULE
    for more details.
    '''
    user = models.OneToOneField(User)

    class Meta:
        app_label = 'agora_core'

    def get_fullname(self):
        '''
        Returns the full user name
        '''
        if self.user.last_name:
            return self.user.first_name + ' ' + self.user.last_name
        else:
            return self.user.first_name

    def get_initials(self):
        '''
        Returns the initials of the profile
        '''
        base_text = self.get_fullname().strip()
        initials = u""
        for word in base_text.split(" "):
            word = word.strip()
            if not word:
                continue
            initials += word[0].upper()
        return unicodedata.normalize('NFKD', initials).encode('ascii','ignore')

    def delete_mugshot(self):
        if self.mugshot.name in ['gravatar', 'initials', '']:
            self.mugshot.name = ""
            return
        self.mugshot.delete()

    def get_initials_mugshot(self, custom_size = userena_settings.USERENA_MUGSHOT_SIZE):
        if userena_settings.USERENA_MUGSHOT_DEFAULT == 'blank-unitials-ssl':
            return 'https://unitials.com/mugshot/%s/%s.png' % (
                custom_size, self.get_initials()
            )
        elif userena_settings.USERENA_MUGSHOT_DEFAULT == 'blank-unitials':
            return 'http://unitials.com/mugshot/%s/%s.png' % (
                custom_size, self.get_initials()
            )

    def get_gravatar_mugshot(self, custom_size = userena_settings.USERENA_MUGSHOT_SIZE):
        d = self.get_initials_mugshot(custom_size)
        return get_gravatar(self.user.email, custom_size, d)

    def get_big_mugshot(self):
        return self.get_mugshot_url(170)

    def add_to_agora(self, request=None, agora_name=None, agora_id=None):
        '''
        Add the user to the specified agora. The agora is specified by its full
        name or id, for example agora_name="username/agoraname" or agora_id=3.
        '''

        if agora_name:
            username, agoraname = agora_name.split("/")
            agora = get_object_or_404(Agora, name=agoraname,
                creator__username=username)
            agora.members.add(self.user)
            agora.save()
        else:
            agora = get_object_or_404(Agora, pk=agora_id)
            agora.members.add(self.user)
            agora.save()

        send_action(self.user, verb='joined', action_object=agora, request=request)

        if not is_following(self.user, agora):
            follow(self.user, agora, actor_only=False, request=request)

        # Mail to the user
        if not self.has_perms('receive_email_updates'):
            return

        translation.activate(self.user.get_profile().lang_code)
        context = get_base_email_context(request)
        context.update(dict(
            agora=agora,
            other_user=self.user,
            notification_text=_('You just joined %(agora)s. '
                'Congratulations!') % dict(agora=agora.get_full_name()),
            to=self.user
        ))

        email = EmailMultiAlternatives(
            subject=_('%(site)s - you are now member of %(agora)s') % dict(
                        site=Site.objects.get_current().domain,
                        agora=agora.get_full_name()
                    ),
            body=render_to_string('agora_core/emails/agora_notification.txt',
                context),
            to=[self.user.email])

        email.attach_alternative(
            render_to_string('agora_core/emails/agora_notification.html',
                context), "text/html")
        email.send()
        translation.deactivate()

    def get_mugshot_url(self, custom_size = userena_settings.USERENA_MUGSHOT_SIZE):
        """
        Returns the image containing the mugshot for the user.

        The mugshot can be a uploaded image or a Gravatar.

        Gravatar functionality will only be used when
        ``USERENA_MUGSHOT_GRAVATAR`` is set to ``True``.

        :return:
            ``None`` when Gravatar is not used and no default image is supplied
            by ``USERENA_MUGSHOT_DEFAULT``.

        """
        # First check for a mugshot and if any return that.
        if self.mugshot.name == "gravatar":
            return self.get_gravatar_mugshot(custom_size)
        elif self.mugshot.name == "initials":
            return self.get_initials_mugshot(custom_size)
        elif self.mugshot:
            return settings.MEDIA_URL +\
                   settings.MUGSHOTS_DIR +\
                   self.mugshot.name.split("/")[-1]

        # Use Gravatar if the user wants to.
        if userena_settings.USERENA_MUGSHOT_GRAVATAR:
            return self.get_gravatar_mugshot(custom_size)

        # Gravatar not used, check for a default image.
        else:
            if userena_settings.USERENA_MUGSHOT_DEFAULT not in ['404', 'mm',
                'identicon', 'monsterid', 'wavatar', 'blank']:
                return userena_settings.USERENA_MUGSHOT_DEFAULT
            else:
                return None


    def get_short_description(self):
        '''
        Returns a short description of the user
        '''
        if self.short_description:
            return self.short_description
        else:
            return _('Is a member of %(num_agoras)d agoras and has emitted '
                ' %(num_votes)d direct votes.') % dict(
                    num_agoras=self.user.agoras.count(),
                    num_votes=self.count_direct_votes())

    def get_first_name_or_nick(self):
        if self.user.first_name:
            return self.user.first_name
        else:
            return self.user.username

    def has_perms(self, permission_name, user=None):
        '''
        Return whether a given user has a given permission name
        '''
        isanon = user and user.is_anonymous()

        if permission_name == 'receive_email_updates':
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                validate_email(self.user.email)
            except ValidationError:
                return False
            return self.email_updates 
        elif permission_name == 'receive_mail':
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            if user.is_anonymous():
                return False
            # only admins of the agora the user is in can send the user an email
            if not user.administrated_agoras.only('id').filter(
                    id__in=self.user.agoras.only('id').all().query).exists():
                return False
            try:
                validate_email(self.user.email)
            except ValidationError:
                return False
            return not isanon
        else:
            return False

    def get_perms(self, user):
        '''
        Returns a list of permissions for a given user calling to self.has_perms()
        '''
        return [perm for perm in ('receive_email_updates', 'receive_mail')
                if self.has_perms(perm, user)]

    short_description = models.CharField(_('Short Description'), max_length=140)

    biography = models.TextField(_('Biography'))

    # This marks the date of the last activity item known to be read by the user
    # so that later on we can for example send to the user update email only
    # showing activity from this date on
    last_activity_read_date = models.DateTimeField(_(u'Last Activity Read Date'), auto_now_add=True, editable=True)

    # Saving the user language allows sending emails to him in his desired
    # language (among other things)
    lang_code = models.CharField(_("Language Code"), max_length=10, default='')

    email_updates = models.BooleanField(_("Receive email updates"),
        default=True)

    # Stores extra data
    extra = JSONField(_('Extra'), null=True)

    def get_open_elections(self, searchquery = None):
        '''
        Returns the list of current and future elections that will or are
        taking place in our agoras.
        '''
        elections = Election.objects.filter(
            Q(voting_extended_until_date__gt=timezone.now()) |
            Q(voting_extended_until_date=None, voting_starts_at_date__lt=timezone.now()),
            Q(is_approved=True, agora__in=self.user.agoras.all())).filter(archived_at_date=None)

        if searchquery and len(searchquery) > 1:
            elections = elections.filter(pretty_name__icontains=searchquery)

        return elections.order_by('-voting_extended_until_date',
                '-voting_starts_at_date')

    def get_requested_elections(self):
        '''
        Returns the list of requested elections related to us.
        '''
        return Election.objects.filter(
            Q(agora__in=self.user.administrated_agoras.all()) | Q(creator=self.user),
            Q(is_approved=False) | Q(result_tallied_at_date=None)
        ).filter(archived_at_date=None).exclude(name='delegation').order_by('-voting_extended_until_date', '-voting_starts_at_date')

    def count_direct_votes(self):
        '''
        Returns the list of valid direct votes by this user
        '''
        return CastVote.objects.filter(voter=self.user, is_direct=True, is_counted=True).count()

    def get_participated_elections(self):
        '''
        Returns the list of elections in which the user participated, either
        via a direct or a delegated vote
        '''
        user_direct_votes=CastVote.objects.filter(voter=self.user, is_direct=True, is_counted=True).all()
        user_delegated_votes=CastVote.objects.filter(voter=self.user).all()
        return Election.objects.filter(agora__isnull=False,
            result_tallied_at_date__isnull=False).filter(
                Q(delegated_votes__in=user_delegated_votes) |
                Q(cast_votes__in=user_direct_votes)).distinct().order_by('-result_tallied_at_date','-voting_extended_until_date')

    def has_delegated_in_agora(self, agora):
        '''
        Returns whether this user has currently delegated his vote in a given
        agora.
        '''
        return bool(CastVote.objects.filter(voter=self.user, is_direct=False,
            election=agora.delegation_election, is_counted=True).count())

    def get_delegation_in_agora(self, agora):
        '''
        Returns this user current vote regarding his delegation (if any)
        '''
        try:
            return CastVote.objects.filter(voter=self.user, is_direct=False,
                election=agora.delegation_election, is_counted=True).order_by('-casted_at_date')[0]
        except Exception, e:
            return None

    def get_vote_in_election(self, election):
        '''
        Returns the vote of this user in the given agora if any. Note: if the
        vote is a delegated one, this only works for tallied elections.
        '''
        if election.cast_votes.filter(voter=self.user, is_counted=True).count() == 1:
            return election.cast_votes.filter(voter=self.user, is_counted=True)[0]
        else:
            votes = election.delegated_votes.filter(voter=self.user)
            if len(votes) == 0:
                return None

            return votes[0]

    def get_link(self):
        return reverse('user-view', kwargs=dict(username=self.user.username))


# definition of UserProfile from above
# ...

def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

post_save.connect(create_user_profile, sender=User)

from tastypie.models import create_api_key
post_save.connect(create_api_key, sender=User)
