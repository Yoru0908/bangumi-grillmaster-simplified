import types
import unittest


class GeminiAiohttpCompatTests(unittest.TestCase):
    def test_missing_client_connector_dns_error_is_aliased(self):
        from services.gemini.compat import ensure_aiohttp_compat

        class ConnectorError(Exception):
            pass

        fake_aiohttp = types.SimpleNamespace(ClientConnectorError=ConnectorError)

        ensure_aiohttp_compat(fake_aiohttp)

        self.assertIs(fake_aiohttp.ClientConnectorDNSError, ConnectorError)


if __name__ == "__main__":
    unittest.main()
