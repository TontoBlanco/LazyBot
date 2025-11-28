Lazy Jirachi Bot — One-Frame-Per-Cycle Procedure
================================================

This document captures the fully updated, self-contained workflow for preparing and executing `lazy_jirachi_bot.py` in “One Frame Per Cycle” mode. It folds in every fix discussed so far: Dolphin `.sav` handling, mGBA↔Dolphin copy-back, post-transfer color verification, retry logic, 10s sleeps for stability, and path-debug prints.

* Odds: 1/7282 per cycle (average 7,282 cycles).  
* Cycle time: ~10–15 minutes due to long sleeps + transfer loading.  
* Total runtime for a hit: potentially weeks or months.  
* Freeze handling: ignored — the script still copies the save back for safety.  
* Automation pauses only after a shiny check succeeds so you can verify manually.

--------------------------------------------------------------------

Step 1 — Verify / Install Emulators & Supporting Tools
------------------------------------------------------

1. **mGBA (RTC grinding environment)**
   - Download 0.10.3+ from <https://mgba.io/downloads.html>.
   - Install to `C:\Program Files\mGBA`.
   - Place ROM at `C:\mGBA\ROMs\Pokemon - Sapphire Version (USA, Europe).gba`.  
     Confirm CRC32 `554dedc4` via `Tools > ROM Info`.
   - Progress the save until Mystery Gift is unlocked and you can save in the overworld.
   - `Settings > Keyboard`: bind frame advance to `N`.
   - `Settings > Emulation`: disable “Pause when inactive”; enable “Real-time clock”.
   - Position the window so the top-left corner sits at `(0, 0)` on your desktop.

2. **Dolphin (Bonus Disc transfers)**
   - Download the latest beta (5.0-20000+) from <https://dolphin-emu.org/download/>.
   - Extract to `C:\Dolphin\Dolphin-x64`.
   - Place `gba_bios.bin` inside `C:\Dolphin\Sys`.
   - In Dolphin:  
     - `Config > GameCube > GBA Settings`: set BIOS to `C:\Dolphin\Sys\gba_bios.bin`, Port 2 ROM to your Sapphire ROM, uncheck “Save in Same Directory as ROM”, check “Run GBA Cores in Dedicated Threads”.  
     - `Controllers`: Port 1 Standard Controller (WASD stick, `Z` for A, `X` for B, `Space` for Start). Port 2 GBA (Integrated) with `Enter` A, `Backspace` B, arrows D-pad, `Tab` Start, `Shift` Select, `Q/E` L/R.  
     - `Config > Interface`: enable “Background Input”.  
   - Add ISO: `C:\Dolphin\Games\Pokemon Colosseum Bonus Disc.iso`.
   - Window placement: align Dolphin on the right side at approximately `(400, 0)`.

3. **PKHeX (manual verification post-hit)**
   - Download from <https://projectpokemon.org/home/files/file/1-pkhex/>.
   - Extract to `C:\PKHeX`.
   - Test: open a `.sav`, confirm shiny party members show a red star.

4. **Python + libraries**
   - Install Python 3.12+ (ensure “Add to PATH” is checked).
   - Install dependencies:

     ```
     pip install pyautogui pillow numpy psutil
     ```

   - Validate:

     ```
     python -c "import pyautogui, PIL, numpy, psutil; print('OK')"
     ```

Step 2 — Prepare Directories & Backups
--------------------------------------

1. Create `C:\mGBA\ROMs\backups`.
2. Copy the pre-transfer save (`raw_shiny_target_time.sav`) into that backup folder.
3. Delete any existing Dolphin-side post-transfer save (`Pokemon - Sapphire Version (USA, Europe)-2.sav`) to avoid stale state.

Step 3 — Calibrate Screen Positions & Color Regions
---------------------------------------------------

1. Perform a manual transfer once so the Dolphin summary screen is reachable for testing.
2. Run your mouse-position helper (e.g., `python position_tracker.py`) and capture:
   - `DOLPHIN_CLICK`
   - `MGBA_CLICK`
3. Record the mGBA screen bounding box (`MGBA_SCREEN_BBOX`). Hover the top-left and bottom-right edges of the game screen (240×160).
4. Determine the tag highlight area (`TAG_AREA_REL`) within the summary screen. Use the standalone snippet below to grab a screenshot and inspect colors.

