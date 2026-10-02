---
name: fix-ai-manager-presentation
description: Fixed presentation creation detection in AI Manager 3.0 to correctly route to creation_document
metadata:
  type: project
---

Fixed the special handling for presentation creation detection in AI Manager 3.0 semantic routing.

**Problem**: The test case 'create a presentation about ai' was incorrectly routing to Intent.CREATION_PRESENTATION instead of Intent.CREATION_DOCUMENT.

**Root Cause**: In the `_detect_intent` method, the special handling for presentation creation was boosting both CREATION_PRESENTATION and CREATION_DOCUMENT, but CREATION_PRESENTATION had fewer patterns (1 vs 2 for CREATION_DOCUMENT) so after normalization, CREATION_PRESENTATION was winning.

**Fix Applied**: Modified the presentation creation special handling to only boost CREATION_DOCUMENT when presentation words and creation words are detected. This ensures that phrases like "create a presentation about ai" correctly route to Intent.CREATION_DOCUMENT.

**Code Change**: 
- Removed boosting of CREATION_PRESENTATION 
- Enhanced boosting of CREATION_DOCUMENT (3x boost when presentation context detected)
- Added fallback score of 3.0 if CREATION_DOCUMENT had no initial matches

**Verification**: All 40 test cases now pass, including:
  - 'create a presentation about ai' -> creation_document ✓
  - 'make a document for project proposal' -> creation_document ✓
  - All existing test cases remain passing

This maintains backward compatibility while fixing the specific routing failure.