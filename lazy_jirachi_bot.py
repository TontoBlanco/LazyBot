# -*- coding: utf-8 -*-
import time
import pydirectinput as pyautogui
from PIL import ImageGrab
import pyperclip
pyautogui.FAILSAFE = False
import os
import shutil
import datetime
import numpy as np
import psutil
import requests

# =====================================
# CONFIGURATION – EDIT THESE VALUES
# =====================================
ROM_PATH = r"C:\mGBA\ROMs\PokemonSapphire.gba"  # Full path to ROM
ISO_PATH = r"C:\Users\colem\OneDrive\Desktop\PokemonColosseumBonusDisk.iso"  # Full path to ISO
SAVE_PATH = r"C:\mGBA\ROMs\PokemonSapphire.sav"  # mGBA save path
STATE_PATH = r"C:\mGBA\ROMs\PokemonSapphire.ss1"  # Optional savestate path if needed
DOLPHIN_SAV_PATH = r"C:\Users\colem\AppData\Roaming\Dolphin Emulator\GBA\Saves\PokemonSapphire-2.sav"  # Dolphin save path
DOLPHIN_SAV_TEMP = os.path.join(os.path.dirname(DOLPHIN_SAV_PATH), "~lazy_bot_sav.tmp")
BACKUP_DIR = r"C:\Users\colem\OneDrive\Desktop\Gameboy Backup"  # Backup folder
ORIGINAL_BACKUP = os.path.join(BACKUP_DIR, "raw_shiny_target_time.sav")  # Pre-transfer backup
STATE_BACKUP_PATH = os.path.join(BACKUP_DIR, "raw_shiny_target_time.ss1")
JUST_IN_CASE_DIR = r"C:\mGBA\Just_In_Case"  # Non-shiny folder
LOG_FILE = "seed_log.txt"  # Seed log
DOLPHIN_CLICK = (1932, 1086)  # Dolphin focus click - updated
MGBA_CLICK = (560, 341)  # mGBA focus click - updated
DOLPHIN_SCREEN_BBOX = (100, 100, 580, 420)  # Dolphin game screen bbox - tune (unused here)
MGBA_SCREEN_BBOX = (0, 30, 240, 190)  # mGBA game screen bbox - tune for your window (GBA is 240x160)
TAG_AREA_REL = (71, 228, 91, 248)  # Tag area relative to SCREEN_BBOX - retune for mGBA if needed
DOLPHIN_EXE_NAME = "Dolphin.exe"  # For killing if needed
MGBA_CONTROL_MODE = "http"  # Options: "http" to use mGBA-http, "gui" to fall back to pyautogui
MGBA_HTTP_BASE_URL = "http://localhost:5000"
MGBA_HTTP_TIMEOUT = 5.0
MGBA_HTTP_RETRIES = 3
MGBA_HTTP_RETRY_DELAY = 0.5
GBA_MENU_BUTTON = "Start"
GBA_ACTION_BUTTON = "A"
GBA_BACK_BUTTON = "B"
GBA_SAVE_MENU_DOWN_PRESSES = 5  # Number of downs needed to highlight Save
PAUSE_SENTINEL_PATH = os.path.join(os.getcwd(), "lazy_bot.pause")
COOLDOWN_ROM_PATH = r"C:\mGBA\ROMs\PokemonFireRed.gba"
COOLDOWN_SLEEP_SECONDS = 2.0

