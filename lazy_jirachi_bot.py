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
_save_menu_needs_navigation = True

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

    def load_rom_core(self, rom_path):
        return self._request("post", "/core/loadfile", params={"path": rom_path})

    def load_save_file(self, save_path, temporary=False):
        params = {"path": save_path, "temporary": str(temporary).lower()}
        return self._request("post", "/core/loadsavefile", params=params)
    def load_state_file(self, state_path, flags=31):
        params = {"path": state_path, "flags": flags}
        return self._request("post", "/core/loadstatefile", params=params)

    def save_state_file(self, state_path, flags=31):
        params = {"path": state_path, "flags": flags}
        return self._request("post", "/core/savestatefile", params=params)

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

# =====================================
# CORE FUNCTIONS
# =====================================
def focus_and_load_rom(load_state=True):
    """Load the configured ROM either via HTTP or GUI automation."""
    if MGBA_CONTROL_MODE.lower() == "http":
        _ensure_http_client()
        MGBA_HTTP_CLIENT.load_rom(ROM_PATH)
        if load_state and STATE_PATH and os.path.exists(STATE_PATH):
            MGBA_HTTP_CLIENT.load_state_file(STATE_PATH)
        time.sleep(1)
        print("Loaded ROM in mGBA via HTTP.")
        return

    pyautogui.click(*MGBA_CLICK)
    time.sleep(10)
    send_hotkey('ctrl', 'o')
    time.sleep(10)
    type_via_clipboard(ROM_PATH)
    time.sleep(10)
    pyautogui.press('enter')
    time.sleep(10)  # Wait for load
    print("Loaded ROM in mGBA.")


def focus_and_load_rom_from_save():
    """Load ROM without restoring the savestate so the copied .sav is used."""
    if MGBA_CONTROL_MODE.lower() == "http":
        _ensure_http_client()
        MGBA_HTTP_CLIENT.load_rom_core(ROM_PATH)
        MGBA_HTTP_CLIENT.load_save_file(SAVE_PATH, temporary=False)
        time.sleep(1)
        print("Loaded ROM in mGBA via HTTP (core load).")
        return
    focus_and_load_rom(load_state=False)

def focus_and_load_iso():
    """Bring Dolphin to the foreground and load the ISO via Ctrl+O."""
    pyautogui.click(*DOLPHIN_CLICK)
    time.sleep(10)
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
    global _save_menu_needs_navigation
    if MGBA_CONTROL_MODE.lower() == "http":
        sequence = [
            (GBA_MENU_BUTTON, 1, 0.5),
        ]
        if _save_menu_needs_navigation:
            sequence.append(("Down", GBA_SAVE_MENU_DOWN_PRESSES, 0.5))
        sequence.extend([
            (GBA_ACTION_BUTTON, 1, 1.5),
            (GBA_ACTION_BUTTON, 1, 1.5),
            (GBA_ACTION_BUTTON, 1, 10),
        ])
        http_sequence(sequence)
        time.sleep(1.5)
        if STATE_PATH:
            MGBA_HTTP_CLIENT.save_state_file(STATE_PATH)
        time.sleep(10)
        _save_menu_needs_navigation = False
        print("Saved in mGBA via HTTP.")
        return

    pyautogui.click(*MGBA_CLICK)  # Ensure focus
    time.sleep(10)
    for _ in range(3):
        pyautogui.press('x')
        time.sleep(10)
    pyautogui.press('enter')
    time.sleep(10)
    if _save_menu_needs_navigation:
        pyautogui.press('down', presses=GBA_SAVE_MENU_DOWN_PRESSES)
    time.sleep(10)
    pyautogui.press('x')
    time.sleep(10)
    pyautogui.press('x')
    time.sleep(10)
    time.sleep(2)  # Wait for save
    time.sleep(10)
    _save_menu_needs_navigation = False
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
    time.sleep(3)
    pyautogui.press('right')  # Your specified arrow
    time.sleep(2)
    pyautogui.press('space')
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(1)
    pyautogui.press('space')
    time.sleep(1)
    pyautogui.press('space')
    time.sleep(1)
    pyautogui.press('space')
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(120)  # Wait 2 min
    print("Transfer completed in Dolphin.")

def close_dolphin_game():
    """Exit the currently running Dolphin game via on-screen hotkeys."""
    pyautogui.click(*DOLPHIN_CLICK)  # Ensure focus
    time.sleep(2)
    pyautogui.press('-')
    time.sleep(2)
    pyautogui.press('space')
    time.sleep(5)
    # Fallback to Alt+F4 to guarantee the emulator closes
    send_hotkey('alt', 'f4')
    time.sleep(3)
    kill_dolphin()
    print("Closed game in Dolphin.")

