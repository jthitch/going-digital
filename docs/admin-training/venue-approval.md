# Venue approval & content changes

Venues use an approval workflow so franchisees can propose locations and content without publishing unchecked changes.

## Who does what

| Role | Can |
|------|-----|
| **Franchisee** | Create venues; edit content on owned venues; request approval; cannot usually toggle public **Active**. |
| **Super user** | Approve / reject venues; apply or reject pending content changes; set **Active**. |

## New venue approval

1. Franchisee creates a venue via **[Add venue]({{ urls.venue_add }})** and saves.
2. They submit for approval (approval decision / request flow on the venue form).
3. Superuser opens **[Venues]({{ urls.venue_changelist }})** — use filters for pending approval.
4. Review address, region, map pin, and content.
5. Set approval to **Approved** or **Rejected** (rejection needs a reason when required).
6. Turn **Active** on when it should appear on [public venues]({{ urls.public_venues }}).

Dashboard alerts may also highlight pending venue approvals.

## Content changes on an already-approved venue

When a franchisee edits marketing content on an approved venue:

1. The **live** public page stays on the previously approved content.
2. A **pending content change** is stored for review.
3. Superuser opens the venue, previews the pending content, then **Apply** or **Reject**.
4. Apply publishes to the live content; reject discards the proposal.

Workshops can usually still be managed while content is pending — check the venue form notes for your role.

## Checking the live site

After approval or apply:

1. Open the [venue list]({{ urls.public_venues }}) on the website.
2. Open your venue’s detail page and check the content looks right.
3. Confirm workshops still list correctly.

## Common mistakes

- Approving without checking lat/lng — map and “near me” suffer.
- Leaving Active off after approval — venue stays invisible.
- Franchisees expecting instant live content edits — those need Apply on pending changes.
- Rejecting without a clear reason — franchisees can’t fix the issue.

## Related guides

- **[Create a venue]({{ urls.guide_create_venue }})**
- **[Create a workshop]({{ urls.guide_create_workshop }})**
- **[Training home]({{ urls.training_index }})**