# =====================================
# mGBA-http CLIENT
# =====================================
class MgbaHttpClient:
    """Thin wrapper around the mGBA-http REST API with retry handling."""
    def __init__(self,
                 base_url=MGBA_HTTP_BASE_URL,
                 timeout=MGBA_HTTP_TIMEOUT,
                 retries=MGBA_HTTP_RETRIES,
                 retry_delay=MGBA_HTTP_RETRY_DELAY):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay
        self.session = requests.Session()

    def _request(self, method, path, params=None, data=None):
        """Send a single HTTP request with retries and bubble up the final error."""
        url = f"{self.base_url}{path}"
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response.text.strip()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(self.retry_delay)
                else:
                    break
        raise RuntimeError(f"mGBA-http request failed for {method.upper()} {path}: {last_error}") from last_error

    def load_rom(self, rom_path):
        return self._request("post", "/mgba-http/extension/loadfile", params={"path": rom_path})

    def load_state_file(self, state_path, flags=29):
        params = {"path": state_path, "flags": flags}
        return self._request("post", "/core/loadstatefile", params=params)

    def save_state_file(self, state_path, flags=31):
        params = {"path": state_path, "flags": flags}
        return self._request("post", "/core/savestatefile", params=params)

    def load_save_file(self, save_path):
        params = {"path": save_path}
        return self._request("post", "/core/loadsavefile", params=params)

    def tap_button(self, button):
        return self._request("post", "/mgba-http/button/tap", params={"button": button})

    def tap_buttons(self, buttons):
        if not buttons:
            return ""
        params = [("buttons", btn) for btn in buttons]
        return self._request("post", "/mgba-http/button/tapmany", params=params)

    def hold_button(self, button, duration_frames):
        params = {"button": button, "duration": duration_frames}
        return self._request("post", "/mgba-http/button/hold", params=params)

    def hold_buttons(self, buttons, duration_frames):
        params = [("buttons", btn) for btn in buttons]
        params.append(("duration", duration_frames))
        return self._request("post", "/mgba-http/button/holdmany", params=params)

    def set_keys(self, bitmask):
        return self._request("post", "/core/setkeys", params={"keys": bitmask})

    def add_keys(self, bitmask):
        return self._request("post", "/core/addkeys", params={"keyBitmask": bitmask})

    def clear_keys(self, bitmask):
        return self._request("post", "/core/clearkeys", params={"keyBitmask": bitmask})

    def step(self, frames=1):
        for _ in range(frames):
            self._request("post", "/core/step")

    def reset_core(self):
        return self._request("post", "/coreadapter/reset")


MGBA_HTTP_CLIENT = None
if MGBA_CONTROL_MODE.lower() == "http":
    try:
        MGBA_HTTP_CLIENT = MgbaHttpClient()
        print(f"[mGBA-http] Client initialised for {MGBA_HTTP_BASE_URL}")
    except Exception as client_error:
        print(f"[mGBA-http] Failed to initialize client: {client_error}")
        MGBA_HTTP_CLIENT = None
        MGBA_CONTROL_MODE = "gui"

# =====================================
# HELPER UTILITIES
# =====================================
def _ensure_http_client():
    """Guard to make sure HTTP mode only runs when the client connected successfully."""
    if MGBA_HTTP_CLIENT is None:
        raise RuntimeError("mGBA-http client is not initialised. Ensure MGBA_CONTROL_MODE is set to 'http' and the server is running.")


def http_tap(button, count=1, delay=0.2):
    """Tap the same virtual GBA button multiple times with a configurable pause."""
    _ensure_http_client()
    for _ in range(count):
        MGBA_HTTP_CLIENT.tap_button(button)
        time.sleep(delay)


def http_step_frames(frames=1, delay=0.0):
    """Advance emulation by a number of single-instruction steps."""
    _ensure_http_client()
    MGBA_HTTP_CLIENT.step(frames)
    if delay:
        time.sleep(delay)


def http_sequence(sequence):
    """
    Execute a higher-level menu macro.

    sequence: iterable of (button, count, delay_between_taps)
    """
    for button, count, delay in sequence:
        http_tap(button, count=count, delay=delay)


def send_hotkey(*keys, interval=0.02):
    """Replicate pyautogui.hotkey using PyDirectInput keyDown/keyUp."""
    if not keys:
        return
    for key in keys:
        pyautogui.keyDown(key)
        time.sleep(interval)
    for key in reversed(keys):
        pyautogui.keyUp(key)
        time.sleep(interval)


def wait_if_paused():
    """Pause the automation when the sentinel file exists."""
    has_announced = False
    while os.path.exists(PAUSE_SENTINEL_PATH):
        if not has_announced:
            print(f"Paused. Remove {PAUSE_SENTINEL_PATH} to resume.")
            has_announced = True
        time.sleep(1.5)


