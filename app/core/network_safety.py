"""Network safety and SSRF (Server-Side Request Forgery) protection utilities.

Protects outbound HTTP requests (such as webhooks) against SSRF, DNS rebinding,
and internal network scanning by validating target URLs, schemes, hostnames, and resolved IPs.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Tuple, Optional
import urllib.parse
import httpx

logger = logging.getLogger(__name__)

# Cloud metadata and internal hostnames/suffixes to explicitly block
BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
}

BLOCKED_HOSTNAME_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".metadata.google.internal",
    ".metadata.internal",
    ".instance-data",
)

# Explicitly blocked cloud metadata and sensitive IPs
BLOCKED_EXACT_IPS = {
    ipaddress.ip_address("169.254.169.254"),  # AWS, GCP, Azure, DO, OpenStack metadata
    ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud metadata
    ipaddress.ip_address("fd00:ec2::254"),    # AWS IPv6 metadata
}

# Carrier-Grade NAT (CGNAT) 100.64.0.0/10
CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

# Allowed URL schemes
ALLOWED_SCHEMES = {"http", "https"}


def is_ip_allowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address | str) -> Tuple[bool, Optional[str]]:
    """Check whether an IP address is safe for outbound communication.
    
    Rejects:
    - Loopback (127.0.0.0/8, ::1)
    - Private (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
    - Link-local (169.254.0.0/16, fe80::/10)
    - Cloud metadata (169.254.169.254, 100.100.100.200, fd00:ec2::254)
    - Multicast (224.0.0.0/4, ff00::/8)
    - Unspecified / 0.0.0.0 / ::
    - Reserved
    - Carrier-Grade NAT (100.64.0.0/10)
    - Broadcast (255.255.255.255)
    - IPv4-mapped IPv6 targeting private/loopback addresses
    """
    if isinstance(ip, str):
        # Strip brackets if IPv6 literal format like "[::1]"
        clean_ip = ip.strip("[]")
        try:
            ip = ipaddress.ip_address(clean_ip)
        except ValueError:
            return False, f"Invalid IP address format: {ip}"

    # Check for IPv4-mapped IPv6 address (e.g. ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return is_ip_allowed(ip.ipv4_mapped)

    # Check 6to4 embedded addresses (2002::/16)
    if isinstance(ip, ipaddress.IPv6Address) and ip.sixtofour:
        return is_ip_allowed(ip.sixtofour)

    if ip in BLOCKED_EXACT_IPS:
        return False, f"Target IP {ip} is a cloud metadata service endpoint."

    if ip.is_loopback:
        return False, f"Target IP {ip} is a loopback address."

    if ip.is_private:
        return False, f"Target IP {ip} is a private network address."

    if ip.is_link_local:
        return False, f"Target IP {ip} is a link-local address."

    if ip.is_multicast:
        return False, f"Target IP {ip} is a multicast address."

    if ip.is_unspecified:
        return False, f"Target IP {ip} is an unspecified address."

    if ip.is_reserved:
        return False, f"Target IP {ip} is a reserved address."

    if isinstance(ip, ipaddress.IPv4Address):
        if ip in CGNAT_NETWORK:
            return False, f"Target IP {ip} is in Carrier-Grade NAT (CGNAT) space."
        if ip == ipaddress.IPv4Address("255.255.255.255"):
            return False, f"Target IP {ip} is a broadcast address."

    return True, None


def validate_url_safety(url: str, resolve_dns: bool = True) -> Tuple[bool, Optional[str]]:
    """Validate that a URL is safe from SSRF vulnerabilities.
    
    Args:
        url: The URL to validate.
        resolve_dns: Whether to perform DNS resolution to verify all resolved IPs.
        
    Returns:
        (is_safe, error_reason) tuple.
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string."

    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except Exception as e:
        return False, f"Malformed URL: {e}"

    # Scheme validation
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        return False, f"Disallowed URL scheme '{scheme}'. Only {sorted(ALLOWED_SCHEMES)} are permitted."

    # Hostname validation
    hostname = parsed.hostname
    if not hostname:
        return False, "URL must have a valid hostname."

    hostname_lower = hostname.lower().strip(".")

    if hostname_lower in BLOCKED_HOSTNAMES:
        return False, f"Target host '{hostname}' is not permitted."

    for suffix in BLOCKED_HOSTNAME_SUFFIXES:
        if hostname_lower.endswith(suffix):
            return False, f"Target host '{hostname}' matches prohibited internal domain suffix '{suffix}'."

    # Check if hostname is an IP literal
    try:
        ip = ipaddress.ip_address(hostname.strip("[]"))
        return is_ip_allowed(ip)
    except ValueError:
        # Not an IP literal; it's a domain name
        pass

    # If DNS resolution is requested, resolve and validate all IP addresses
    if resolve_dns:
        port = parsed.port or (443 if scheme == "https" else 80)
        try:
            addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
            if not addr_info:
                return False, f"Host '{hostname}' could not be resolved."
            
            for res in addr_info:
                sockaddr = res[4]
                resolved_ip_str = sockaddr[0]
                allowed, reason = is_ip_allowed(resolved_ip_str)
                if not allowed:
                    return False, f"Host '{hostname}' resolves to prohibited IP ({resolved_ip_str}): {reason}"
        except socket.gaierror as gaie:
            # If DNS resolution fails, reject unless it's a recognized public test host
            return False, f"DNS resolution failed for host '{hostname}': {gaie}"
        except Exception as ex:
            return False, f"DNS resolution error for host '{hostname}': {ex}"

    return True, None


def assert_safe_url(url: str, resolve_dns: bool = True) -> None:
    """Validate URL safety and raise ValueError if unsafe."""
    is_safe, reason = validate_url_safety(url, resolve_dns=resolve_dns)
    if not is_safe:
        raise ValueError(f"SSRF safety check failed: {reason}")


def create_ssrf_safe_httpx_client(**kwargs) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient with SSRF request validation on every request and redirect."""
    async def ssrf_request_hook(request: httpx.Request):
        url_str = str(request.url)
        is_safe, reason = validate_url_safety(url_str, resolve_dns=True)
        if not is_safe:
            raise ValueError(f"SSRF blocked outbound request to {request.url.host}: {reason}")

    event_hooks = kwargs.pop("event_hooks", {})
    req_hooks = list(event_hooks.get("request", []))
    req_hooks.append(ssrf_request_hook)
    event_hooks["request"] = req_hooks

    return httpx.AsyncClient(event_hooks=event_hooks, **kwargs)
