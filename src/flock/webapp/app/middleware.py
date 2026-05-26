
# Custom middleware for handling proxy headers
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

#from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to handle proxy headers for HTTPS detection.
    This ensures url_for() generates HTTPS URLs when behind an HTTPS proxy.
    """
    def __init__(self, app, force_https: bool = False):
        super().__init__(app)
        self.force_https = force_https

    async def dispatch(self, request: StarletteRequest, call_next):
        import json
        import logging
        logger = logging.getLogger(__name__)

        # Log original scheme and relevant headers for debugging
        original_scheme = request.scope.get("scheme", "unknown")
        original_host = request.headers.get("host")
        logger.info(f"ProxyHeadersMiddleware - Original scheme: {original_scheme}, Host: {original_host}, URL: {request.url}")

        # If force_https is enabled, always use HTTPS
        if self.force_https:
            request.scope["scheme"] = "https"
            logger.info("ProxyHeadersMiddleware - Force HTTPS enabled, setting scheme to https")
        else:
            # Check for common proxy headers that indicate HTTPS
            forwarded_proto = request.headers.get("x-forwarded-proto")
            forwarded_scheme = request.headers.get("x-forwarded-scheme")
            forwarded_host = request.headers.get("x-forwarded-host")
            cloudflare_proto = request.headers.get("cf-visitor")
            forwarded_ssl = request.headers.get("x-forwarded-ssl")
            front_end_https = request.headers.get("front-end-https")

            # Log proxy headers for debugging
            proxy_headers = {
                "x-forwarded-proto": forwarded_proto,
                "x-forwarded-scheme": forwarded_scheme,
                "x-forwarded-host": forwarded_host,
                "cf-visitor": cloudflare_proto,
                "x-forwarded-ssl": forwarded_ssl,
                "front-end-https": front_end_https,
                "x-forwarded-for": request.headers.get("x-forwarded-for"),
                "host": request.headers.get("host")
            }
            logger.info(f"ProxyHeadersMiddleware - Proxy headers: {proxy_headers}")

            scheme_updated = False

            # Handle X-Forwarded-Proto header (most common)
            if forwarded_proto:
                request.scope["scheme"] = forwarded_proto.lower()
                scheme_updated = True
                logger.info(f"ProxyHeadersMiddleware - Updated scheme from X-Forwarded-Proto: {forwarded_proto}")

            # Handle X-Forwarded-Scheme header
            elif forwarded_scheme:
                request.scope["scheme"] = forwarded_scheme.lower()
                scheme_updated = True
                logger.info(f"ProxyHeadersMiddleware - Updated scheme from X-Forwarded-Scheme: {forwarded_scheme}")

            # Handle X-Forwarded-SSL header (on/off)
            elif forwarded_ssl and forwarded_ssl.lower() == "on":
                request.scope["scheme"] = "https"
                scheme_updated = True
                logger.info(f"ProxyHeadersMiddleware - Updated scheme from X-Forwarded-SSL: on -> https")

            # Handle Front-End-Https header (on/off)
            elif front_end_https and front_end_https.lower() == "on":
                request.scope["scheme"] = "https"
                scheme_updated = True
                logger.info(f"ProxyHeadersMiddleware - Updated scheme from Front-End-Https: on -> https")

            # Handle Cloudflare's CF-Visitor header (JSON format)
            elif cloudflare_proto:
                try:
                    visitor_info = json.loads(cloudflare_proto)
                    if visitor_info.get("scheme"):
                        request.scope["scheme"] = visitor_info["scheme"].lower()
                        scheme_updated = True
                        logger.info(f"ProxyHeadersMiddleware - Updated scheme from CF-Visitor: {visitor_info['scheme']}")
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"ProxyHeadersMiddleware - Failed to parse CF-Visitor header: {e}")

            if not scheme_updated:
                logger.info("ProxyHeadersMiddleware - No proxy headers found, keeping original scheme")

        # Handle X-Forwarded-Host for proper host handling
        forwarded_host = request.headers.get("x-forwarded-host")
        if forwarded_host:
            # Update the server scope to reflect the original host
            request.scope["server"] = (forwarded_host, 443 if request.scope.get("scheme") == "https" else 80)
            logger.info(f"ProxyHeadersMiddleware - Updated host from X-Forwarded-Host: {forwarded_host}")

        # Handle X-Forwarded-For for client IP (optional but good practice)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain (the original client)
            client_ip = forwarded_for.split(",")[0].strip()
            request.scope["client"] = (client_ip, request.scope.get("client", ["", 0])[1])

        # Log final scheme and reconstructed URL
        final_scheme = request.scope.get("scheme")
        final_server = request.scope.get("server", ("unknown", 0))
        logger.info(f"ProxyHeadersMiddleware - Final scheme: {final_scheme}, server: {final_server}")
        logger.info(f"ProxyHeadersMiddleware - Reconstructed URL would be: {final_scheme}://{final_server[0]}{request.url.path}")

        response = await call_next(request)
        return response
