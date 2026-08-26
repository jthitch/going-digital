# Create a venue

This guide shows how to add a photography venue so workshops can be scheduled there and the venue can appear on the public site.

## Who can do this

- **Super users / administrators** — full control, including Active and final approval.
- **Franchisees** — can create and edit venues in their regions; new venues and content changes usually need superuser approval before they go live.

## What “done” looks like

1. Venue exists in admin with a clear name, town, address, and map coordinates.
2. Approval is **Approved** (and **Active** is on) if it should appear publicly.
3. Optional content (strapline, main content, images) is filled in.
4. You can open the public venue page and see it listed under [Venues]({{ urls.public_venues }}).

## Prerequisites

- Know which **region** the venue belongs to (franchise territory).
- Have the postal address (and ideally a UK postcode) ready.
- Optional: photos and joining-instructions PDF.

## Steps

### 1. Open Venues in admin

Go to **[Venues]({{ urls.venue_changelist }})** in the Courses section of admin.

### 2. Add a venue

Click **[Add venue]({{ urls.venue_add }})**.

Fill in at least:

| Field | Guidance |
|-------|----------|
| **Venue name** | Public name students will see. |
| **Slug** | URL segment (auto-fills from the name; keep it short and unique). |
| **Location** | Town/city label (e.g. `Bath`). Used on the site and for city SEO pages. |
| **Venue address** | Full postal address including postcode when possible. |
| **Region** | Correct franchise region. |
| **County** | Optional but helps structured data. |
| **Latitude / Longitude** | Required for map search; use postcode lookup on the form when available. |
| **Telephone / URL** | Optional contact details for the venue. |

### 3. Content & SEO (recommended)

Add or edit linked content fields when shown:

- Strapline and main content (what makes this venue good for photography).
- Meta title / description for search engines.

### 4. Images

Attach venue images from the media section when available. Prefer clear exterior/interior shots students will recognise.

### 5. Save and approval

- Franchisees: save and **request approval** if the form offers it. The live page stays unchanged until a superuser approves.
- Superusers: set approval to **Approved**, ensure **Active** is on, then save.

See also: [Venue approval & content changes]({{ urls.guide_venue_approval }}).

### 6. Check the public site

1. Open **[Venues on the website]({{ urls.public_venues }})** and find your venue (or search by town).
2. Open the venue detail page and confirm name, address, and content.
3. Later, when workshops exist, they should list under “Upcoming courses at this venue”.

## Common mistakes

- Leaving **Location** blank — town pages and filters work better when this is filled.
- Missing lat/lng — venue won’t show usefully on the course map.
- **Active** off — venue is hidden from the public site.
- Editing content on an approved venue as a franchisee — changes may sit as a **pending content change** until approved (live page unchanged).

## Related admin tools

- **[Region map]({{ urls.region_map }})** — check which region a place falls into.
- **[Training home]({{ urls.training_index }})** — all guides.

## Next step

Once the venue is approved and active, create bookable dates: **[Create a workshop]({{ urls.guide_create_workshop }})**.