def type_via_clipboard(text):
    """Paste text reliably (preserving case) by using the clipboard."""
    pyperclip.copy(text)
    time.sleep(0.1)
    send_hotkey('ctrl', 'v')


def _ensure_dir(path):
    if path and not os.path.exists(path):
        os.makedirs(path)


def ensure_working_save_present():
    """Restore the working save from backup if the main slot is empty."""
    if os.path.exists(SAVE_PATH):
        return
    if os.path.exists(ORIGINAL_BACKUP):
        _ensure_dir(os.path.dirname(SAVE_PATH))
        shutil.copy2(ORIGINAL_BACKUP, SAVE_PATH)
        print(f"Restored working save from backup: {ORIGINAL_BACKUP}")
        return
    raise FileNotFoundError(f"Working save not found at {SAVE_PATH} and backup {ORIGINAL_BACKUP} missing.")


def _copy_with_log(src, dest, message):
    if not src or not os.path.exists(src):
        return
    _ensure_dir(os.path.dirname(dest))
    shutil.copy2(src, dest)
    print(message)


def update_primary_backups():
    """Persist the freshly saved attempt into the configured backups."""
    _copy_with_log(SAVE_PATH, ORIGINAL_BACKUP, "Updated .sav backup with latest working file.")
    if STATE_PATH and STATE_BACKUP_PATH:
        _copy_with_log(STATE_PATH, STATE_BACKUP_PATH, "Updated .ss1 backup with latest working file.")


def copy_save_to_dolphin():
    """Mirror the current working save into Dolphin's slot."""
    if not os.path.exists(SAVE_PATH):
        raise FileNotFoundError(f"Working save not found at {SAVE_PATH}")
    _ensure_dir(os.path.dirname(DOLPHIN_SAV_TEMP))
    shutil.copy2(SAVE_PATH, DOLPHIN_SAV_TEMP)
    shutil.move(DOLPHIN_SAV_TEMP, DOLPHIN_SAV_PATH)
    print(f"Copied working save to Dolphin path: {DOLPHIN_SAV_PATH}")


def copy_dolphin_save_back():
    """Bring the Dolphin save back to the mGBA directory after a transfer."""
    if not os.path.exists(DOLPHIN_SAV_PATH):
        raise FileNotFoundError(f"Dolphin save missing at {DOLPHIN_SAV_PATH}")
    shutil.copy2(DOLPHIN_SAV_PATH, SAVE_PATH)
    print("Copied Dolphin save back to mGBA path.")


def archive_non_shiny_save(trial_num):
    """Keep a copy of non-shiny results for future reference."""
    _ensure_dir(JUST_IN_CASE_DIR)
    destination = os.path.join(JUST_IN_CASE_DIR, f"JirachiTrial{trial_num}.sav")
    shutil.copy2(SAVE_PATH, destination)
    print(f"Moved non-shiny to {destination}")


def inject_save_into_mgba(save_path=SAVE_PATH):
    """Use the HTTP endpoint to push a .sav directly into the running core."""
    if MGBA_CONTROL_MODE.lower() != "http":
        return
    if not os.path.exists(save_path):
        raise FileNotFoundError(f"Cannot inject missing save file: {save_path}")
    _ensure_http_client()
    MGBA_HTTP_CLIENT.load_save_file(save_path)
    print("Injected SAVE_PATH via /core/loadsavefile.")


def load_save_from_title(no_save=False):
    """
    Navigate the title screen to load the save file.

    Setting no_save=True skips the navigation entirely (used for cooldown ROMs).
    """
    if no_save:
        print("Cooldown ROM started; skipping save load.")
        return

    if MGBA_CONTROL_MODE.lower() == "http":
        sequence = [
            (GBA_ACTION_BUTTON, 1, 0.6),  # Press A/Start to pass intro
            (GBA_ACTION_BUTTON, 1, 0.6),  # Confirm continue
        ]
        http_sequence(sequence)
        print("Loaded save from title screen via HTTP.")
        return

    pyautogui.click(*MGBA_CLICK)
    time.sleep(10)
    pyautogui.press('x')
    time.sleep(10)
    pyautogui.press('x')
    time.sleep(10)
    print("Loaded save from title screen (GUI).")


