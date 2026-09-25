# Claims ledger

Every capability the film shows or says, and every number on screen, with the place it comes from. `npm run check:claims` reads this table: a line or an on-screen string in `src/timeline.ts` that points at a claim id must find its row here, with a source and the status `OK`.

Sources for a real product are specific: a docs page with its URL, a file and line in the product's code, a screen you opened yourself, a pricing page as fetched on a date. "Marketing says so" is not a source. A claim you cannot source gets rewritten, softened until it is true, or cut.

Fernwise is a fictional product, so its sources point at the fictional spec in `brief.md`.

| id | Claim (what the film shows or says) | Source (where the product really does this) | Status |
|----|-------------------------------------|---------------------------------------------|--------|
| C1 | Knows when each plant needs water | brief.md, "What it does", point 1: a per plant schedule from species, pot size and the last watering | OK |
| C2 | Sends one reminder with the amount of water | brief.md, "What it does", point 2: one notification per watering, with millilitres | OK |
| C3 | Shows the week's waterings in one list | brief.md, "What it does", point 3: the This week screen | OK |

Reserved kinds that need no row: `story` (fiction inside the film: the fern, Tuesday, the other plants), `brand` (name, tagline, URL), `label` (UI chrome that promises nothing, such as "now"), `legal` (disclaimers).
