# Relics

A relic is earned by the practice and by nothing else. None can be bought. Progress is computed by `public.my_relics()` from the member's own days and vows.

| Relic | Pillar | Rule | Counted from |
|---|---|---|---|
| The Iron Ring | Body | Thirty sealed days with the Body pillar marked. | `days.ticks.body` on sealed days |
| The Owl of Athena | Mind | Fifty sealed days with the Mind pillar marked. | `days.ticks.mind` on sealed days |
| The Vigil Lamp | Faith | Thirty evening reviews sealed. | sealed days with a review |
| The Sealed Vow | Relationships | A thirty-day vow, reached to its end. | `vows` of 30 days, days since it began |
| The Broken Chain | All | Fall a rank, then keep thirty days unbroken. | `standings.drops` ≥ 1 and current streak ≥ 30 |
| The Hourglass of Seneca | Mind | The oath taken before six, on thirty mornings. | `days.oath_at` in the member's timezone |
| The Laurel of the Hundred | All | One hundred days unbroken. | longest streak |
| The Helm of the Three Hundred | Body | A forty-day campaign with your house. | Campaigns are not built yet. Shown as "Not open yet". |

Notes
- The Hourglass counts thirty mornings in total, not thirty in a row.
- The Sealed Vow counts days since the vow began. It does not yet check that each of those days was sealed.
- The site only displays relics. A member cannot write relic state; it is always recomputed.
