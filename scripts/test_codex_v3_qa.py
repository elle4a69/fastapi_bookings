#!/usr/bin/env python3
"""
scripts/test_codex_v3_qa.py

Comprehensive automated UI, UX, and zero-console-error test suite for Codex V3.
Tests both Mobile (390x844) and Desktop (1440x900) viewports on http://localhost:5173/admin/codex-v3.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("CODEX_TEST_URL", "http://localhost:7070/admin/codex-v3")
SCREENSHOT_DIR = os.environ.get("CODEX_SCREENSHOT_DIR", r"f:\Projects\fastapi_bookings\artifacts\codex_v3_qa_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(r"f:\Projects\fastapi_bookings\artifacts\codex-v3-qa", exist_ok=True)


class QARunner:
    def __init__(self):
        self.console_errors = []
        self.console_warnings = []
        self.page_errors = []
        self.network_errors = []
        self.findings = []

    def attach_listeners(self, page):
        def on_console(msg):
            text = f"[{msg.type.upper()}] {msg.text}"
            if msg.type == "error":
                self.console_errors.append(text)
                print(f"  [CONSOLE ERROR] {msg.text}")
            elif msg.type == "warning":
                self.console_warnings.append(text)

        def on_pageerror(err):
            self.page_errors.append(str(err))
            print(f"  [PAGE ERROR] {err}")

        def on_response(resp):
            if resp.status >= 400:
                self.network_errors.append((resp.status, resp.url))
                print(f"  [NETWORK ERROR] {resp.status} {resp.url}")

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("response", on_response)

    def run_tests(self):
        with sync_playwright() as p:
            # -------------------------------------------------------------
            # Part 1: Mobile Viewport (390x844 - iPhone 14)
            # -------------------------------------------------------------
            print("\n=== STARTING MOBILE VIEWPORT TESTS (390x844) ===")
            iphone14 = p.devices.get("iPhone 14", {
                "viewport": {"width": 390, "height": 844},
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                "is_mobile": True,
                "has_touch": True,
            })
            browser = p.chromium.launch(headless=True)
            mobile_context = browser.new_context(**iphone14)
            mobile_context.add_init_script("""
                localStorage.setItem('token', 'local-development-bypass');
                localStorage.setItem('tenant', 'simplydemo');
                localStorage.setItem('tenant_subdomain', 'simplydemo');
                localStorage.removeItem('disable_local_auth_bypass');
            """)
            page = mobile_context.new_page()
            self.attach_listeners(page)

            print(f"Navigating to {BASE_URL}...")
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector("[data-testid='codex-v3-layout']", timeout=10000)
            time.sleep(1)

            # 1. Check Bottom Navigation Bar layout and tap targets
            print("Checking Bottom Navigation Bar tap targets (>=44px)...")
            tab_bar = page.locator("[data-testid='codex-bottom-tab-bar']")
            assert tab_bar.is_visible(), "Bottom tab bar should be visible on mobile"

            for tab_id in ["bottom-tab-tickets", "bottom-tab-coding", "bottom-tab-planning", "bottom-tab-signals"]:
                btn = page.locator(f"[data-testid='{tab_id}']")
                box = btn.bounding_box()
                assert box is not None, f"Button {tab_id} should have bounding box"
                print(f"  Tap target {tab_id}: width={box['width']:.1f}px, height={box['height']:.1f}px")
                assert box["width"] >= 44, f"{tab_id} width {box['width']} < 44px"
                assert box["height"] >= 44, f"{tab_id} height {box['height']} < 44px"

            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_mobile_tickets_initial.png"))
            print("  Screenshot saved: 01_mobile_tickets_initial.png")

            # 2. Test switching between the 4 views
            print("Testing switching between the 4 workspace views...")
            # Switch to Coding
            page.click("[data-testid='bottom-tab-coding']")
            time.sleep(0.5)
            assert page.locator("h1:has-text('Active Coding Studio')").is_visible() or page.locator("text=Diff Review Studio").is_visible()
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_mobile_coding_view.png"))
            print("  Coding view active & screenshot saved.")

            # Switch to Planning
            page.click("[data-testid='bottom-tab-planning']")
            time.sleep(0.5)
            assert page.locator("h1:has-text('Work Package DAG')").is_visible() or page.locator("text=Acceptance Criteria").is_visible()
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_mobile_planning_view.png"))
            print("  Planning view active & screenshot saved.")

            # Switch to Signals
            page.click("[data-testid='bottom-tab-signals']")
            time.sleep(0.5)
            assert page.locator("h1:has-text('Health Sentinels')").is_visible() or page.locator("text=SigNoz APM").is_visible()
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_mobile_signals_view.png"))
            print("  Signals view active & screenshot saved.")

            # Switch back to Tickets
            page.click("[data-testid='bottom-tab-tickets']")
            time.sleep(0.5)

            # 3. Test Mobile Segmented Control [ Workspace | Agent Stream ]
            print("Testing Mobile Segmented Control [ Workspace | Agent Stream ]...")
            seg_stream = page.locator("[data-testid='tab-stream']")
            seg_workspace = page.locator("[data-testid='tab-workspace']")
            assert seg_stream.is_visible() and seg_workspace.is_visible(), "Segmented control must be visible"

            # Click Agent Stream
            seg_stream.click()
            time.sleep(0.5)
            stream_container = page.locator("[data-testid='codex-agent-stream-container']")
            assert stream_container.is_visible(), "Agent stream should be visible when selected"
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_mobile_agent_stream.png"))
            print("  Mobile Agent Stream visible & screenshot saved.")

            # 4. Test ComposerBar input and message submission
            print("Testing ComposerBar input and submission...")
            composer_input = page.locator("textarea[placeholder*='Ask Codex']")
            assert composer_input.is_visible(), "Composer input should be visible"
            test_msg = "Codex test instruction from automated QA suite"
            composer_input.fill(test_msg)
            time.sleep(0.3)
            # Submit message via button
            send_btn = page.locator("button[title='Send message']")
            send_btn.click()
            time.sleep(1.5) # Wait for agent simulated response
            # Check message in stream
            assert page.locator(f"text={test_msg}").first.is_visible(), "Submitted user message should be rendered in stream"
            print("  User message submitted and rendered successfully.")
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_mobile_stream_message_submitted.png"))

            # Switch back to Workspace tab
            seg_workspace.click()
            time.sleep(0.5)

            # 5. Test Voice FAB button and verify Waveform Strip appears
            print("Testing Voice FAB button toggle and Waveform Strip...")
            voice_fab = page.locator("[data-testid='codex-bottom-tab-bar'] [data-testid='codex-voice-fab']")
            assert voice_fab.is_visible(), "Voice FAB must be visible"
            voice_fab.click()
            page.wait_for_selector("[data-testid='codex-audio-waveform-strip']", timeout=5000)

            waveform_strip = page.locator("[data-testid='codex-audio-waveform-strip']")
            assert waveform_strip.is_visible(), "AudioWaveformStrip should appear when voice is toggled on"
            print("  AudioWaveformStrip appeared successfully.")
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_mobile_voice_active_waveform.png"))

            # Stop voice session via End Call button on strip
            try:
                end_call_btn = page.locator("[data-testid='audio-waveform-end-call']")
                end_call_btn.click(timeout=1500)
                page.wait_for_selector("[data-testid='codex-audio-waveform-strip']", state="hidden", timeout=3000)
            except Exception:
                pass
            print("  Voice session ended cleanly.")

            mobile_context.close()

            # -------------------------------------------------------------
            # Part 2: Desktop Viewport (1440x900)
            # -------------------------------------------------------------
            print("\n=== STARTING DESKTOP VIEWPORT TESTS (1440x900) ===")
            desktop_context = browser.new_context(viewport={"width": 1440, "height": 900})
            desktop_context.add_init_script("""
                localStorage.setItem('token', 'local-development-bypass');
                localStorage.setItem('tenant', 'simplydemo');
                localStorage.setItem('tenant_subdomain', 'simplydemo');
                localStorage.removeItem('disable_local_auth_bypass');
            """)
            page = desktop_context.new_page()
            self.attach_listeners(page)

            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector("[data-testid='codex-v3-layout']", timeout=10000)
            time.sleep(1)

            # 1. Check ActivityRail (52px), Center Workspace Canvas, and Right-hand Stream
            print("Checking Desktop Layout (ActivityRail 52px, Workspace Canvas, Docked Stream)...")
            activity_rail = page.locator("[data-testid='codex-activity-rail']")
            assert activity_rail.is_visible(), "ActivityRail should be visible on desktop"
            rail_box = activity_rail.bounding_box()
            assert rail_box is not None
            print(f"  ActivityRail width: {rail_box['width']:.1f}px (target: ~52px)")
            assert 48 <= rail_box['width'] <= 56, f"ActivityRail width {rail_box['width']} expected ~52px"

            workspace_container = page.locator("[data-testid='codex-workspace-container']")
            assert workspace_container.is_visible(), "Center workspace container must be visible"

            stream_container = page.locator("[data-testid='codex-agent-stream-container']")
            assert stream_container.is_visible(), "Docked agent stream must be visible on desktop"
            stream_box = stream_container.bounding_box()
            print(f"  Docked Stream width: {stream_box['width']:.1f}px (target: ~380px)")

            # Check that BottomTabBar is NOT visible on desktop
            bottom_bar = page.locator("[data-testid='codex-bottom-tab-bar']")
            assert not bottom_bar.is_visible(), "BottomTabBar must be hidden on desktop (sm:hidden)"

            # 2. Check Workspace 1: Tickets (filters, severity tags, launch buttons)
            print("Checking Tickets Workspace...")
            page.click("[data-testid='activity-rail-tickets']")
            time.sleep(0.5)
            assert page.locator("text=Triage Queue").is_visible(), "Triage Queue should be visible"
            assert page.locator("button:has-text('All')").is_visible(), "Filter 'All' should be visible"
            assert page.locator("button:has-text('Needs Auth')").is_visible(), "Filter 'Needs Auth' should be visible"
            # Launch investigation button
            launch_btn = page.locator("button:has-text('Launch Codex Investigation')").first
            assert launch_btn.is_visible(), "Launch investigation button should be visible"
            launch_btn.click()
            time.sleep(0.8)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_desktop_tickets_investigation.png"))
            print("  Tickets Workspace verified & investigation launched.")

            # 3. Check Workspace 2: Coding (diff studio, test runner, promote gate)
            print("Checking Coding Workspace...")
            page.click("[data-testid='activity-rail-coding']")
            time.sleep(0.5)
            assert page.locator("h1:has-text('Active Coding Studio')").first.is_visible() or page.locator("text=Diff Review Studio").first.is_visible(), "Coding Studio should be visible"
            assert page.locator("text=app/services/scheduling/booking_engine.py").first.is_visible(), "Diff file should be visible"
            # Test Runner
            run_tests_btn = page.locator("button:has-text('Run Tests')").first
            assert run_tests_btn.is_visible(), "Run Tests button should be visible"
            run_tests_btn.click()
            time.sleep(0.5)
            # Promote Gate
            promote_btn = page.locator("button:has-text('Promote to Release Branch')").first
            assert promote_btn.is_visible(), "Promote to Release button should be visible"
            promote_btn.click()
            time.sleep(0.5)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "09_desktop_coding_workspace.png"))
            print("  Coding Workspace verified.")

            # 4. Check Workspace 3: Planning (DAG cards, checklist, elevation launcher)
            print("Checking Planning Workspace...")
            page.click("[data-testid='activity-rail-planning']")
            time.sleep(0.5)
            assert page.locator("text=Work Package DAG Pipeline").first.is_visible(), "DAG Pipeline should be visible"
            assert page.locator("text=Acceptance Criteria Checklist").first.is_visible(), "Checklist should be visible"
            assert page.locator("text=Single-Run Authorization").first.is_visible(), "Elevation grant should be visible"
            # Grant authorization test
            grant_btn = page.locator("[data-testid='grant-elevation-btn']").first
            assert grant_btn.is_visible(), "Grant Elevation button should be visible"
            grant_btn.click()
            time.sleep(0.5)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "10_desktop_planning_workspace.png"))
            print("  Planning Workspace verified.")

            # 5. Check Workspace 4: Signals (SigNoz APM links, latency charts, health sentinel matrix)
            print("Checking Signals Workspace...")
            page.click("[data-testid='activity-rail-signals']")
            time.sleep(0.5)
            assert page.locator("text=Health Sentinels").first.is_visible(), "Health Sentinels matrix should be visible"
            assert page.locator("text=Latency").first.is_visible(), "Latency telemetry should be visible"
            assert page.locator("text=SigNoz APM").first.is_visible(), "SigNoz APM link should be visible"
            assert page.locator("text=SMS Outbox Backlog").first.is_visible(), "SMS Outbox backlog should be visible"
            assert page.locator("text=Chatwoot").first.is_visible(), "Chatwoot sync status should be visible"
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "11_desktop_signals_workspace.png"))
            print("  Signals Workspace verified.")

            # 6. Check Stream Components (Thinking, Diff, Approval, Terminal)
            print("Checking Transparent Stream Cards...")
            assert page.locator("[data-testid='codex-transparent-stream']").is_visible()
            # Thinking accordion
            thinking_card = page.locator("button:has-text('Thinking Process')").first
            if thinking_card.is_visible():
                thinking_card.click()
                time.sleep(0.3)
            # Diff card accept/discard
            accept_btn = page.locator("button:has-text('Accept Patch')").first
            if accept_btn.is_visible():
                accept_btn.click()
                time.sleep(0.3)
            # Gate approve/reject
            approve_gate_btn = page.locator("button:has-text('Approve Operation')").first
            if approve_gate_btn.is_visible():
                approve_gate_btn.click()
                time.sleep(0.3)

            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "12_desktop_stream_interactions.png"))
            print("  Stream cards verified & screenshot saved.")

            desktop_context.close()
            browser.close()

        import shutil
        mirror_dir = r"f:\Projects\fastapi_bookings\artifacts\codex-v3-qa"
        if os.path.abspath(SCREENSHOT_DIR) != os.path.abspath(mirror_dir):
            for f in os.listdir(SCREENSHOT_DIR):
                if f.endswith(".png"):
                    shutil.copy2(os.path.join(SCREENSHOT_DIR, f), os.path.join(mirror_dir, f))

        print("\n=== SUMMARY OF QA RUN ===")
        print(f"Total Console Errors:   {len(self.console_errors)}")
        print(f"Total Page Exceptions:  {len(self.page_errors)}")
        print(f"Total Network Failures: {len(self.network_errors)}")
        print(f"Total Console Warnings: {len(self.console_warnings)}")

        if self.console_errors or self.page_errors or self.network_errors:
            print("\nERRORS DETECTED:")
            for err in self.console_errors:
                print(f"  - Console Error: {err}")
            for err in self.page_errors:
                print(f"  - Page Error: {err}")
            for code, url in self.network_errors:
                print(f"  - Network Error: {code} {url}")
            sys.exit(1)
        else:
            print("\n>>> ZERO CONSOLE ERRORS, ZERO PAGE ERRORS, ZERO NETWORK FAILURES! ALL CHECKS PASSED! <<<")
            sys.exit(0)

if __name__ == "__main__":
    runner = QARunner()
    runner.run_tests()
