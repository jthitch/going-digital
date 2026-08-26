# Discount codes

Promotional codes that take a fixed £ amount or a percentage off eligible workshops at checkout. These are separate from purchased **gift vouchers**.

## Who can do this

- **Super users** — see and edit all discount codes.
- **Franchisees** — can create codes and attach workshops in their scope; they only see codes they created.

## What “done” looks like

1. An **Active** code exists with a clear string students can type (e.g. `SPRING10`).
2. At least one **workshop** is selected on the code.
3. Optional **expiry date** is set if the offer is time-limited.
4. Students can enter the code in the basket / checkout for those workshops and see the discount.

## Prerequisites

- The workshops you want to discount already exist ([Create a workshop]({{ urls.guide_create_workshop }})).
- Agree the offer: fixed £ off vs % off, and which dates/courses it covers.

## Steps

### 1. Open Discount codes

In admin, go to **Bookings → [Discount codes]({{ urls.discount_code_changelist }})**.

### 2. Add a code

Click **[Add discount code]({{ urls.discount_code_add }})**.

| Field | Guidance |
|-------|----------|
| **Code** | Letters and numbers only; no spaces. Stored in **uppercase**. |
| **Discount type** | **Fixed amount (£)** or **Percentage (%)**. |
| **Amount** | For fixed: pounds off (e.g. `10` = £10). For percent: e.g. `10` = 10% off. |
| **Active** | Must be on for students to use it. |
| **Expiry date** | Optional. After this date the code stops working. |
| **Workshops** | **Required.** Select every workshop the code may be used on. |
| **Notes** | Internal only (why the code exists, campaign name, etc.). |

Save the code.

### 3. Check it on a workshop

Open a linked **[workshop]({{ urls.workshop_changelist }})**. The workshop form shows **Discount codes** that apply to that workshop, plus a shortcut to create another code.

### 4. How students use it

At checkout, the student enters the code. It only applies if:

- the code is **active** and not past its **expiry**,
- the basket includes at least one of the selected **workshops**,
- the calculated discount reduces the payable total.

**Times redeemed** updates when bookings successfully use the code (read-only on the code).

## Common mistakes

- **No workshops selected** — the form requires at least one; without them the code cannot be used.
- **Spaces in the code** — not allowed; use `EARLYBIRD` not `EARLY BIRD`.
- **Wrong amount for type** — `10` as percent is 10%, not £10; check **Discount type**.
- **Inactive or expired** — students will see an error; turn **Active** on or extend **Expiry date**.
- **Expecting gift vouchers** — purchased gift vouchers live under a different admin (Vouchers), not Discount codes.
- **Franchisee can’t see a colleague’s code** — franchisees only see codes they created; ask a superuser if you need a shared/global code.

## Related guides

- **[Create a workshop]({{ urls.guide_create_workshop }})**
- **[Training home]({{ urls.training_index }})**
