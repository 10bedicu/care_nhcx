from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

PLUGIN_NAME = "nhcx"


class NHCXConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = _("NHCX")

    def ready(self):
        import nhcx.extensions  # noqa: F401
        import nhcx.permissions.claim_consent  # noqa: F401
