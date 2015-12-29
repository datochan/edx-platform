"""Tests covering Credentials utilities."""
from django.test import TestCase
import httpretty
import mock
from oauth2_provider.tests.factories import ClientFactory
from provider.constants import CONFIDENTIAL

from openedx.core.djangoapps.credentials.tests.mixins import CredentialsApiConfigMixin, CredentialsDataMixin
from openedx.core.djangoapps.credentials.models import CredentialsApiConfig
from openedx.core.djangoapps.credentials.utils import (
    get_user_credentials, get_user_program_credentials
)
from openedx.core.djangoapps.programs.tests.mixins import ProgramsApiConfigMixin, ProgramsDataMixin
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from student.tests.factories import UserFactory


class TestCredentialsRetrieval(ProgramsApiConfigMixin, CredentialsApiConfigMixin, CredentialsDataMixin,
                               ProgramsDataMixin, TestCase):
    """ Tests covering the retrieval of user credentials from the Credentials
    service.
    """
    def setUp(self):
        super(TestCredentialsRetrieval, self).setUp()

        ClientFactory(name=CredentialsApiConfig.OAUTH2_CLIENT_NAME, client_type=CONFIDENTIAL)
        ClientFactory(name=ProgramsApiConfig.OAUTH2_CLIENT_NAME, client_type=CONFIDENTIAL)
        self.user = UserFactory()

    @httpretty.activate
    def test_get_user_credentials(self):
        """Verify user credentials data can be retrieve."""
        self.create_credential_config()
        self.mock_credentials_api(self.user.username)

        actual = get_user_credentials(self.user)
        self.assertEqual(actual, self.CREDENTIALS_API_RESPONSE['results'])

    def test_get_user_credentials_credentials_disabled(self):
        """Verify behavior when Credentials is disabled."""
        self.create_credential_config(enabled=False)

        actual = get_user_credentials(self.user)
        self.assertEqual(actual, [])

    @mock.patch('edx_rest_api_client.client.EdxRestApiClient.__init__')
    def test_get_credentials_client_initialization_failure(self, mock_init):
        """Verify behavior when API client fails to initialize."""
        self.create_credential_config()
        mock_init.side_effect = Exception

        actual = get_user_credentials(self.user)
        self.assertEqual(actual, [])
        self.assertTrue(mock_init.called)

    @httpretty.activate
    def test_get_user_credentials_retrieval_failure(self):
        """Verify behavior when data can't be retrieved from Credentials."""
        self.create_credential_config()
        self.mock_credentials_api(self.user.username, status_code=500)

        actual = get_user_credentials(self.user)
        self.assertEqual(actual, [])

    def test_get_user_program_credentials_issuance_disable(self):
        """Verify that user program credentials cannot be retrieved if issuance is disabled."""
        self.create_credential_config(enable_learner_issuance=False)
        actual = get_user_program_credentials(self.user)
        self.assertEqual(actual, [])

    @httpretty.activate
    def test_get_user_program_credentials_no_credential(self):
        """Verify behavior if no credential exist."""
        self.create_credential_config()
        self.mock_credentials_api(self.user.username, data={'results': []})
        actual = get_user_program_credentials(self.user)
        self.assertEqual(actual, [])

    @httpretty.activate
    def test_get_user_program_credentials_revoked(self):
        """Verify behavior if credential revoked."""
        credential_data = {"results": [
            {
                "id": 1,
                "username": "test",
                "credential": {
                    "credential_id": 1,
                    "program_id": 1
                },
                "status": "revoked",
                "uuid": "dummy-uuid-1"
            }
        ]}
        self.create_credential_config()
        self.mock_credentials_api(self.user.username, data=credential_data)
        actual = get_user_program_credentials(self.user)
        self.assertEqual(actual, [])

    @httpretty.activate
    def test_get_user_program(self):
        """Verify program credentials data can be retrieved and parsed correctly."""
        credentials_config = self.create_credential_config()
        self.create_program_config()
        self.mock_programs_api()
        self.mock_credentials_api(self.user.username, reset_uri=False)
        actual = get_user_program_credentials(self.user)
        expected = self.PROGRAMS_API_RESPONSE['results']
        expected[0]['credential_url'] = \
            credentials_config.public_service_url + 'credentials/' + self.PROGRAMS_CREDENTIALS_DATA[0]['uuid']
        expected[1]['credential_url'] = \
            credentials_config.public_service_url + 'credentials/' + self.PROGRAMS_CREDENTIALS_DATA[1]['uuid']
        self.assertEqual(len(actual), 2)
        self.assertEqual(actual, expected)

        httpretty.reset()
