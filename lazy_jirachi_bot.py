import time
import pyautogui
from PIL import ImageGrab
import os
import shutil
import datetime
import numpy as np
import psutil

# =====================================
# CONFIGURATION – EDIT THESE VALUES
# =====================================
ROM_PATH = r"C:\mGBA\ROMs\Pokemon - Sapphire Version (USA, Europe).gba"  # Full path to ROM
ISO_PATH = r"C:\Dolphin\Games\Pokemon Colosseum Bonus Disc.iso"  # Full path to ISO
SAVE_PATH = r"C:\mGBA\ROMs\Pokemon - Sapphire Version (USA, Europe).sav"  # mGBA save path
DOLPHIN_SAV_PATH = r"C:\Users\colem\AppData\Roaming\Dolphin Emulator\GBA\Saves\Pokemon - Sapphire Version (USA, Europe)-2.sav"  # Dolphin save path
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

# =====================================
# CORE FUNCTIONS
# =====================================
def focus_and_load_rom():
    pyautogui.click(MGBA_CLICK)
    time.sleep(10)
    pyautogui.hotkey('ctrl', 'o')
    time.sleep(10)
    pyautogui.typewrite(ROM_PATH)
    time.sleep(10)
    pyautogui.press('enter')
    time.sleep(10)  # Wait for load
    print("Loaded ROM in mGBA.")

def focus_and_load_iso():
    pyautogui.click(DOLPHIN_CLICK)
    time.sleep(10)
    pyautogui.hotkey('ctrl', 'o')
    time.sleep(10)
    pyautogui.typewrite(ISO_PATH)
    time.sleep(10)
    pyautogui.press('enter')
    time.sleep(10)  # Wait for load
    print("Loaded ISO in Dolphin.")

def advance_frame():
    pyautogui.click(MGBA_CLICK)  # Ensure focus
    time.sleep(10)
    pyautogui.press('n')
    time.sleep(10)
    print("Advanced frame in mGBA.")

def save_at_new_frame():
    pyautogui.click(MGBA_CLICK)  # Ensure focus
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
    pyautogui.click(DOLPHIN_CLICK)  # Ensure focus
    time.sleep(10)
    pyautogui.press('left')  # Your specified arrow
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
    pyautogui.click(DOLPHIN_CLICK)  # Ensure focus
    time.sleep(10)
    pyautogui.press('-')
    time.sleep(10)
    pyautogui.press('space')
    time.sleep(10)
    print("Closed game in Dolphin.")

def close_mgba_rom():
    pyautogui.click(MGBA_CLICK)  # Ensure focus
    time.sleep(10)
    pyautogui.hotkey('ctrl', 'k')
    time.sleep(10)
    print("Closed ROM in mGBA.")

def open_summary_for_check():
    pyautogui.click(MGBA_CLICK)  # Ensure focus
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
    for proc in psutil.process_iter():
        if proc.name() == DOLPHIN_EXE_NAME:
            proc.kill()
            print("Killed Dolphin process.")
            time.sleep(2)
            break

def get_trial_number():
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
backup_save_files()
input("Press Enter to start...")

attempt = 1
while True:
    print(f"Attempt {attempt} started.")
    
    # Step 1: Copy original sav to mGBA path
    if os.path.exists(ORIGINAL_BACKUP):
        shutil.copy(ORIGINAL_BACKUP, SAVE_PATH)
        print(f"Debug: Copied to SAVE_PATH, now exists: {os.path.exists(SAVE_PATH)}")
    else:
        print("ERROR: Original backup not found - check path.")
        break
    
    # Load ROM in mGBA, advance frame, save, close
    focus_and_load_rom()
    advance_frame()
    save_at_new_frame()
    close_mgba_rom()
    
    # Step 2: Move sav to Dolphin path
    if os.path.exists(SAVE_PATH):
        shutil.move(SAVE_PATH, DOLPHIN_SAV_PATH)
        print("Moved save to Dolphin path.")
    else:
        print("ERROR: Save file not found after save - check mGBA settings.")
        break
    
    # Step 3: Load ISO in Dolphin
    focus_and_load_iso()
    
    # Step 4: Transfer
    auto_transfer_dolphin()
    
    # Step 5: Close Dolphin game
    close_dolphin_game()
    # kill_dolphin()  # Uncomment if close fails
    
    # Step 6: Copy Dolphin sav back to mGBA path
    shutil.copy(DOLPHIN_SAV_PATH, SAVE_PATH)
    print("Copied Dolphin save back to mGBA path.")
    
    # Step 7: Load ROM in mGBA
    focus_and_load_rom()
    
    # Step 8: Open summary and check if shiny via color
    open_summary_for_check()
    if detect_shiny_color():
        print("\n*** SHINY JIRACHI FOUND! ***\n")
        print("🎉🎉🎉 CONGRATULATIONS! You've got a shiny Jirachi after {} attempts! 🎉🎉🎉".format(attempt))
        print("Verify in mGBA (red tags) or PKHeX (red star). Save is at {}".format(SAVE_PATH))
        input("Press Enter to exit...")
        break
    else:
        # Step 10: Not shiny - close ROM, move to Just_In_Case
        close_mgba_rom()
        if not os.path.exists(JUST_IN_CASE_DIR):
            os.makedirs(JUST_IN_CASE_DIR)
        trial_num = get_trial_number()
        non_shiny_rename = os.path.join(JUST_IN_CASE_DIR, f"JirachiTrial{trial_num}.sav")
        shutil.move(SAVE_PATH, non_shiny_rename)
        print(f"Moved non-shiny to {non_shiny_rename}")
    
    attempt += 1
    time.sleep(1)  # Brief pause between cycles