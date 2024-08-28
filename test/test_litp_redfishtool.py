from collections import namedtuple
from unittest import TestCase

from mock import patch

import redfishtool
from redfishtool import RedfishClient

# Common Constants
REDFISH_V1 = '/redfish/v1/'
RESET = "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset/"


class TestLitpRedfishCloudTool(TestCase):

    """
    LITP Vapps suite case
    """

    def setUp(self):
        pass  # Ignore

    @patch('redfishtool.urllib2.Request')
    @patch('redfishtool.urllib2.urlopen')
    def test_set_poweroff(self, mock_urlopen, mock_request):
        resp = namedtuple('resp', 'code')
        mock_urlopen.return_value = resp(code=200)

        self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)

        returned_response = self.adapter.set_poweroff()
        mock_request.assert_called_once_with('https://10.42.34.79/Vms/poweroff_api/vm_name:ms-1.xml')
        self.assertEquals(200, returned_response.status)
        self.assertEquals('Chassis Power Control: Down/Off', returned_response.dict["Message"])

    @patch('redfishtool.urllib2.Request')
    @patch('redfishtool.urllib2.urlopen')
    def test_set_poweron(self, mock_urlopen, mock_request):
        resp = namedtuple('resp', 'code')
        mock_urlopen.return_value = resp(code=200)

        self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)
        mocked_sleep = patch('redfishtool.time.sleep')
        mocked_sleep.return_value = 0
        mocked_sleep.start()

        returned_response = self.adapter.set_poweron()
        mock_request.has_calls(['https://10.42.34.79/Vms/poweron_api/vm_name:ms-1.xml',
                                'https://10.42.34.79/Vms/boot_devices:hd/vm_name:ms-1.xml'])
        mocked_sleep.stop()
        self.assertEquals(200, returned_response.status)
        self.assertEquals('Chassis Power Control: Up/On', returned_response.dict["Message"])

    @patch('redfishtool.urllib2.Request')
    @patch('redfishtool.urllib2.urlopen')
    def test_set_bootdev_pxe(self, mock_urlopen, mock_request):
        resp = namedtuple('resp', 'code')
        mock_urlopen.return_value = resp(code=200)

        self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)

        returned_response = self.adapter.set_bootdev_pxe()
        mock_request.assert_called_once_with(
            'https://10.42.34.79/Vms/set_boot_device_api/boot_devices:net/vm_name:ms-1.xml')
        self.assertEquals(200, returned_response.status)
        self.assertEquals('Set Boot Device to pxe', returned_response.dict["Message"])

    @patch('redfishtool.urllib2.Request')
    @patch('redfishtool.urllib2.urlopen')
    def test_set_bootdev_hd(self, mock_urlopen, mock_request):
        resp = namedtuple('resp', 'code')
        mock_urlopen.return_value = resp(code=200)

        self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)

        returned_response = self.adapter.set_bootdev_hd()
        mock_request.assert_called_once_with(
            'https://10.42.34.79/Vms/set_boot_device_api/boot_devices:hd/vm_name:ms-1.xml')
        self.assertEquals(200, returned_response.status)
        self.assertEquals('Set Boot Device to disk', returned_response.dict["Message"])

    @patch('redfishtool.urllib2.urlopen')
    def test_http_error(self, mock_urlopen):
        class MockHttpError(Exception):
            def __init__(self):
                self.code = 404
                self.read = lambda: 'foo'

        mock_exception = MockHttpError
        mock_urlopen.side_effect = mock_exception
        actual_httperror = None
        try:
            actual_httperror = redfishtool.urllib2.HTTPError
            redfishtool.urllib2.HTTPError = mock_exception

            self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)
            returned_response = self.adapter.set_bootdev_hd()
            self.assertEquals(404, returned_response.status)
            self.assertEquals('foo', returned_response.dict["Message"])
        finally:
            redfishtool.urllib2.HTTPError = actual_httperror

    @patch('redfishtool.urllib2.urlopen')
    def test_url_error(self, mock_urlopen):
        class MockUrlError(Exception):
            def __init__(self):
                # Yes, in URLError args == reason
                self.reason = self.args = '[Errno 110] Connection timed out'

        mock_exception = MockUrlError
        mock_urlopen.side_effect = mock_exception
        actual_urlerror = None
        try:
            actual_urlerror = redfishtool.urllib2.URLError
            redfishtool.urllib2.URLError = mock_exception

            self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)
            returned_response = self.adapter.set_bootdev_hd()
            self.assertEquals(0, returned_response.status)
            self.assertEquals('[Errno 110] Connection timed out', returned_response.dict["Message"])
        finally:
            redfishtool.urllib2.URLError = actual_urlerror

    def test_bad_vapp_node_address(self):
        bad_addresses = ['foo', 'sada:sad', '0.0.0.0', '1.2.f.3']
        for bad_address in bad_addresses:
            self.assertRaises(ValueError, RedfishClient, bad_address)

    def test_invalid_vapp_node_address(self):
        self.assertRaises(ValueError, RedfishClient, '15.16.17.18')

    @patch('redfishtool.RedfishClient.set_bootdev_pxe')
    def test_patch_bootdev_pxe(self, mock_method):
        resp = namedtuple('resp', 'status')
        mock_method.return_value = resp(status=200)
        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"Boot": {"BootSourceOverrideTarget": "Pxe",
                         "BootSourceOverrideEnabled": "Once"}}
        returned_response = self.adapter.patch("/redfish/v1/Systems/1/", body=body)
        self.assertEquals(200, returned_response.status)
        mock_method.assert_called_once()

    @patch('redfishtool.RedfishClient.set_poweroff')
    def test_post_poweroff(self, mock_method):
        resp = namedtuple('resp', 'status')
        mock_method.return_value = resp(status=200)
        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"ResetType": "ForceOff"}
        returned_response = self.adapter.post(RESET, body=body)
        self.assertEquals(200, returned_response.status)
        mock_method.assert_called_once()

    @patch('redfishtool.RedfishClient.set_poweron')
    def test_post_poweron(self, mock_method):
        resp = namedtuple('resp', 'status')
        mock_method.return_value = resp(status=200)
        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"ResetType": "On"}
        returned_response = self.adapter.post(RESET, body=body)
        self.assertEquals(200, returned_response.status)
        mock_method.assert_called_once()

    def test_post_power_bad_action(self):
        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"ResetType": "Foo"}
        returned_response = self.adapter.post(RESET, body=body)
        self.assertEquals(400, returned_response.status)
        self.assertEquals('ActionNotSupported', returned_response.dict["Message"])

    def test_post_power_bad_path(self):
        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"ResetType": "ForceOff"}
        returned_response = self.adapter.post("/redfish/v1/Systems/1/Actions/Invalid/", body=body)
        self.assertEquals(400, returned_response.status)
        self.assertEquals('ActionNotSupported', returned_response.dict["Message"])

    def test_patch_bootdev_bad_action(self):
        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"Boot": {"BootSourceOverrideTarget": "Foo",
                         "BootSourceOverrideEnabled": "Once"}}
        returned_response = self.adapter.patch("/redfish/v1/Systems/1/", body=body)
        self.assertEquals(400, returned_response.status)
        self.assertEquals('ActionNotSupported', returned_response.dict["Message"])

    def test_patch_bootdev_bad_path(self):
        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"Boot": {"BootSourceOverrideTarget": "Pxe",
                         "BootSourceOverrideEnabled": "Once"}}
        returned_response = self.adapter.patch("/invalid", body=body)
        self.assertEquals(400, returned_response.status)
        self.assertEquals('ActionNotSupported', returned_response.dict["Message"])
