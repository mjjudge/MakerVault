# UX Notes

> These notes describe intended user experience direction. No UI has been built yet. They are inputs for frontend design and implementation.

---

## Core principle: the system should feel like a workshop tool, not an enterprise application

The primary user is a maker at a workbench. Interactions should be fast, low-friction, and forgiving. Assume the user knows roughly what they want but may not remember exact names or part numbers.

---

## Fast search-first workflow

- The search bar should be prominent and always accessible
- Search should work on partial names, common abbreviations, capabilities, and tags
- Results should show: part name, category, total quantity owned, and location summary — all visible without clicking through
- Typing "esp32" should return ESP32 boards; typing "i2c temp" should return I2C temperature sensors
- The user should never have to browse a hierarchy to find something they can describe

---

## Physical location clarity

- Every stock item should display its full location path clearly: Room → Container → (optional sub-container)
- Example: "Loft → Box B → Blue Tray 4"
- Location should be visible without expanding any extra panel
- Moving a part to a different location should be a single action (drag, button, or quick form — TBD)

---

## Low-friction stock updates

- Updating quantity should be a single click-to-edit field, not a full form
- Marking a part as used (decreasing stock) should be fast, with an optional reason field
- Adding a new stock instance should allow specifying quantity, location, and condition in one form
- Common actions (find, add, move, mark used) should not require more than two or three interactions

---

## Document attachment and viewing

- Attaching a document to a part should be a simple drag-and-drop or file picker
- Supported types: PDF, image (JPEG, PNG, WebP), plain text, HTML
- Inline viewer: PDFs should be viewable in-browser without downloading; images should display immediately
- Documents should be clearly labelled with their type: datasheet, manual, pinout, note, receipt, vendor page
- If a document has an original URL, it should be shown for reference — but the locally stored copy is what is used
- Users should be able to add a plain-text note directly in the UI without uploading a file

---

## Project inspiration flows

- A "what could I build?" prompt should return a short list of project ideas, each with:
  - A brief description
  - Which parts from the inventory would be used
  - A confidence or relevance indicator
- Users should be able to click through from a suggestion to see the actual parts and their locations
- Project records should allow the user to capture a description, status, and BOM — but starting from a suggestion should be low friction
- AI suggestions should be clearly labelled as AI-generated and show the source inventory they are based on

---

## Trust and grounding in AI responses

- AI responses should never be presented as facts about what the user owns
- Every AI result should be accompanied by: "Based on your inventory of N parts" or similar grounding statement
- When the AI references a specific part or document, the UI should show a link to that entity in the database
- If the AI cannot find a relevant answer in the inventory, it should say so clearly rather than hallucinating parts the user does not own
- The user should always be able to see the raw database result alongside the AI-augmented result

---

## Error and empty states

- Empty inventory should show a prompt to add the first part, not just a blank list
- Search with no results should suggest alternate search terms or offer to add the part
- AI errors (provider unavailable, quota exceeded) should fail gracefully with a clear message and fallback to database-only results
- Document upload failures should show a clear error with the reason

---

## Open questions for design

- Should the primary navigation be search-led or category-led? (Recommendation: search-led)
- Should there be a dashboard / summary view? If so, what should it show? (Candidate: parts count, recent additions, low stock alerts, recent AI activity)
- What is the right metaphor for the location hierarchy? (Tree view, breadcrumb trail, card stacks?)
- Should AI suggestions be proactive (shown on load) or on-demand (triggered by the user)?
