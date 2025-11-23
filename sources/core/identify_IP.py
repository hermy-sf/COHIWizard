from scapy.all import ARP, Ether, srp, sniff

def find_linklocal_devices(interface="eth0"):
    # ARP-Scan für 169.254.0.0/16
    arp = ARP(pdst="169.254.0.0/16")
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")
    result = srp(ether/arp, timeout=2, iface=interface, verbose=False)[0]

    devices = []
    for _, rcv in result:
        devices.append((rcv.psrc, rcv.hwsrc))  # (IP, MAC)

    return devices

#devices = find_linklocal_devices("eth0")
#print(devices)

#from scapy.all import sniff, ARP

def listen_for_redpitaya(timeout=10):
    devices = []
    def handler(pkt):
        if ARP in pkt and pkt[ARP].op == 2:  # ARP reply or gratuitous ARP
            devices.append((pkt[ARP].psrc, pkt[ARP].hwsrc))

    sniff(filter="arp", prn=handler, timeout=timeout)
    return devices

#print(listen_for_redpitaya())


def get_arp_table():
    devices = []
    with open("/proc/net/arp") as f:
        next(f)  # skip header
        for line in f:
            parts = line.split()
            ip = parts[0]
            mac = parts[3]
            devices.append((ip, mac))
    return devices

print(get_arp_table())

import re
import ipaddress

def valid_mac(mac):
    """Check if MAC is valid and not all zeros."""
    if mac.lower() == "00:00:00:00:00:00":
        return False
    # basic MAC validation pattern
    return bool(re.match(r"([0-9a-f]{2}:){5}[0-9a-f]{2}$", mac.lower()))

def is_linklocal(ip):
    """Check if IP is in 169.254.x.y (link-local range)."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_link_local
    except ValueError:
        return False

def read_arp_linklocal(filter_oui=None):
    """
    Returns list of (IP, MAC) pairs:
    - IP is 169.254.x.y
    - MAC is valid
    - optional: MAC starts with one of the given OUIs
    """
    results = []

    with open("/proc/net/arp") as f:
        next(f)  # skip header
        for line in f:
            parts = line.split()
            ip = parts[0]
            mac = parts[3].lower()

            if not is_linklocal(ip):
                continue
            if not valid_mac(mac):
                continue

            # OUI filter (optional)
            if filter_oui:
                if not any(mac.startswith(prefix.lower()) for prefix in filter_oui):
                    continue

            results.append((ip, mac))

    return results


# Beispiel: MAC-Präfixe für Red Pitaya (je nach Modell unterschiedlich)
redpitaya_ouis = [
    "00:26:32",
    "3c:2c:30",
    "b8:27:eb"   # manche Geräte basieren auf RPi-Boards
]

redpitaya_ouis = [
    "00:26:32",
    "3c:2c:30",
    "b8:27:eb"   # manche Geräte basieren auf RPi-Boards
]

devices = read_arp_linklocal(filter_oui=redpitaya_ouis)

print("Gefundene Red Pitayas:")
for ip, mac in devices:
    print(f"{ip}  →  {mac}")


