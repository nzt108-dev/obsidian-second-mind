# 🎨 Design System — Midnight Luxe

> nzt108.dev · 2026 · Single source of truth for all UI
> Generated from architect-portfolio CSS, adapted for cross-project use

---

## Color Palette

### Backgrounds
| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#0D0D12` | Page background |
| `--bg-secondary` | `#13131A` | Sections, sidebars |
| `--bg-card` | `#16161E` | Cards, panels |
| `--bg-card-hover` | `#1C1C26` | Card hover state |
| `--bg-surface` | `#1A1A24` | Elevated surfaces |

### Accent — Plasma Violet
| Token | Value | Usage |
|-------|-------|-------|
| `--accent-primary` | `#7B61FF` | Primary actions, links, focus |
| `--accent-secondary` | `#9B85FF` | Hover states, secondary accent |
| `--accent-gradient` | `linear-gradient(135deg, #7B61FF, #9B85FF)` | CTAs, gradient text |
| `--accent-light` | `rgba(123, 97, 255, 0.10)` | Badge backgrounds, subtle tint |
| `--accent-glow` | `rgba(123, 97, 255, 0.25)` | Glow effects |

### Gold (Premium accents)
| Token | Value | Usage |
|-------|-------|-------|
| `--gold` | `#C9A84C` | Premium badges, highlights |
| `--gold-light` | `rgba(201, 168, 76, 0.12)` | Gold badge background |

### Status Colors
| Token | Value | Usage |
|-------|-------|-------|
| `--accent-green` | `#34D399` | Success, online, positive |
| `--accent-amber` | `#FBBF24` | Warning, pending |
| `--accent-red` | `#EF4444` | Error, destructive, critical |

### Text
| Token | Value | Usage |
|-------|-------|-------|
| `--text-primary` | `#F0EFF4` | Headings, body text |
| `--text-secondary` | `#A1A1AA` | Descriptions, labels |
| `--text-muted` | `#71717A` | Hints, placeholders |

### Borders
| Token | Value | Usage |
|-------|-------|-------|
| `--border-color` | `rgba(255, 255, 255, 0.06)` | Default borders |
| `--border-hover` | `rgba(123, 97, 255, 0.3)` | Hover state borders |
| `--border-subtle` | `rgba(255, 255, 255, 0.03)` | Minimal dividers |

---

## Typography

### Fonts
| Role | Font | Fallback |
|------|------|----------|
| Sans (body) | **Inter** | system-ui, -apple-system, sans-serif |
| Serif (display) | **Playfair Display** | Georgia, serif |
| Mono (code) | **JetBrains Mono** | monospace |

### Scale
| Element | Size | Weight | Line Height | Letter Spacing |
|---------|------|--------|-------------|----------------|
| H1 (hero) | 3.5rem / 56px | 800 | 1.05 | -0.04em |
| H2 (section) | 2.5rem / 40px | 800 | 1.1 | -0.03em |
| H3 (card title) | 1.5rem / 24px | 700 | 1.2 | -0.02em |
| H4 (subsection) | 1.25rem / 20px | 600 | 1.3 | -0.01em |
| Body | 1rem / 16px | 400 | 1.7 | normal |
| Body large | 1.125rem / 18px | 400 | 1.7 | normal |
| Small | 0.875rem / 14px | 500 | 1.5 | normal |
| Caption | 0.8125rem / 13px | 500 | 1.4 | 0.01em |

---

## Spacing

Base unit: **4px**

| Token | Value | Usage |
|-------|-------|-------|
| `space-1` | 4px | Minimal gap |
| `space-2` | 8px | Tight spacing |
| `space-3` | 12px | Element gap |
| `space-4` | 16px | Component padding (small) |
| `space-5` | 20px | Component padding (medium) |
| `space-6` | 24px | Card padding |
| `space-8` | 32px | Section gap |
| `space-10` | 40px | Section padding |
| `space-12` | 48px | Large section gap |
| `space-16` | 64px | Page section margin |
| `space-20` | 80px | Hero padding |

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `radius-sm` | 8px | Badges, small buttons |
| `radius-md` | 12px | Buttons, inputs |
| `radius-lg` | 20px | Cards |
| `radius-xl` | 24px | Bento cards, modals |
| `radius-full` | 9999px | Pill badges, avatars |

---

