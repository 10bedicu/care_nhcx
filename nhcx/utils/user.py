from care.users.models import User
from nhcx.settings import plugin_settings as settings

NHCX_USER = None


def get_or_create_nhcx_user():
    global NHCX_USER
    if NHCX_USER:
        return NHCX_USER

    user, _ = User.objects.get_or_create(
        username=settings.NHCX_USERNAME,
        defaults={
            "email": "nhcx@ohc.network",
            "phone_number": "917777777777",
            "verified": True,
        },
    )
    NHCX_USER = user

    return user