def close_mgba_rom():
    """Reset/close mGBA so the save file is flushed before leaving."""
    if MGBA_CONTROL_MODE.lower() == "http":
        time.sleep(5)
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


def load_save_from_title():
    """Automate skipping intros and selecting Continue from the title screen after ROM load."""
    if MGBA_CONTROL_MODE.lower() == "http":
        time.sleep(5.0)
        http_tap("Up", count=1, delay=0.2)
        http_tap(GBA_ACTION_BUTTON, count=1, delay=1.0)
        http_tap(GBA_ACTION_BUTTON, count=1, delay=0.3)
        http_tap(GBA_ACTION_BUTTON, count=1, delay=0.3)
        http_tap(GBA_ACTION_BUTTON, count=1, delay=0.3)
        print("Loaded save from title screen via HTTP.")
        return

    pyautogui.click(*MGBA_CLICK)  # Ensure focus
    time.sleep(5.0)
    pyautogui.press('up')
    time.sleep(0.2)
    pyautogui.press('enter')
    time.sleep(1.0)
    pyautogui.press('enter')
    time.sleep(0.3)
    pyautogui.press('enter')
    print("Loaded save from title screen.")

def open_summary_for_check():
    """Navigate through the in-game menus until the Pokémon summary screen is shown."""
    if MGBA_CONTROL_MODE.lower() == "http":
        sequence = [
            (GBA_MENU_BUTTON, 1, 0.4),  # Open pause menu
            ("Down", 1, 0.25),
            (GBA_ACTION_BUTTON, 1, 0.4),
            ("Down", 4, 0.25),
            (GBA_ACTION_BUTTON, 1, 0.4),
            (GBA_ACTION_BUTTON, 1, 0.4),
        ]
        http_sequence(sequence)
        time.sleep(2)
        print("Opened summary in mGBA via HTTP for check.")
        return

    pyautogui.click(*MGBA_CLICK)  # Ensure focus
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
    wait_if_paused()
    print(f"Attempt {attempt} started.")
    
    # ---- Step 1: Load ROM, advance by a frame, save, then close mGBA ----
    focus_and_load_rom()
    advance_frame()
    save_at_new_frame()
    
    # ---- Step 2: Move the fresh save into Dolphin's shared GBA slot ----
    if os.path.exists(SAVE_PATH):
        shutil.copy(SAVE_PATH, DOLPHIN_SAV_TEMP)
        shutil.move(DOLPHIN_SAV_TEMP, DOLPHIN_SAV_PATH)
        print("Moved save to Dolphin path.")
    else:
        print("ERROR: Save file not found after save - check mGBA settings.")
        break
    
    # ---- Step 3: Launch the ISO and run the scripted transfer ----
    wait_if_paused()
    focus_and_load_iso()
    
    # ---- Step 4: Execute the menu rhythm that initiates the Jirachi gift ----
    wait_if_paused()
    auto_transfer_dolphin()
    
    # ---- Step 5: Close Dolphin to flush its save ----
    close_dolphin_game()
    # kill_dolphin()  # Uncomment if close fails
    
    # ---- Step 6: Bring the Dolphin save back into mGBA territory ----
    shutil.copy(DOLPHIN_SAV_PATH, SAVE_PATH)
    print("Copied Dolphin save back to mGBA path.")
    
    # ---- Step 7: Reset mGBA so the copied .sav loads ----
    wait_if_paused()
    close_mgba_rom()
    focus_and_load_rom_from_save()
    load_save_from_title()
    
    # ---- Step 8: Inspect the summary page to check the ribbon colour ----
    wait_if_paused()
    open_summary_for_check()
    if detect_shiny_color():
        print("\n*** SHINY JIRACHI FOUND! ***\n")
        print("🎉🎉🎉 CONGRATULATIONS! You've got a shiny Jirachi after {} attempts! 🎉🎉🎉".format(attempt))
        print("Verify in mGBA (red tags) or PKHeX (red star). Save is at {}".format(SAVE_PATH))
        input("Press Enter to exit...")
        break
    else:
        # ---- Step 9: Not shiny – archive the save for reference ----
        close_mgba_rom()
        if not os.path.exists(JUST_IN_CASE_DIR):
            os.makedirs(JUST_IN_CASE_DIR)
        trial_num = get_trial_number()
        non_shiny_rename = os.path.join(JUST_IN_CASE_DIR, f"JirachiTrial{trial_num}.sav")
        shutil.copy(SAVE_PATH, non_shiny_rename)
        print(f"Copied non-shiny to {non_shiny_rename}")
    
    attempt += 1
    time.sleep(1)  # Brief pause between cycles
