# Van Damage — TestingServer Player Guide

**Build 42 (unstable branch)**

This is the testing server where we trial mods and settings before they land on prod. Things may change or break. If something feels off, say so — that's the point.

> **Before you join:** This server runs 51 mods. Project Zomboid defaults to 2 GB of RAM for its Java process — that's not enough. You will likely crash or freeze on the loading screen without allocating more. See [Allocating More RAM](#allocating-more-ram) below before your first session.

---

## Joining the Server

### Step 1 — Add the server to your list

1. Launch Project Zomboid and click **Join** from the main menu
2. Select the **Internet** tab at the top
3. Click **Add** (bottom of the server list) to open the server entry form
4. Fill in the fields:
   - **Name:** Van Damage Testing (or whatever you like)
   - **IP:** `damage.servegame.com`
   - **Port:** `16261`
   - Leave password blank — the server is open
5. Click **Add** to save it, then double-click the entry to connect

### Step 2 — Create your account

The first time you connect you'll be asked for a **username** and **password**. This is your server account — it's not your Steam name, and it's not shared with any other server. Pick something you'll remember; there's no recovery if you forget it.

### Step 3 — Create your character

After logging in you'll land on the character creation screen:

1. Pick a **profession** — each gives a head start in certain skills
2. Spend your **trait points** — you have the normal pool plus **12 bonus free points** on this server
3. Click **Spawn** and pick a location (default: Muldraugh)

You're in. The server **pauses when empty** so you won't miss anything if you're the first one on.

---

## Allocating More RAM

Project Zomboid is a Java game and defaults to a 2 GB heap. With 51 mods loaded, that ceiling is too low — expect crashes or a frozen loading screen without this fix.

**The Steam launch options field does not work reliably for this.** You need to edit the game's JSON config file directly.

### Finding the file

1. Open Steam and go to your Library
2. Right-click **Project Zomboid** → **Manage** → **Browse local files**
3. This opens the game's install folder (something like `Steam\steamapps\common\ProjectZomboid`)
4. Find the file **`ProjectZomboid64.json`** in that folder and open it in a text editor (Notepad works)

### What to change

Look for a line containing `-Xmx` — it controls the maximum heap size. It will look something like:

```
"-Xmx2048m"
```

Change the value to at least **4096m** (4 GB). If you have 16 GB of system RAM or more, **8192m** is better and gives you headroom:

```
"-Xmx8192m"
```

Save the file, then launch the game normally through Steam. You do not need to set anything in Steam's launch options.

> **How much to allocate:** Leave at least 4–6 GB free for Windows and other apps. If your system has 8 GB total, use `4096m`. If you have 16 GB, use `8192m`. More than 16 GB allocated rarely helps and can actually hurt due to garbage collection pauses.

---

## Server Basics

| Setting | Value |
|---|---|
| Max players | 32 |
| PvP | Disabled |
| Server pauses | When empty |
| Day length | 3 real-world hours |
| World start date | July 9, Year 1 (summer) |
| Map | Muldraugh, KY (default spawn) |

---

## Zombies

- **Speed:** Fast shamblers — no sprinters
- **Population:** Normal, skewed toward urban areas
- **Doors:** Cannot open doors
- **Respawn:** Low rate
- **Transmission:** Blood and saliva only
- **Infection:** 2–3 days to turn after infection
- **Reanimate:** Near-instant (under a minute)
- **Strength/Toughness:** Normal

---

## World & Survival

- **Loot:** Slightly reduced across the board (0.6× most categories) — nothing is pre-looted
- **Loot respawn:** Every 8 in-game hours, containers need at least 5 items to trigger
- **Water/electricity:** Shuts off 2–6 months in (14-day grace period modifier)
- **Erosion:** Full erosion at 100 in-game days
- **Fire:** Spreads normally
- **Alarms:** 50% chance on break-ins
- **Blood splats:** Never disappear

---

## Vehicles