## Shadows (Elevation)

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.3)` | Subtle lift |
| `--shadow-md` | `0 4px 16px rgba(0,0,0,0.4)` | Cards, dropdowns |
| `--shadow-lg` | `0 12px 40px rgba(0,0,0,0.5)` | Modals, dialogs |
| `--shadow-xl` | `0 20px 60px rgba(0,0,0,0.6)` | Hero elements |
| `--shadow-glow` | `0 0 40px rgba(123,97,255,0.15)` | Accent glow on hover |

---

## Transitions

| Token | Value | Usage |
|-------|-------|-------|
| `--transition-fast` | `150ms cubic-bezier(0.4, 0, 0.2, 1)` | Hover color changes |
| `--transition-normal` | `300ms cubic-bezier(0.4, 0, 0.2, 1)` | Card transforms |
| `--transition-slow` | `500ms cubic-bezier(0.4, 0, 0.2, 1)` | Page transitions |
| `--transition-magnetic` | `300ms cubic-bezier(0.25, 0.46, 0.45, 0.94)` | Buttons, interactive |

---

## Components

### Buttons

#### Primary (CTA)
```css
padding: 14px 28px;
font-weight: 600;
font-size: 15px;
background: var(--accent-primary);
color: white;
border: none;
border-radius: 12px;
/* Hover: scale(1.03) translateY(-1px), glow shadow */
/* Active: scale(0.98) */
/* Shimmer overlay on hover */
```

#### Secondary (Outline)
```css
padding: 14px 28px;
font-weight: 600;
font-size: 15px;
background: transparent;
color: var(--text-primary);
border: 1px solid var(--border-color);
border-radius: 12px;
/* Hover: border-color accent, text accent */
```

#### Ghost
```css
padding: 8px 16px;
font-weight: 500;
font-size: 14px;
background: transparent;
color: var(--accent-primary);
border: none;
border-radius: 8px;
/* Hover: background accent-light */
```

### Cards

#### Standard Card
```css
background: var(--bg-card);
border: 1px solid var(--border-color);
border-radius: 20px;
/* Hover: border-hover, shadow-md + shadow-glow, translateY(-2px) */
```

#### Bento Card (Interactive)
```css
background: var(--bg-card);
border: 1px solid var(--border-color);
border-radius: 24px;
padding: 24px;
/* Hover: bg-card-hover, shimmer overlay animation */
```

#### Glass Card (Premium)
```css
background: rgba(22, 22, 30, 0.6);
backdrop-filter: blur(20px);
border: 1px solid var(--border-color);
```

### Inputs
```css
padding: 14px 16px;
background: var(--bg-secondary);
border: 1px solid var(--border-color);
border-radius: 12px;
color: var(--text-primary);
font-size: 15px;
/* Focus: border-accent, glow ring 3px */
```

### Badges
```css
/* Default (accent) */
padding: 5px 14px;
background: var(--accent-light);
border-radius: 20px;
color: var(--accent-primary);
font-size: 13px;
font-weight: 500;

/* Gold (premium) */
background: var(--gold-light);
color: var(--gold);
```

### Section Headers
```css
/* Title */
font-size: 2.5rem;
font-weight: 800;
letter-spacing: -0.03em;
line-height: 1.1;

/* Subtitle */
color: var(--text-secondary);
font-size: 1.125rem;
max-width: 600px;
line-height: 1.7;
```

---

## Animations

| Name | Effect | Duration | Usage |
|------|--------|----------|-------|
| `fade-in-up` | Opacity 0→1, Y+24→0 | 0.6s ease-out | Page sections on scroll |
| `fade-in` | Opacity 0→1 | 0.4s ease-out | Elements appearing |
| `float` | Y oscillation ±8px | 6s infinite | Decorative elements |
| `pulse-glow` | Shadow intensity oscillation | 3s infinite | Status indicators |
| `gradient-shift` | Background position sweep | loop | Animated gradients |
| `shimmer` | X -100% → +100% | 0.6s on hover | Card hover shimmer |

---

## Decorative

### Grid Background
```css
background-image:
  linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
  linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
background-size: 60px 60px;
```

### Gradient Text
```css
background: var(--accent-gradient);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
```

### Accent Blob (Background decoration)
```css
width: 40rem; height: 40rem;
border-radius: 50%;
background: var(--accent-primary);
opacity: 0.04;
filter: blur(150px);
```

---

## Responsive Breakpoints

| Breakpoint | Width | Usage |
|-----------|-------|-------|
| Mobile | < 640px | Single column, stacked |
| Tablet | 640px–1024px | 2 columns, compact nav |
| Desktop | > 1024px | Full layout, sidebar |
| Wide | > 1280px | Max-width constraints |

**Mobile rules:**
- Touch targets ≥ 44px
- Bottom safe area: `env(safe-area-inset-bottom) + 80px`
- No horizontal scroll
- Font sizes: min 14px body

---

## Light Theme Variant (Landing Pages)

For client-facing landing pages, invert to light mode:

```css
[data-theme="light"] {
  --bg-primary: #FFFFFF;
  --bg-secondary: #F8F9FA;
  --bg-card: #FFFFFF;
  --bg-card-hover: #F3F4F6;
  --bg-surface: #F9FAFB;
  --text-primary: #111827;
  --text-secondary: #6B7280;
  --text-muted: #9CA3AF;
  --border-color: rgba(0, 0, 0, 0.08);
  --border-hover: rgba(123, 97, 255, 0.4);
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
  --shadow-lg: 0 12px 40px rgba(0,0,0,0.12);
}
```

---

## Flutter Adaptation

For mobile apps (BriefTube), map tokens to Flutter ThemeData:

```dart
// Colors → ColorScheme.dark()
primary: Color(0xFF7B61FF),       // --accent-primary
onPrimary: Colors.white,
surface: Color(0xFF16161E),       // --bg-card
onSurface: Color(0xFFF0EFF4),     // --text-primary
background: Color(0xFF0D0D12),    // --bg-primary
error: Color(0xFFEF4444),         // --accent-red

// Typography → Google Fonts
headlineFont: GoogleFonts.outfit(fontWeight: FontWeight.w800),
bodyFont: GoogleFonts.inter(),

// Border radius
cardRadius: BorderRadius.circular(20),
buttonRadius: BorderRadius.circular(12),
badgeRadius: BorderRadius.circular(20),
```

---

*Last updated: 2026-04-11 · Midnight Luxe v1.0*
