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
            "first_name": "NHCX",
            "last_name": "System",
            "email": "nhcx@ohc.network",
            "phone_number": "917777777777",
            "verified": True,
        },
    )

    if not user.get_full_name().strip():
        user.first_name = "NHCX"
        user.last_name = "System"
        user.save(update_fields=["first_name", "last_name"])

    NHCX_USER = user

    return user
