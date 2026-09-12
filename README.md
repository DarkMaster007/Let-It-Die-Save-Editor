# LET IT DIE Save Editor

Version 5.0.0 is a Windows save editor for the Steam edition of LET IT DIE. It reads the game's compressed `.sav` files, edits the decoded data, and writes them back in the format expected by the game. Equipment, material, decal and armor-set catalogs are included.

This release moves the desktop interface to PySide6. The save engine remains the engine from 4.2.0; the migration fixes are in the interface and its connections to that engine. The previous Tkinter interface is retained for comparison and maintenance.

[Download 5.0.0](https://github.com/g3usyk/Let-It-Die-Save-Editor/releases/tag/v5.0.0) | [Technical documentation](docs/README.md) | [License](LICENSE)

## Running the editor

Download `LetItDieSaveEditor.exe` from the release page and place it in a writable folder. This full build includes the image catalog and does not require Python. It requests administrator privileges because some Steam installations restrict access to game files.

Close the game before opening a save. The editor searches Steam libraries for `<SteamLibrary>/steamapps/common/LET IT DIE/Savedata/<account>.sav`. It also checks a `CurrentSave` folder beside the application. Use the file browser if detection selects the wrong file. The path at the top of the window is the file being edited.

Most editing actions save immediately. The main Save button also applies the currency fields before writing. Keep the original backup: a successful write does not establish that every possible combination of edited values is valid in the game.

The full 5.0.0 download replaces the Lite executable offered in the previous release. Keep your save and backup folders when replacing the executable. Personal saves and the game database are not included.

## Features

| Area | Operations |
| --- | --- |
| Currencies and facilities | Death Metals, Kill Coins, SPLithium, Bloodnium, Recycle Points, bank and tank levels, player rank, VIP state and account counters |
| Fighters | Names, classes, grades, levels, allocation points, character models, revival, creation, cloning, deletion and freezer order |
| Materials and inventory | Exact locker quantities, additive deposits, capacity, recipe deficits, equipment, mushrooms and beasts |
| Decals | Standard and premium inventory, collection filters, presets and fighter equipment |
| Equipment and research | Blueprint unlocks, research targets, equipment delivery, armor-set progression, durability and ammunition |
| Mastery and tower | Weapon mastery, exploration records, elevators, progression flags, quests, stamps and TDM repairs |
| Save management | Ten local slots, original and session backups, restoration, JSON import/export and account re-binding |

Some commands modify `masters.db` rather than the save. Death Bag database expansion and shop-tier changes belong to this category. Their effects and backups are separate from `.sav` edits. The editor locates the database in the game installation; it does not ship a replacement database.

## Changes in 5.0.0

- The eight main sections and their dialogs now use Qt widgets and a shared stylesheet.
- Rebuilding the fighter list preserves the selected fighter. Saving an edit no longer redirects the next action to the first entry.
- Materials, blueprints and decals retain their selection when a catalog refreshes.
- Setting a material quantity differs from adding units. Reducing stock clears the corresponding locker references and leaves bag items alone.
- The inventory viewer reads the actual entity collections instead of an unrelated `storage.part` structure.
- Premium decal edits retain the premium ID when their catalog metadata comes from a standard entry.
- Dialogs and the main Save action no longer write the same save twice. Autosave failures are reported instead of discarded.
- Account re-binding uses the existing engine API, copies the source before editing, and exposes name, UID and session options.
- The speculative compatibility functions introduced during the migration have been removed. Callers use the established core operations.

The maintainer tested the repaired interface in-game before release. The automated suite passed 140 tests; one further test was skipped because its external save fixture was unavailable. These checks cover specific regression cases, not every game state.

## Architecture

```text
editor_gui.py               Entry point; Qt launcher and retained Tkinter window
ui_qt/
  main_window.py            Active save, application actions and persistence
  tabs/                     Eight editor sections
  dialogs/                  Armor sets, inventory, account tools and backups
  save_actions.py           Exact stock adjustment and inventory grouping
  theme.py, styles.qss      Assets and presentation
ui/                         Previous Tkinter tabs and dialogs
modifiers.py                Public re-exports of core operations
core/
  fighters.py               Fighter edits and freezer synchronization
  storage.py                Inventory entities and locker slots
  blueprints.py             Research, equipment and progression
  currencies.py             Resources, facilities and VIP state
  decals.py                 Owned and equipped decals
  mastery.py, tower.py      Mastery and tower progression
  tdm.py                    TDM repair
  helpers.py                Structure normalization and database discovery
  save_slots.py             Local slots and backup history
  account_rebind.py         Account identity and UID adaptation
  asset_manager.py          Local assets and download cache
save_io.py                  BRG/ZLIB reader, writer and backups
game_data.py, *.json         Catalogs, constants and reference data
i18n.py, locales/           Localization
tests/                      Engine and UI integration tests
tools/                      CLI, catalog tools and packaged build checks
build_exe.py                PyInstaller configuration
version.json, updater.py    Release metadata and update checks
```

The normal edit path is:

```text
Qt action -> modifiers/core function -> active save dictionary
          -> main window autosave -> save_io.save_to_file
          -> backup -> normalization -> compression -> atomic replacement
          -> active slot/session synchronization, when a slot is selected
```

Core operations usually mutate the supplied dictionary in place. The UI owns selection, input, refreshes and when to persist the result. `modifiers.py` is an import surface, not a second implementation of the game rules. A function with a similar name is not a valid adapter unless its arguments and behavior match the operation being requested.

## TODO Tracker

A read-only TODO tracker for monitoring grinding progress toward material, mushroom, beast and currency targets. It reads the encrypted `.sav` file and reports how much of each tracked item is in Coin Locker storage, in fighters' deathbags, and in items sent back to F0 / Waiting room via Dustin (found in `soul.present` under `DUSTSHOOTER_CHARGE`).

The tracker does not modify the save file.

### Running

From a checkout with the project dependencies installed:

```bash
python3 start_todo_tracker.py
```

Or use the project launcher scripts after setting up a virtual environment:

```bash
./setup_and_run.sh            # Linux
setup_and_run.bat             # Windows
```

Use `--save <path>` to open a specific save on launch:

```bash
python3 start_todo_tracker.py --save Savedata/76561198140783693.sav
```

The save path can also be selected from the File menu or the Select Save File button.

### Reading saves directly

Three CLI scripts read specific save structures from an encrypted `.sav`:

```bash
python3 read_deathbag.py <save.sav>        # fighter deathbags
python3 read_base_storage.py <save.sav>    # soul.cl Coin Locker contents
python3 read_reward_box.py <save.sav>      # soul.present (including Dustin-sent items)
```

Each script can also pick a file with a file dialog when no path is given.

### How the progress counter works

Each TODO item shows the storage amount and target, for example `12/207`. When a non-storage amount is present — items in a fighter's deathbag or items sent to base via Dustin — a green `+n` prefix is shown on the left of that counter, for example `+3 12/207`. The prefix is omitted entirely when the combined non-storage count is zero.

### Adding and managing TODOs

Use the Add TODO dialog to pick a material, mushroom, beast or currency, give it a target amount, and start tracking it. Double-click a row to edit a TODO. Completed TODOs can be cleared from the TODO menu. The TODO list is saved as JSON in `~/.lid_todo_tracker/todo_list.json`.

### Files

```text
start_todo_tracker.py     Launcher
setup_and_run.sh / .bat   Virtual environment setup and launch helpers
todo_tracker/
  read_save.py            Save analysis: storage, deathbag, Dustin-sent items, currencies
  todo_manager.py         TODO list management and progress tracking
  todo_types.py           TodoItem and TodoType definitions
  gui.py                  PySide6 interface and progress column delegate
  test_todo_tracker.py    Basic tests
```

### Notes

- The tracker is read-only. It does not write to the save file.
- The Dustin-sent items count reflects items waiting in base storage / the Reward Box. Once those items are collected in-game and moved into the Coin Locker, they are counted as storage and the `+n` prefix is reduced accordingly.
- Personal saves and the game database are not included in the repository.

The implementation is in [save_io.py](save_io.py). Integer fields below are unsigned 32-bit little-endian values.

| Offset | Length | Writer output |
| --- | ---: | --- |
| `0x00` | 4 | `BRG\0` magic |
| `0x04` | 4 | Save-format version retained from the loaded file |
| `0x08` | 4 | Total uncompressed JSON size in bytes |
| `0x0C` | 4 | `ZLIB` marker |
| `0x10` onward | Variable | Chunk headers and compressed payloads |
| End | 4 | Zero chunk-length terminator |

Each chunk begins with its uncompressed size and compressed size, followed by a separate zlib stream. The reader joins the decompressed chunks and parses UTF-8 JSON. The writer emits compact JSON in four balanced chunks by default. The save-format version is independent of the editor version: editor 5.0.0 does not convert a save's version to 5.

Writing normalizes known empty-list structures, compresses the result, writes a temporary file beside the destination and replaces the destination with `os.replace`. Equivalent decoded data does not imply byte-identical compressed output.

## Save schema and references

There is no single flat fighter or inventory object. Editing an entity often requires updating references elsewhere in the save.

| Save path | Meaning and relationship |
| --- | --- |
| `user.uid` / `soul.uid` | Internal account identifier. JSON object keys use its string representation. This is separate from the Steam account ID. |
| `user.psnacid` | External account identifier used by the Steam save and re-binding tools. |
| `bodyuser[uid]` | Fighter bodies, level, allocation points and bonuses. Entries carry a fighter `cid`. |
| `soul.chr.chrs[uid]` | Character records: name, class, grade, model and live state. The engine coordinates these with `bodyuser`. |
| `soul.chr.slots[uid]` | Freezer positions referencing fighter CIDs. Reordering and cloning must update these references. |
| `item.items` | Material entities, with an `eid`, `itemid` and owner. |
| `mushroom.msrs` / `beast.bsts` | Mushroom and beast entities using `msrid` and `bstid`. Mushroom state distinguishes cooked items. |
| `part.pts` | Equipment entities. Existing readers handle lists and UID-keyed collections. |
| `soul.cl` | Coin Locker slots referencing entity EIDs. Types: equipment `0`, mushroom `1`, beast `2`, material `3`, empty `-1`. |
| `soul.skl.psskl` | Owned decals, identified by `sklid`, with quantity in `cnt`. Premium IDs use `_P`. |
| `soul.skl.eqskl[uid]` | Equipped decals associated with a fighter CID and a slot. |
| `soul.partresearch.user` | Blueprint research records. Several records and states may describe one progression chain. |
| `playlog.base` and progression sections | Statistics and progression data. Editing the highest-floor counter differs from unlocking access to floors. |

Use `get_player_uid` instead of assuming a UID key of `"1"`. Do not substitute HP allocation points for live HP. Fighter maximization includes the engine's existing normalization and synchronization work; it does more than assign `lvl = 247`.

Locker quantities are derived from entities and references. Adding a synthetic count under `storage.part` does not create usable items. Removing stock must remove the intended entities and clear their locker references without deleting items owned by a fighter.

Displayed equipment enhancement and stored level are not interchangeable. Equipment commonly displays `+0` for stored level `1`. Research has its own state and target rules. Use `core.blueprints` rather than applying one conversion to every level field.

## Backups, slots and account identity

`Backups/` lives beside the executable, or under the project directory when running from source. The first original backup is retained separately; timestamped backups rotate with a default limit of ten per save filename.

`SaveSlots/` contains ten slots, metadata and per-slot backup directories. Session recording archives history and synchronizes the selected slot with the current edited save. A slot is therefore not an immutable checkpoint. Restore its original or historical backup to return to an earlier state. Session backups normally use a 15-second interval and retain up to 25 non-original backups per slot.

Account re-binding copies the decoded source before changing it. Steam ID replacement, player-name changes, session clearing and UID adaptation are separate options. [core/account_rebind.py](core/account_rebind.py) defines exactly which collections are remapped; it does not recursively replace every matching number in the file.

## Development and tests

The 5.0.0 Windows build uses Python 3.13, PySide6 and PyInstaller. From a checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python editor_gui.py
```

Use `python editor_gui.py --legacy-tk` to run the previous interface.

Run `python run_tests.py` for the suite. Some integration tests expect a local fixture under `CurrentSave`; personal files are intentionally absent from Git. These tests assert specific fixture values, so an arbitrary save is not interchangeable. Synthetic-data tests can be run independently, for example `python -m unittest tests.test_currencies tests.test_storage`.

Qt tests disable automatic save detection and use temporary destinations. A regression test should exercise the UI action, check the affected structures and verify unrelated entities are preserved. For persistence changes, decompress the written file and inspect the result. Do not point automated editing tests at the game's active save.

## Building a release

```powershell
python -m pip install pyinstaller
python build_exe.py
```

The result is `dist/LetItDieSaveEditor.exe`. The full build contains Qt dependencies, catalogs, locales, the stylesheet and the image library. `--onedir` produces a directory build. `--lite` includes only essential icons; it is not the full catalog distributed for 5.0.0.

The packaged executable can verify its imports, catalogs, eight tabs and a synthetic save round trip without loading a player's save:

```powershell
.\dist\LetItDieSaveEditor.exe --self-test C:\Temp\lid-build-check
```

This writes `result.json` and a window capture, or `error.txt` on failure. Windows file metadata is in `tools/windows_version_info.txt`. Keep it synchronized with `version.json`, `updater.py` and `installer.iss` when releasing.

## Contributing

Keep game-state operations in `core`, UI behavior in its frontend and binary serialization in `save_io`. Explain the save paths an operation touches and whether it modifies a database on disk. Add a regression test for the failure being fixed, including entity references when creating, removing or reordering data.

Do not commit personal saves, account tokens, local databases, generated executables, caches or backups. Executables belong in GitHub Releases. Older research notes remain in [docs](docs/README.md); where historical limits conflict with current code, use the implementation and tests as the reference.

Project code is licensed under MIT. Game names and extracted game assets belong to their respective owners.
