"""
MYRAA Vision V3
Ordinal Resolver

Handles ordinal reference resolution for target descriptions.
Supports both English and Hindi/Hinglish ordinal references.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
from .text_normalizer import ORDINAL_MAP, extract_ordinal


class OrdinalResolver:
    """
    Resolves ordinal references in target descriptions.

    Supports:
    - English: first, second, third, fourth, fifth, 1st, 2nd, etc.
    - Hindi/Hinglish: pehla, doosra, dusra, teesra, chautha, paanchva
    """

    def __init__(self):
        """Initialize the ordinal resolver."""
        pass

    def resolve_ordinal(
        self,
        description: str,
        candidates: List[any]
    ) -> Tuple[Optional[int], List[any]]:
        """
        Extract ordinal from description and filter candidates accordingly.

        Args:
            description: Target description that may contain ordinal reference
            candidates: List of candidate UI elements to filter

        Returns:
            Tuple of (ordinal_number, filtered_candidates)
            ordinal_number is None if no ordinal found
            filtered_candidates are candidates matching the ordinal position
        """
        if not description or not candidates:
            return None, candidates

        # Extract ordinal number from description
        ordinal_num = extract_ordinal(description)
        if ordinal_num is None:
            return None, candidates

        # Convert to zero-based index for list access
        ordinal_index = ordinal_num - 1

        # Check if ordinal is within bounds
        if 0 <= ordinal_index < len(candidates):
            # Return the specific element at the ordinal position
            return ordinal_num, [candidates[ordinal_index]]
        else:
            # Ordinal out of bounds - return empty list
            return ordinal_num, []

    def resolve_ordinal_from_position(
        self,
        description: str,
        candidates: List[any],
        primary_sort_key: str = "y",
        secondary_sort_key: str = "x"
    ) -> Tuple[Optional[int], List[any]]:
        """
        Resolve ordinal by first sorting candidates spatially, then selecting by ordinal.

        Args:
            description: Target description that may contain ordinal reference
            candidates: List of candidate UI elements
            primary_sort_key: Primary sort dimension ('y' for top-to-bottom, 'x' for left-to-right)
            secondary_sort_key: Secondary sort dimension for tie-breaking

        Returns:
            Tuple of (ordinal_number, filtered_candidates)
        """
        if not description or not candidates:
            return None, candidates

        # Extract ordinal number from description
        ordinal_num = extract_ordinal(description)
        if ordinal_num is None:
            return None, candidates

        # Sort candidates spatially (top-to-bottom, left-to-right by default)
        sorted_candidates = self._sort_candidates_spatially(
            candidates,
            primary_sort_key,
            secondary_sort_key
        )

        # Convert to zero-based index
        ordinal_index = ordinal_num - 1

        # Check bounds and return result
        if 0 <= ordinal_index < len(sorted_candidates):
            return ordinal_num, [sorted_candidates[ordinal_index]]
        else:
            return ordinal_num, []

    def _sort_candidates_spatially(
        self,
        candidates: List[any],
        primary_key: str = "y",
        secondary_key: str = "x"
    ) -> List[any]:
        """
        Sort candidates spatially for ordinal resolution.

        Args:
            candidates: List of candidate UI elements with bounds
            primary_key: Primary sort dimension ('y' or 'x')
            secondary_key: Secondary sort dimension ('y' or 'x')

        Returns:
            List of candidates sorted spatially
        """
        def get_coordinate(elem: any, key: str) -> int:
            """Extract coordinate from element bounds."""
            if hasattr(elem, 'bounds'):
                if key == 'x':
                    return elem.bounds.x
                elif key == 'y':
                    return elem.bounds.y
                elif key == 'center_x':
                    return elem.bounds.center[0]
                elif key == 'center_y':
                    return elem.bounds.center[1]
            elif isinstance(elem, dict) and 'bounds' in elem:
                bounds = elem['bounds']
                if key == 'x':
                    return bounds.get('x', 0)
                elif key == 'y':
                    return bounds.get('y', 0)
                elif key == 'center_x':
                    return (bounds.get('x', 0) + bounds.get('width', 0)) // 2
                elif key == 'center_y':
                    return (bounds.get('y', 0) + bounds.get('height', 0)) // 2
            return 0

        # Sort by primary key, then secondary key
        return sorted(
            candidates,
            key=lambda elem: (
                get_coordinate(elem, primary_key),
                get_coordinate(elem, secondary_key)
            )
        )

    def get_ordinal_text(self, ordinal_num: int, language: str = "english") -> str:
        """
        Get the textual representation of an ordinal number.

        Args:
            ordinal_num: Ordinal number (1-based)
            language: Language for ordinal text ("english" or "hindi")

        Returns:
            Textual representation of the ordinal
        """
        if language.lower() == "hindi":
            hindi_ordinals = {
                1: "pehla",
                2: "doosra",
                3: "teesra",
                4: "chautha",
                5: "paanchva"
            }
            return hindi_ordinals.get(ordinal_num, f"{ordinal_num}th")
        else:
            # English ordinals
            if ordinal_num == 1:
                return "first"
            elif ordinal_num == 2:
                return "second"
            elif ordinal_num == 3:
                return "third"
            elif ordinal_num == 4:
                return "fourth"
            elif ordinal_num == 5:
                return "fifth"
            elif 10 <= ordinal_num % 100 <= 20:
                return f"{ordinal_num}th"
            else:
                last_digit = ordinal_num % 10
                if last_digit == 1:
                    return f"{ordinal_num}st"
                elif last_digit == 2:
                    return f"{ordinal_num}nd"
                elif last_digit == 3:
                    return f"{ordinal_num}rd"
                else:
                    return f"{ordinal_num}th"

    def is_ordinal_reference(self, description: str) -> bool:
        """
        Check if description contains an ordinal reference.

        Args:
            description: Target description to check

        Returns:
            True if description contains ordinal reference, False otherwise
        """
        return extract_ordinal(description) is not None