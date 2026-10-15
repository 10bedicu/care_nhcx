import io
import logging

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.core.handlers.wsgi import LimitedStream
from django.http.request import HttpRequest

logger = logging.getLogger(__name__)


class ChunkedTransferEncodingMiddleware:
    """
    Normalize requests that arrive with ``Transfer-Encoding: chunked`` and no
    ``Content-Length``.

    Django's ``WSGIRequest`` wraps ``wsgi.input`` in a ``LimitedStream`` bounded
    by ``CONTENT_LENGTH``. If the client (e.g. NHCX) sends a chunked body without
    ``Content-Length``, Django reads 0 bytes even though the WSGI server
    (Gunicorn / werkzeug) has already dechunked the payload and signalled
    ``wsgi.input_terminated``. This middleware buffers the real body and rewires
    the request so ``request.body`` / ``request.data`` work as expected.

    Registered from ``NHCXConfig.ready`` so care core settings stay unchanged.
    It inserts itself at the front of ``MIDDLEWARE`` before the WSGI handler
    loads the stack.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if self._needs_rewiring(request):
            self._buffer_body(request)
        return self.get_response(request)

    @staticmethod
    def _needs_rewiring(request: HttpRequest) -> bool:
        transfer_encoding = request.META.get("HTTP_TRANSFER_ENCODING", "").lower()
        if "chunked" not in transfer_encoding:
            return False
        try:
            content_length = int(request.META.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            content_length = 0
        return content_length <= 0

    def _buffer_body(self, request: HttpRequest) -> None:
        wsgi_input = request.META.get("wsgi.input")
        if wsgi_input is None:
            return

        # Only safe to read to EOF when the WSGI server promises it has
        # already dechunked the body. Gunicorn and werkzeug both set this;
        # the stdlib wsgiref dev server does not support chunked requests.
        if not request.META.get("wsgi.input_terminated"):
            logger.warning(
                "Chunked request received but wsgi.input_terminated is not set; "
                "server does not support chunked transfer encoding."
            )
            return

        max_size = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", None)
        # Read one extra byte so we can detect overflow deterministically.
        read_limit = (max_size + 1) if max_size else -1
        body = wsgi_input.read(read_limit)
        if max_size is not None and len(body) > max_size:
            raise RequestDataTooBig(
                "Request body exceeded settings.DATA_UPLOAD_MAX_MEMORY_SIZE."
            )

        buffered = io.BytesIO(body)
        request.META["CONTENT_LENGTH"] = str(len(body))
        request.META["wsgi.input"] = buffered
        request._stream = LimitedStream(buffered, len(body))
        # Reset any cached parsing so DRF / form parsers re-read the new stream.
        for attr in ("_body", "_post", "_files", "_read_started"):
            if hasattr(request, attr):
                try:
                    delattr(request, attr)
                except AttributeError:
                    pass
        request._read_started = False
