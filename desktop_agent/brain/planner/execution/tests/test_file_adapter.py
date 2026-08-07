"""
MYRAA File Adapter Integration Test
"""

from __future__ import annotations

import asyncio
from pathlib import Path


from ..action_adapters.file_adapter import FileAdapter
from ...models.action_types import ActionType

from desktop_agent.desktop.filesystem.file_bridge import FileToolBridge



async def test_file_adapter():


    print("\n==============================")
    print(" MYRAA FILE ADAPTER TEST ")
    print("==============================\n")


    # -----------------------------
    # Create Adapter
    # -----------------------------

    file_tools = FileToolBridge()

    adapter = FileAdapter(
        file_tools=file_tools
    )


    # -----------------------------
    # Test Location
    # -----------------------------

    test_folder = (
        Path.home()
        /
        "Desktop"
        /
        "MYRAA_TEST"
    )


    test_file = (
        test_folder
        /
        "hello.txt"
    )


    # -----------------------------
    # CREATE FOLDER
    # -----------------------------

    print("Creating folder...")


    folder_result = await adapter.execute(

        ActionType.CREATE_FOLDER,

        {
            "path": str(test_folder)
        }

    )


    print(folder_result)



    assert folder_result is not None



    # -----------------------------
    # CREATE FILE
    # -----------------------------

    print("\nCreating file...")


    file_result = await adapter.execute(

        ActionType.CREATE_FILE,

        {
            "path": str(test_file)
        }

    )


    print(file_result)



    assert file_result is not None



    # -----------------------------
    # VERIFY
    # -----------------------------

    print("\nVerification:")


    print(
        "Folder:",
        test_folder.exists()
    )


    print(
        "File:",
        test_file.exists()
    )



    assert test_folder.exists()

    assert test_file.exists()



    print(
        "\nFILE ADAPTER TEST PASSED ✅"
    )



if __name__ == "__main__":

    asyncio.run(
        test_file_adapter()
    )