from __future__ import annotations


def ensure_aiohttp_compat(aiohttp_module=None) -> None:
    """Patch older aiohttp for google-genai versions that catch DNSError."""
    if aiohttp_module is None:
        try:
            import aiohttp as aiohttp_module
        except ModuleNotFoundError:
            return
    if (
        hasattr(aiohttp_module, "ClientConnectorError")
        and not hasattr(aiohttp_module, "ClientConnectorDNSError")
    ):
        aiohttp_module.ClientConnectorDNSError = aiohttp_module.ClientConnectorError
