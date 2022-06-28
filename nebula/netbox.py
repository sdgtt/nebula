import json
import logging
import os
import pathlib
from re import L

import pynetbox
import yaml
from nebula.common import utils
from numpy import isin

log = logging.getLogger(__name__)


def obj_dic(d):
    """Convert dictionary to object"""
    top = type("new", (object,), d)
    seqs = tuple, list, set, frozenset
    for i, j in d.items():
        if isinstance(j, dict):
            setattr(top, i, obj_dic(j))
        elif isinstance(j, seqs):
            setattr(
                top, i, type(j)(obj_dic(sj) if isinstance(sj, dict) else sj for sj in j)
            )
        else:
            setattr(top, i, j)
    return top


def todict(obj, classkey=None):
    """Convert object to dictionary"""
    if isinstance(obj, dict):
        data = {}
        for (k, v) in obj.items():
            data[k] = todict(v, classkey)
        return data
    elif hasattr(obj, "_ast"):
        return todict(obj._ast())
    elif hasattr(obj, "__iter__") and not isinstance(obj, str):
        return [todict(v, classkey) for v in obj]
    elif hasattr(obj, "__dict__"):
        data = dict(
            [
                (key, todict(value, classkey))
                for key, value in obj.__dict__.items()
                if not callable(value) and not key.startswith("_")
            ]
        )
        if classkey is not None and hasattr(obj, "__class__"):
            data[classkey] = obj.__class__.__name__
        return data
    else:
        return obj


def ddepth(d):
    """Return depth of a dictionary"""
    if isinstance(d, dict):
        return 1 + (max(map(ddepth, d.values())) if d else 0)
    return 0


class netbox(utils):
    """NetBox interface"""

    def __init__(
        self,
        ip="localhost",
        port=8000,
        token="0123456789abcdef0123456789abcdef01234567",
        base_url="",
        yamlfilename=None,
        board_name=None,
        load_config=True
    ):
        port = ":" + str(port) if port else ""
        base_url = "/" + str(base_url) if base_url else ""
        self.netbox_server = ip
        self.netbox_server_port = port
        self.netbox_api_token = token
        self.netbox_base_url = base_url
        self.nb = pynetbox.api(f"http://{ip}{port}{base_url}", token=token)
        if load_config:
            self.update_defaults_from_yaml(
                yamlfilename, __class__.__name__, board_name=board_name
            )

    def interface(self):
        return self.nb

    def get_mac_from_asset_tag(self, asset_tag):
        dev = self.nb.dcim.devices.get(asset_tag=asset_tag)
        if not dev:
            raise Exception(f"No devices for with asset tag: {asset_tag}")
        intf = self.nb.dcim.interfaces.get(device_id=dev.id)
        return intf.mac_address

    def get_devices_name(self, include_variants=False, **filters):
        devices = self.nb.dcim.devices.filter(**filters)
        devices_names = list()
        for device in devices:
            device_dict = dict(device)
            if include_variants:
                if "variants" in device_dict["config_context"]:
                    for type in device_dict["config_context"]["variants"]:
                        if ddepth(device_dict["config_context"]["variants"][type]) == 3:
                            for variant in device_dict["config_context"]["variants"][
                                type
                            ]:
                                devices_names.append(
                                    device_dict["name"] + "-" + type + "-v" + variant
                                )
                        else:
                            # type is a variant
                            devices_names.append(device_dict["name"] + "-v" + type)
                    continue
            devices_names.append(device_dict["name"])
        return devices_names

    def get_devices(self, **filters):
        if not filters:
            return [dict(device) for device in self.nb.dcim.devices.all()]
        return [dict(device) for device in self.nb.dcim.devices.filter(**filters)]

    def get_console_ports(self, **filters):
        if not filters:
            return [dict(device) for device in self.nb.dcim.console_ports.all()]
        return [dict(cp) for cp in self.nb.dcim.console_ports.filter(**filters)]

    def get_interfaces(self, **filters):
        if not filters:
            return [dict(device) for device in self.nb.dcim.interfaces.all()]
        return [dict(inf) for inf in self.nb.dcim.interfaces.filter(**filters)]

    def get_ip_addresses(self, **filters):
        if not filters:
            return [dict(device) for device in self.nb.ipam.ip_addresses.all()]
        return [dict(ip) for ip in self.nb.ipam.ip_addresses.filter(**filters)]

    def get_power_ports(self, **filters):
        if not filters:
            return [dict(device) for device in self.nb.dcim.power_ports.all()]
        return [dict(pow) for pow in self.nb.dcim.power_ports.filter(**filters)]

    def get_power_outlets(self, **filters):
        if not filters:
            return [dict(device) for device in self.nb.dcim.power_outlets.all()]
        return [dict(out) for out in self.nb.dcim.power_outlets.filter(**filters)]

    def get_clusters(self, **filters):
        if not filters:
            return [dict(device) for device in self.nb.virtualization.clusters.all()]
        return [dict(out) for out in self.nb.virtualization.clusters.filter(**filters)]


