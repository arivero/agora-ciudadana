import json

from django.conf.urls.defaults import *
from django.contrib.auth.models import User
from tastypie.utils import trailing_slash

from agora_site.misc.generic_resource import GenericResource, GenericMeta


class UserResource(GenericResource):
    class Meta(GenericMeta):
        queryset = User.objects.all()
        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get', 'put']
        excludes = ['password', 'is_staff', 'is_superuser']

    def override_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/username/(?P<username>[\w\d_.-]+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
            url(r"^(?P<resource_name>%s)/settings%s$" % (self._meta.resource_name, trailing_slash()),
                                                         self.wrap_view('user_settings'), name="api_user_settings"),
        ]

    def user_settings(self, request, **kwargs):
        '''
            Get the properties of the user currently authenticated
        '''

        if request.method == 'GET':
            user = User.objects.get(username=request.user)
            bundle = self.build_bundle(obj=user, request=request)
            bundle = self.full_dehydrate(bundle)

            return self.create_response(request, bundle)
        elif request.method == 'PUT':
            # TODO
            pass
