"""Document structure extraction from Markdown."""

import re
from dataclasses import dataclass, field


@dataclass
class HeadingNode:
    """A heading node in the document structure tree."""

    level: int  # 0 (root/no heading) or 1-6 (# to ######)
    title: str
    start_pos: int  # Character offset in original document
    end_pos: int  # Character offset where this heading's content ends
    children: list["HeadingNode"] = field(default_factory=list)


@dataclass
class DocumentStructure:
    """Document structure containing heading hierarchy."""

    root: HeadingNode
    heading_map: dict[int, HeadingNode]  # start_pos -> HeadingNode

    def get_heading_at_pos(self, pos: int) -> HeadingNode | None:
        """Find the deepest heading that contains the given position.

        Args:
            pos: Character position in document

        Returns:
            HeadingNode: Deepest heading containing this position, or None
        """

        def find_deepest(node: HeadingNode) -> HeadingNode | None:
            """Recursively find the deepest node containing pos."""
            if not (node.start_pos <= pos < node.end_pos):
                return None

            # Check children first (to find deepest)
            for child in node.children:
                result = find_deepest(child)
                if result:
                    return result

            # No child contains it, so this node is the deepest
            return node

        return find_deepest(self.root)

    def get_heading_path(self, heading: HeadingNode) -> str:
        """Get the full path to a heading.

        Args:
            heading: The heading node

        Returns:
            str: Path like "# Main > ## Section > ### Subsection"
        """

        def find_path(node: HeadingNode, target: HeadingNode, path: list[str]) -> bool:
            """Recursively find path to target node."""
            # Format heading with # symbols
            if node.level > 0:
                heading_str = "#" * node.level + " " + node.title
                path.append(heading_str)

            if node == target:
                return True

            # Search children
            for child in node.children:
                if find_path(child, target, path):
                    return True

            # Not found in this branch, remove from path
            if node.level > 0:
                path.pop()

            return False

        path: list[str] = []
        find_path(self.root, heading, path)
        return " > ".join(path)


class StructureExtractor:
    """Extractor for document structure from Markdown."""

    # Regex to match markdown headings: ^#{1,6} Title
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def extract_structure(self, markdown: str) -> DocumentStructure:
        """Extract heading structure from markdown text.

        Args:
            markdown: Markdown text

        Returns:
            DocumentStructure: Extracted structure
        """
        # Find all headings with their positions
        headings = []
        for match in self.HEADING_PATTERN.finditer(markdown):
            level = len(match.group(1))  # Count # symbols
            title = match.group(2).strip()
            start_pos = match.start()
            headings.append((level, title, start_pos))

        # Create root node
        root = HeadingNode(level=0, title="", start_pos=0, end_pos=len(markdown), children=[])

        if not headings:
            # No headings, return empty structure
            return DocumentStructure(root=root, heading_map={})

        # Build heading tree
        heading_map: dict[int, HeadingNode] = {}
        stack: list[HeadingNode] = [root]  # Stack of ancestor nodes

        for i, (level, title, start_pos) in enumerate(headings):
            # Calculate end position (start of next heading or end of document)
            if i + 1 < len(headings):
                end_pos = headings[i + 1][2]
            else:
                end_pos = len(markdown)

            # Create node
            node = HeadingNode(
                level=level, title=title, start_pos=start_pos, end_pos=end_pos, children=[]
            )
            heading_map[start_pos] = node

            # Find parent by popping stack until we find a lower level
            while len(stack) > 1 and stack[-1].level >= level:
                stack.pop()

            # Add as child of current top of stack
            parent = stack[-1]
            parent.children.append(node)

            # Push this node onto stack
            stack.append(node)

        # Update parent end positions to include all their children's content
        def update_end_positions(node: HeadingNode):
            """Recursively update end positions to include all children."""
            if node.children:
                # Update children first
                for child in node.children:
                    update_end_positions(child)
                # This node's end is the end of its last child
                node.end_pos = node.children[-1].end_pos

        update_end_positions(root)

        # Update root's level if it has children
        if root.children:
            root.level = root.children[0].level  # Take level from first child if root has content
            if len(root.children) == 1:
                # Single top-level heading becomes the root
                return DocumentStructure(root=root.children[0], heading_map=heading_map)

        return DocumentStructure(root=root, heading_map=heading_map)