def run_cooldown_rom(duration=COOLDOWN_SLEEP_SECONDS):
    """Optionally swap to a cooldown ROM between attempts."""
    if not COOLDOWN_ROM_PATH:
        return
    try:
        load_save_from_title(no_save=True)
        focus_and_load_rom(rom_path=COOLDOWN_ROM_PATH, load_state=False, state_path=None)
        print(f"Loaded cooldown ROM {COOLDOWN_ROM_PATH}.")
        if duration and duration > 0:
            time.sleep(duration)
    except Exception as exc:
        print(f"Cooldown ROM skipped: {exc}")
# =====================================
# CORE FUNCTIONS
# =====================================
def focus_and_load_rom(rom_path=None, load_state=True, state_path=None):
    """Load a ROM either via HTTP or GUI automation."""
    rom_path = rom_path or ROM_PATH
    if state_path is None:
        state_path = STATE_PATH

    if MGBA_CONTROL_MODE.lower() == "http":
        _ensure_http_client()
        MGBA_HTTP_CLIENT.load_rom(rom_path)
        if load_state and state_path and os.path.exists(state_path):
            MGBA_HTTP_CLIENT.load_state_file(state_path)
        time.sleep(1)
        print(f"Loaded ROM in mGBA via HTTP: {rom_path}")
        return

    pyautogui.click(*MGBA_CLICK)
    time.sleep(10)
    send_hotkey('ctrl', 'o')
    time.sleep(10)
    type_via_clipboard(rom_path)
    time.sleep(10)
    pyautogui.press('enter')
    time.sleep(10)  # Wait for load
    print(f"Loaded ROM in mGBA: {rom_path}")

def focus_and_load_iso():
    """Bring Dolphin to the foreground and load the ISO via Ctrl+O."""
    pyautogui.click(*DOLPHIN_CLICK)
    time.sleep(10)
    print("Dolphin already running; focused window.")
    send_hotkey('ctrl', 'o')
    time.sleep(10)
    type_via_clipboard(ISO_PATH)
    time.sleep(10)
    pyautogui.press('enter')
    time.sleep(10)  # Wait for load
    print("Loaded ISO in Dolphin.")

def advance_frame():
    """Advance the GBA timeline by one step to create a new seed."""
    if MGBA_CONTROL_MODE.lower() == "http":
        http_step_frames(1, delay=0.1)
        print("Advanced frame in mGBA via HTTP.")
        return

    pyautogui.click(*MGBA_CLICK)  # Ensure focus
    time.sleep(10)
    pyautogui.press('n')
    time.sleep(10)
    print("Advanced frame in mGBA.")

def save_at_new_frame():
    """Perform the in-game save routine so the new frame lands on disk."""
    if MGBA_CONTROL_MODE.lower() == "http":
        sequence = [
            (GBA_MENU_BUTTON, 1, 0.5),  # Open pause menu
            ("Down", GBA_SAVE_MENU_DOWN_PRESSES, 0.5),  # Navigate to Save
            (GBA_ACTION_BUTTON, 1, 1.5),
            (GBA_ACTION_BUTTON, 1, 1.5),
            (GBA_ACTION_BUTTON, 1, 10),  # Confirm save prompts
        ]
        http_sequence(sequence)
        time.sleep(1.5)
        if STATE_PATH:
            MGBA_HTTP_CLIENT.save_state_file(STATE_PATH)
        print("Saved in mGBA via HTTP.")
        return

    pyautogui.click(*MGBA_CLICK)  # Ensure focus
    time.sleep(10)
    for _ in range(3):
        pyautogui.press('x')
        time.sleep(10)
    pyautogui.press('enter')
    time.sleep(10)
    pyautogui.press('down', presses=5)
    time.sleep(10)
    pyautogui.press('x')
    time.sleep(10)
    pyautogui.press('x')
    time.sleep(10)
    time.sleep(2)  # Wait for save
    print("Saved in mGBA.")

    # Alternative sequence if 'x' doesn't work (uncomment if needed):
    # pyautogui.press('enter')
    # time.sleep(10)
    # pyautogui.press('down', presses=4)
    # time.sleep(10)
    # pyautogui.press('enter')
    # time.sleep(10)
    # pyautogui.press('enter')
    # time.sleep(10)
    # time.sleep(2)
    # print("Alternative save completed in mGBA.")