class NetboxDevice:
    """Netbox Device Model"""

    def __init__(self, netbox_interface, device_name, dtype=None, variant=None):

        self.data = dict()
        self.nbi = netbox_interface
        self.data_object = object()
        self.type_list = ["rx2tx2"]
        self.device_type = None
        self.device_variant = None

        log.info("Creating model for {}".format(device_name))

        #  check if device is variant
        if len(device_name.split("-v")) == 2:
            if not variant:
                variant = device_name.split("-v")[1]
            device_name = device_name.split("-v")[0]

        if not dtype:
            if device_name.split("-")[-1] in self.type_list:
                dtype = device_name.split("-")[-1]

        if dtype:
            device_name = device_name.split("-" + dtype)[0]

        dev_raw = self.nbi.get_devices(name=device_name)
        if len(dev_raw) != 1:
            raise Exception(
                f"Either {device_name} is not found or has multiple netbox entry"
            )

        self.data.update({"devices": dev_raw[0]})

        # get associated console ports
        cp_raw = self.nbi.get_console_ports(device_id=self.data["devices"]["id"])
        self.data["devices"].update({"console_ports": dict()})
        for port in cp_raw:
            self.data["devices"]["console_ports"].update({port["name"]: port})

        # get associated interfaces
        inf_raw = self.nbi.get_interfaces(device_id=self.data["devices"]["id"])
        self.data["devices"].update({"interfaces": dict()})
        for inf in inf_raw:
            inf_name = inf["name"]
            if bool(inf["mgmt_only"]):
                inf_name = "mgmt"

            # add ip information
            ip_raw = self.nbi.get_ip_addresses(interface_id=inf["id"])
            inf.update({"ip": ip_raw[0]})
            self.data["devices"]["interfaces"].update({inf_name: inf})

        # get associated power ports
        pow_raw = self.nbi.get_power_ports(device_id=self.data["devices"]["id"])
        self.data["devices"].update({"power_ports": dict()})
        for pow in pow_raw:
            # get associated oulet
            outlet_id = pow["connected_endpoint"]["id"]
            outlet = self.nbi.get_power_outlets(id=outlet_id)
            pow["connected_endpoint"]["outlet"] = outlet[0]["custom_fields"]["outlet"]

            # get ip of pdu
            pdu_raw = self.nbi.get_devices(id=pow["connected_endpoint"]["device"]["id"])
            pow["pdus"] = list()
            for pdu in pdu_raw:
                pow["pdus"].append(pdu)

            self.data["devices"]["power_ports"].update({"input": pow})

        # update for type/variant
        if "variants" in self.data["devices"]["config_context"]:
            variants_dict = self.data["devices"]["config_context"]["variants"]

            if dtype:
                if dtype in variants_dict:
                    log.info(f"Processing for type {dtype}")
                    variants_dict = variants_dict[dtype]
                    device_name = device_name + "-" + dtype
                else:
                    raise Exception(f"Type {dtype} not defined")

            if variant:
                if variant in variants_dict:
                    log.info(f"Processing for variant {variant}")
                    if variants_dict[variant] == "default":
                        self.data["devices"]["variant_data"] = None
                    else:
                        self.data["devices"]["variant_data"] = json.dumps(
                            variants_dict[variant]
                        )
                    device_name = device_name + "-v" + variant
                else:
                    raise Exception(f"Variant {variant} not defined")

            self.data["devices"]["name"] = device_name

        data_object = obj_dic(self.data)
        self.__dict__.update(data_object.__dict__.copy())

    def to_config(self, template):  # noqa: C901
        log.info("Generating config for {}".format(self.devices.name))
        template_dict = dict()
        required_fields = list()
        if template:
            for name, section in template.items():
                template_dict[name] = dict()
                for field in section.values():
                    try:
                        value = None
                        if "netbox_field" in field:
                            value = eval("self." + field["netbox_field"])

                            # check for Null/None values
                            if str(value) == "None":
                                raise Exception(
                                    "None value not valid for {}".format(field["name"])
                                )

                            # check if value is a valid option
                            if (
                                "options" in field
                                and str(value) not in field["options"]
                            ):
                                if (
                                    "optional" in field
                                    and bool(field["optional"]) is False
                                ):
                                    raise Exception(
                                        "value {} not in valid options {}".format(
                                            value, field["options"]
                                        )
                                    )

                            # convert value to list if csv
                            if isinstance(value, str) and len(value.split(",")) > 1:
                                value = value.split(",")

                            # extract ip from cidr
                            if isinstance(value, str) and len(value.split("/")) == 2:
                                value = value.split("/")[0]
                        else:
                            raise Exception(
                                "netbox_field undefined for {}:{}".format(
                                    name, field["name"]
                                )
                            )

                        template_dict[name][field["name"]] = value

                    except Exception as ex:
                        if "optional" in field and bool(field["optional"]) is True:
                            log.warning(str(ex) + "." + " Skipping since optional")
                            continue

                        if "default" in field:
                            template_dict[name][field["name"]] = field["default"]
                            log.warning(str(ex) + "." + " Will try to use default")
                            continue

                        log.error("Cannot parse {}".format(field["name"]))
                        raise Exception("Template mapping failed")
                    finally:
                        # check if field had some required fields
                        if "requires" in field:
                            answer = field["requires"].split(":")[0]
                            if value == answer:
                                for rf in field["requires"].split(":")[1].split(","):
                                    required_fields.append((name, rf))

                # remove empty sections
                if not template_dict[name]:
                    del template_dict[name]

        # check for required fields
        for r_sec, r_field in required_fields:
            try:
                value = template_dict[r_sec][r_field]
                log.info("{}{} with value {} exists".format(r_sec, r_field, value))
            except Exception:
                log.error(
                    "A required field {}{} cannot be found".format(r_sec, r_field)
                )
                raise Exception("Template mapping failed")

        # update for variant
        if hasattr(self.devices, "variant_data"):
            if self.devices.variant_data:
                for sctn_name, fld in json.loads(self.devices.variant_data).items():
                    for fld_name, fld_val in fld.items():
                        if sctn_name not in template_dict:
                            template_dict[sctn_name] = dict()
                        template_dict[sctn_name][fld_name] = fld_val

        # convert to fields to list
        template_dict_list = dict()
        for sctn, flds in template_dict.items():
            template_dict_list[sctn] = [{fld: fld_val} for fld, fld_val in flds.items()]

        return template_dict_list


class NetboxDevices:
    """List of NetboxDevice"""

    def __init__(self, ni, status="active", role="fpga_dut", agent=None):
        # get cluster agent
        dut_bank_id = None
        for cluster in ni.get_clusters():
            if (
                "custom_fields" in cluster
                and "cluster_agent" in cluster["custom_fields"]
            ):
                if cluster["custom_fields"]["cluster_agent"] == agent:
                    dut_bank_id = cluster["id"]
                    break
            else:
                log.warning("cluster agent not defined")

        if agent and not dut_bank_id:
            raise Exception(f"Cannot find agent {agent}")

        # get devices
        kwargs = dict()
        if dut_bank_id:
            kwargs["cluster_id"] = dut_bank_id

        kwargs["role_name"] = role
        kwargs["status"] = status

        devices_names = ni.get_devices_name(include_variants=True, **kwargs)

        self.devices = [NetboxDevice(ni, dev) for dev in devices_names]

    def generate_config(self, template=None):
        template_dict = dict()
        for dev in self.devices:
            template_dict.update({dev.devices.name: dev.to_config(template)})

        return template_dict
