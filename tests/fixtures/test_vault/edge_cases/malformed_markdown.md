# Malformed Markdown Test

This file intentionally contains malformed markdown to test error handling.

## Unclosed Code Block

```python
def broken_function():
    print("This code block is never closed")
    return True

## This heading is inside the code block but shouldn't be

Some text here.

## Another Section

Normal content with **bold** and *italic*.

[Broken link without URL]

![Image without source]

| Table | Missing |
|-------|
| Cells |

## Nested Formatting

**Bold with *italic inside but not closed

> Blockquote
>> Nested blockquote
> Back to first level but forgot to close

---

Triple backticks in content: ```

End of file
