import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

from warhammer.calculator import EngagementContext, evaluate_unit
from warhammer.importers.csv_loader import load_units_from_directory
from warhammer.matchups import evaluate_unit_with_weapon_filter


ROOT = Path(__file__).resolve().parents[1]
LOCAL_HTML = ROOT / "warhammer_calculator_local.html"
CSV_DIR = ROOT / "data" / "10e" / "latest"


def _find_chrome() -> str | None:
    for name in ("chrome", "chrome.exe", "msedge", "msedge.exe"):
        found = shutil.which(name)
        if found:
            return found
    for path in (
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
    ):
        if path.exists():
            return str(path)
    return None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _read_targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as response:
        return json.loads(response.read().decode("utf-8"))


class _DevToolsWebSocket:
    def __init__(self, url: str) -> None:
        if not url.startswith("ws://"):
            raise ValueError(f"Unsupported websocket URL: {url}")
        remainder = url[len("ws://") :]
        host_port, path = remainder.split("/", 1)
        if ":" in host_port:
            host, port_text = host_port.rsplit(":", 1)
            port = int(port_text)
        else:
            host, port = host_port, 80
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.settimeout(5)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET /{path} HTTP/1.1\r\n"
            f"Host: {host_port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"WebSocket upgrade failed: {response[:120]!r}")
        self._next_id = 1

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def call(self, method: str, params: dict | None = None) -> dict:
        message_id = self._next_id
        self._next_id += 1
        self._send_text(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        deadline = time.time() + 10
        while time.time() < deadline:
            message = json.loads(self._recv_text())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message
        raise TimeoutError(f"Timed out waiting for DevTools response to {method}")

    def _send_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        if len(payload) < 126:
            header.append(0x80 | len(payload))
        elif len(payload) < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", len(payload)))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", len(payload)))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _recv_text(self) -> str:
        chunks: list[bytes] = []
        while True:
            first, second = self._recv_exact(2)
            opcode = first & 0x0F
            fin = bool(first & 0x80)
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if masked else b""
            payload = self._recv_exact(length) if length else b""
            if masked:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
            if opcode == 0x8:
                raise RuntimeError("DevTools WebSocket closed")
            if opcode in {0x1, 0x0}:
                chunks.append(payload)
                if fin:
                    return b"".join(chunks).decode("utf-8")

    def _recv_exact(self, length: int) -> bytes:
        buffer = bytearray()
        while len(buffer) < length:
            chunk = self.sock.recv(length - len(buffer))
            if not chunk:
                raise RuntimeError("Socket closed")
            buffer.extend(chunk)
        return bytes(buffer)


