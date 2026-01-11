"""
Validation test for Story 020 - Structure Preservation Score >95%.

Tests that the complete pipeline preserves >95% of document headings.

USES REAL OLLAMA AND WEAVIATE (no mocks).
"""

import pytest

from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.aletheia.structure_extractor import StructureExtractor
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.iris.structure_quality import StructurePreservationAnalyzer
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


class TestStructurePreservationValidation:
    """Validation tests for >95% structure preservation."""

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_simple_document_100_percent_preservation(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test simple document achieves 100% structure preservation."""
        # GIVEN: Document with clear heading structure and enough content for multiple chunks
        markdown_content = (
            """# Main Topic

Content under main topic. """
            + "More content here. " * 50
            + """

## Section One

First section content. """
            + "Additional text here. " * 50
            + """

## Section Two

Second section content. """
            + "Even more text here. " * 50
            + """

### Subsection

Nested content here. """
            + "Final content block. " * 50
        )

        test_file = tmp_path / "simple.md"
        test_file.write_text(markdown_content)

        # Define expected headings
        expected_headings = ["# Main Topic", "## Section One", "## Section Two", "### Subsection"]

        # Use REAL Ollama client
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"],
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        # WHEN: Ingesting through pipeline
        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
        )
        ingestor.ingest_file(str(test_file))

        # THEN: Fetch stored chunks from Weaviate
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=100)
        stored_chunks = [obj.properties for obj in results.objects]

        # Analyze structure preservation
        analyzer = StructurePreservationAnalyzer(stored_chunks, expected_headings)
        metrics = analyzer.analyze()

        # Should achieve 100% preservation for simple document
        assert metrics.preservation_score == 1.0
        assert metrics.n_headings_expected == 4
        assert metrics.n_headings_found == 4
        assert metrics.heading_depth_accuracy == 1.0

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_complex_document_95_percent_preservation(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test complex document achieves >95% structure preservation."""
        # GIVEN: Complex document with multiple levels and enough content
        markdown_content = (
            """# Python Development Guide

Introduction to Python development. """
            + "Learn Python basics. " * 50
            + """

## Setup

How to set up your environment. """
            + "Setup instructions. " * 50
            + """

### Virtual Environments

Use venv or virtualenv. """
            + "Virtual env details. " * 50
            + """

### Package Management

Use pip or poetry. """
            + "Package management tips. " * 50
            + """

## Best Practices

Follow these guidelines. """
            + "Best practice details. " * 50
            + """

### Code Style

Use PEP 8 formatting. """
            + "Code style guidelines. " * 50
            + """

### Testing

Write comprehensive tests. """
            + "Testing strategies. " * 50
            + """

#### Unit Tests

Test individual functions. """
            + "Unit testing details. " * 50
            + """

#### Integration Tests

Test component interactions. """
            + "Integration testing details. " * 50
            + """

## Advanced Topics

Deep dive into advanced features. """
            + "Advanced concepts. " * 50
            + """

### Async Programming

Using asyncio effectively. """
            + "Async programming guide. " * 50
            + """

### Type Hints

Static type checking with mypy. """
            + "Type hints tutorial. " * 50
        )

        test_file = tmp_path / "complex.md"
        test_file.write_text(markdown_content)

        # Define expected headings
        expected_headings = [
            "# Python Development Guide",
            "## Setup",
            "### Virtual Environments",
            "### Package Management",
            "## Best Practices",
            "### Code Style",
            "### Testing",
            "#### Unit Tests",
            "#### Integration Tests",
            "## Advanced Topics",
            "### Async Programming",
            "### Type Hints",
        ]

        # Use REAL Ollama client
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"],
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        # WHEN: Ingesting through pipeline
        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
        )
        ingestor.ingest_file(str(test_file))

        # THEN: Fetch stored chunks from Weaviate
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=100)
        stored_chunks = [obj.properties for obj in results.objects]

        # Analyze structure preservation
        analyzer = StructurePreservationAnalyzer(stored_chunks, expected_headings)
        metrics = analyzer.analyze()

        # CRITICAL: Must achieve >95% preservation
        assert metrics.preservation_score >= 0.95
        assert metrics.n_headings_expected == 12
        assert metrics.n_headings_found >= 11  # At least 11/12

        # Heading depth accuracy should also be high
        assert metrics.heading_depth_accuracy >= 0.95

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_large_document_95_percent_preservation(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test large document with lots of content achieves >95% preservation."""
        # GIVEN: Large document with multiple chunks per section
        markdown_content = (
            """# Machine Learning Fundamentals

"""
            + "Introduction to machine learning concepts. " * 50
            + """

## Supervised Learning

"""
            + "Supervised learning uses labeled data. " * 100
            + """

### Classification

"""
            + "Classification predicts discrete categories. " * 100
            + """

#### Decision Trees

"""
            + "Decision trees split data recursively. " * 80
            + """

#### Neural Networks

"""
            + "Neural networks learn complex patterns. " * 80
            + """

### Regression

"""
            + "Regression predicts continuous values. " * 100
            + """

## Unsupervised Learning

"""
            + "Unsupervised learning finds patterns in unlabeled data. " * 100
            + """

### Clustering

"""
            + "Clustering groups similar data points. " * 100
            + """

### Dimensionality Reduction

"""
            + "Reducing feature space while preserving information. " * 80
        )

        test_file = tmp_path / "large.md"
        test_file.write_text(markdown_content)

        expected_headings = [
            "# Machine Learning Fundamentals",
            "## Supervised Learning",
            "### Classification",
            "#### Decision Trees",
            "#### Neural Networks",
            "### Regression",
            "## Unsupervised Learning",
            "### Clustering",
            "### Dimensionality Reduction",
        ]

        # Use REAL Ollama client
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"],
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        # WHEN: Ingesting through pipeline
        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
        )
        ingestor.ingest_file(str(test_file))

        # THEN: Fetch stored chunks from Weaviate
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=100)
        stored_chunks = [obj.properties for obj in results.objects]

        # Should have created many chunks
        assert len(stored_chunks) > 10

        # Analyze structure preservation
        analyzer = StructurePreservationAnalyzer(stored_chunks, expected_headings)
        metrics = analyzer.analyze()

        # CRITICAL: Must achieve >95% even with many chunks
        assert metrics.preservation_score >= 0.95
        assert metrics.n_headings_expected == 9
        assert metrics.n_headings_found >= 9  # All headings preserved

        # Print metrics for visibility
        print("\nStructure Preservation Metrics:")
        print(f"  Preservation Score: {metrics.preservation_score:.1%}")
        print(f"  Headings Found: {metrics.n_headings_found}/{metrics.n_headings_expected}")
        print(f"  Depth Accuracy: {metrics.heading_depth_accuracy:.1%}")
        print(f"  Total Chunks: {len(stored_chunks)}")

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_preservation_across_multiple_documents(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test preservation score across multiple documents."""
        # GIVEN: Multiple documents with different structures and enough content
        docs = {
            "doc1.md": """# Doc One

## Section A

Content here. """
            + "More text. " * 50
            + """

## Section B

More content. """
            + "Additional text. " * 50,
            "doc2.md": """# Doc Two

## Introduction

### Background

Context here. """
            + "More context. " * 50
            + """

## Methods

Details here. """
            + "More details. " * 50,
            "doc3.md": """# Doc Three

## Overview

### Goal One

Goal one details. """
            + "More goal one. " * 30
            + """

### Goal Two

Goal two details. """
            + "More goal two. " * 30
            + """

### Goal Three

Goal three details. """
            + "More goal three. " * 30
            + """

## Conclusion

Final thoughts. """
            + "Concluding remarks. " * 30,
        }

        all_expected_headings = []

        for filename, content in docs.items():
            test_file = tmp_path / filename
            test_file.write_text(content)

            # Extract headings from this doc
            extractor = StructureExtractor()
            structure = extractor.extract_structure(content)

            # Collect all headings
            def collect_headings(node, headings_list):
                if node.level > 0:
                    heading_str = "#" * node.level + " " + node.title
                    headings_list.append(heading_str)
                for child in node.children:
                    collect_headings(child, headings_list)

            collect_headings(structure.root, all_expected_headings)

        # Use REAL Ollama client
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"],
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        # WHEN: Ingesting all documents
        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
        )

        for filename in docs.keys():
            ingestor.ingest_file(str(tmp_path / filename))

        # THEN: Fetch all chunks from Weaviate
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=200)
        stored_chunks = [obj.properties for obj in results.objects]

        # Overall preservation should be >95%
        analyzer = StructurePreservationAnalyzer(stored_chunks, all_expected_headings)
        metrics = analyzer.analyze()

        # CRITICAL: Cross-document preservation >95%
        assert metrics.preservation_score >= 0.95

        print("\nMulti-Document Preservation:")
        print(f"  Documents: {len(docs)}")
        print(f"  Total Headings: {metrics.n_headings_expected}")
        print(f"  Headings Found: {metrics.n_headings_found}")
        print(f"  Preservation: {metrics.preservation_score:.1%}")
