#!/usr/bin/env python
####################################################################
# COPYRIGHT Ericsson AB 2020
#
# The copyright to the computer program(s) herein is the property of
# Ericsson AB. The programs may be used and/or copied only with written
# permission from Ericsson AB. or in accordance with the terms and
# conditions stipulated in the agreement/contract under which the
# program(s) have been supplied.
####################################################################
import time
import urllib2
from collections import namedtuple
from subprocess import PIPE, Popen, STDOUT

import netaddr
from simplejson import loads


def log_times(execute_time, function_name):
    logtime = 'FunctionExec: {0:.2f}s: {1}'.format(execute_time, function_name)
    syslog(logtime)


def time_function():
    def real_decorator(function):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            fnction = '{0}({1}) '.format(function.func_name,
                                         ','.join(str(args[1:])))
            try:
                syslog('Entering function {0}'.format(fnction))
                return function(*args, **kwargs)
            finally:
                log_times(time.time() - start_time, fnction)

        return wrapper

    return real_decorator


# pylint: disable=C0325, W0621
def syslog(message):
    _m = 'redfish.cloud : {0}'.format(message)
    try:
        import syslog

        syslog.syslog(syslog.LOG_INFO, _m)
    except ImportError:
        print(_m)


def is_enm_vapp():
    """
    A check to determine if we are using ENM Vapp.
    Otherwise, it will be considered LITP Vapp.
    """
    try:
        output = exec_process(['ls', '-lrt', '/var/www/html/'])
        if 'ENM' in output:
            return True
        else:
            return False
    except IOError:
        return False


def curl(url):
    try:
        return exec_process(['/usr/bin/curl', '--insecure', '-s', url])
    except IOError as ioe:
        if ioe.args[0] == 6:
            syslog('DNS error using hostname, updating nameserver ..')
            with open('/etc/resolv.conf', 'a') as _f:
                _f.write('nameserver 192.168.0.1\n')
            return exec_process(['/usr/bin/curl', '--insecure', '-s', url])
        raise


@time_function()
def get_spp_pod(retry_wait=10):
    gateway_hostname = curl('https://atvpcspp12.athtem.eei.ericsson.se'
                            '/Vms/gateway_hostname')
    attempts = 0
    while attempts < 4:
        try:
            pod_address = curl('https://ci-portal.seli.wh.rnd.internal.'
                               'ericsson.com/getSpp/?gateway={0}'
                               .format(gateway_hostname))
            syslog('get_spp_pod result: {0}'.format(pod_address))
            if pod_address in ['', 'Gateway supplied'
                                   ' does not exist in database']:
                raise ValueError('Failed to get the pod information.')
            else:
                return pod_address
        except IOError:
            if attempts == 3:
                raise
            syslog('CI Portal not responding, trying to reconnect..')
            attempts += 1
            time.sleep(retry_wait)


def exec_process(command, ignore_error=False):
    syslog(' '.join(command))
    process = Popen(command, stdout=PIPE, stderr=STDOUT)
    stdout = process.communicate()[0]
    if process.returncode != 0 and not ignore_error:
        raise IOError(process.returncode, stdout)
    return stdout


class LitpModelObject(object):

    @staticmethod
    def to_object(json_data):
        return LitpModelObject(json_data)

    @staticmethod
    def get_path_from_url(model_url):
        start = model_url.index(LitpWrapper.BASE_REST_PATH)
        path = model_url[start + len(LitpWrapper.BASE_REST_PATH):]
        return path

    def __init__(self, data):
        if isinstance(data, str):
            json_data = loads(data)
        else:
            json_data = data
        self.__item_type = json_data['item-type-name']
        self.__oid = json_data['id']
        if 'state' in json_data:
            self.__state = json_data['state']
        else:
            self.__state = 'N/A'
        self.__path = LitpModelObject.get_path_from_url(
            json_data['_links']['self']['href'])
        self.__children = {}
        self.__properties = {}
        if '_embedded' in json_data:
            for item in json_data['_embedded']['item']:
                child = LitpModelObject(item)
                self.__children[child.get_oid()] = child
        if 'properties' in json_data:
            self.__properties.update(json_data['properties'])

        if 'description' in json_data:
            self.description = json_data['description']
        else:
            self.description = None

        if 'reference-to' in json_data['_links']:
            self.__reference_to = LitpModelObject.get_path_from_url(
                json_data['_links']['reference-to']['href'])
        else:
            self.__reference_to = None

    def get_property(self, property_name):
        if property_name in self.__properties:
            return self.__properties[property_name]
        return None

    def get_oid(self):
        return self.__oid

    def get_path(self):
        return self.__path

    def is_type(self, item_type):
        return self.__item_type == item_type

    def get_children(self):
        return self.__children.values()

    def __str__(self):
        return self.get_path()


class LitpWrapper(object):
    BASE_REST_PATH = '/litp/rest/v1'

    def _find(self, lobject, item_type):
        found = []
        if lobject.is_type(item_type):
            found.append(lobject)
        for child in lobject.get_children():
            found.extend(self._find(child, item_type))
        return found

    @staticmethod
    def get_item(model_path):
        json_data = exec_process(['/usr/bin/litp', 'show', '-p',
                                  model_path, '--json'])
        return LitpModelObject.to_object(json_data)

    def find(self, start_path, item_type, depth=0):
        command = ['/usr/bin/litp', 'show', '-p', start_path, '-r', '--json']
        if depth > 0:
            command.extend(['-n', str(depth)])
        json_data = exec_process(command)
        root_object = LitpModelObject.to_object(json_data)
        return self._find(root_object, item_type)