- **Spawn rate:** Low
- **Starting condition:** Low — most cars will need work
- **Fuel stations:** Infinite gas
- **Player crash damage:** None
- **Locked cars:** 50% of vehicles are locked
- **Traffic jams:** Enabled
- **Towing:** Available (see mods below)

---

## Safehouses

- Any building type can be claimed (not just residential)
- **Trespassing allowed** even without an invitation
- No fire damage inside your safehouse
- Loot inside your safehouse does not respawn
- Auto-respawn at your safehouse on death
- Safehouse is released after **144 real-world hours** (6 days) of owner inactivity

---

## Character Creation

- **12 bonus free points** on top of the normal trait system
- Bone fractures enabled
- Nutrition system active

---

## Mods

### UI & Quality of Life

| Mod | What it does |
|---|---|
| CleanUI / Clean HotBar | Cleaner, less cluttered interface |
| Equipment UI (Paper Doll) | Visual equipment slots overlay |
| Mini Health Panel | Compact health/injury display |
| Simple Status | Status effect indicators |
| Condition on Dash | Shows item condition on the hotbar |
| Item Use Tooltips | Extra info shown when using items |
| Combat Text | Floating damage numbers |
| Picking Meister | Better lockpick feedback and UI |
| Map Symbol Size Slider | Resize your custom map markers |
| Add More Map Symbols | More icons for the map |
| Has Been Read | Tracks which books and magazines you've already read |
| Proximity Inventory | Access nearby containers without walking to them |
| Visible Generator Range | Shows the power radius of generators |
| Replace Bandage | Quick-replace dirty/used bandages |
| Simple Flashlight on Belt | Attach a flashlight to your belt slot |

### Crafting & Building

| Mod | What it does |
|---|---|
| Neat Crafting | Improved crafting menu |
| Neat Building | Improved building menu |
| The Shortcut | Shortcuts for common build actions |
| Better Electronics | More electronics crafting/repair options |
| Better Auto Mechanics | Expanded vehicle repair options |
| [B42] Useful Barrels | Craft and use barrels for storage/liquid |
| [B42] Water Pipes | Build water pipe networks |
| Common Sense | More intuitive interactions (breaking windows, entering buildings) |

### Inventory & Containers

| Mod | What it does |
|---|---|
| Stack All | Stack all stackable items in one click |
| Manage Containers | Better container sorting and management |
| Containers! | Additional container types |
| Dynamic Backpack Upgrades | Upgrade backpack capacity with found items |
| Open All Containers | Open nearby containers simultaneously |
| [B42] Now You Can Loot It! | Loot more world objects that were previously inert |

### Food & Survival

| Mod | What it does |
|---|---|
| Project Cook | Expanded cooking system with new recipes |
| Vanilla Foods Expanded | More food item variety from existing world loot |
| Rain Cleans Blood | Rain gradually washes blood off surfaces and clothes |

### Skills & Character Progression

| Mod | What it does |
|---|---|
| Lifestyle: Hobbies | Hobby system — activities your character does during downtime that grant bonuses |
| Gyde's Trait Magazines | Find magazines in the world that unlock traits |
| Skill Recovery Journal | Write journal entries that let you recover skills after death |
| Burd's Survival Journals | Expanded journal system for tracking survival progress |
| Jeeve's PC | Computers found in the world run training disks to level skills |

### Combat & Gear

| Mod | What it does |
|---|---|
| darlak's H.E.C.U. | Military equipment and uniforms |
| ALICE Gear | Military-style backpacks and loadout gear |
| Legendary Katana & Wakizashi | Craftable high-tier melee weapons |
| Drag Bodies Faster (60%) | Move zombie bodies at 60% speed instead of the vanilla crawl |

### Vehicles & Transport

| Mod | What it does |
|---|---|
| Autotsar Trailers | Tow trailers behind vehicles for extra hauling capacity |
| Effortless Towing | Simplified hookup for towing vehicles and trailers |

---

## Notes for Testers

- Settings and mods here may not match prod — that's intentional
- If a mod breaks something or causes lag, report it with the mod name
- The server is on Build 42 **unstable** — PZ itself may have bugs unrelated to our setup
