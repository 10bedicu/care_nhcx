from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

PLUGIN_NAME = "nhcx"


class NHCXConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = _("NHCX")