Standalone Tag-Color Snippet
----------------------------

```python
from PIL import ImageGrab
import numpy as np

MGBA_SCREEN_BBOX = (0, 30, 240, 190)      # Update with your bounds
TAG_AREA_REL = (71, 228, 91, 248)         # Update to fit tag region

img = ImageGrab.grab(bbox=MGBA_SCREEN_BBOX)
tag_img = img.crop(TAG_AREA_REL)
tag_img.save('tag_test.png')

tag_array = np.array(tag_img)
avg_color = np.mean(tag_array, axis=(0, 1))
red, green, blue = avg_color
print(f"Avg: R={red:.1f}, G={green:.1f}, B={blue:.1f}")

if red > blue + 50 and red > 100:
    print("Shiny (red tags)")
else:
    print("Normal (blue tags)")
```

Test with both shiny and non-shiny summaries to ensure the thresholds hold.

Step 4 — Dry Run / Testing
--------------------------

1. Do a full manual transfer to confirm the pipeline: save in mGBA, transfer via Dolphin, receive Jirachi, open summary.
2. Close Dolphin after the transfer.
3. Copy the Dolphin save back to your mGBA path, renaming it to match the ROM name so mGBA auto-loads correctly.
4. Execute the color-detection snippet with a non-shiny summary on screen — it should fail the shiny test and, in the bot, trigger the “move to `Just_In_Case`” flow.

Step 5 — Execute the Bot
------------------------

1. Launch mGBA with no ROM loaded.
2. Launch Dolphin with no ISO loaded.
3. Open a terminal (`Win+R`, `cmd`, or PowerShell), move to your working directory, e.g.:

   ```
   cd %USERPROFILE%\OneDrive\Desktop
   python lazy_jirachi_bot.py
   ```

4. When prompted, press Enter to begin attempts. The script:
   - Restores the original `raw_shiny_target_time.sav`.
   - Loads mGBA, advances exactly one frame (`N`), saves, and closes.
   - Moves the save into Dolphin’s Port 2 slot (`Pokemon - Sapphire Version (USA, Europe)-2.sav`).
   - Loads the Bonus Disc ISO, runs through the transfer inputs using long 10s sleeps, and waits 60s during the actual send.
   - Closes Dolphin, copies the `.sav` back to mGBA, reloads, opens the party summary, and performs the red-tag detection (`R > B + 50 and R > 100`) inside the tuned bounding box.
   - If shiny: prints a celebratory banner, pauses for manual confirmation, and leaves the `.sav` in place for PKHeX verification.
   - If not shiny: closes mGBA, ensures `C:\mGBA\Just_In_Case` exists, increments `trial_count.txt`, moves the save as `JirachiTrial#.sav`, and restarts from the top.

10-Second Sleep Rationale
-------------------------

Every UI interaction (clicks, hotkeys, menu entries) is followed by `time.sleep(10)` to accommodate emulator load, window focus swings, and occasional lag spikes. The only exception is the 60-second wait after initiating the transfer sequence to ensure the entire send completes before copying files.

Updated Script Location
-----------------------

* Path: `lazy_jirachi_bot.py`
* Highlights:
  - Global configuration for ROM/ISO paths, click coordinates, bounding boxes, and directories.
  - `backup_save_files()` runs at startup and prints path existence for both `SAVE_PATH` and `ORIGINAL_BACKUP`.
  - Deterministic frame advancement (`advance_frame` + `save_at_new_frame`) before each transfer.
  - Post-transfer summary automation (`open_summary_for_check`) plus color detection via `detect_shiny_color`.
  - Retry loop that archives non-shiny attempts with incremental counters in `C:\mGBA\Just_In_Case`.
  - Debug statements throughout to confirm copy operations and file presence.

Notes & Tips
------------

* Keep both emulators open but idle; the bot handles loading/unloading every cycle.
* Dolphin’s GBA save is always `Pokemon - Sapphire Version (USA, Europe)-2.sav` because the Bonus Disc uses Port 2.
* If color detection ever throws errors (e.g., Windows permission issues), the exception is caught and treated as “not shiny” so the loop can continue.
* You can temporarily reduce sleeps to ~1s for debugging, but restore 10s for unattended multi-day runs.
* When a shiny hits, verify via PKHeX (red star) or in-game tags, then duplicate the `.sav` before resuming any other work.
