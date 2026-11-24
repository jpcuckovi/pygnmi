#!/usr/bin/env python

# Modules
from pygnmi.client import gNMIclient
import json

host = ('192.0.2.1', '57400')

if __name__ == '__main__':
    with gNMIclient(target=host, username='admin', password='admin', path_cert='/path/to/target-cert.pem', override='target.example.net') as gc:
        raw_data = gc.get(path=['openconfig-interfaces:interfaces'], encoding='json_ietf')
        print(json.dumps(raw_data, sort_keys=True, indent=2))

        