@time_function()
def get_vm_name(ilo_address):
    """
    Map an iLO address to a VM name.
    This will search the model for item types of reference-to-bmc (these
    usually exist below the node item-type) and then return the node.hostname
    property.

    :param ilo_address: The iLO address. Any address will do as long as it's
     unique to the node.
    :type ilo_address: str
    :return: The hostname of node that contains the bmc entry
    :rtype: str
    """
    wlitp = LitpWrapper()
    hostmap = {}
    nodes = wlitp.find('/deployments', 'node')
    for node in nodes:
        hostname = node.get_property('hostname')
        link = wlitp.find(node.get_path(), 'reference-to-bmc', depth=2)
        if link:
            link = link[0]
            syslog('Getting iLO address for {0}'.format(link.get_path()))
            ilo = link.get_property('ipaddress')
            if ilo in hostmap:
                msg = 'iLO address {0} is linked to more than' \
                      ' one node -> {1}, {2}'.format(ilo_address, hostmap[ilo],
                                                     hostname)
                syslog(msg)
                raise ValueError(msg)
            else:
                hostmap[ilo] = {'hostname': hostname, 'path': node.get_path()}
    if ilo_address in hostmap:
        mapped_node = hostmap[ilo_address]['hostname']
        syslog('Found mapping from {0} to '
               '{1}'.format(ilo_address,
                            hostmap[ilo_address]['path']))
        return mapped_node
    else:
        msg = 'Could not find a node with a bmc ' \
              'reference to {0}'.format(ilo_address)
        syslog(msg)
        raise ValueError(msg)


class RedfishClient(object):

    ip_name = {
        42: "ms-1",
        43: "sc-1",
        44: "sc-2",
        235: "sc-3",
        241: "sc-4",
        45: "pl-3",
        46: "pl-4",
        193: "topology",
        194: "pmstream",
        195: "csl-eps1",
        196: "csl-eps2",
        202: "svc1",
        203: "svc2",
        204: "db1",
        205: "db2",
    }

    def __init__(self, base_url, username=None, password=None,
                 default_prefix='/redfish/v1/'):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.default_prefix = default_prefix
        if is_enm_vapp():
            self.pod_prefix = get_spp_pod()
            self.vmname = get_vm_name(base_url)
        else:
            self.pod_prefix = "https://10.42.34.79/"
            try:
                node_addr = netaddr.IPAddress(base_url)
            except netaddr.core.AddrFormatError as ex:
                raise ValueError(ex)

            try:
                self.vmname = self.ip_name[node_addr.words[-1]]
            except KeyError:
                raise ValueError("VApp node IP {0} is not valid"
                                 .format(node_addr))

        syslog('Cloud POD is {0}'.format(self.pod_prefix))
        syslog('Mapped iLO {0} to {1}'.format(base_url, self.vmname))

    def patch(self, path, body):
        if '/redfish/v1/Systems/1/' in path and \
                body["Boot"]["BootSourceOverrideTarget"] == "Pxe":
            return self.set_bootdev_pxe()
        return RedfishClient._create_spp_response(400, 'ActionNotSupported')

    def post(self, path, body=None):
        if 'ComputerSystem.Reset' in path:
            if body["ResetType"] == "ForceOff":
                return self.set_poweroff()
            elif body["ResetType"] == "On":
                return self.set_poweron()
        return RedfishClient._create_spp_response(400, 'ActionNotSupported')

    def login(self, username=None, password=None):
        pass  # Ignore

    def logout(self):
        pass  # Ignore

    @time_function()
    def set_bootdev_pxe(self):
        return self._set_boot_device('net')

    @time_function()
    def set_bootdev_hd(self):
        return self._set_boot_device('hd')

    def _set_boot_device(self, dev):
        apistr = "Vms/set_boot_device_api/boot_devices:{0}/vm_name:{1}.xml". \
            format(dev, str(self.vmname))
        if dev == 'hd':
            return self._call_cloud_api(apistr, "Set Boot Device to disk")

        apistr = "{0}:{1}/vm_name:{2}.xml".format(
            'Vms/set_boot_device_api/boot_devices', 'net', str(self.vmname))
        return self._call_cloud_api(apistr, "Set Boot Device to pxe")

    @time_function()
    def set_poweroff(self):
        apistr = "Vms/poweroff_api/vm_name:%s.xml" % (str(self.vmname))
        return self._call_cloud_api(apistr, "Chassis Power Control: Down/Off")

    @time_function()
    def set_poweron(self):
        apistr = "Vms/poweron_api/vm_name:%s.xml" % (str(self.vmname))
        poweron_resp = self._call_cloud_api(
            apistr, "Chassis Power Control: Up/On")

        # As Redfish can set boot device to pxe once, with SPP boot device
        # needs to be manually reset after power on.
        time.sleep(180)
        boot_dev_resp = self.set_bootdev_hd()

        if poweron_resp.status == 200 and boot_dev_resp.status != 200:
            msg = 'Error setting boot device to disk: ' + \
                  boot_dev_resp.dict["Message"]
            return RedfishClient._create_spp_response(boot_dev_resp.status,
                                                      msg)
        return poweron_resp

    @time_function()
    def _call_cloud_api(self, apistr, msg):
        url = '{0}{1}'.format(self.pod_prefix, apistr)
        syslog('Adapted SPP Rest call: {0}'.format(url))
        req = urllib2.Request(url)
        try:
            resp = urllib2.urlopen(req)
            return RedfishClient._create_spp_response(resp.code, msg)
        except urllib2.HTTPError as e:
            return RedfishClient._create_spp_response(e.code, e.read())
        except urllib2.URLError as e:
            return RedfishClient._create_spp_response(0, e.reason)

    @staticmethod
    def _create_spp_response(status, msg):
        spp_response = namedtuple('spp_response', 'status dict')
        msg_dict = {"Message": msg}
        return spp_response(status=status, dict=msg_dict)
