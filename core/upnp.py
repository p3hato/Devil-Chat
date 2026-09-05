import socket
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from typing import Optional, Tuple

PUBLIC_IP_PROVIDERS = [
    "https://api.ipify.org",
    "https://checkip.amazonaws.com",
    "https://ifconfig.me/ip"
]

def get_public_ip(timeout: float = 2.5) -> Optional[str]:
    """
    Attempts to discover the host's public Internet IPv4 address.
    Fast and safe with short timeout; returns None if offline or blocked.
    """
    for url in PUBLIC_IP_PROVIDERS:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                ip = response.read().decode("utf-8").strip()
                # Simple sanity check for IPv4
                parts = ip.split(".")
                if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                    return ip
        except Exception:
            continue
    return None

class UPnPManager:
    """
    Pure Python standard-library UPnP IGD client.
    Attempts automatic port forwarding on home routers without external tools.
    """
    def __init__(self):
        self.control_url: Optional[str] = None
        self.service_type: Optional[str] = None
        self._discovered = False

    def discover(self, timeout: float = 2.0) -> bool:
        """Discovers UPnP router control URL using SSDP broadcast."""
        if self._discovered:
            return bool(self.control_url)

        ssdp_req = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            "MAN: \"ssdp:discover\"\r\n"
            "MX: 2\r\n"
            "ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n"
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.settimeout(timeout)

        location = None
        try:
            sock.sendto(ssdp_req.encode("utf-8"), ("239.255.255.250", 1900))
            while True:
                data, _ = sock.recvfrom(2048)
                resp = data.decode("utf-8", errors="replace")
                for line in resp.splitlines():
                    if line.upper().startswith("LOCATION:"):
                        location = line.split(":", 1)[1].strip()
                        break
                if location:
                    break
        except Exception:
            pass
        finally:
            sock.close()

        if not location:
            self._discovered = True
            return False

        # Parse IGD descriptor XML
        try:
            req = urllib.request.Request(location, headers={"User-Agent": "DEVIL_CHAT/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as res:
                xml_data = res.read()

            root = ET.fromstring(xml_data)
            parsed_url = urlparse(location)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

            # Search for WANIPConnection or WANPPPConnection service
            for service in root.iter("{urn:schemas-upnp-org:device-1-0}service"):
                st = service.findtext("{urn:schemas-upnp-org:device-1-0}serviceType")
                if st and ("WANIPConnection" in st or "WANPPPConnection" in st):
                    ctrl = service.findtext("{urn:schemas-upnp-org:device-1-0}controlURL")
                    if ctrl:
                        self.control_url = ctrl if ctrl.startswith("http") else base_url + ctrl
                        self.service_type = st
                        self._discovered = True
                        return True
        except Exception:
            pass

        self._discovered = True
        return False

    def forward_port(self, local_ip: str, port: int, desc: str = "DEVIL CHAT") -> bool:
        """Requests the router to forward 'port' to 'local_ip'."""
        if not self.discover():
            return False

        soap_body = f"""<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body>
<u:AddPortMapping xmlns:u="{self.service_type}">
  <NewRemoteHost></NewRemoteHost>
  <NewExternalPort>{port}</NewExternalPort>
  <NewProtocol>TCP</NewProtocol>
  <NewInternalPort>{port}</NewInternalPort>
  <NewInternalClient>{local_ip}</NewInternalClient>
  <NewEnabled>1</NewEnabled>
  <NewPortMappingDescription>{desc}</NewPortMappingDescription>
  <NewLeaseDuration>0</NewLeaseDuration>
</u:AddPortMapping>
</s:Body>
</s:Envelope>"""

        headers = {
            "SOAPAction": f'"{self.service_type}#AddPortMapping"',
            "Content-Type": "text/xml; charset=\"utf-8\""
        }

        try:
            req = urllib.request.Request(self.control_url, data=soap_body.encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def release_port(self, port: int) -> bool:
        """Releases the forwarded port from the router."""
        if not self.control_url or not self.service_type:
            return False

        soap_body = f"""<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body>
<u:DeletePortMapping xmlns:u="{self.service_type}">
  <NewRemoteHost></NewRemoteHost>
  <NewExternalPort>{port}</NewExternalPort>
  <NewProtocol>TCP</NewProtocol>
</u:DeletePortMapping>
</s:Body>
</s:Envelope>"""

        headers = {
            "SOAPAction": f'"{self.service_type}#DeletePortMapping"',
            "Content-Type": "text/xml; charset=\"utf-8\""
        }

        try:
            req = urllib.request.Request(self.control_url, data=soap_body.encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:
            return False
