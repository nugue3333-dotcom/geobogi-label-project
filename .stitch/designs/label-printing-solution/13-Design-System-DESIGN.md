---
name: Precision Logic
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#424754'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#727785'
  outline-variant: '#c2c6d6'
  surface-tint: '#005ac2'
  primary: '#0058be'
  on-primary: '#ffffff'
  primary-container: '#2170e4'
  on-primary-container: '#fefcff'
  inverse-primary: '#adc6ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#006b26'
  on-tertiary: '#ffffff'
  tertiary-container: '#008732'
  on-tertiary-container: '#f7fff2'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#004395'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#6bff84'
  tertiary-fixed-dim: '#3be365'
  on-tertiary-fixed: '#002107'
  on-tertiary-fixed-variant: '#00531c'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
  tech-cyan: '#0EA5E9'
  surface-gray: '#F8FAFC'
  border-subtle: '#E2E8F0'
typography:
  headline-xl:
    fontFamily: Hanken Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  button-text:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 8px
  container-max: 1280px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  section-gap: 80px
---

## Brand & Style

This design system is engineered for a label printing and software solutions provider, emphasizing technical precision and industrial reliability. The brand personality is professional, efficient, and solution-oriented, targeting enterprise logistics and manufacturing sectors.

The visual style follows a **Corporate Modern** aesthetic with **Minimalist** influences. It prioritizes clarity and high-tech sophistication through the use of expansive white space, structured grids, and subtle depth. The design should evoke a sense of "zero-error" performance?봠lean lines, high-contrast readability, and a systematic approach to information density.

## Colors

The palette is anchored by a **Deep Navy (Secondary)** and a **Vibrant Blue (Primary)** to establish a "high-tech" and "trustworthy" foundation. 

- **Primary Blue (#3B82F6):** Used for primary actions, progress indicators, and active states. It represents the "software" intelligence.
- **Secondary Navy (#0F172A):** Used for headlines and core navigation elements to provide weight and authority.
- **Tertiary Green (#02C94F):** Reserved for "Success" states and "Ready" indicators on hardware status dashboards.
- **Surface Gray:** A cool-toned off-white is used for section backgrounds to distinguish hardware specs from software features.

## Typography

The typography strategy balances modern marketing with technical utility. 
- **Hanken Grotesk** is used for headlines to provide a sharp, contemporary feel that suggests innovation.
- **Inter** is the workhorse for body copy, chosen for its exceptional legibility in complex data environments.
- **JetBrains Mono** is introduced for labels, serial numbers, and technical specifications, reinforcing the precision of the hardware and label-printing output.

Tighten letter-spacing on large headlines to maintain a compact, "engineered" look. Increase line-height for body text to ensure readability during prolonged software use.

## Layout & Spacing

The design system utilizes a **12-column fixed grid** for desktop, centering the content at a 1280px maximum width. A 4-column grid is used for mobile devices.

- **Vertical Rhythm:** A strict 8px baseline grid ensures alignment across hardware spec tables and software dashboard layouts.
- **Sectioning:** Use large `section-gap` values to separate product photography from technical documentation, allowing the UI to "breathe" and avoiding visual clutter.
- **Data Density:** While marketing pages are spacious, application screens (label designers, printer queues) should use a more compact 4px/8px spacing scale to maximize information visibility.

## Elevation & Depth

To maintain a high-tech feel, this design system uses **Tonal Layers** combined with **Low-Contrast Outlines**. 

- **Surfaces:** Use flat, solid colors for primary backgrounds. Secondary surfaces (like sidebar or card backgrounds) should use `surface-gray`.
- **Borders:** Define structure using 1px borders in `border-subtle`. This creates a "blueprint" or "schematic" aesthetic.
- **Shadows:** Avoid heavy, muddy shadows. Use a single, highly diffused "Ambient Shadow" (0px 4px 20px rgba(15, 23, 42, 0.08)) only for floating elements like dropdowns or active modals to signify depth without breaking the clean, flat aesthetic.

## Shapes

The shape language is **Soft (0.25rem)**. This provides a subtle nod to the hardware's industrial design?봫odern but not overly organic. 

- **Primary Components:** Buttons and inputs use a consistent 4px (0.25rem) radius.
- **Product Cards:** Larger containers may use `rounded-lg` (8px) to softly frame product photography or software mockups.
- **Icons:** Use geometric, stroke-based icons with square ends to match the technical brand voice.

## Components

### Buttons
- **Primary:** Solid `#3B82F6` background with white text. High-contrast, rectangular with minimal rounding.
- **Secondary:** Transparent background with a `border-subtle` and `#0F172A` text.
- **Tertiary/Ghost:** No border or background; uses Primary Blue for text to indicate secondary actions like "View Specs."

### Cards
Feature cards should use a white background with a 1px `border-subtle`. On hover, apply the "Ambient Shadow" and a subtle top-border accent in Primary Blue. This signifies interactivity without visual noise.

### Data Tables
Tables are critical for package info and technical specs. Use a "Zebra" stripe pattern with `surface-gray` for alternate rows. Headers should be in `Secondary Navy` with `label-mono` typography for a professional, systematic look.

### Input Fields
Inputs use a white background and a 1px `border-subtle`. On focus, the border transitions to Primary Blue with a 2px outer glow (Primary Blue at 10% opacity). Labels use `body-sm` weight 600 for clarity.

### Status Chips
Use small, pill-shaped indicators for printer status (e.g., Online, Offline, Error). These utilize the `tertiary_color` (Green) or `brand-red` with 10% background opacity for high-tech legibility.
