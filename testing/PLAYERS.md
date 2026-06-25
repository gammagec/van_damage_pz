# Van Damage — TestingServer Player Guide

**Build 42 (unstable branch)**

This is the testing server where we trial mods and settings before they land on prod. Things may change or break. If something feels off, say so — that's the point.

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