def auto_transfer_dolphin():
    """Execute the button rhythm inside Dolphin to trigger the Jirachi transfer."""
    pyautogui.click(*DOLPHIN_CLICK)  # Ensure focus
    time.sleep(10)
    pyautogui.press('right')  # Your specified arrow
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(10)
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(60)  # Wait 1 min
    print("Transfer completed in Dolphin.")

def close_dolphin_game():
    """Exit the currently running Dolphin game via on-screen hotkeys."""
    pyautogui.click(*DOLPHIN_CLICK)  # Ensure focus
    time.sleep(10)
    pyautogui.press('-')
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(10)
    print("Closed game in Dolphin.")

def close_mgba_rom():
    """Reset/close mGBA so the save file is flushed before leaving."""
    if MGBA_CONTROL_MODE.lower() == "http":
        _ensure_http_client()
        MGBA_HTTP_CLIENT.reset_core()
        time.sleep(0.5)
        print("Reset/closed ROM in mGBA via HTTP.")
        return

    pyautogui.click(*MGBA_CLICK)  # Ensure focus
    time.sleep(10)
    send_hotkey('ctrl', 'k')
    time.sleep(10)
    print("Closed ROM in mGBA.")

def open_summary_for_check():
    """Navigate through the in-game menus until the Pokémon summary screen is shown."""
    if MGBA_CONTROL_MODE.lower() == "http":
        sequence = [
            (GBA_MENU_BUTTON, 1, 0.4),  # Open pause menu
            (GBA_ACTION_BUTTON, 1, 0.4),  # Select Pokémon (assumes default cursor)
            (GBA_ACTION_BUTTON, 1, 0.4),  # Choose first Pokémon
            ("Down", 4, 0.25),           # Navigate to Summary
            (GBA_ACTION_BUTTON, 1, 0.4),  # Open Summary
        ]
        http_sequence(sequence)
        time.sleep(2)
        print("Opened summary in mGBA via HTTP for check.")
        return

    pyautogui.click(*MGBA_CLICK)  # Ensure focus
    time.sleep(10)
    for _ in range(3):
        pyautogui.press('x')
        time.sleep(10)
    pyautogui.press('enter')
    time.sleep(10)
    pyautogui.press('down')
    time.sleep(10)
    pyautogui.press('x')
    time.sleep(10)
    pyautogui.press('down', presses=4)
    time.sleep(10)
    pyautogui.press('x')
    time.sleep(10)
    pyautogui.press('x')
    time.sleep(10)
    time.sleep(2)  # Wait for summary
    print("Opened summary in mGBA for check.")

def detect_shiny_color(bbox=MGBA_SCREEN_BBOX):
    """Sample the summary tag pixels and decide whether they match the red shiny palette."""
    try:
        img = ImageGrab.grab(bbox=bbox)
        tag_img = img.crop(TAG_AREA_REL)
        tag_array = np.array(tag_img)
        avg_color = np.mean(tag_array, axis=(0, 1))
        red, green, blue = avg_color
        print(f"Average tag color: R={red:.1f}, G={green:.1f}, B={blue:.1f}")
        if red > blue + 50 and red > 100:
            print("Color check: Red tags – SHINY CONFIRMED!")
            return True
        else:
            print("Color check: Blue tags – NOT SHINY")
            return False
    except Exception as e:
        print(f"ERROR in color detection: {e}")
        return False