def _start_chrome(chrome: str, port: int, html_path: Path, user_data_dir: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--disable-background-networking",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            html_path.resolve().as_uri(),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_standalone_html_can_calculate_matchup_in_headless_browser():
    chrome = _find_chrome()
    if not chrome:
        pytest.skip("Chrome or Edge is not installed")
    if not LOCAL_HTML.exists():
        pytest.skip("warhammer_calculator_local.html has not been generated")

    port = _free_port()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as user_data:
        process = _start_chrome(chrome, port, LOCAL_HTML, Path(user_data))
        websocket = None
        try:
            target = None
            for _ in range(80):
                if process.poll() is not None:
                    pytest.fail("Headless browser exited before DevTools was ready")
                try:
                    targets = _read_targets(port)
                except Exception:
                    time.sleep(0.1)
                    continue
                target = next((item for item in targets if item.get("type") == "page"), None)
                if target:
                    break
                time.sleep(0.1)
            if not target:
                pytest.fail("No DevTools page target found for standalone HTML")

            websocket = _DevToolsWebSocket(target["webSocketDebuggerUrl"])
            expression = r"""
                (async () => {
                  await new Promise((resolve, reject) => {
                    const started = Date.now();
                    const wait = () => {
                      if (typeof state !== "undefined" && state.units && state.units.length) resolve();
                      else if (Date.now() - started > 10000) reject(new Error("local data did not initialise"));
                      else setTimeout(wait, 50);
                    };
                    wait();
                  });
                  const choose = (field, predicate) => {
                    const unit = state.units.find(predicate);
                    if (!unit) throw new Error(`Could not find ${field} test unit`);
                    document.getElementById(field).value = unit.name;
                    state.selectedUnitIds[field] = unit.id || null;
                    return unit;
                  };
                  const attacker = choose("attacker", (unit) => unit.name === "Boyz" && /Orks/.test(unit.faction || ""));
                  const defender = choose("defender", (unit) => unit.name === "Intercessor Squad" && /Space Marines/.test(unit.faction || ""));
                  updateSelectedUnitInfos();
                  document.getElementById("mode").value = "melee";
                  await refreshWeaponSelectors();
                  await calculate();
                  return {
                    units: state.units.length,
                    attackerId: state.selectedUnitIds.attacker,
                    defenderId: state.selectedUnitIds.defender,
                    error: document.getElementById("error").textContent,
                    judgement: document.querySelector(".judgement h3")?.textContent || "",
                    firstResultHeading: document.querySelector("#results h3")?.textContent || "",
                    summary: document.querySelector(".summary")?.innerText || "",
                    attackerSelected: document.getElementById("attacker-selected")?.textContent || "",
                    defenderSelected: document.getElementById("defender-selected")?.textContent || "",
                    actionTop: document.querySelector(".actions")?.getBoundingClientRect().top || 0,
                    viewportHeight: window.innerHeight,
                    attackerContextOpen: document.querySelectorAll(".options-group")[1]?.open || false,
                    returnContextOpen: document.querySelectorAll(".options-group")[2]?.open || false,
                    resultsText: document.getElementById("results")?.innerText || "",
                    status: document.getElementById("status")?.textContent || "",
                    statusTitle: document.getElementById("status")?.title || "",
                    editionValue: document.getElementById("edition")?.value || "",
                    editionDisabled: document.getElementById("edition")?.disabled || false,
                    editionTitle: document.getElementById("edition")?.title || "",
                    weaponRows: document.querySelectorAll(".weapon").length,
                    outgoingDamage: state.lastResult?.outgoing?.total_damage,
                    incomingDamage: state.lastResult?.incoming?.total_damage,
                    outgoingModels: state.lastResult?.outgoing?.expected_models_destroyed,
                    incomingModels: state.lastResult?.incoming?.expected_models_destroyed
                  };
                })()
            """
            response = websocket.call(
                "Runtime.evaluate",
                {"expression": expression, "awaitPromise": True, "returnByValue": True},
            )
            result = response["result"]["result"].get("value")
            if response["result"].get("exceptionDetails"):
                pytest.fail(str(response["result"]["exceptionDetails"]))

            assert result["units"] >= 1400
            assert result["attackerId"]
            assert result["defenderId"]
            assert result["error"] == ""
            assert result["judgement"].startswith("AI judgement:")
            assert result["firstResultHeading"].startswith("AI judgement:")
            assert result["actionTop"] < result["viewportHeight"]
            assert result["attackerContextOpen"] is False
            assert result["returnContextOpen"] is False
            assert "ID " in result["attackerSelected"]
            assert "ID " in result["defenderSelected"]
            assert "Source " in result["attackerSelected"]
            assert "Source " in result["defenderSelected"]
            assert "Source " in result["resultsText"]
            assert "pts" in result["attackerSelected"]
            assert "pts" in result["defenderSelected"]
            assert "Models unknown" not in result["attackerSelected"]
            assert "Models unknown" not in result["defenderSelected"]
            assert "Models 10-20" in result["attackerSelected"]
            assert "Models 6-11" in result["defenderSelected"]
            assert "10E rules" in result["status"]
            assert "ML " in result["status"]
            assert result["editionValue"] == "10e"
            assert result["editionDisabled"] is True
            assert "10th Edition" in result["editionTitle"]
            assert "loaded" in result["editionTitle"]
            assert "BSData" in result["status"]
            assert "generated" in result["status"]
            assert "wh40k-10e" in result["statusTitle"]
            assert "training rows" in result["statusTitle"]
            assert "Ruleset capabilities" in result["statusTitle"]
            assert "Hit rolls" in result["statusTitle"]
            summary = result["summary"].casefold()
            assert "net points" in summary
            assert "net damage" in summary
            assert "outgoing damage" in summary
            assert "return damage" in summary
            assert result["weaponRows"] > 0

            units_by_id = load_units_from_directory(CSV_DIR)
            attacker = units_by_id[result["attackerId"]]
            defender = units_by_id[result["defenderId"]]
            outgoing = evaluate_unit(attacker, defender, "melee", context=EngagementContext())
            incoming = evaluate_unit(defender, attacker, "melee", context=EngagementContext())
            assert result["outgoingDamage"] == pytest.approx(outgoing.total_damage)
            assert result["incomingDamage"] == pytest.approx(incoming.total_damage)
            assert result["outgoingModels"] == pytest.approx(outgoing.expected_models_destroyed)
            assert result["incomingModels"] == pytest.approx(incoming.expected_models_destroyed)

            keyboard_response = websocket.call(
                "Runtime.evaluate",
                {
                    "expression": r"""
                        (async () => {
                          document.getElementById("defender").value = "";
                          state.selectedUnitIds.defender = null;
                          await openDropdown("defender");
                          const countText = document.getElementById("defender-menu-count").textContent;
                          document.getElementById("defender").dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
                          const activeAfterArrow = state.activeOptionIndex.defender;
                          const activeId = document.getElementById("defender").getAttribute("aria-activedescendant");
                          document.getElementById("defender").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
                          return {
                            activeAfterArrow,
                            activeId,
                            selected: document.getElementById("defender").value,
                            selectedId: state.selectedUnitIds.defender,
                            menuOpen: document.getElementById("defender-menu").classList.contains("open"),
                            expanded: document.getElementById("defender").getAttribute("aria-expanded"),
                            toggleExpanded: document.querySelector(".combo-toggle[data-target='defender']").getAttribute("aria-expanded"),
                            toggleControls: document.querySelector(".combo-toggle[data-target='defender']").getAttribute("aria-controls"),
                            countText
                          };
                        })()
                    """,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
            )
            keyboard = keyboard_response["result"]["result"].get("value")
            if keyboard_response["result"].get("exceptionDetails"):
                pytest.fail(str(keyboard_response["result"]["exceptionDetails"]))
            assert keyboard["activeAfterArrow"] == 1
            assert keyboard["activeId"] == "defender-option-1"
            assert keyboard["selected"]
            assert keyboard["selectedId"]
            assert keyboard["menuOpen"] is False
            assert keyboard["expanded"] == "false"
            assert keyboard["toggleExpanded"] == "false"
            assert keyboard["toggleControls"] == "defender-options"
            assert "Showing first" in keyboard["countText"]
            assert "Type to narrow" in keyboard["countText"]

            done_response = websocket.call(
                "Runtime.evaluate",
                {
                    "expression": r"""
                        (async () => {
                          await openDropdown("defender");
                          const toggleExpandedOpen = document.querySelector(".combo-toggle[data-target='defender']").getAttribute("aria-expanded");
                          document.querySelector(".combo-done[data-target='defender']").click();
                          return {
                            controls: document.getElementById("defender").getAttribute("aria-controls"),
                            menuOpen: document.getElementById("defender-menu").classList.contains("open"),
                            expanded: document.getElementById("defender").getAttribute("aria-expanded"),
                            toggleExpandedOpen,
                            toggleExpandedClosed: document.querySelector(".combo-toggle[data-target='defender']").getAttribute("aria-expanded"),
                            activeDescendant: document.getElementById("defender").getAttribute("aria-activedescendant")
                          };
                        })()
                    """,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
            )
            done = done_response["result"]["result"].get("value")
            if done_response["result"].get("exceptionDetails"):
                pytest.fail(str(done_response["result"]["exceptionDetails"]))
            assert done["controls"] == "defender-options"
            assert done["menuOpen"] is False
            assert done["expanded"] == "false"
            assert done["toggleExpandedOpen"] == "true"
            assert done["toggleExpandedClosed"] == "false"
            assert done["activeDescendant"] is None

            ranged_response = websocket.call(
                "Runtime.evaluate",
                {
                    "expression": r"""
                        (async () => {
                          const choose = (field, predicate) => {
                            const unit = state.units.find(predicate);
                            if (!unit) throw new Error(`Could not find ${field} ranged test unit`);
                            document.getElementById(field).value = unit.name;
                            state.selectedUnitIds[field] = unit.id || null;
                            return unit;
                          };
                          choose("attacker", (unit) => unit.name === "Intercessor Squad" && /Space Marines/.test(unit.faction || ""));
                          choose("defender", (unit) => unit.name === "Boyz" && /Orks/.test(unit.faction || ""));
                          updateSelectedUnitInfos();
                          document.getElementById("mode").value = "ranged";
                          document.getElementById("attacker-target-model-count").value = "10";
                          document.getElementById("attacker-moved").checked = false;
                          document.getElementById("attacker-advanced").checked = false;
                          document.getElementById("attacker-half-range").checked = true;
                          document.getElementById("attacker-cover").checked = true;
                          document.getElementById("return-target-model-count").value = "5";
                          document.getElementById("return-moved").checked = true;
                          document.getElementById("return-advanced").checked = false;
                          document.getElementById("return-half-range").checked = false;
                          document.getElementById("return-cover").checked = true;
                          await refreshWeaponSelectors();
                          const outgoingSelect = document.getElementById("outgoing-weapon");
                          const incomingSelect = document.getElementById("incoming-weapon");
                          const outgoingWeapon = [...outgoingSelect.options].find((option) => option.value !== "__all__")?.value;
                          const incomingWeapon = [...incomingSelect.options].find((option) => option.value !== "__all__")?.value;
                          if (!outgoingWeapon || !incomingWeapon) throw new Error("Expected ranged weapons for parity test");
                          outgoingSelect.value = outgoingWeapon;
                          incomingSelect.value = incomingWeapon;
                          document.getElementById("outgoing-multiplier").value = "2";
                          document.getElementById("incoming-multiplier").value = "3";
                          await calculate();
                          return {
                            attackerId: state.selectedUnitIds.attacker,
                            defenderId: state.selectedUnitIds.defender,
                            outgoingWeapon,
                            incomingWeapon,
                            error: document.getElementById("error").textContent,
                            outgoingDamage: state.lastResult?.outgoing?.total_damage,
                            incomingDamage: state.lastResult?.incoming?.total_damage,
                            outgoingModels: state.lastResult?.outgoing?.expected_models_destroyed,
                            incomingModels: state.lastResult?.incoming?.expected_models_destroyed,
                            outgoingScope: state.lastResult?.weapon_filters?.outgoing,
                            incomingScope: state.lastResult?.weapon_filters?.incoming,
                            outgoingMultiplier: state.lastResult?.multipliers?.outgoing,
                            incomingMultiplier: state.lastResult?.multipliers?.incoming,
                            mlAvailable: state.lastResult?.ml_judgement?.available === true,
                            mlText: document.body.textContent.includes("ML advisory")
                          };
                        })()
                    """,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
            )
            ranged = ranged_response["result"]["result"].get("value")
            if ranged_response["result"].get("exceptionDetails"):
                pytest.fail(str(ranged_response["result"]["exceptionDetails"]))

            assert ranged["error"] == ""
            assert ranged["outgoingScope"] == ranged["outgoingWeapon"]
            assert ranged["incomingScope"] == ranged["incomingWeapon"]
            assert ranged["outgoingMultiplier"] == 2
            assert ranged["incomingMultiplier"] == 3
            assert ranged["mlAvailable"] is True
            assert ranged["mlText"] is True
            ranged_attacker = units_by_id[ranged["attackerId"]]
            ranged_defender = units_by_id[ranged["defenderId"]]
            outgoing_context = EngagementContext(
                target_within_half_range=True,
                target_in_cover=True,
                target_model_count=10,
            )
            incoming_context = EngagementContext(
                attacker_moved=True,
                target_in_cover=True,
                target_model_count=5,
            )
            outgoing_ranged = evaluate_unit_with_weapon_filter(
                ranged_attacker,
                ranged_defender,
                "ranged",
                context=outgoing_context,
                weapon_name=ranged["outgoingWeapon"],
                multiplier=2,
            )
            incoming_ranged = evaluate_unit_with_weapon_filter(
                ranged_defender,
                ranged_attacker,
                "ranged",
                context=incoming_context,
                weapon_name=ranged["incomingWeapon"],
                multiplier=3,
            )
            assert ranged["outgoingDamage"] == pytest.approx(outgoing_ranged.total_damage)
            assert ranged["incomingDamage"] == pytest.approx(incoming_ranged.total_damage)
            assert ranged["outgoingModels"] == pytest.approx(outgoing_ranged.expected_models_destroyed)
            assert ranged["incomingModels"] == pytest.approx(incoming_ranged.expected_models_destroyed)

            websocket.call(
                "Emulation.setDeviceMetricsOverride",
                {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True},
            )
            mobile_response = websocket.call(
                "Runtime.evaluate",
                {
                    "expression": r"""
                        (async () => {
                          const choose = (field, predicate) => {
                            const unit = state.units.find(predicate);
                            if (!unit) throw new Error(`Could not find ${field} mobile test unit`);
                            document.getElementById(field).value = unit.name;
                            state.selectedUnitIds[field] = unit.id || null;
                          };
                          choose("attacker", (unit) => unit.name === "Intercessor Squad" && /Space Marines/.test(unit.faction || ""));
                          choose("defender", (unit) => unit.name === "Boyz" && /Orks/.test(unit.faction || ""));
                          updateSelectedUnitInfos();
                          await refreshWeaponSelectors();
                          window.scrollTo(0, 0);
                          const initialActionRect = document.querySelector(".actions").getBoundingClientRect();
                          await calculate();
                          await new Promise((resolve) => setTimeout(resolve, 800));
                          const resultRect = document.getElementById("results").getBoundingClientRect();
                          return {
                            scrollWidth: document.documentElement.scrollWidth,
                            viewportWidth: window.innerWidth,
                            resultTop: resultRect.top,
                            initialActionTop: initialActionRect.top,
                            initialActionBottom: initialActionRect.bottom,
                            resultHeading: document.querySelector("#results h3")?.textContent || ""
                          };
                        })()
                    """,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
            )
            mobile = mobile_response["result"]["result"].get("value")
            if mobile_response["result"].get("exceptionDetails"):
                pytest.fail(str(mobile_response["result"]["exceptionDetails"]))
            assert mobile["scrollWidth"] <= mobile["viewportWidth"]
            assert -5 <= mobile["resultTop"] <= 120
            assert mobile["initialActionTop"] < 844
            assert mobile["initialActionBottom"] > 0
            assert mobile["resultHeading"].startswith("AI judgement:")

            websocket.call(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1280, "height": 720, "deviceScaleFactor": 1, "mobile": False},
            )
            review_response = websocket.call(
                "Runtime.evaluate",
                {
                    "expression": r"""
                        (async () => {
                          renderDataReview(await loadDataReview());
                          return {
                            sourceLinks: document.querySelectorAll('.report-markdown a[href*="github.com/BSData/wh40k-10e/blob/"]').length,
                            schemaReviewLink: [...document.querySelectorAll('.review-link')].some((link) => /schema_review\.csv/.test(link.getAttribute("download") || link.textContent || "")),
                            editionStatusLink: [...document.querySelectorAll('.review-link')].some((link) => /edition_status\.json/.test(link.getAttribute("download") || link.textContent || "")),
                            editionReadinessLink: [...document.querySelectorAll('.review-link')].some((link) => /edition_readiness\.md/.test(link.getAttribute("download") || link.textContent || "")),
                            modelAuditLink: [...document.querySelectorAll('.review-link')].some((link) => /matchup_centroid_model\.md/.test(link.getAttribute("download") || link.textContent || "")),
                            modelComparisonLink: [...document.querySelectorAll('.review-link')].some((link) => /model_comparison\.md/.test(link.getAttribute("download") || link.textContent || "")),
                            readinessText: document.body.textContent.includes("Edition Readiness"),
                            readinessReportText: document.body.textContent.includes("Edition Readiness Report"),
                            modelAuditText: document.body.textContent.includes("ML Model Audit"),
                            modelComparisonText: document.body.textContent.includes("ML Model Comparison"),
                            provenanceGeneratedArtifactsText: document.body.textContent.includes("Generated artifacts"),
                            provenanceLinkedArtifactsText: document.body.textContent.includes("Linked ML artifacts"),
                            provenanceModelTypeText: document.body.textContent.includes("ML model type"),
                            provenanceComparisonText: document.body.textContent.includes("Model comparison"),
                            capabilityCoverageText: document.body.textContent.includes("Ruleset Capability Coverage"),
                            capabilityHitRollsText: document.body.textContent.includes("Hit rolls"),
                            reviewNavLinks: document.querySelectorAll(".review-nav a").length,
                            reviewNavText: document.querySelector(".review-nav")?.textContent || "",
                            reviewSearchExists: Boolean(document.getElementById("data-review-search")),
                            reviewStatusExists: Boolean(document.getElementById("data-review-status")),
                            initialFilterStatus: document.getElementById("data-review-filter-status")?.textContent || "",
                            initialReviewSections: [...document.querySelectorAll("#results .review-section")].filter((section) => !section.hidden).length
                          };
                        })()
                    """,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
            )
            review_result = review_response["result"]["result"].get("value")
            if review_response["result"].get("exceptionDetails"):
                pytest.fail(str(review_response["result"]["exceptionDetails"]))
            assert review_result["sourceLinks"] > 0
            assert review_result["schemaReviewLink"] is True
            assert review_result["editionStatusLink"] is True
            assert review_result["editionReadinessLink"] is True
            assert review_result["modelAuditLink"] is True
            assert review_result["modelComparisonLink"] is True
            assert review_result["readinessText"] is True
            assert review_result["readinessReportText"] is True
            assert review_result["modelAuditText"] is True
            assert review_result["modelComparisonText"] is True
            assert review_result["provenanceGeneratedArtifactsText"] is True
            assert review_result["provenanceLinkedArtifactsText"] is True
            assert review_result["provenanceModelTypeText"] is True
            assert review_result["provenanceComparisonText"] is True
            assert review_result["capabilityCoverageText"] is True
            assert review_result["capabilityHitRollsText"] is True
            assert review_result["reviewNavLinks"] == 6
            assert "Suspicious Weapons" in review_result["reviewNavText"]
            assert review_result["reviewSearchExists"] is True
            assert review_result["reviewStatusExists"] is True
            assert "review sections visible" in review_result["initialFilterStatus"]

            review_filter_response = websocket.call(
                "Runtime.evaluate",
                {
                    "expression": r"""
                        (() => {
                          const search = document.getElementById("data-review-search");
                          const status = document.getElementById("data-review-status");
                          const targetSection = document.getElementById("review-provenance") || document.querySelector("#results .review-section");
                          const targetTitle = targetSection.querySelector("h3")?.textContent || "";
                          const searchTerm = targetTitle.toLowerCase().split(/\s+/).find((word) => word.length > 4) || targetTitle.toLowerCase();
                          search.value = searchTerm;
                          search.dispatchEvent(new Event("input", { bubbles: true }));
                          const targetVisible = !targetSection.hidden;
                          const filteredStatus = document.getElementById("data-review-filter-status").textContent;
                          const filteredSections = [...document.querySelectorAll("#results .review-section")].filter((section) => !section.hidden).length;
                          status.value = "problem";
                          status.dispatchEvent(new Event("change", { bubbles: true }));
                          const problemStatus = document.getElementById("data-review-filter-status").textContent;
                          search.value = "__no_such_review_row__";
                          status.value = "";
                          search.dispatchEvent(new Event("input", { bubbles: true }));
                          const emptyVisible = document.getElementById("data-review-filter-empty").classList.contains("visible");
                          const emptyText = document.getElementById("data-review-filter-empty").textContent;
                          document.getElementById("data-review-clear").click();
                          return {
                            targetVisible,
                            filteredStatus,
                            filteredSections,
                            problemStatus,
                            emptyVisible,
                            emptyText,
                            afterClearSearch: search.value,
                            afterClearStatus: status.value,
                            afterClearSections: [...document.querySelectorAll("#results .review-section")].filter((section) => !section.hidden).length
                          };
                        })()
                    """,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
            )
            review_filter = review_filter_response["result"]["result"].get("value")
            if review_filter_response["result"].get("exceptionDetails"):
                pytest.fail(str(review_filter_response["result"]["exceptionDetails"]))
            assert review_filter["targetVisible"] is True
            assert review_filter["filteredSections"] < review_result["initialReviewSections"]
            assert "review sections visible" in review_filter["filteredStatus"]
            assert "table rows" in review_filter["problemStatus"]
            assert review_filter["emptyVisible"] is True
            assert "No review rows match" in review_filter["emptyText"]
            assert review_filter["afterClearSearch"] == ""
            assert review_filter["afterClearStatus"] == ""
            assert review_filter["afterClearSections"] >= review_result["reviewNavLinks"]
        finally:
            if websocket is not None:
                try:
                    websocket.call("Browser.close")
                except Exception:
                    pass
                websocket.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def test_standalone_html_battlefield_mode_smoke():
    chrome = _find_chrome()
    if not chrome:
        pytest.skip("Chrome or Edge is not installed")
    if not LOCAL_HTML.exists():
        pytest.skip("warhammer_calculator_local.html has not been generated")

    port = _free_port()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as user_data:
        process = _start_chrome(chrome, port, LOCAL_HTML, Path(user_data))
        websocket = None
        try:
            target = None
            for _ in range(80):
                if process.poll() is not None:
                    pytest.fail("Headless browser exited before DevTools was ready")
                try:
                    targets = _read_targets(port)
                except Exception:
                    time.sleep(0.1)
                    continue
                target = next((item for item in targets if item.get("type") == "page"), None)
                if target:
                    break
                time.sleep(0.1)
            if not target:
                pytest.fail("No DevTools page target found for standalone HTML")

            websocket = _DevToolsWebSocket(target["webSocketDebuggerUrl"])
            response = websocket.call(
                "Runtime.evaluate",
                {
                    "expression": r"""
                        (async () => {
                          await new Promise((resolve, reject) => {
                            const started = Date.now();
                            const wait = () => {
                              if (typeof state !== "undefined" && state.units && state.units.length) resolve();
                              else if (Date.now() - started > 10000) reject(new Error("local data did not initialise"));
                              else setTimeout(wait, 50);
                            };
                            wait();
                          });
                          await showBattlefield();
                          document.querySelector(".battle-add-unit[data-side='red']").click();
                          const firstRedCount = document.querySelector(".army-card.red .army-row .battle-army-count");
                          firstRedCount.value = "2";
                          firstRedCount.dispatchEvent(new Event("change", { bubbles: true }));
                          const secondRed = document.querySelectorAll(".army-card.red .army-row")[1];
                          const redOptions = [...secondRed.querySelector(".battle-army-unit").options].filter((option) => option.value);
                          secondRed.querySelector(".battle-army-unit").value = redOptions[1]?.value || redOptions[0]?.value || "";
                          secondRed.querySelector(".battle-army-unit").dispatchEvent(new Event("change", { bubbles: true }));
                          await battlefieldGenerate();
                          const firstUnit = document.querySelector(".bf-unit.red");
                          await selectBattleUnit(firstUnit.dataset.unitId);
                          const inspectorText = document.querySelector("[data-testid='battle-unit-inspector']")?.innerText || "";
                          const inspectorWeaponRows = document.querySelectorAll(".inspector-weapon").length;
                          const selectedClassApplied = document.querySelector(".bf-unit.selected") !== null;
                          await battlefieldSuggest();
                          const plannedActions = state.battlefield.plan?.actions?.length || 0;
                          const resolveButtons = document.querySelectorAll(".battle-resolve-action").length;
                          await battlefieldResolvePlannedAction(0);
                          const afterResolveLogLength = state.battlefield.state.log.length;
                          const afterResolvePlanEmpty = document.querySelector(".battle-resolve-action") === null;
                          await battlefieldSuggest();
                          await battlefieldAutoplay();
                          return {
                            visible: Boolean(document.querySelector("[data-testid='battlefield-view']")),
                            board: Boolean(document.getElementById("battle-board")),
                            redUnits: [...document.querySelectorAll(".bf-unit.red")].length,
                            blueUnits: [...document.querySelectorAll(".bf-unit.blue")].length,
                            redRows: [...document.querySelectorAll(".army-card.red .army-row")].length,
                            redArmyEntries: battlefieldArmies()[0].units.length,
                            inspectorText,
                            inspectorWeaponRows,
                            selectedClassApplied,
                            plannedActions,
                            resolveButtons,
                            afterResolveLogLength,
                            afterResolvePlanEmpty,
                            turn: state.battlefield.state.turn,
                            logLength: state.battlefield.state.log.length,
                            logText: document.querySelector(".battle-log")?.innerText || "",
                            error: document.getElementById("error").textContent
                          };
                        })()
                    """,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
            )
            result = response["result"]["result"].get("value")
            if response["result"].get("exceptionDetails"):
                pytest.fail(str(response["result"]["exceptionDetails"]))

            assert result["visible"] is True
            assert result["board"] is True
            assert result["redRows"] == 2
            assert result["redArmyEntries"] == 2
            assert result["redUnits"] >= 3
            assert result["blueUnits"] >= 1
            assert "Nearest enemy" in result["inspectorText"]
            assert "Wounds remaining" in result["inspectorText"]
            assert result["inspectorWeaponRows"] >= 1
            assert result["selectedClassApplied"] is True
            assert result["plannedActions"] >= 1
            assert result["resolveButtons"] >= 1
            assert result["afterResolveLogLength"] >= 1
            assert result["afterResolvePlanEmpty"] is True
            assert result["turn"] == 2
            assert result["logLength"] >= 1
            assert "Damage" in result["logText"] or "Move toward" in result["logText"]
            assert result["error"] == ""
        finally:
            if websocket is not None:
                try:
                    websocket.call("Browser.close")
                except Exception:
                    pass
                websocket.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
