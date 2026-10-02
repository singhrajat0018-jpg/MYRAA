"""
MYRAA Execution Verifier

Verifies whether an executed task actually completed.

Current Version:
- Generic verification
- File verification
- Folder verification
- Simple application verification

Future:
- OCR verification
- Screen verification
- Vision verification
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class VerificationResult:

    def __init__(
        self,
        success: bool,
        message: str = "",
    ):

        self.success = success
        self.message = message

    def __bool__(self):

        return self.success

    def __repr__(self):

        return (
            f"VerificationResult("
            f"success={self.success}, "
            f"message='{self.message}')"
        )


class ExecutionVerifier:

    """
    Verifies execution results.
    """

    def verify(
        self,
        tool: str,
        parameters: dict[str, Any] | None = None,
        result: Any = None,
    ) -> VerificationResult:

        parameters = parameters or {}

        method = getattr(
            self,
            f"_verify_{tool}",
            None,
        )

        if method is None:
            return self._default(result)

        return method(parameters, result)

    # =======================================================
    # Default
    # =======================================================

    def _default(
        self,
        result: Any,
    ) -> VerificationResult:

        if result is None:
            return VerificationResult(
                False,
                "Tool returned None.",
            )

        return VerificationResult(
            True,
            "Execution completed.",
        )

    # =======================================================
    # Create Folder
    # =======================================================

    def _verify_createFolder(
        self,
        params,
        result,
    ):

        path = params.get("path")

        if not path:

            return VerificationResult(
                False,
                "Folder path missing.",
            )

        if Path(path).exists():

            return VerificationResult(
                True,
                "Folder verified.",
            )

        return VerificationResult(
            False,
            "Folder not found.",
        )

    # =======================================================
    # Create File
    # =======================================================

    def _verify_createFile(
        self,
        params,
        result,
    ):

        path = params.get("path")

        if not path:

            return VerificationResult(
                False,
                "File path missing.",
            )

        if Path(path).is_file():

            return VerificationResult(
                True,
                "File verified.",
            )

        return VerificationResult(
            False,
            "File not found.",
        )

    # =======================================================
    # Screenshot
    # =======================================================

    def _verify_takeScreenshot(
        self,
        params,
        result,
    ):

        path = params.get("path")

        if not path:

            return VerificationResult(
                True,
                "Screenshot created.",
            )

        if Path(path).exists():

            return VerificationResult(
                True,
                "Screenshot verified.",
            )

        return VerificationResult(
            False,
            "Screenshot missing.",
        )

    # =======================================================
    # Open Application
    # =======================================================

    def _verify_openApplication(
        self,
        params,
        result,
    ):

        if result is None:

            return VerificationResult(
                False,
                "Application did not launch.",
            )

        return VerificationResult(
            True,
            "Application launch reported.",
        )

    # =======================================================
    # Delete File
    # =======================================================

    def _verify_deleteFile(
        self,
        params,
        result,
    ):

        path = params.get("path")

        if not path:

            return VerificationResult(
                False,
                "File path missing.",
            )

        if not os.path.exists(path):

            return VerificationResult(
                True,
                "File removed.",
            )

        return VerificationResult(
            False,
            "File still exists.",
        )

    # =======================================================
    # Move File
    # =======================================================

    def _verify_moveFile(
        self,
        params,
        result,
    ):

        destination = params.get("destination")

        if not destination:

            return VerificationResult(
                False,
                "Destination missing.",
            )

        if Path(destination).exists():

            return VerificationResult(
                True,
                "Move verified.",
            )

        return VerificationResult(
            False,
            "Move failed.",
        )

    # =======================================================
    # Rename File
    # =======================================================

    def _verify_renameFile(
        self,
        params,
        result,
    ):

        target = None

        if isinstance(result, dict):
            target = result.get("path")

        if not target and params.get("new_name"):

            source = params.get("path")

            if source:
                target = os.path.join(
                    os.path.dirname(source),
                    str(params.get("new_name")),
                )

        if not target:

            return VerificationResult(
                False,
                "Renamed path missing.",
            )

        if os.path.exists(target):

            return VerificationResult(
                True,
                "Rename verified.",
            )

        return VerificationResult(
            False,
            "Renamed file not found.",
        )

    # =======================================================
    # Copy File
    # =======================================================

    def _verify_copyFile(
        self,
        params,
        result,
    ):

        target = None

        if isinstance(result, dict):
            target = result.get("path")

        if not target and params.get("destination"):

            target = params.get("destination")

        if not target:

            return VerificationResult(
                False,
                "Copy destination missing.",
            )

        if Path(target).exists():

            return VerificationResult(
                True,
                "Copy verified.",
            )

        return VerificationResult(
            False,
            "Copied file not found.",
        )

    # =======================================================
    # Write File
    # =======================================================

    def _verify_writeFile(
        self,
        params,
        result,
    ):

        path = params.get("path")

        if not path:

            return VerificationResult(
                False,
                "File path missing.",
            )

        if Path(path).is_file():

            return VerificationResult(
                True,
                "Write verified.",
            )

        return VerificationResult(
            False,
            "File not found after write.",
        )

    # =======================================================
    # Open Folder
    # =======================================================

    def _verify_openFolder(
        self,
        params,
        result,
    ):

        path = params.get("path") or params.get("name")

        if not path:

            return VerificationResult(
                False,
                "Folder missing.",
            )

        if Path(path).exists() and Path(path).is_dir():

            return VerificationResult(
                True,
                "Folder verified.",
            )

        return VerificationResult(
            False,
            "Folder not found.",
        )

    # =======================================================
    # Read File
    # =======================================================

    def _verify_readFile(
        self,
        params,
        result,
    ):

        path = params.get("path")

        if not path:

            return VerificationResult(
                False,
                "File path missing.",
            )

        if Path(path).is_file():

            return VerificationResult(
                True,
                "Read verified.",
            )

        return VerificationResult(
            False,
            "File not found.",
        )