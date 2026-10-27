# Dak design direction

## October 2026 refresh

The workspace combines a calm product UI with an original isometric correspondence illustration. The illustration explains the path from message to evidence and human review; operational information stays flat and readable. Cool ivory, forest green, restrained amber and slate accents, fine borders, and soft surface shadows establish the hierarchy. Sans-serif typography supports the workspace; a single italic serif phrase gives the opening statement a more personal voice.

References reviewed: [beUI](https://beui.dev/) for considered press feedback, selection states, and restrained motion; [Beautiful UI](https://www.beautifului.dev/) for human approval, trace, source context, and navigation patterns. The supplied `beauitfului.dev` address was inaccessible; the intended reference was found at the corrected spelling. The implementation uses original SVG, React, and CSS rather than copied components or additional dependencies.

A persistent desktop sidebar frames Compose, Review, Activity, and Evaluation. On mobile it becomes a compact navigation row. Compose pairs selectable sample correspondence with a focused email editor. The process strip explains the workflow without presenting invented live metrics. Selected samples have a visible, accessible pressed state. The reference shelf continues to use API-provided policy data.

Review retains correspondence, cited drafts, triage evidence, blocked attempts, and recorded human decisions. Surface treatments and green selection states connect it visually to the Compose page. Activity tables, metrics, evaluation charts, and run traces share the same tokens and control styles. API contracts and review behavior are preserved.

The system follows the device's light or dark preference, respects reduced motion, and includes keyboard focus indicators. The illustration is decorative and hidden from assistive technology; adjacent copy describes the workflow. No remote font, image, or new UI library is required.

Verification uses the existing Playwright interaction and axe accessibility suite, extended to 320, 390, 768, 1024, and 1440 pixel viewports in both themes. Browser data is explicitly mocked for these UI checks. Live provider inference is outside this visual redesign. Screenshots are written to `frontend/test-results/` by the suite.