def backup_save_files():
    """Copy both the active mGBA and Dolphin saves into timestamped backups."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if os.path.exists(SAVE_PATH):
        backup_sav = os.path.join(BACKUP_DIR, f"Pokemon_Sapphire_{timestamp}.sav")
        shutil.copy(SAVE_PATH, backup_sav)
        print(f"Backed up mGBA save to: {backup_sav}")
    if os.path.exists(DOLPHIN_SAV_PATH):
        backup_srm = os.path.join(BACKUP_DIR, f"Pokemon_Sapphire-2_{timestamp}.sav")
        shutil.copy(DOLPHIN_SAV_PATH, backup_srm)
        print(f"Backed up Dolphin save to: {backup_srm}")

def kill_dolphin():
    """Forcefully terminate the Dolphin process if it stalls."""
    for proc in psutil.process_iter():
        if proc.name() == DOLPHIN_EXE_NAME:
            proc.kill()
            print("Killed Dolphin process.")
            time.sleep(2)
            break

def get_trial_number():
    """Increment and persist a simple attempt counter used for naming .sav archives."""
    trial_count_file = "trial_count.txt"  # Simple counter file
    if os.path.exists(trial_count_file):
        with open(trial_count_file, 'r') as f:
            count = int(f.read().strip())
    else:
        count = 0
    count += 1
    with open(trial_count_file, 'w') as f:
        f.write(str(count))
    return count

# =====================================
# MAIN BOT LOOP
# =====================================
print("=== Lazy Jirachi Bot Started (One Frame Per Cycle Mode) ===")
print("This will take a LONG time (potentially weeks/months) due to full reloads/transfers per frame.")
print("Position mGBA top-left, Dolphin right. Emulators open but unloaded.")
print("=================================")
print(f"Debug: SAVE_PATH is {SAVE_PATH}, exists: {os.path.exists(SAVE_PATH)}")
print(f"Debug: ORIGINAL_BACKUP is {ORIGINAL_BACKUP}, exists: {os.path.exists(ORIGINAL_BACKUP)}")
input("Press Enter to start...")

attempt = 1
while True:
    ensure_working_save_present()
    wait_if_paused()
    attempt_label = f"[Attempt {attempt}]"
    print(f"{attempt_label} Started")
    attempt_start = time.time()

    # ---- Step 1: Load ROM, advance by a frame, save, then close mGBA ----
    focus_and_load_rom()
    advance_frame()
    save_at_new_frame()
    close_mgba_rom()
    update_primary_backups()
    run_cooldown_rom()

    # ---- Step 2: Move the fresh save into Dolphin's shared GBA slot ----
    try:
        copy_save_to_dolphin()
    except FileNotFoundError as err:
        print(f"ERROR: Failed to copy save to Dolphin path: {err}")
        break

    # ---- Step 3: Launch the ISO and run the scripted transfer ----
    wait_if_paused()
    focus_and_load_iso()

    # ---- Step 4: Execute the menu rhythm that initiates the Jirachi gift ----
    wait_if_paused()
    auto_transfer_dolphin()

    # ---- Step 5: Close Dolphin to flush its save ----
    kill_dolphin()
    close_dolphin_game()

    # ---- Step 6: Bring the Dolphin save back into mGBA territory ----
    try:
        copy_dolphin_save_back()
    except FileNotFoundError as err:
        print(f"ERROR: Failed to copy Dolphin save back: {err}")
        break

    # ---- Step 7: Reopen the ROM in mGBA to examine the result ----
    close_mgba_rom()
    try:
        inject_save_into_mgba()
    except FileNotFoundError as err:
        print(f"ERROR: Could not inject save into mGBA: {err}")
        break
    focus_and_load_rom()
    load_save_from_title()

    # ---- Step 8: Inspect the summary page to check the ribbon colour ----
    wait_if_paused()
    open_summary_for_check()
    if detect_shiny_color():
        elapsed = time.time() - attempt_start
        print("\n*** SHINY JIRACHI FOUND! ***\n")
        print(f"🎉🎉🎉 CONGRATULATIONS! You've got a shiny Jirachi after {attempt} attempts! 🎉🎉🎉")
        print(f"Run time this attempt: {elapsed:.1f}s")
        print(f"Verify in mGBA (red tags) or PKHeX (red star). Save is at {SAVE_PATH}")
        input("Press Enter to exit...")
        break

    # ---- Step 9: Not shiny – archive the save for reference ----
    close_mgba_rom()
    run_cooldown_rom()
    trial_num = get_trial_number()
    archive_non_shiny_save(trial_num)
    elapsed = time.time() - attempt_start
    print(f"{attempt_label} Completed (not shiny) in {elapsed:.1f}s")

    attempt += 1
    time.sleep(1)  # Brief pause between cycles
