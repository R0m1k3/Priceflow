# Walkthrough: Vision-First Price Extraction

In response to issues where the AI was being misled by hidden text (like unit prices or old prices in HTML), we have implemented a **Vision-Priority Strategy**.

## Changes Implemented

### 1. Updated AI System Prompt (`app/ai_schema.py`)

We completely rewrote the `EXTRACTION_PROMPT_TEMPLATE` to enforce the following rules:

- **Source of Truth = Image**: explicit instruction that the screenshot takes precedence over any text.
- **Conflict Resolution**: "IF IMAGE AND TEXT CONFLICT, TRUST THE IMAGE."
- **Visual Focus Rules**:
  - Look for the largest/boldest price.
  - Ignore small, styling-less text (often unit prices).
  - Ignore crossed-out text.

### Verification

We verified the new prompt generation using `verify_vision_priority.py`.

**Generated Prompt Preview:**

```text
You are a Vision-First Price Extraction Agent.
Your Goal: Extract the main product price exactly as a human sees it on the screen.

**SOURCE OF TRUTH = IMAGE**
- The image provided is the **Absolute Truth**.
- The text provided below is scraped HTML content which may contain hidden/old prices.
- **IF IMAGE AND TEXT CONFLICT, TRUST THE IMAGE.**
```

## How to Test

1. Go to "Suivis Prix".
2. Force refresh an item that was previously incorrect (e.g., B&M item showing unit price).
3. The AI should now ignore the "hidden" unit price text and read the main price tag from the image.
