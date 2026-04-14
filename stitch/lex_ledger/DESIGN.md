# Design System Document: Structured Academic Editorial

## 1. Overview & Creative North Star: "The Digital Jurist"

The design system moves beyond the standard "SaaS dashboard" aesthetic to embrace the role of **The Digital Jurist**. In the world of labor law and overtime compliance, the interface must act as an authoritative, unwavering source of truth. We achieve this by blending the precision of a legal brief with the high-end editorial feel of an academic journal.

**The Creative North Star** is characterized by:
*   **Intentional Asymmetry:** Breaking the monotonous grid to highlight critical compliance metrics.
*   **Tonal Authority:** Using deep, ink-like blues (`primary`) against vast, "paper" surfaces (`surface`) to create a sense of permanence and intellectual rigor.
*   **Editorial Scaling:** Using dramatic shifts in typography size to guide the eye through complex legal data without the need for cluttered lines.

We reject the "boxed-in" look. This design system treats the screen as a canvas of layered intelligence rather than a collection of widgets.

---

## 2. Colors: Tonal Depth & The "No-Line" Rule

To maintain an academic and premium feel, we rely on the sophistication of the palette rather than decorative elements.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to section off content. Traditional "boxes" make an application feel like a template. Instead:
*   **Sectioning:** Define boundaries through background shifts. A `surface-container-low` section sitting on a `surface` background provides all the separation needed.
*   **Vertical Hierarchy:** Use `surface-container-lowest` for the most prominent content (like a focused legal calculation) and `surface-container-highest` for background utility areas (like the navigation sidebar).

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. 
1.  **Base:** `surface` (#fbf8ff) - The background "paper."
2.  **Middle:** `surface-container` (#eeedf8) - The logical grouping of a data set.
3.  **Peak:** `surface-container-lowest` (#ffffff) - The active "document" or card being worked on.

### The "Glass & Gradient" Rule
For floating elements, such as "Compliance Alerts" or "Active Calculations," use **Glassmorphism**. Apply `surface_container_low` at 80% opacity with a `24px` backdrop-blur. This ensures the app feels like a modern, high-end tool rather than a static spreadsheet.

### Signature Textures
Apply a subtle linear gradient to the Sidebar and Primary CTAs:
*   **Sidebar:** From `primary` (#000666) to `primary_container` (#1a237e). This provides a "weighted" anchor to the left, establishing the authoritative tone.

---

## 3. Typography: The Editorial Voice

We utilize two distinct typefaces to create a "Structured Academic" hierarchy.

*   **Display & Headlines (Manrope):** A modern, geometric sans-serif that feels authoritative yet approachable. Used for large data points and section titles.
*   **Body & Labels (Inter):** A highly legible, "workhorse" sans-serif designed for complex data and fine print.

**Key Scales:**
*   **Display-LG (3.5rem, Manrope):** Reserved for hero metrics, such as total overtime hours.
*   **Headline-SM (1.5rem, Manrope):** For section headers like "Labor Law Violations."
*   **Body-MD (0.875rem, Inter):** The standard for all legal text and table data.
*   **Label-SM (0.6875rem, Inter):** Used for metadata, such as timestamps and specific law citations.

---

## 4. Elevation & Depth: Tonal Layering

Traditional drop shadows are too "soft" for a legal application. We use **Tonal Layering** to convey hierarchy.

*   **The Layering Principle:** Place a `surface-container-lowest` card on a `surface-container-low` section to create a soft, natural lift.
*   **Ambient Shadows:** If a floating state is required (e.g., a modal), use a shadow tinted with `on_surface` (#1a1b23) at 6% opacity with a `48px` blur. It should look like a soft glow of light, not a "drop shadow."
*   **The Ghost Border Fallback:** If high-contrast accessibility is required, use `outline_variant` at **15% opacity**. This creates a "Ghost Border" that defines the edge without cluttering the visual field.

---

## 5. Components: Precision & Authority

### Buttons
*   **Primary:** Gradient from `primary` to `primary_container`. `0.25rem` (sm) corner radius.
*   **Secondary:** No background, `outline` ghost border at 20% opacity. Text in `primary`.
*   **State:** Hovering a primary button should shift the gradient slightly, never just "darken" it.

### Data Tables (The "Academic" Table)
*   **Forbid dividers.** Use `body-sm` typography for headers in `on_surface_variant`.
*   **Zebra striping:** Use `surface-container-low` for even rows.
*   **Cell Alignment:** All numerical data must be tabular-lining (monospaced) to allow for easy compliance auditing.

### Labor Compliance Chips
*   **Success Green (`secondary`):** Approved hours. Use `on_secondary_container` text on `secondary_container` background.
*   **Warning Orange (`tertiary`):** Weekend work. Subtle and informative.
*   **Danger Red (`error`):** Holiday/Compliance violations. High contrast using `on_error_container`.

### Input Fields
*   **Style:** Minimalist. No 4-sided boxes. Use a bottom-border (2px) in `outline_variant` that transforms to `primary` on focus.
*   **Micro-copy:** All helper text must be in `label-md`, positioned precisely `4px` below the input line.

---

## 6. Do’s and Don'ts

### Do:
*   **Do** use white space as a structural element. If you think a section needs a line, try adding 24px of padding instead.
*   **Do** use `headline-lg` for critical compliance numbers. Make them unmissable.
*   **Do** ensure all data visualizations (charts) use the `primary`, `secondary`, and `tertiary` tokens exclusively to maintain brand cohesion.

### Don't:
*   **Don't** use pure black (#000000). Use `on_surface` (#1a1b23) for all text to maintain the "ink on paper" feel.
*   **Don't** use large corner radii. Stick to `DEFAULT` (0.25rem) or `sm` (0.125rem). This application should feel "sharp" and professional, not "bubbly."
*   **Don't** use standard blue for links. Links are an extension of authority; use `primary` with a 1px underline.

---

## 7. Signature Layout: The Compliance Sidebar

The sidebar is not just a menu; it is an **Authority Panel**.
*   **Background:** Deep Navy Gradient (`primary` to `primary_container`).
*   **Active State:** Instead of a highlight box, the active menu item should use a "negative space" notch—the background of the main content `surface` bleeds into the sidebar, signaling the current "active document."