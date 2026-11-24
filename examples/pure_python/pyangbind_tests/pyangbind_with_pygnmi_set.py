#!/usr/bin/env python

# Modules
from pygnmi.client import gNMIclient
import json
from binding import Cisco_IOS_XR_ifmgr_cfg
import pyangbind.lib.pybindJSON as pybindJSON

host=('192.0.2.1','57400')

ifmgr=Cisco_IOS_XR_ifmgr_cfg()

intf=ifmgr.interface_configurations.interface_configuration.add(active="act",interface_name="Optics0/2/0/0")
intf.secondary_admin_state='maintenance'
intf.shutdown=True

pybindJSON.dump(ifmgr,"test.json",mode="ietf")
fn=open("test.json")
data=json.load(fn)
set_list = [(k, v) for k, v in data.items()]

if __name__ == '__main__':
    with gNMIclient(target=host, username='admin',password='admin', path_cert='/path/to/target-cert.pem',override='target.example.net',debug=True) as gc:
        result = gc.set(update=set_list,encoding='json_ietf')
        print(result)

