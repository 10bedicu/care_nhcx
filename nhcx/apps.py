from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

PLUGIN_NAME = "nhcx"


class NHCXConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = _("NHCX")

    def ready(self):
        from django.conf import settings

        import nhcx.extensions  # noqa: F401
        import nhcx.permissions.claim_consent  # noqa: F401

        middleware = "nhcx.middleware.ChunkedTransferEncodingMiddleware"
        if middleware not in settings.MIDDLEWARE:
            # Before the handler calls load_middleware(), which happens after ready().
            settings.MIDDLEWARE.insert(0, middleware)
