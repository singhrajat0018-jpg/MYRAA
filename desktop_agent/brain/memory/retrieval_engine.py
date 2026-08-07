from __future__ import annotations

from .retrieval_result import RetrievalResult
from .retrieval_rules import *


class MemoryRetrievalEngine:

    def resolve(
        self,
        text: str,
        working_memory,
    ) -> RetrievalResult:
        text = text.lower()

        entities = working_memory.snapshot.entities
        print("Retrieval WM:", id(working_memory))
        print("\n===== RETRIEVAL WORKING MEMORY =====")
        print("WorkingMemory id:", id(working_memory))
        print("Snapshot id:", id(working_memory.snapshot))
        print("====================================")
        print("\n========== MEMORY RETRIEVAL ==========")
        print("Query :", repr(text))
        print("Website :", entities.current_website)
        print("Application :", entities.current_application)
        print("File :", entities.current_file)
        print("======================================")

        # -----------------------------
        # Website
        # -----------------------------

        matched = [x for x in WEBSITE_PATTERNS if x in text]

        print("WEBSITE_PATTERNS =", WEBSITE_PATTERNS)
        print("Matched =", matched)

        if matched:

            if entities.current_website:

                return RetrievalResult(

                    handled=True,

                    response=f"You currently have {entities.current_website} open.",

                    source="working_memory",

                    confidence=1.0,

                )
        # -----------------------------
        # Application
        # -----------------------------

        if any(x in text for x in APPLICATION_PATTERNS):

            if entities.current_application:

                return RetrievalResult(

                    handled=True,

                    response=f"You are currently using {entities.current_application}.",

                    source="working_memory",

                    confidence=1.0,

                )

        # -----------------------------
        # File
        # -----------------------------

        if any(x in text for x in FILE_PATTERNS):

            if entities.current_file:

                return RetrievalResult(

                    handled=True,

                    response=f"The current file is {entities.current_file}.",

                    source="working_memory",

                    confidence=1.0,

                )

        return RetrievalResult()