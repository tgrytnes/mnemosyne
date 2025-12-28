"""Unit tests for document structure extraction."""


from mnemosyne.aletheia.structure_extractor import (
    DocumentStructure,
    HeadingNode,
    StructureExtractor,
)


class TestHeadingNode:
    """Test suite for HeadingNode dataclass."""

    def test_heading_node_creation(self):
        """Test creating a HeadingNode."""
        node = HeadingNode(level=1, title="Main Heading", start_pos=0, end_pos=100, children=[])

        assert node.level == 1
        assert node.title == "Main Heading"
        assert node.start_pos == 0
        assert node.end_pos == 100
        assert node.children == []

    def test_heading_node_with_children(self):
        """Test HeadingNode with child nodes."""
        child = HeadingNode(level=2, title="Child Heading", start_pos=50, end_pos=100, children=[])
        parent = HeadingNode(
            level=1, title="Parent Heading", start_pos=0, end_pos=100, children=[child]
        )

        assert len(parent.children) == 1
        assert parent.children[0].title == "Child Heading"


class TestDocumentStructure:
    """Test suite for DocumentStructure."""

    def test_document_structure_creation(self):
        """Test creating a DocumentStructure."""
        root = HeadingNode(level=0, title="Root", start_pos=0, end_pos=200, children=[])
        structure = DocumentStructure(root=root, heading_map={})

        assert structure.root.title == "Root"
        assert structure.heading_map == {}

    def test_get_heading_at_pos(self):
        """Test finding heading at specific position."""
        child = HeadingNode(level=2, title="Section", start_pos=50, end_pos=150, children=[])
        root = HeadingNode(level=1, title="Main", start_pos=0, end_pos=200, children=[child])
        heading_map = {0: root, 50: child}
        structure = DocumentStructure(root=root, heading_map=heading_map)

        # Position 75 is within the child heading
        heading = structure.get_heading_at_pos(75)
        assert heading is not None
        assert heading.title == "Section"

    def test_get_heading_at_pos_returns_deepest(self):
        """Test that get_heading_at_pos returns the deepest heading."""
        grandchild = HeadingNode(
            level=3, title="Subsection", start_pos=100, end_pos=150, children=[]
        )
        child = HeadingNode(
            level=2, title="Section", start_pos=50, end_pos=150, children=[grandchild]
        )
        root = HeadingNode(level=1, title="Main", start_pos=0, end_pos=200, children=[child])
        heading_map = {0: root, 50: child, 100: grandchild}
        structure = DocumentStructure(root=root, heading_map=heading_map)

        # Position 125 is within grandchild - should return deepest
        heading = structure.get_heading_at_pos(125)
        assert heading is not None
        assert heading.title == "Subsection"
        assert heading.level == 3

    def test_get_heading_path(self):
        """Test getting heading path string."""
        grandchild = HeadingNode(
            level=3, title="Subsection", start_pos=100, end_pos=150, children=[]
        )
        child = HeadingNode(
            level=2, title="Section", start_pos=50, end_pos=150, children=[grandchild]
        )
        root = HeadingNode(level=1, title="Main", start_pos=0, end_pos=200, children=[child])
        structure = DocumentStructure(root=root, heading_map={})

        path = structure.get_heading_path(grandchild)
        assert path == "# Main > ## Section > ### Subsection"


class TestStructureExtractor:
    """Test suite for StructureExtractor."""

    def test_extract_structure_simple(self):
        """Test extracting structure from simple markdown."""
        markdown = """# Main Heading

Some content here.

## Section One

More content.

## Section Two

Even more content.
"""

        extractor = StructureExtractor()
        structure = extractor.extract_structure(markdown)

        assert structure.root.title == "Main Heading"
        assert structure.root.level == 1
        assert len(structure.root.children) == 2
        assert structure.root.children[0].title == "Section One"
        assert structure.root.children[1].title == "Section Two"

    def test_extract_structure_nested(self):
        """Test extracting nested heading structure."""
        markdown = """# Main

## Section

### Subsection

Content here.

## Another Section

More content.
"""

        extractor = StructureExtractor()
        structure = extractor.extract_structure(markdown)

        assert structure.root.level == 1
        assert len(structure.root.children) == 2
        # First child has a subsection
        assert len(structure.root.children[0].children) == 1
        assert structure.root.children[0].children[0].title == "Subsection"

    def test_extract_structure_no_headings(self):
        """Test extracting structure from document without headings."""
        markdown = "Just some plain text without any headings."

        extractor = StructureExtractor()
        structure = extractor.extract_structure(markdown)

        # Should have a root with no children
        assert structure.root.level == 0
        assert structure.root.title == ""
        assert len(structure.root.children) == 0

    def test_extract_structure_heading_positions(self):
        """Test that heading positions are correctly calculated."""
        markdown = """# Main Heading

Content under main.

## Section

Content under section.
"""

        extractor = StructureExtractor()
        structure = extractor.extract_structure(markdown)

        # Main heading starts at position 0
        assert structure.root.start_pos == 0
        # Section heading is further in the text
        assert structure.root.children[0].start_pos > 0

    def test_extract_structure_with_multiple_levels(self):
        """Test extracting structure with multiple heading levels."""
        markdown = """# Level 1

## Level 2

### Level 3

#### Level 4

##### Level 5

###### Level 6

Content.
"""

        extractor = StructureExtractor()
        structure = extractor.extract_structure(markdown)

        # Navigate down the tree
        current = structure.root
        for expected_level in [1, 2, 3, 4, 5, 6]:
            assert current.level == expected_level
            if expected_level < 6:
                assert len(current.children) == 1
                current = current.children[0]
