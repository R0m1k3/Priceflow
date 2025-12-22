# Task Board: Vision-Based Price Extraction

## 🚀 Current Focus

- [x] Analysing current hybrid (Text + Image) extraction logic
- [x] Proposing "Vision First" strategy to owner
- [ ] **Implementation Phase**:
  - [ ] Update `ai_schema.py` STRICT Vision Definition.
  - [ ] Refine Prompt with "IMAGE IS TRUTH" directive.
- [ ] **Verification Phase**:
  - [ ] Verify prompt generation.

## 📝 Progress Log

- **2025-12-22**: Initialized task. Confirmed current system is *already* sending images, but likely confusing the AI with conflicting text data.
- **2025-12-22**: User selected **Option 2 (Vision Priority)**. Proceeding to rewrite AI System Prompt.
- **2025-12-22**: **FIX**: Detected that `scheduler_service.py` was prioritizing a text-only extractor (0.99€ found in text) before checking the image. Disabled the text-only extractor to force Vision AI usage.
