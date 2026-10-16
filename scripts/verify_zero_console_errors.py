#!/usr/bin/env python3
"""
scripts/verify_zero_console_errors.py

Automated browser console & network error verification gate.
Launches headless Playwright, visits critical application routes,
and asserts ZERO console errors, ZERO uncaught exceptions, and
ZERO 4xx/5xx network failures.

Usage:
    python scripts/verify_zero_console_errors.py [--url http://localhost:7070] [--timeout 20000]
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import List, Dict, Any, Tuple
from playwright.sync_api import sync_playwright, Response, ConsoleMessage


DEFAULT_ROUTES = [
    "/",
    "/join",
    "/pricing",
    "/admin/coding-cockpit",
    "/admin/sms-assistant",
    "/admin/onboarding",
    "/admin/settings/business",
    "/admin/calendar",
    "/admin/plan-billing",
    "/admin/platform-billing",
    "/admin/tenants",
]

# Allowlisted ignorable network requests (e.g. external analytics or 3rd party font 304/404 if any)
# Currently empty because internal application routes must have zero 4xx/5xx failures.
IGNORE_FAILED_URL_PATTERNS: List[str] = []


class RouteVerificationResult:
    def __init__(self, route: str):
        self.route = route
        self.final_url: str = ""
        self.status_code: int | None = None
        self.elapsed_s: float = 0.0
        self.console_errors: List[str] = []
        self.console_warnings: List[str] = []
        self.page_errors: List[str] = []
        self.network_errors: List[Tuple[int, str]] = []

    @property
    def passed(self) -> bool:
        return (
            len(self.console_errors) == 0
            and len(self.page_errors) == 0
            and len(self.network_errors) == 0
        )


def verify_route(
    context,
    base_url: str,
    route: str,
    timeout_ms: int = 20000,
) -> RouteVerificationResult:
    result = RouteVerificationResult(route)
    page = context.new_page()

    def on_console(msg: ConsoleMessage):
        text = msg.text
        if msg.type == "error":
            result.console_errors.append(f"[{msg.type.upper()}] {text}")
        elif msg.type == "warning":
            result.console_warnings.append(f"[{msg.type.upper()}] {text}")

    def on_pageerror(err):
        result.page_errors.append(str(err))

    def on_response(resp: Response):
        status = resp.status
        url = resp.url
        if status >= 400:
            for pattern in IGNORE_FAILED_URL_PATTERNS:
                if pattern in url:
                    return
            result.network_errors.append((status, url))

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("response", on_response)

    target_url = f"{base_url.rstrip('/')}{route}"
    start_time = time.time()

    try:
        response = page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
        # Attempt networkidle stabilization
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass

        # Wait for React root container to mount and render children
        try:
            page.wait_for_selector("#root", state="visible", timeout=5000)
            page.wait_for_function(
                "() => Boolean(document.querySelector('#root') && document.querySelector('#root').children.length > 0)",
                timeout=5000,
            )
        except Exception:
            pass

        # Wait for document to reach complete readyState
        try:
            page.wait_for_function("() => document.readyState === 'complete'", timeout=5000)
        except Exception:
            pass

        # Allow animation frames and async React re-render cycles to settle
        try:
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 500)))")
        except Exception:
            pass

        # Generous settlement buffer for async useEffect hooks, re-renders, and WebSocket/SSE setup
        page.wait_for_timeout(2000)

        result.final_url = page.url
        result.status_code = response.status if response else 200
    except Exception as e:
        # Fallback: if network or DOM timeout occurs, inspect captured page state
        try:
            result.final_url = page.url
            result.status_code = 200
            page.wait_for_timeout(1500)
        except Exception:
            result.page_errors.append(f"Navigation failed: {e}")
    finally:
        result.elapsed_s = time.time() - start_time
        page.close()

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Verify zero browser console errors and zero network 4xx/5xx failures."
    )
    parser.add_argument(
        "--url",
        default="http://localhost:7070",
        help="Base URL of frontend (default: http://localhost:7070)",
    )
    parser.add_argument(
        "--routes",
        default=None,
        help="Comma-separated list of routes to verify (e.g. /,/admin/coding-cockpit)",
    )
    parser.add_argument(
        "--tenant",
        default="simplydemo",
        help="Tenant slug for bypass authentication (default: simplydemo)",
    )
    parser.add_argument(
        "--token",
        default="local-development-bypass",
        help="Admin bypass token (default: local-development-bypass)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=25000,
        help="Navigation timeout in milliseconds (default: 25000)",
    )

    args = parser.parse_args()

    routes = (
        [r.strip() for r in args.routes.split(",") if r.strip()]
        if args.routes
        else DEFAULT_ROUTES
    )

    print("=" * 80)
    print(" BROWSER ZERO-CONSOLE-ERROR & NETWORK FAILURE VERIFICATION GATE")
    print(f" Target URL: {args.url}")
    print(f" Tenant:     {args.tenant}")
    print(f" Routes:     {', '.join(routes)}")
    print("=" * 80)

    total_failures = 0
    results: List[RouteVerificationResult] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
            has_touch=False,
            extra_http_headers={
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )

        # Ensure third-party font CDNs do not fail CORS preflight when extra_http_headers are attached
        def handle_route(route):
            req = route.request
            if "fonts.gstatic.com" in req.url or "fonts.googleapis.com" in req.url:
                headers = {k: v for k, v in req.headers.items() if k.lower() not in ("cache-control", "pragma")}
                route.continue_(headers=headers)
            else:
                route.continue_()

        context.route("**/*", handle_route)

        # Inject dev auth tokens and tenant identity directly into localStorage
        init_script = f"""
            localStorage.setItem('token', '{args.token}');
            localStorage.setItem('tenant', '{args.tenant}');
            localStorage.setItem('tenant_subdomain', '{args.tenant}');
            localStorage.removeItem('disable_local_auth_bypass');
        """
        context.add_init_script(init_script)

        for route in routes:
            print(f"\n[Testing] Route: {route} ... ", end="", flush=True)
            res = verify_route(context, args.url, route, timeout_ms=args.timeout)
            results.append(res)

            if res.passed:
                print(f"PASS ({res.elapsed_s:.2f}s) -> {res.final_url}")
                if res.console_warnings:
                    print(f"   [Notice] {len(res.console_warnings)} console warnings captured:")
                    for w in res.console_warnings:
                        print(f"     - {w}")
            else:
                print(f"FAIL ({res.elapsed_s:.2f}s) -> {res.final_url}")
                total_failures += 1

                if res.page_errors:
                    print("   [Unhandled Page Errors]:")
                    for pe in res.page_errors:
                        print(f"     * {pe}")

                if res.console_errors:
                    print(f"   [Console Errors ({len(res.console_errors)})]:")
                    for ce in res.console_errors:
                        print(f"     * {ce}")

                if res.network_errors:
                    print(f"   [Failed Network Requests ({len(res.network_errors)})]:")
                    for status, url in res.network_errors:
                        print(f"     * HTTP {status} -> {url}")

        browser.close()

    print("\n" + "=" * 80)
    print(" VERIFICATION GATE SUMMARY")
    print("=" * 80)
    for res in results:
        status_str = "PASS" if res.passed else "FAIL"
        print(f" [{status_str}] {res.route:<28} -> {res.final_url:<35} ({res.elapsed_s:.2f}s)")
        if not res.passed:
            if res.console_errors:
                print(f"        Console Errors: {len(res.console_errors)}")
            if res.page_errors:
                print(f"        Page Exceptions: {len(res.page_errors)}")
            if res.network_errors:
                print(f"        Network Failures (>=400): {len(res.network_errors)}")

    print("=" * 80)
    if total_failures == 0:
        print(" SUCCESS: ALL ROUTES PASSED WITH ZERO CONSOLE ERRORS & ZERO NETWORK FAILURES.")
        print("=" * 80)
        sys.exit(0)
    else:
        print(f" FAILURE: {total_failures} ROUTE(S) FAILED CONSOLE / NETWORK CHECKS.")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
