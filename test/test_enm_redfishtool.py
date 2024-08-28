from collections import namedtuple
from os.path import dirname, join, realpath
from unittest import TestCase

from mock import call, MagicMock, patch

import redfishtool
from redfishtool import RedfishClient

# Common Constants
URL = 'http://url.com'
REDFISH_V1 = '/redfish/v1/'
ATVCLOUD = 'https://atvcloud3/'
SPP_POD = 'redfishtool.get_spp_pod'
RESET = "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset/"
POWER_ON = 'https://atvcloud3/Vms/poweron_api/vm_name:cloud-svc-1.xml'
HD_BOOT = 'https://atvcloud3/Vms/set_boot_device_api/boot_devices:hd/vm_name:cloud-svc-1.xml'


class TestEnmRedfishCloudTool(TestCase):

    """
    ENM Vapps suite case
    """

    def setUp(self):
        pass  # Ignore

    def mock_curl(self, exec_process, gateway_host,
                  pod='https://pod.athtem.eei.ericsson.se/'):
        def side_effect(command):
            if ' '.join(command).endswith('gateway_hostname'):
                return gateway_host
            elif ' '.join(command).endswith(gateway_host):
                return pod

        exec_process.side_effect = side_effect
        return self

    def mock_curl_failure(self, exec_process, gateway_host):
        def side_effect(command):
            if ' '.join(command).endswith('gateway_hostname'):
                return gateway_host
            elif ' '.join(command).endswith(gateway_host):
                raise IOError(9, 'TEST IOError')

        exec_process.side_effect = side_effect
        return self

    def mock_node(self, hostname, model_id, ilo_address):
        json_data = open(join(dirname(realpath(__file__)), 'node.json')).read()
        json_data = json_data.replace('@@HOSTNAME@@', hostname)
        json_data = json_data.replace('@@MODELID@@', model_id)
        json_data = json_data.replace('@@ILOADDRESS@@', ilo_address)
        if self:
            return json_data

    def mock_find_nodes(self, exec_process, node_data):
        def findse(command):
            nodes = ''
            for nd in node_data:
                nodes += self.mock_node(*nd)
            return nodes

        exec_process.side_effect = findse
        return self

    @patch('redfishtool.exec_process')
    def test_get_vm_name(self, exec_process):
        self.mock_find_nodes(exec_process, [('vm1', 'vm1', '1.1.1.222')])

        vmname = redfishtool.get_vm_name('1.1.1.222')
        self.assertEquals('vm1', vmname)

        self.assertRaises(ValueError, redfishtool.get_vm_name, '1.1.1.1')

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    @patch('redfishtool.urllib2.Request')
    @patch('redfishtool.urllib2.urlopen')
    def test_set_poweroff(self, mock_urlopen, mock_request, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('a1', 'a1', '1.1.1.42')])

        with patch(SPP_POD) as get_spp_pod:
            resp = namedtuple('resp', 'code')
            mock_urlopen.return_value = resp(code=200)
            get_spp_pod.return_value = ATVCLOUD
            mock_enm.return_value = True

            self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)
            returned_response = self.adapter.set_poweroff()
            mock_request.assert_called_once_with('https://atvcloud3/Vms/'
                                                 'poweroff_api/vm_name:a1.xml')
            self.assertEquals(200, returned_response.status)
            self.assertEquals('Chassis Power Control: Down/Off', returned_response.dict["Message"])

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    @patch('redfishtool.urllib2.Request')
    @patch('redfishtool.urllib2.urlopen')
    def test_set_poweron(self, mock_urlopen, mock_request, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('cloud-svc-1', 'cloud-svc-1', '1.1.1.42')])

        with patch(SPP_POD) as get_spp_pod:
            resp = namedtuple('resp', 'code')
            mock_urlopen.return_value = resp(code=200)
            get_spp_pod.return_value = ATVCLOUD
            mock_enm.return_value = True

            self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)
            returned_response = self.adapter.set_poweron()
            mock_request.assert_has_calls([call(POWER_ON), call(HD_BOOT)])
            self.assertEquals(200, returned_response.status)
            self.assertEquals('Chassis Power Control: Up/On', returned_response.dict["Message"])

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    @patch('redfishtool.urllib2.Request')
    @patch('redfishtool.urllib2.urlopen')
    def test_set_poweron_error(self, mock_urlopen, mock_request, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('cloud-svc-1', 'cloud-svc-1', '1.1.1.202')])

        with patch(SPP_POD) as get_spp_pod:
            resp = namedtuple('resp', 'code message')
            mock_urlopen.side_effect = [resp(code=404, message='Error on power on'), resp(code=200, message='OK')]
            get_spp_pod.return_value = ATVCLOUD
            mock_enm.return_value = True

            self.adapter = RedfishClient('1.1.1.202', 'user', 'pass', REDFISH_V1)
            returned_response = self.adapter.set_poweron()
            mock_request.assert_has_calls([call(POWER_ON), call(HD_BOOT)])
            self.assertEquals(404, returned_response.status)
            self.assertEquals('Chassis Power Control: Up/On', returned_response.dict["Message"])

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    @patch('redfishtool.urllib2.Request')
    @patch('redfishtool.urllib2.urlopen')
    def test_set_poweron_device_error(self, mock_urlopen, mock_request, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('cloud-svc-1', 'cloud-svc-1', '1.1.1.202')])

        with patch(SPP_POD) as get_spp_pod:
            resp = namedtuple('resp', 'code')
            mock_urlopen.side_effect = [resp(code=200), resp(code=404)]
            get_spp_pod.return_value = ATVCLOUD
            mock_enm.return_value = True

            self.adapter = RedfishClient('1.1.1.202', 'user', 'pass', REDFISH_V1)
            returned_response = self.adapter.set_poweron()
            mock_request.assert_has_calls([call(POWER_ON), call(HD_BOOT)])
            self.assertEquals(404, returned_response.status)
            self.assertEquals('Error setting boot device to disk: Set Boot Device to disk',
                              returned_response.dict["Message"])

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    @patch('redfishtool.urllib2.Request')
    @patch('redfishtool.urllib2.urlopen')
    def test_set_bootdev_pxe(self, mock_urlopen, mock_request, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('cloud-svc-1', 'cloud-svc-1', '1.1.1.42')])

        with patch(SPP_POD) as get_spp_pod:
            resp = namedtuple('resp', 'code')
            mock_urlopen.return_value = resp(code=200)
            get_spp_pod.return_value = ATVCLOUD
            mock_enm.return_value = True
            self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)

            returned_response = self.adapter.set_bootdev_pxe()
            mock_request.assert_called_once_with(
                'https://atvcloud3/Vms/'
                'set_boot_device_api/boot_devices:net/vm_name:cloud-svc-1.xml')
            self.assertEquals(200, returned_response.status)
            self.assertEquals('Set Boot Device to pxe', returned_response.dict["Message"])

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    @patch('redfishtool.urllib2.Request')
    @patch('redfishtool.urllib2.urlopen')
    def test_set_bootdev_hd(self, mock_urlopen, mock_request, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('ms-1', 'ms-1', '1.1.1.42')])
        with patch(SPP_POD) as get_spp_pod:
            resp = namedtuple('resp', 'code')
            mock_urlopen.return_value = resp(code=200)
            get_spp_pod.return_value = ATVCLOUD
            mock_enm.return_value = True
            self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)

            returned_response = self.adapter.set_bootdev_hd()
            mock_request.assert_called_once_with(
                'https://atvcloud3/Vms/'
                'set_boot_device_api/boot_devices:hd/vm_name:ms-1.xml')
            self.assertEquals(200, returned_response.status)
            self.assertEquals('Set Boot Device to disk', returned_response.dict["Message"])

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    @patch('redfishtool.urllib2.urlopen')
    def test_http_error(self, mock_urlopen, exec_process, mock_enm):
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

            self.mock_find_nodes(exec_process, [('vm1', 'vm1', '1.1.1.222')])
            mock_enm.return_value = True
            self.adapter = RedfishClient('1.1.1.222', 'user', 'pass', REDFISH_V1)
            returned_response = self.adapter.set_bootdev_hd()
            self.assertEquals(404, returned_response.status)
            self.assertEquals('foo', returned_response.dict["Message"])
        finally:
            redfishtool.urllib2.HTTPError = actual_httperror

    @patch('redfishtool.exec_process')
    @patch('redfishtool.urllib2.urlopen')
    def test_url_error(self, mock_urlopen, exec_process):
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

            self.mock_find_nodes(exec_process, [('ms-1', 'ms-1', '1.1.1.42')])
            with patch(SPP_POD) as get_spp_pod:
                get_spp_pod.return_value = ATVCLOUD

                self.adapter = RedfishClient('1.1.1.42', 'user', 'pass', REDFISH_V1)
                returned_response = self.adapter.set_bootdev_hd()
                self.assertEquals(0, returned_response.status)
                self.assertEquals('[Errno 110] Connection timed out', returned_response.dict["Message"])
        finally:
            redfishtool.urllib2.URLError = actual_urlerror

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    @patch('redfishtool.RedfishClient.set_bootdev_pxe')
    def test_patch_bootdev_pxe(self, mock_method, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('vm1', 'vm1', '15.16.17.43')])
        resp = namedtuple('resp', 'status')
        mock_method.return_value = resp(status=200)
        mock_enm.return_value = True

        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"Boot": {"BootSourceOverrideTarget": "Pxe",
                         "BootSourceOverrideEnabled": "Once"}}
        returned_response = self.adapter.patch("/redfish/v1/Systems/1/", body=body)
        self.assertEquals(200, returned_response.status)
        mock_method.assert_called_once()

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    @patch('redfishtool.RedfishClient.set_poweroff')
    def test_post_poweroff(self, mock_method,  exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('vm1', 'vm1', '15.16.17.43')])
        resp = namedtuple('resp', 'status')
        mock_method.return_value = resp(status=200)
        mock_enm.return_value = True

        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"ResetType": "ForceOff"}
        returned_response = self.adapter.post(RESET, body=body)
        self.assertEquals(200, returned_response.status)
        mock_method.assert_called_once()

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    @patch('redfishtool.RedfishClient.set_poweron')
    def test_post_poweron(self, mock_method, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('vm1', 'vm1', '15.16.17.43')])
        resp = namedtuple('resp', 'status')
        mock_method.return_value = resp(status=200)
        mock_enm.return_value = True

        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"ResetType": "On"}
        returned_response = self.adapter.post(RESET, body=body)
        self.assertEquals(200, returned_response.status)
        mock_method.assert_called_once()

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    def test_post_power_bad_action(self, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('vm1', 'vm1', '15.16.17.43')])
        mock_enm.return_value = True

        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"ResetType": "Foo"}
        returned_response = self.adapter.post(RESET, body=body)
        self.assertEquals(400, returned_response.status)
        self.assertEquals('ActionNotSupported', returned_response.dict["Message"])

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    def test_post_power_bad_path(self, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('vm1', 'vm1', '15.16.17.43')])
        mock_enm.return_value = True

        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"ResetType": "ForceOff"}
        returned_response = self.adapter.post("/redfish/v1/Systems/1/Actions/Invalid/", body=body)
        self.assertEquals(400, returned_response.status)
        self.assertEquals('ActionNotSupported', returned_response.dict["Message"])

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    def test_patch_bootdev_bad_action(self, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('vm1', 'vm1', '15.16.17.43')])
        mock_enm.return_value = True

        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"Boot": {"BootSourceOverrideTarget": "Foo",
                         "BootSourceOverrideEnabled": "Once"}}
        returned_response = self.adapter.patch("/redfish/v1/Systems/1/", body=body)
        self.assertEquals(400, returned_response.status)
        self.assertEquals('ActionNotSupported', returned_response.dict["Message"])

    @patch('redfishtool.is_enm_vapp')
    @patch('redfishtool.exec_process')
    def test_patch_bootdev_bad_path(self, exec_process, mock_enm):
        self.mock_find_nodes(exec_process, [('vm1', 'vm1', '15.16.17.43')])
        mock_enm.return_value = True

        self.adapter = RedfishClient('15.16.17.43', 'user', 'pass', REDFISH_V1)
        body = {"Boot": {"BootSourceOverrideTarget": "Pxe",
                         "BootSourceOverrideEnabled": "Once"}}
        returned_response = self.adapter.patch("/invalid", body=body)
        self.assertEquals(400, returned_response.status)
        self.assertEquals('ActionNotSupported', returned_response.dict["Message"])

    @patch('redfishtool.exec_process')
    def test_get_spp_pod(self, exec_process):
        self.mock_curl(exec_process, 'atvts1234')

        pod = redfishtool.get_spp_pod()
        self.assertEquals('https://pod.athtem.eei.ericsson.se/', pod)

        self.mock_curl(exec_process, 'atvts1234', pod='')
        self.assertRaises(ValueError, lambda: redfishtool.get_spp_pod())

        self.mock_curl_failure(exec_process, 'atvts1234')
        self.assertRaises(IOError, lambda: redfishtool.get_spp_pod(retry_wait=1))

    @patch('redfishtool.exec_process')
    def test_curl(self, exec_process):

        self.error_code = 0
        return_string = 'returned'

        def side_effect(command):
            if self.error_code:
                try:
                    raise IOError(self.error_code)
                finally:
                    self.error_code = 0
            else:
                return return_string

        exec_process.side_effect = side_effect
        output = redfishtool.curl(URL)
        self.assertEquals(return_string, output)

        self.error_code = 1
        self.assertRaises(IOError, redfishtool.curl, URL)

        self.error_code = 6
        exec_process.call_count = 0
        with patch('redfishtool.open', create=True) as mock_open:
            mock_open.return_value = MagicMock(spec=file)
            output = redfishtool.curl(URL)
            self.assertEquals(return_string, output)
            self.assertEquals(2, exec_process.call_count)
