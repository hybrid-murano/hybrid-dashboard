#    Copyright (c) 2013 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import ast

from django.core import validators
from django import forms
from django.utils.translation import ugettext_lazy as _
from horizon import exceptions
from horizon import forms as horizon_forms
from horizon import messages
from oslo_log import log as logging

from muranoclient.common import exceptions as exc
from muranodashboard.common import net
from muranodashboard.environments import api

LOG = logging.getLogger(__name__)
NAME_VALIDATORS = [validators.RegexValidator('^[a-zA-Z]+[\w.-]*$')]
ENV_NAME_HELP_TEXT = _("Environment names must contain only "
                       "alphanumeric or '_-.' characters "
                       "and must start with alpha")


class CreateEnvironmentForm(horizon_forms.SelfHandlingForm):
    name = forms.CharField(label="Environment Name",
                           validators=NAME_VALIDATORS,
                           error_messages={'invalid': ENV_NAME_HELP_TEXT},
                           help_text=ENV_NAME_HELP_TEXT,
                           max_length=255)

    net_config = forms.ChoiceField(
        label=_("Environment Default Network"),
        required=True
    )

    def __init__(self, request, *args, **kwargs):
        super(CreateEnvironmentForm, self).__init__(request, *args, **kwargs)
        net_choices = net.get_available_networks(request,
                                                 murano_networks='translate')
        if net_choices is None:  # NovaNetwork case
            net_choices = [((None, None), _('Unavailable'))]
            help_text = net.NN_HELP
        else:
            net_choices.insert(0, ((None, None), _('Create New')))
            help_text = net.NEUTRON_NET_HELP
        self.fields['net_config'].choices = net_choices
        self.fields['net_config'].help_text = help_text

    def handle(self, request, data):
        try:
            net_config = ast.literal_eval(data.pop('net_config'))
            if net_config[0] is not None:
                data.update(net.generate_join_existing_net(net_config))
            env = api.environment_create(request, data)
            request.session['env_id'] = env.id
            messages.success(request,
                             'Created environment "{0}"'.format(data['name']))
            return True
        except exc.HTTPConflict:
            msg = _('Environment with specified name already exists')
            LOG.exception(msg)
            exceptions.handle(request, ignore=True)
            messages.error(request, msg)
            return False
        except Exception:
            msg = _('Failed to create environment')
            LOG.exception(msg)
            exceptions.handle(request)
            messages.error(request, msg)
            return False


class EditEnvironmentForm(horizon_forms.SelfHandlingForm):
    name = forms.CharField(label="Environment Name",
                           validators=NAME_VALIDATORS,
                           error_messages={'invalid': ENV_NAME_HELP_TEXT},
                           max_length=255)

    def handle(self, request, data):
        try:
            env_id = self.initial['environment_id']
            env = api.environment_update(request, env_id, data['name'])

            messages.success(request,
                             "Edited environment '{0}'".format(data['name']))
            return env
        except exc.HTTPConflict:
            msg = _('Environment with specified name already exists')
            LOG.exception(msg)
            exceptions.handle(request, ignore=True)
            messages.error(request, msg)
        except Exception:
            name = data.get('name', '')
            msg = _("Unable to edit environment {0}").format(name)
            LOG.exception(msg)
            exceptions.handle(request)
            messages.error(request, msg)
