"""Domain models for Second Brain items.

These Pydantic models represent items stored in DynamoDB. Each category
(People, Projects, Ideas, Admin) is a distinct model class with:
- PK/SK building and parsing for DynamoDB access patterns
- Common attributes for all items
- Type-safe field access
"""

from typing import Optional, Tuple
from pydantic import BaseModel, Field
import uuid


class Item(BaseModel):
    """Base model for all Second Brain items.

    Represents an item stored in DynamoDB with:
    - PK: {category}#{item_id}
    - SK: PROFILE (for primary item representation)
    """

    # DynamoDB keys
    pk: str = Field(..., description="Partition key: {category}#{item_id}")
    sk: str = Field(default="PROFILE", description="Sort key")

    # Core item data
    name: Optional[str] = Field(None, description="Short title/name")
    status: str = Field(
        default="open", description='Status: "open", "in-progress", "completed", etc'
    )
    next_action: Optional[str] = Field(None, description="Next specific action to take")
    notes: Optional[str] = Field(None, description="Additional details or context")

    # Metadata
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="AI confidence score (0-1)",
    )
    created_at: str = Field(..., description="ISO8601 timestamp when created")
    updated_at: Optional[str] = Field(
        None, description="ISO8601 timestamp when updated"
    )

    # Original message for reference
    original_text: Optional[str] = Field(
        None, description="Original message text that created this item"
    )

    class Config:
        """Pydantic config for DynamoDB compatibility."""

        # Allow arbitrary types for DynamoDB operations
        arbitrary_types_allowed = True

    @staticmethod
    def build_pk(category: str, item_id: str) -> str:
        """Build PK from category and item_id.

        Args:
            category: The item category (lowercase: people, projects, ideas, admin)
            item_id: Unique identifier for the item

        Returns:
            PK in format: {category}#{item_id}
        """
        return f"{category}#{item_id}"

    @staticmethod
    def parse_pk(pk: str) -> Tuple[str, str]:
        """Parse PK into category and item_id.

        Args:
            pk: Partition key in format: {category}#{item_id}

        Returns:
            Tuple of (category, item_id)
        """
        parts = pk.split("#", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid PK format: {pk}")
        return parts[0], parts[1]

    @staticmethod
    def build_sk(sk_type: str = "PROFILE", sequence: Optional[int] = None) -> str:
        """Build SK for item.

        Currently supports only PROFILE type (primary item representation).
        Can be extended for other SK patterns (history, metadata, etc).

        Args:
            sk_type: Type of sort key (default: "PROFILE")
            sequence: Optional sequence number for multiple entries

        Returns:
            SK string
        """
        if sequence is not None:
            return f"{sk_type}#{sequence}"
        return sk_type

    @staticmethod
    def parse_sk(sk: str) -> Tuple[str, Optional[int]]:
        """Parse SK into components.

        Args:
            sk: Sort key string

        Returns:
            Tuple of (sk_type, sequence_number or None)
        """
        if "#" in sk:
            parts = sk.split("#", 1)
            try:
                sequence = int(parts[1])
                return parts[0], sequence
            except ValueError:
                return sk, None
        return sk, None


class People(Item):
    """Model for People items.

    Example PK/SK:
    - PK: people#john-smith-uuid
    - SK: PROFILE

    Additional fields could include:
    - contact_info, relationship_type, etc.
    """

    category: str = Field(default="people", description="Category: people")

    @classmethod
    def create(
        cls,
        name: str,
        item_id: Optional[str] = None,
        status: str = "open",
        next_action: Optional[str] = None,
        notes: Optional[str] = None,
        confidence: float = 0.0,
        created_at: str = "",
        updated_at: Optional[str] = None,
        original_text: Optional[str] = None,
    ) -> "People":
        """Factory method to create a People item.

        Args:
            name: Person's name
            item_id: Unique identifier (defaults to UUID)
            status: Current status
            next_action: Next action to take
            notes: Additional notes
            confidence: AI confidence score
            created_at: ISO8601 creation timestamp
            updated_at: ISO8601 update timestamp
            original_text: Original message text

        Returns:
            People instance
        """
        if not item_id:
            item_id = str(uuid.uuid4())[:8]

        return cls(
            pk=cls.build_pk("people", item_id),
            sk="PROFILE",
            name=name,
            status=status,
            next_action=next_action,
            notes=notes,
            confidence=confidence,
            created_at=created_at,
            updated_at=updated_at,
            original_text=original_text,
        )


class Projects(Item):
    """Model for Projects items.

    Example PK/SK:
    - PK: projects#project-alpha-uuid
    - SK: PROFILE

    Additional fields could include:
    - deadline, priority, team_members, etc.
    """

    category: str = Field(default="projects", description="Category: projects")

    @classmethod
    def create(
        cls,
        name: str,
        item_id: Optional[str] = None,
        status: str = "open",
        next_action: Optional[str] = None,
        notes: Optional[str] = None,
        confidence: float = 0.0,
        created_at: str = "",
        updated_at: Optional[str] = None,
        original_text: Optional[str] = None,
    ) -> "Projects":
        """Factory method to create a Projects item.

        Args:
            name: Project name
            item_id: Unique identifier (defaults to UUID)
            status: Current status
            next_action: Next action to take
            notes: Additional notes
            confidence: AI confidence score
            created_at: ISO8601 creation timestamp
            updated_at: ISO8601 update timestamp
            original_text: Original message text

        Returns:
            Projects instance
        """
        if not item_id:
            item_id = str(uuid.uuid4())[:8]

        return cls(
            pk=cls.build_pk("projects", item_id),
            sk="PROFILE",
            name=name,
            status=status,
            next_action=next_action,
            notes=notes,
            confidence=confidence,
            created_at=created_at,
            updated_at=updated_at,
            original_text=original_text,
        )


class Ideas(Item):
    """Model for Ideas items.

    Example PK/SK:
    - PK: ideas#idea-brainstorm-uuid
    - SK: PROFILE

    Additional fields could include:
    - potential_impact, implementation_effort, etc.
    """

    category: str = Field(default="ideas", description="Category: ideas")

    @classmethod
    def create(
        cls,
        name: str,
        item_id: Optional[str] = None,
        status: str = "open",
        next_action: Optional[str] = None,
        notes: Optional[str] = None,
        confidence: float = 0.0,
        created_at: str = "",
        updated_at: Optional[str] = None,
        original_text: Optional[str] = None,
    ) -> "Ideas":
        """Factory method to create an Ideas item.

        Args:
            name: Idea title
            item_id: Unique identifier (defaults to UUID)
            status: Current status
            next_action: Next action to take
            notes: Additional notes
            confidence: AI confidence score
            created_at: ISO8601 creation timestamp
            updated_at: ISO8601 update timestamp
            original_text: Original message text

        Returns:
            Ideas instance
        """
        if not item_id:
            item_id = str(uuid.uuid4())[:8]

        return cls(
            pk=cls.build_pk("ideas", item_id),
            sk="PROFILE",
            name=name,
            status=status,
            next_action=next_action,
            notes=notes,
            confidence=confidence,
            created_at=created_at,
            updated_at=updated_at,
            original_text=original_text,
        )


class Admin(Item):
    """Model for Admin items.

    Example PK/SK:
    - PK: admin#task-review-uuid
    - SK: PROFILE

    Additional fields could include:
    - priority, assigned_to, deadline, etc.
    """

    category: str = Field(default="admin", description="Category: admin")

    @classmethod
    def create(
        cls,
        name: str,
        item_id: Optional[str] = None,
        status: str = "open",
        next_action: Optional[str] = None,
        notes: Optional[str] = None,
        confidence: float = 0.0,
        created_at: str = "",
        updated_at: Optional[str] = None,
        original_text: Optional[str] = None,
    ) -> "Admin":
        """Factory method to create an Admin item.

        Args:
            name: Admin task name
            item_id: Unique identifier (defaults to UUID)
            status: Current status
            next_action: Next action to take
            notes: Additional notes
            confidence: AI confidence score
            created_at: ISO8601 creation timestamp
            updated_at: ISO8601 update timestamp
            original_text: Original message text

        Returns:
            Admin instance
        """
        if not item_id:
            item_id = str(uuid.uuid4())[:8]

        return cls(
            pk=cls.build_pk("admin", item_id),
            sk="PROFILE",
            name=name,
            status=status,
            next_action=next_action,
            notes=notes,
            confidence=confidence,
            created_at=created_at,
            updated_at=updated_at,
            original_text=original_text,
        )
