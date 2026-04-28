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
                  const initialCalculatorEmptyArt = Boolean(document.querySelector("[data-testid='calculator-empty-art']"));
                  const initialCalculatorEmptyText = document.querySelector("[data-testid='calculator-empty-state']")?.innerText || "";
                  const choose = (field, predicate) => {
                    const unit = state.units.find(predicate);
                    if (!unit) throw new Error(`Could not find ${field} test unit`);
                    document.getElementById(field).value = unit.name;
                    state.selectedUnitIds[field] = unit.id || null;
                    return unit;
                  };
                  const attacker = choose("attacker", (unit) => unit.name === "Boyz" && /Orks/.test(unit.faction || ""));
                  const defender = choose("defender", (unit) => unit.name === "Intercessor Squad" && /Space Marines/.test(unit.faction || ""));
                  document.getElementById("attacker-faction").value = attacker.faction;
                  document.getElementById("defender-faction").value = defender.faction;
                  await loadUnits("", "attacker");
                  await loadUnits("", "defender");
                  await openDropdown("attacker");
                  const attackerMenuText = document.getElementById("attacker-options")?.innerText || "";
                  await openDropdown("defender");
                  const defenderMenuText = document.getElementById("defender-options")?.innerText || "";
                  closeDropdown("defender");
                  updateSelectedUnitInfos();
                  document.getElementById("mode").value = "melee";
                  await refreshWeaponSelectors();
                  await calculate();
                  const resultHeadingBeforeModeSwitch = document.querySelector("#results h3")?.textContent || "";
                  await showBattlefield();
                  const battlefieldVisibleBeforeCalculatorReturn = Boolean(document.querySelector("[data-testid='battlefield-view']"));
                  document.getElementById("nav-calculator").click();
                  const resultHeadingAfterCalculatorReturn = document.querySelector("#results h3")?.textContent || "";
                  return {
                    units: state.units.length,
                    initialCalculatorEmptyArt,
                    initialCalculatorEmptyText,
                    attackerId: state.selectedUnitIds.attacker,
                    defenderId: state.selectedUnitIds.defender,
                    oldGlobalFactionExists: Boolean(document.getElementById("faction")),
                    attackerFactionValue: document.getElementById("attacker-faction")?.value || "",
                    defenderFactionValue: document.getElementById("defender-faction")?.value || "",
                    attackerMenuText,
                    defenderMenuText,
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
                    incomingModels: state.lastResult?.incoming?.expected_models_destroyed,
                    bodyView: document.body.dataset.view,
                    calculatorNavPressed: document.getElementById("nav-calculator")?.getAttribute("aria-pressed") || "",
                    asideDisplay: getComputedStyle(document.querySelector("aside")).display,
                    battlefieldVisibleBeforeCalculatorReturn,
                    resultHeadingBeforeModeSwitch,
                    resultHeadingAfterCalculatorReturn,
                    resultsView: document.getElementById("results")?.dataset.view || ""
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
            assert result["initialCalculatorEmptyArt"] is True
            assert "Choose a matchup" in result["initialCalculatorEmptyText"]
            assert result["attackerId"]
            assert result["defenderId"]
            assert result["oldGlobalFactionExists"] is False
            assert "Orks" in result["attackerFactionValue"]
            assert "Space Marines" in result["defenderFactionValue"]
            assert "Boyz" in result["attackerMenuText"]
            assert "Intercessor Squad" not in result["attackerMenuText"]
            assert "Intercessor Squad" in result["defenderMenuText"]
            assert "Boyz" not in result["defenderMenuText"]
            assert result["error"] == ""
            assert result["bodyView"] == "calculator"
            assert result["calculatorNavPressed"] == "true"
            assert result["asideDisplay"] != "none"
            assert result["battlefieldVisibleBeforeCalculatorReturn"] is True
            assert result["resultHeadingAfterCalculatorReturn"] == result["resultHeadingBeforeModeSwitch"]
            assert result["resultsView"] == "calculator"
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
                          await showDataReview();
                          return {
                            bodyView: document.body.dataset.view,
                            dataReviewNavPressed: document.getElementById("nav-data-review")?.getAttribute("aria-pressed") || "",
                            asideDisplay: getComputedStyle(document.querySelector("aside")).display,
                            sourceLinks: document.querySelectorAll('.report-markdown a[href*="github.com/BSData/wh40k-10e/blob/"]').length,
                            schemaReviewLink: [...document.querySelectorAll('.review-link')].some((link) => /schema_review\.csv/.test(link.getAttribute("download") || link.textContent || "")),
                            editionStatusLink: [...document.querySelectorAll('.review-link')].some((link) => /edition_status\.json/.test(link.getAttribute("download") || link.textContent || "")),
                            editionReadinessLink: [...document.querySelectorAll('.review-link')].some((link) => /edition_readiness\.md/.test(link.getAttribute("download") || link.textContent || "")),
                            footprintReviewLink: [...document.querySelectorAll('.review-link')].some((link) => /unit_footprint_review\.md/.test(link.getAttribute("download") || link.textContent || "")),
                            footprintTemplateLink: [...document.querySelectorAll('.review-link')].some((link) => /unit_footprint_override_template\.csv/.test(link.getAttribute("download") || link.textContent || "")),
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
                            footprintSuggestionsText: document.body.textContent.includes("Footprint Match Suggestions"),
                            footprintSuggestionsSourceText: document.body.textContent.includes("Guide source"),
                            footprintTemplateStatusText: document.body.textContent.includes("Footprint Override Template Status"),
                            footprintTemplateReadyText: document.body.textContent.includes("Ready to promote"),
                            footprintQueueText: document.body.textContent.includes("Footprint Review Queue"),
                            footprintQueueHintText: document.body.textContent.includes("Prioritized manual review batch"),
                            footprintQueueSourceText: document.body.textContent.includes("Guide source"),
                            footprintReviewText: document.body.textContent.includes("Unit Footprint Review"),
                            footprintEstimateText: document.body.textContent.includes("Non-Numeric Footprint Estimates"),
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
            assert review_result["bodyView"] == "data-review"
            assert review_result["dataReviewNavPressed"] == "true"
            assert review_result["asideDisplay"] == "none"
            assert review_result["sourceLinks"] > 0
            assert review_result["schemaReviewLink"] is True
            assert review_result["editionStatusLink"] is True
            assert review_result["editionReadinessLink"] is True
            assert review_result["footprintReviewLink"] is True
            assert review_result["footprintTemplateLink"] is True
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
            assert review_result["reviewNavLinks"] == 7
            assert "Suspicious Weapons" in review_result["reviewNavText"]
            assert "Footprints" in review_result["reviewNavText"]
            assert review_result["footprintSuggestionsText"] is True
            assert review_result["footprintSuggestionsSourceText"] is True
            assert review_result["footprintTemplateStatusText"] is True
            assert review_result["footprintTemplateReadyText"] is True
            assert review_result["footprintQueueText"] is True
            assert review_result["footprintQueueHintText"] is True
            assert review_result["footprintQueueSourceText"] is True
            assert review_result["footprintReviewText"] is True
            assert review_result["footprintEstimateText"] is True
            assert review_result["reviewSearchExists"] is True
            assert review_result["reviewStatusExists"] is True
            assert "review sections visible" in review_result["initialFilterStatus"]

            review_empty_response = websocket.call(
                "Runtime.evaluate",
                {
                    "expression": r"""
                        (() => {
                          renderDataReview({});
                          return {
                            emptyArt: Boolean(document.querySelector("[data-testid='data-review-empty-art']")),
                            emptyText: document.querySelector("[data-testid='data-review-empty-state']")?.innerText || "",
                            view: document.getElementById("results")?.dataset.view || ""
                          };
                        })()
                    """,
                    "returnByValue": True,
                },
            )
            review_empty = review_empty_response["result"]["result"].get("value")
            if review_empty_response["result"].get("exceptionDetails"):
                pytest.fail(str(review_empty_response["result"]["exceptionDetails"]))
            assert review_empty["emptyArt"] is True
            assert "No review artifacts found" in review_empty["emptyText"]
            assert review_empty["view"] == "data-review"

            review_filter_response = websocket.call(
                "Runtime.evaluate",
                {
                    "expression": r"""
                        (async () => {
                          await showDataReview();
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
                          state.battlefield.state = null;
                          state.battlefield.plan = null;
                          renderBattlefield();
                          const initialBattlefieldEmptyArt = Boolean(document.querySelector("[data-testid='battlefield-empty-art']"));
                          const initialBattlefieldEmptyText = document.querySelector("[data-testid='battlefield-empty-state']")?.innerText || "";
                          await updateBattlefieldArmyFaction("red", "Xenos - Orks");
                          const redFactionValue = document.getElementById("battle-red-faction").value;
                          const redSelectableText = document.querySelector(".army-card.red .small")?.textContent || "";
                          const redFactionOptions = [...document.querySelector(".army-card.red .battle-army-unit").options]
                            .filter((option) => option.value)
                            .map((option) => option.textContent);
                          document.querySelector(".battle-add-unit[data-side='red']").click();
                          const firstRedCount = document.querySelector(".army-card.red .army-row .battle-army-count");
                          firstRedCount.value = "2";
                          firstRedCount.dispatchEvent(new Event("change", { bubbles: true }));
                          const secondRed = document.querySelectorAll(".army-card.red .army-row")[1];
                          const redOptions = [...secondRed.querySelector(".battle-army-unit").options].filter((option) => option.value);
                          secondRed.querySelector(".battle-army-unit").value = redOptions[1]?.value || redOptions[0]?.value || "";
                          secondRed.querySelector(".battle-army-unit").dispatchEvent(new Event("change", { bubbles: true }));
                          const expectedRedValidationPoints = battlefieldArmies()[0].units.reduce((sum, entry) => {
                            const unit = state.units.find((row) => row.id === entry.unit_id);
                            return sum + Number(unit?.points || 0) * Math.max(1, Number(entry.count || 1));
                          }, 0);
                          const expectedRedValidationUnitCount = battlefieldArmies()[0].units.reduce((sum, entry) => sum + Math.max(1, Number(entry.count || 1)), 0);
                          await battlefieldValidate();
                          const localRedValidationPoints = state.battlefield.validation.red.points;
                          const localRedValidationUnitCount = state.battlefield.validation.red.unit_count;
                          const localRedValidationWarnings = state.battlefield.validation.red.warnings.join(" | ");
                          const localValidationPanelText = [...document.querySelectorAll(".battlefield-panels")].map((node) => node.innerText || "").join("\n");
                          const savedArmyRowsForInvalidValidation = JSON.parse(JSON.stringify(state.battlefield.armyRows));
                          state.battlefield.armyRows.red.push({ unitId: "__missing_unit__", count: 3 });
                          await battlefieldValidate();
                          const invalidLocalValidationErrors = state.battlefield.validation.red.errors.join(" | ");
                          const invalidLocalValidationUnitCount = state.battlefield.validation.red.unit_count;
                          const invalidValidationPanelText = [...document.querySelectorAll(".battlefield-panels")].map((node) => node.innerText || "").join("\n");
                          state.battlefield.armyRows = savedArmyRowsForInvalidValidation;
                          renderBattlefield();
                          await battlefieldGenerate();
                          const boardLabels = [...document.querySelectorAll(".bf-label")];
                          const boardLabelMaxLength = Math.max(...boardLabels.map((node) => node.textContent.length));
                          const boardLabelsCentered = boardLabels.every((node) => {
                            const circle = node.parentElement.querySelector(".bf-unit");
                            return circle && node.getAttribute("x") === circle.getAttribute("cx");
                          });
                          const unitStatLabels = [...document.querySelectorAll(".bf-unit-stat-label")].map((node) => node.textContent);
                          const unitBadgeLabels = [...document.querySelectorAll(".bf-unit-badge-text")].map((node) => node.textContent);
                          const unitMarker = document.querySelector(".bf-unit-marker");
                          const unitTooltipText = unitMarker?.dataset.hoverText || "";
                          const nativeUnitTitles = document.querySelectorAll(".bf-unit-marker title").length;
                          const hoverUnit = document.querySelector(".bf-unit");
                          const hoverRect = hoverUnit.getBoundingClientRect();
                          const board = document.getElementById("battle-board");
                          const hoverUnitState = state.battlefield.state.units.find((unit) => unit.instance_id === hoverUnit.dataset.unitId);
                          const hoverUnitSvgPoint = board.createSVGPoint();
                          hoverUnitSvgPoint.x = hoverUnitState.x;
                          hoverUnitSvgPoint.y = hoverUnitState.y;
                          const hoverUnitScreenPoint = hoverUnitSvgPoint.matrixTransform(board.getScreenCTM());
                          const remappedHoverUnitPoint = svgPoint(board, hoverUnitScreenPoint.x, hoverUnitScreenPoint.y);
                          const dragCoordinateDelta = Math.hypot(
                            remappedHoverUnitPoint.x - hoverUnitState.x,
                            remappedHoverUnitPoint.y - hoverUnitState.y
                          );
                          showBattleHoverCard(hoverUnit.dataset.unitId, { clientX: hoverRect.left + 4, clientY: hoverRect.top + 4 });
                          const hoverCard = document.querySelector("[data-testid='battle-hover-card']");
                          const hoverCardText = hoverCard?.textContent || "";
                          const hoverCardVisible = hoverCard?.classList.contains("visible") || false;
                          const hoverCardAria = hoverCard?.getAttribute("aria-hidden") || "";
                          hideBattleHoverCard();
                          const hoverCardHidden = hoverCard?.getAttribute("aria-hidden") || "";
                          const terrainNode = document.querySelector(".bf-terrain");
                          const terrainRect = terrainNode.getBoundingClientRect();
                          showBattleHoverText(terrainNode.dataset.hoverText || "", { clientX: terrainRect.left + 4, clientY: terrainRect.top + 4 });
                          const terrainHoverText = hoverCard?.textContent || "";
                          const objectiveNode = document.querySelector(".bf-objective");
                          const objectiveRect = objectiveNode.getBoundingClientRect();
                          showBattleHoverText(objectiveNode.dataset.hoverText || "", { clientX: objectiveRect.left + 4, clientY: objectiveRect.top + 4 });
                          const objectiveHoverText = hoverCard?.textContent || "";
                          hideBattleHoverCard();
                          document.getElementById("battle-next-phase").click();
                          await new Promise((resolve) => setTimeout(resolve, 0));
                          const nextPhaseAfterClick = state.battlefield.state.phase;
                          const nextPhaseLogAction = state.battlefield.state.log.at(-1)?.action || "";
                          const turnTrackerText = document.querySelector("[data-testid='battle-turn-tracker']")?.innerText || "";
                          const redeployUnitId = state.battlefield.state.units.find((unit) => unit.side === "red").instance_id;
                          const redeployBefore = { ...state.battlefield.state.units.find((unit) => unit.instance_id === redeployUnitId) };
                          state.battlefield.state.units.find((unit) => unit.instance_id === redeployUnitId).x = state.battlefield.state.map.width - 2;
                          state.battlefield.state.units.find((unit) => unit.instance_id === redeployUnitId).y = state.battlefield.state.map.height - 2;
                          state.battlefield.state.log.push({ turn: 99, side: "red", action: "test" });
                          await battlefieldRedeploy();
                          const redeployAfter = state.battlefield.state.units.find((unit) => unit.instance_id === redeployUnitId);
                          const redeployMapId = state.battlefield.state.map.id;
                          const redeployClearedLog = state.battlefield.state.log.length === 0;
                          const armyExport = battlefieldExportPayload("armies");
                          const stateExport = battlefieldExportPayload("state");
                          state.battlefield.armyRows = { red: [], blue: [] };
                          state.battlefield.state = null;
                          renderBattlefield();
                          await battlefieldImportJson({ text: async () => JSON.stringify(armyExport) });
                          const armyImportRedRows = [...document.querySelectorAll(".army-card.red .army-row")].length;
                          const armyImportRedEntries = battlefieldArmies()[0].units.length;
                          const armyImportStateCleared = state.battlefield.state === null;
                          await battlefieldImportJson({ text: async () => JSON.stringify(stateExport) });
                          const stateImportUnits = state.battlefield.state.units.length;
                          const stateImportBoard = Boolean(document.getElementById("battle-board"));
                          const mapExport = battlefieldExportPayload("map");
                          state.battlefield.state = null;
                          renderBattlefield();
                          await battlefieldImportJson({ text: async () => JSON.stringify(mapExport) });
                          const mapImportBoard = Boolean(document.getElementById("battle-board"));
                          const mapImportUnits = state.battlefield.state.units.length;
                          const mapImportId = state.battlefield.state.map.id;
                          const badMapExport = JSON.parse(JSON.stringify(mapExport));
                          badMapExport.map.terrain[0].x = badMapExport.map.width + 10;
                          let badMapError = "";
                          try {
                            await battlefieldImportJson({ text: async () => JSON.stringify(badMapExport) });
                          } catch (error) {
                            badMapError = error.message;
                          }
                          const badStateExport = JSON.parse(JSON.stringify(stateExport));
                          badStateExport.state.units[0].x = badStateExport.state.map.width + 5;
                          let badStateError = "";
                          try {
                            await battlefieldImportJson({ text: async () => JSON.stringify(badStateExport) });
                          } catch (error) {
                            badStateError = error.message;
                          }
                          const badStateMetadataExport = JSON.parse(JSON.stringify(stateExport));
                          badStateMetadataExport.state.turn = 0;
                          badStateMetadataExport.state.phase = "psychic";
                          badStateMetadataExport.state.active_side = "green";
                          badStateMetadataExport.state.score = { red: -1 };
                          let badStateMetadataError = "";
                          try {
                            await battlefieldImportJson({ text: async () => JSON.stringify(badStateMetadataExport) });
                          } catch (error) {
                            badStateMetadataError = error.message;
                          }
                          const badStateUnitExport = JSON.parse(JSON.stringify(stateExport));
                          badStateUnitExport.state.units[1].instance_id = badStateUnitExport.state.units[0].instance_id;
                          badStateUnitExport.state.units[0].unit_id = "missing";
                          badStateUnitExport.state.units[0].side = "green";
                          badStateUnitExport.state.units[0].radius = 0;
                          let badStateUnitError = "";
                          try {
                            await battlefieldImportJson({ text: async () => JSON.stringify(badStateUnitExport) });
                          } catch (error) {
                            badStateUnitError = error.message;
                          }
                          const newerSchemaExport = { ...stateExport, schema_version: 99 };
                          let newerSchemaError = "";
                          try {
                            await battlefieldImportJson({ text: async () => JSON.stringify(newerSchemaExport) });
                          } catch (error) {
                            newerSchemaError = error.message;
                          }
                          const wrongEditionExport = { ...stateExport, rules_edition: "11e" };
                          let wrongEditionError = "";
                          try {
                            await battlefieldImportJson({ text: async () => JSON.stringify(wrongEditionExport) });
                          } catch (error) {
                            wrongEditionError = error.message;
                          }
                          const wrongPresetExport = { ...stateExport, rules_preset: "tournament_exact_v2" };
                          let wrongPresetError = "";
                          try {
                            await battlefieldImportJson({ text: async () => JSON.stringify(wrongPresetExport) });
                          } catch (error) {
                            wrongPresetError = error.message;
                          }
                          const legacyExport = JSON.parse(JSON.stringify(stateExport));
                          delete legacyExport.schema_version;
                          delete legacyExport.rules_edition;
                          delete legacyExport.rules_preset;
                          await battlefieldImportJson({ text: async () => JSON.stringify(legacyExport) });
                          const legacyImportUnits = state.battlefield.state.units.length;
                          const redForCollision = state.battlefield.state.units.find((unit) => unit.side === "red");
                          const blueForCollision = state.battlefield.state.units.find((unit) => unit.side === "blue");
                          const originalBluePosition = { x: blueForCollision.x, y: blueForCollision.y };
                          blueForCollision.x = redForCollision.x;
                          blueForCollision.y = redForCollision.y;
                          const collisionErrors = localStateValidationErrors(state.battlefield.state);
                          blueForCollision.x = originalBluePosition.x;
                          blueForCollision.y = originalBluePosition.y;
                          const limitedMove = localMovementLimitedDestination(
                            state.battlefield.state,
                            redForCollision,
                            state.units.find((unit) => unit.id === redForCollision.unit_id),
                            { x: redForCollision.x + 30, y: redForCollision.y }
                          );
                          const limitedMoveDistance = Math.hypot(limitedMove.destination.x - redForCollision.x, limitedMove.destination.y - redForCollision.y);
                          blueForCollision.x = redForCollision.x + 7;
                          blueForCollision.y = redForCollision.y;
                          state.battlefield.state.phase = "charge";
                          setBattlefieldPhase("charge");
                          const chargeAction = localBattleActions().find((action) => action.type === "charge");
                          const chargeOutcome = localResolveBattleAction(chargeAction);
                          renderBattlefield([{ outcome: chargeOutcome }]);
                          const chargeLogText = document.querySelector(".battle-history-log")?.innerText || "";
                          const objective = state.battlefield.state.map.objectives[2];
                          redForCollision.x = objective.x;
                          redForCollision.y = objective.y;
                          state.battlefield.state.phase = "scoring";
                          setBattlefieldPhase("scoring");
                          const scoreAction = localBattleActions().find((action) => action.type === "score");
                          const scoreOutcome = localResolveBattleAction(scoreAction);
                          renderBattlefield([{ outcome: scoreOutcome }]);
                          const scoreLogText = document.querySelector(".battle-history-log")?.innerText || "";
                          const duplicateScoreAction = localBattleActions().find((action) => action.type === "score");
                          state.battlefield.state.phase = "movement";
                          setBattlefieldPhase("movement");
                          const firstUnit = document.querySelector(".bf-unit.red");
                          await selectBattleUnit(firstUnit.dataset.unitId);
                          const inspectorText = document.querySelector("[data-testid='battle-unit-inspector']")?.innerText || "";
                          const inspectorWeaponRows = document.querySelectorAll(".inspector-weapon").length;
                          const selectedClassApplied = document.querySelector(".bf-unit.selected") !== null;
                          const selectedUnitNameLabels = [...document.querySelectorAll(".bf-unit-name-label")].map((node) => node.textContent);
                          const moveRadius = document.querySelector(".bf-move-radius")?.getAttribute("r") || "";
                          const targetLine = document.querySelector(".bf-target-line") !== null;
                          const objectiveLine = document.querySelector(".bf-objective-line") !== null;
                          const manualActions = state.battlefield.manualActions?.length || 0;
                          const manualButtons = document.querySelectorAll(".battle-resolve-manual-action").length;
                          const unavailableActionsText = document.querySelector("[data-testid='battle-unavailable-actions']")?.innerText || "";
                          const selectedForDestroyedNotice = state.battlefield.state.units.find((unit) => unit.instance_id === firstUnit.dataset.unitId);
                          const selectedBeforeDestroyedNotice = {
                            models_remaining: selectedForDestroyedNotice.models_remaining,
                            wounds_remaining: selectedForDestroyedNotice.wounds_remaining,
                            status_flags: [...(selectedForDestroyedNotice.status_flags || [])]
                          };
                          selectedForDestroyedNotice.models_remaining = 0;
                          selectedForDestroyedNotice.wounds_remaining = 0;
                          selectedForDestroyedNotice.status_flags = [...selectedBeforeDestroyedNotice.status_flags, "destroyed"];
                          await battlefieldLoadSelectedActions();
                          renderBattlefield();
                          const destroyedSelectedNotice = document.querySelector(".battle-panel .empty")?.innerText || "";
                          selectedForDestroyedNotice.models_remaining = selectedBeforeDestroyedNotice.models_remaining;
                          selectedForDestroyedNotice.wounds_remaining = selectedBeforeDestroyedNotice.wounds_remaining;
                          selectedForDestroyedNotice.status_flags = selectedBeforeDestroyedNotice.status_flags;
                          await selectBattleUnit(firstUnit.dataset.unitId);
                          await battlefieldResolveManualAction(0);
                          const afterManualLogLength = state.battlefield.state.log.length;
                          const afterManualActionsEmpty = document.querySelector(".battle-resolve-manual-action") === null;
                          const selectedAfterManual = document.querySelector(".bf-unit.red") || document.querySelector(".bf-unit");
                          if (selectedAfterManual) await selectBattleUnit(selectedAfterManual.dataset.unitId);
                          document.getElementById("battle-phase").value = "shooting";
                          document.getElementById("battle-phase").dispatchEvent(new Event("change", { bubbles: true }));
                          await new Promise((resolve) => setTimeout(resolve, 0));
                          const phaseAfterSelect = state.battlefield.state.phase;
                          const selectedActionsAfterPhaseChange = document.querySelector(".selected-actions-log")?.innerText || "";
                          await battlefieldSuggest();
                          const planPhaseText = document.querySelector("[data-testid='battle-ai-plan'] .battle-log-entry .small")?.innerText || "";
                          const plannedActions = state.battlefield.plan?.actions?.length || 0;
                          const resolveButtons = document.querySelectorAll(".battle-resolve-action").length;
                          await battlefieldResolvePlannedAction(0);
                          const afterResolveLogLength = state.battlefield.state.log.length;
                          const resolvedPhase = state.battlefield.state.log.at(-1)?.phase || "";
                          const afterResolvePlanEmpty = document.querySelector(".battle-resolve-action") === null;
                          await battlefieldSuggest();
                          await battlefieldAutoplay();
                          const oneTurnAfterAutoplay = state.battlefield.state.turn;
                          const replayExport = battlefieldExportPayload("replay");
                          state.battlefield.state = null;
                          state.battlefield.plan = null;
                          renderBattlefield();
                          await battlefieldImportJson({ text: async () => JSON.stringify(replayExport) });
                          const replayImportBoard = Boolean(document.getElementById("battle-board"));
                          const replayImportLogLength = state.battlefield.state.log.length;
                          const replayImportText = document.querySelector(".battle-history-log")?.innerText || "";
                          await battlefieldGenerate();
                          document.getElementById("battle-autoplay-turns").value = "3";
                          const battleAutoplayStartTurn = state.battlefield.state.turn;
                          const outcomeSummaryBeforeAutoplay = document.querySelector("[data-testid='battle-outcome-summary']")?.innerText || "";
                          await battlefieldAutoplayBattle();
                          const battleAutoplayTurn = state.battlefield.state.turn;
                          const battleAutoplayLogLength = state.battlefield.state.log.length;
                          const autoplayTurns = state.battlefield.autoplayTurns;
                          const outcomeSummaryAfterAutoplay = document.querySelector("[data-testid='battle-outcome-summary']")?.innerText || "";
                          const toolbarGroups = document.querySelectorAll(".battlefield-control-group").length;
                          const toolbarMapText = document.querySelector("[data-testid='battlefield-map-controls']")?.innerText || "";
                          const toolbarTurnText = document.querySelector("[data-testid='battlefield-turn-controls']")?.innerText || "";
                          const toolbarFileText = document.querySelector("[data-testid='battlefield-file-controls']")?.innerText || "";
                          const boardHeaderText = document.querySelector("[data-testid='battlefield-board-header']")?.innerText || "";
                          const boardLegendText = document.querySelector(".battlefield-board-legend")?.innerText || "";
                          const boardGridBackground = Boolean(document.querySelector(".bf-board-bg") && document.querySelector("#bf-grid"));
                          const rulerLabels = [...document.querySelectorAll(".bf-board-ruler .bf-ruler-text")].map((node) => node.textContent);
                          const rulerLineCount = document.querySelectorAll(".bf-board-ruler .bf-ruler-line").length;
                          const rulerScaleLineCount = document.querySelectorAll(".bf-board-ruler .bf-ruler-scale").length;
                          const terrainFeatureCount = document.querySelectorAll(".bf-terrain-feature").length;
                          const terrainEllipseCount = document.querySelectorAll("ellipse.bf-terrain").length;
                          const terrainPolygonCount = document.querySelectorAll("polygon.bf-terrain").length;
                          const terrainLabelText = [...document.querySelectorAll(".bf-terrain-label")].map((node) => node.textContent).join(" ");
                          const unitNameLabels = document.querySelectorAll(".bf-unit-name-label").length;
                          const mainGridColumns = getComputedStyle(document.querySelector(".battlefield-main-grid")).gridTemplateColumns;
                          const deploymentZones = document.querySelectorAll(".bf-deployment").length;
                          const deploymentLabelText = [...document.querySelectorAll(".bf-deployment-label")].map((node) => node.textContent).join(" ");
                          const objectiveLabels = [...document.querySelectorAll(".bf-objective-label")].map((node) => node.textContent);
                          return {
                            visible: Boolean(document.querySelector("[data-testid='battlefield-view']")),
                            board: Boolean(document.getElementById("battle-board")),
                            bodyView: document.body.dataset.view,
                            battlefieldNavPressed: document.getElementById("nav-battlefield")?.getAttribute("aria-pressed") || "",
                            asideDisplay: getComputedStyle(document.querySelector("aside")).display,
                            initialBattlefieldEmptyArt,
                            initialBattlefieldEmptyText,
                            boardLabelMaxLength,
                            boardLabelsCentered,
                            unitStatLabels,
                            unitBadgeLabels,
                            unitTooltipText,
                            nativeUnitTitles,
                            dragCoordinateDelta,
                            hoverCardText,
                            hoverCardVisible,
                            hoverCardAria,
                            hoverCardHidden,
                            terrainHoverText,
                            objectiveHoverText,
                            redFactionValue,
                            redSelectableText,
                            redFactionOptions,
                            expectedRedValidationPoints,
                            expectedRedValidationUnitCount,
                            localRedValidationPoints,
                            localRedValidationUnitCount,
                            localRedValidationWarnings,
                            localValidationPanelText,
                            invalidLocalValidationErrors,
                            invalidLocalValidationUnitCount,
                            invalidValidationPanelText,
                            nextPhaseAfterClick,
                            nextPhaseLogAction,
                            turnTrackerText,
                            redeployBeforeX: redeployBefore.x,
                            redeployAfterX: redeployAfter?.x || 0,
                            redeployMapId,
                            redeployClearedLog,
                            collisionErrors,
                            limitedMoveDistance,
                            limitedMoveNotes: limitedMove.assumptions,
                            chargeProbability: chargeAction?.context?.charge_probability || 0,
                            chargeReason: chargeAction?.reason || "",
                            chargeExpectedDamage: chargeAction?.expected_damage || 0,
                            chargeFullDamage: chargeAction?.context?.full_melee_damage_if_charge_connects || 0,
                            chargeOutcomeDamage: chargeOutcome?.damage || 0,
                            chargeLogText,
                            scoreReason: scoreAction?.reason || "",
                            scoreDelta: scoreOutcome?.score_delta?.red || 0,
                            scoreObjectives: scoreOutcome?.objectives || [],
                            scoreLogText,
                            duplicateScoreAvailable: Boolean(duplicateScoreAction),
                            redUnits: [...document.querySelectorAll(".bf-unit.red")].length,
                            blueUnits: [...document.querySelectorAll(".bf-unit.blue")].length,
                            redRows: [...document.querySelectorAll(".army-card.red .army-row")].length,
                            redArmyEntries: battlefieldArmies()[0].units.length,
                            armyExportFormat: armyExport.format,
                            armyExportSchemaVersion: armyExport.schema_version,
                            armyExportEdition: armyExport.rules_edition,
                            armyExportRulesPreset: armyExport.rules_preset,
                            armyExportStateMissing: !("state" in armyExport),
                            stateExportFormat: stateExport.format,
                            stateExportSchemaVersion: stateExport.schema_version,
                            stateExportEdition: stateExport.rules_edition,
                            stateExportRulesPreset: stateExport.rules_preset,
                            stateExportUnits: stateExport.state?.units?.length || 0,
                            armyImportRedRows,
                            armyImportRedEntries,
                            armyImportStateCleared,
                            stateImportUnits,
                            stateImportBoard,
                            mapExportFormat: mapExport.format,
                            mapExportSchemaVersion: mapExport.schema_version,
                            mapExportEdition: mapExport.rules_edition,
                            mapExportRulesPreset: mapExport.rules_preset,
                            mapExportId: mapExport.map?.id || "",
                            mapImportBoard,
                            mapImportUnits,
                            mapImportId,
                            badMapError,
                            badStateError,
                            badStateMetadataError,
                            badStateUnitError,
                            newerSchemaError,
                            wrongEditionError,
                            wrongPresetError,
                            legacyImportUnits,
                            replayExportFormat: replayExport.format,
                            replayExportSchemaVersion: replayExport.schema_version,
                            replayExportEdition: replayExport.rules_edition,
                            replayExportRulesPreset: replayExport.rules_preset,
                            replayExportEntries: replayExport.replay_entries?.length || 0,
                            replayExportFinalTurn: replayExport.final_state?.turn || 0,
                            replayImportBoard,
                            replayImportLogLength,
                            replayImportText,
                            oneTurnAfterAutoplay,
                            battleAutoplayStartTurn,
                            battleAutoplayTurn,
                            battleAutoplayLogLength,
                            autoplayTurns,
                            outcomeSummaryBeforeAutoplay,
                            outcomeSummaryAfterAutoplay,
                            toolbarGroups,
                            toolbarMapText,
                            toolbarTurnText,
                            toolbarFileText,
                            boardHeaderText,
                            boardLegendText,
                            boardGridBackground,
                            rulerLabels,
                            rulerLineCount,
                            rulerScaleLineCount,
                            terrainFeatureCount,
                            terrainEllipseCount,
                            terrainPolygonCount,
                            terrainLabelText,
                            unitNameLabels,
                            selectedUnitNameLabels,
                            mainGridColumns,
                            deploymentZones,
                            deploymentLabelText,
                            objectiveLabels,
                            inspectorText,
                            inspectorWeaponRows,
                            selectedClassApplied,
                            moveRadius,
                            targetLine,
                            objectiveLine,
                            manualActions,
                            manualButtons,
                            unavailableActionsText,
                            destroyedSelectedNotice,
                            afterManualLogLength,
                            afterManualActionsEmpty,
                            phaseAfterSelect,
                            selectedActionsAfterPhaseChange,
                            planPhaseText,
                            plannedActions,
                            resolveButtons,
                            afterResolveLogLength,
                            resolvedPhase,
                            afterResolvePlanEmpty,
                            turn: state.battlefield.state.turn,
                            logLength: state.battlefield.state.log.length,
                            logText: document.querySelector(".battle-history-log")?.innerText || "",
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
            assert result["bodyView"] == "battlefield"
            assert result["battlefieldNavPressed"] == "true"
            assert result["asideDisplay"] == "none"
            assert result["initialBattlefieldEmptyArt"] is True
            assert "Ready for deployment" in result["initialBattlefieldEmptyText"]
            assert result["toolbarGroups"] == 3
            assert "map" in result["toolbarMapText"].lower()
            assert "Generate map" in result["toolbarMapText"]
            assert "turn and ai" in result["toolbarTurnText"].lower()
            assert "Suggest AI action" in result["toolbarTurnText"]
            assert "files" in result["toolbarFileText"].lower()
            assert "Export replay" in result["toolbarFileText"]
            assert "44\" x 60\"" in result["boardHeaderText"]
            assert "Red" in result["boardHeaderText"]
            assert "Ruin" in result["boardLegendText"]
            assert "Woods" in result["boardLegendText"]
            assert "Crater" in result["boardLegendText"]
            assert "Barricade" in result["boardLegendText"]
            assert "Northwest ruin" in result["boardLegendText"]
            assert "rectangle" in result["boardLegendText"]
            assert "oval" in result["boardLegendText"]
            assert "blocks LOS" in result["boardLegendText"]
            assert "normal move" in result["boardLegendText"]
            assert "storeys" in result["boardLegendText"]
            assert "objective" in result["boardLegendText"]
            assert "Red home" in result["boardLegendText"]
            assert "Blue home" in result["boardLegendText"]
            assert "Centre objective" in result["boardLegendText"]
            assert "3\" radius" in result["boardLegendText"]
            assert "5 VP" in result["boardLegendText"]
            assert result["boardGridBackground"] is True
            assert "12\"" in result["rulerLabels"]
            assert "44\"" in result["rulerLabels"]
            assert "60\"" in result["rulerLabels"]
            assert "6\" scale" in result["rulerLabels"]
            assert result["rulerLineCount"] >= 9
            assert result["rulerScaleLineCount"] == 3
            assert result["terrainFeatureCount"] >= 7
            assert result["terrainEllipseCount"] >= 3
            assert result["terrainPolygonCount"] >= 2
            assert "2S" in result["terrainLabelText"] or "3S" in result["terrainLabelText"]
            assert result["unitNameLabels"] == 0
            assert result["mainGridColumns"] != "none"
            assert result["deploymentZones"] == 2
            assert "Red DZ" in result["deploymentLabelText"]
            assert "Blue DZ" in result["deploymentLabelText"]
            assert len(result["objectiveLabels"]) == 5
            assert {"R", "B", "W", "C", "E"}.issubset(set(result["objectiveLabels"]))
            assert result["boardLabelMaxLength"] <= 2
            assert result["boardLabelsCentered"] is True
            assert any(label.startswith("M") and " W" in label for label in result["unitStatLabels"])
            assert all(label for label in result["unitBadgeLabels"])
            assert "Models " in result["unitTooltipText"]
            assert "Nearest enemy:" in result["unitTooltipText"]
            assert "Position x " in result["unitTooltipText"]
            assert "Footprint " in result["unitTooltipText"]
            assert "Base " in result["unitTooltipText"]
            assert result["nativeUnitTitles"] == 0
            assert result["dragCoordinateDelta"] < 0.01
            assert result["hoverCardVisible"] is True
            assert result["hoverCardAria"] == "false"
            assert result["hoverCardHidden"] == "true"
            assert "Models " in result["hoverCardText"]
            assert "Nearest enemy:" in result["hoverCardText"]
            assert "storey" in result["terrainHoverText"]
            assert "cover" in result["terrainHoverText"]
            assert "LOS" in result["terrainHoverText"]
            assert "objective" in result["objectiveHoverText"]
            assert "Radius " in result["objectiveHoverText"]
            assert "VP " in result["objectiveHoverText"]
            assert result["redFactionValue"] == "Xenos - Orks"
            assert "selectable units" in result["redSelectableText"]
            assert any("Boyz" in option for option in result["redFactionOptions"])
            assert result["localRedValidationPoints"] == result["expectedRedValidationPoints"]
            assert result["localRedValidationUnitCount"] == result["expectedRedValidationUnitCount"]
            assert "unsupported special rules" in result["localRedValidationWarnings"]
            assert f"{result['expectedRedValidationUnitCount']} units" in result["localValidationPanelText"]
            assert f"{result['expectedRedValidationPoints']} pts" in result["localValidationPanelText"]
            assert "Warning:" in result["localValidationPanelText"]
            assert "Unknown unit id __missing_unit__" in result["invalidLocalValidationErrors"]
            assert result["invalidLocalValidationUnitCount"] == result["expectedRedValidationUnitCount"] + 3
            assert "Error:" in result["invalidValidationPanelText"]
            assert result["nextPhaseAfterClick"] == "shooting"
            assert result["nextPhaseLogAction"] == "advance_phase"
            assert "ACTIVE SIDE" in result["turnTrackerText"]
            assert "Shooting" in result["turnTrackerText"]
            assert result["redeployAfterX"] == result["redeployBeforeX"]
            assert result["redeployMapId"] == "strike_force_44x60"
            assert result["redeployClearedLog"] is True
            assert any("overlaps" in error for error in result["collisionErrors"])
            assert result["limitedMoveDistance"] <= 6.01
            assert any("clamped" in note for note in result["limitedMoveNotes"])
            assert 0 < result["chargeProbability"] < 1
            assert "charge probability" in result["chargeReason"]
            assert result["chargeExpectedDamage"] < result["chargeFullDamage"]
            assert result["chargeOutcomeDamage"] == 0
            assert "Follow-up fight" in result["chargeLogText"]
            assert "controlled objectives" in result["scoreReason"]
            assert result["scoreDelta"] >= 5
            assert result["scoreObjectives"]
            assert "Score Red +" in result["scoreLogText"]
            assert "Objectives" in result["scoreLogText"]
            assert result["duplicateScoreAvailable"] is False
            assert result["redRows"] == 2
            assert result["redArmyEntries"] == 2
            assert result["armyExportFormat"] == "army_list_v1"
            assert result["armyExportSchemaVersion"] == 1
            assert result["armyExportEdition"] == "10e"
            assert result["armyExportRulesPreset"] == "tactical_mvp_v1"
            assert result["armyExportStateMissing"] is True
            assert result["stateExportFormat"] == "battle_state_v1"
            assert result["stateExportSchemaVersion"] == 1
            assert result["stateExportEdition"] == "10e"
            assert result["stateExportRulesPreset"] == "tactical_mvp_v1"
            assert result["stateExportUnits"] >= 4
            assert result["armyImportRedRows"] == 2
            assert result["armyImportRedEntries"] == 2
            assert result["armyImportStateCleared"] is True
            assert result["stateImportUnits"] == result["stateExportUnits"]
            assert result["stateImportBoard"] is True
            assert result["mapExportFormat"] == "battle_map_v1"
            assert result["mapExportSchemaVersion"] == 1
            assert result["mapExportEdition"] == "10e"
            assert result["mapExportRulesPreset"] == "tactical_mvp_v1"
            assert result["mapExportId"] == "strike_force_44x60"
            assert result["mapImportBoard"] is True
            assert result["mapImportUnits"] == result["stateExportUnits"]
            assert result["mapImportId"] == "strike_force_44x60"
            assert "Terrain feature" in result["badMapError"]
            assert "outside the battlefield" in result["badStateError"]
            assert "Battle turn must be a positive integer" in result["badStateMetadataError"]
            assert "Battle active side must be red or blue" in result["badStateMetadataError"]
            assert "Battle phase psychic is not supported" in result["badStateMetadataError"]
            assert "Battle score for red cannot be negative" in result["badStateMetadataError"]
            assert "Battle score is missing blue" in result["badStateMetadataError"]
            assert "Duplicate battlefield unit id" in result["badStateUnitError"]
            assert "unknown unit id missing" in result["badStateUnitError"]
            assert "invalid side green" in result["badStateUnitError"]
            assert "positive footprint radius" in result["badStateUnitError"]
            assert "newer than this app supports" in result["newerSchemaError"]
            assert "11th Edition" in result["wrongEditionError"]
            assert "unsupported rules preset" in result["wrongPresetError"]
            assert result["legacyImportUnits"] == result["stateExportUnits"]
            assert result["replayExportFormat"] == "battle_replay_v1"
            assert result["replayExportSchemaVersion"] == 1
            assert result["replayExportEdition"] == "10e"
            assert result["replayExportRulesPreset"] == "tactical_mvp_v1"
            assert result["replayExportEntries"] >= 1
            assert result["replayExportFinalTurn"] == 2
            assert result["replayImportBoard"] is True
            assert result["replayImportLogLength"] == result["replayExportEntries"]
            assert "Turn" in result["replayImportText"]
            assert result["oneTurnAfterAutoplay"] == 2
            assert result["autoplayTurns"] == 3
            assert result["battleAutoplayTurn"] >= result["battleAutoplayStartTurn"] + 1
            assert result["battleAutoplayTurn"] <= result["battleAutoplayStartTurn"] + 3
            assert result["battleAutoplayLogLength"] >= 1
            assert "battlefield judgement" in result["outcomeSummaryBeforeAutoplay"].lower()
            assert "VP" in result["outcomeSummaryAfterAutoplay"]
            assert result["redUnits"] >= 3
            assert result["blueUnits"] >= 1
            assert "Nearest enemy" in result["inspectorText"]
            assert "Wounds remaining" in result["inspectorText"]
            assert "Footprint " in result["inspectorText"]
            assert "Base " in result["inspectorText"]
            assert result["inspectorWeaponRows"] >= 1
            assert result["selectedClassApplied"] is True
            assert len(result["selectedUnitNameLabels"]) == 1
            assert result["selectedUnitNameLabels"][0]
            assert float(result["moveRadius"]) >= 1
            assert result["targetLine"] is True
            assert result["objectiveLine"] is True
            assert result["manualActions"] >= 1
            assert result["manualButtons"] >= 1
            assert "Unavailable:" in result["unavailableActionsText"]
            assert "has no live models and cannot act" in result["destroyedSelectedNotice"]
            assert result["afterManualLogLength"] >= 1
            assert result["afterManualActionsEmpty"] is True
            assert result["phaseAfterSelect"] == "shooting"
            assert "Phase Shooting" in result["selectedActionsAfterPhaseChange"]
            assert "Phase Shooting" in result["planPhaseText"]
            assert result["plannedActions"] >= 1
            assert result["resolveButtons"] >= 1
            assert result["afterResolveLogLength"] >= 1
            assert result["resolvedPhase"] == "shooting"
            assert result["afterResolvePlanEmpty"] is True
            assert result["turn"] == result["battleAutoplayTurn"]
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
