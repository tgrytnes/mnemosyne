# Story 007: Multi-Turn Reasoning Loop

**As a** user
**I want** to watch the Agent loop through "Search" and "Summarize" nodes until it finds a complete answer
**So that** I can see the AI's "thinking process" in the LangGraph visualizer

## Acceptance Criteria
- [ ] LangGraph graph with iterative loop: Search → Evaluate → Summarize → Decision
- [ ] Decision node determines if answer is complete or needs more searching
- [ ] Maximum iteration limit (e.g., 5 loops) to prevent infinite loops
- [ ] Each iteration logged with intermediate results
- [ ] LangGraph Studio visualization shows the execution path
- [ ] User-facing feedback during iterations (via Hermes Telegram bot)
- [ ] Final answer includes provenance (which iterations/searches contributed)

## Technical Notes

### Graph Structure
```python
from langgraph.graph import StateGraph, END

class ReasoningState(BaseModel):
    query: str
    iterations: int
    search_results: List[Document]
    partial_answer: str
    is_complete: bool
    max_iterations: int = 5

graph = StateGraph(ReasoningState)

graph.add_node("search", search_node)
graph.add_node("evaluate", evaluate_node)
graph.add_node("summarize", summarize_node)
graph.add_node("decide", decision_node)

graph.add_edge("search", "evaluate")
graph.add_edge("evaluate", "summarize")
graph.add_edge("summarize", "decide")

# Conditional edge: loop or end
graph.add_conditional_edges(
    "decide",
    lambda state: "search" if not state.is_complete and state.iterations < state.max_iterations else END
)

graph.set_entry_point("search")
```

### Node Implementations
1. **Search Node**: Uses Router (Story 005) to find relevant docs
2. **Evaluate Node**: LLM checks if search results answer the query
3. **Summarize Node**: Generates partial answer from current results
4. **Decision Node**: Determines if complete (confidence threshold) or needs refinement

### Iteration Feedback (Hermes Integration)
```
Telegram Bot Message:
"🔍 Iteration 1/5: Searching clusters about 'Docker networking'...
📄 Found 12 relevant notes, synthesizing...
❓ Partial answer confidence: 65% - searching for more details...

🔍 Iteration 2/5: Refining search with 'Docker bridge networks'...
📄 Found 8 more notes, updating answer...
✅ Answer complete (confidence: 92%)"
```

### Visualization in LangGraph Studio
- Each node execution highlighted in real-time
- Edge traversals animated
- State inspector shows search_results and partial_answer at each step

### Dependencies
- LangGraph framework
- Story 005: Semantic Routing (used by search node)
- Story 004: Checkpointed Knowledge (save state between iterations)
- Hermes: Telegram bot for user notifications
- LangGraph Studio for visualization

## Affected Components
- **Argus**: Core reasoning loop implementation
- **Hermes**: Iteration progress notifications
- **Iris**: Search execution

## Priority
**Medium** - Showcase feature, not critical for MVP

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-3`, `langgraph`, `visualization`, `showcase`, `argus`, `hermes`

## Related Stories
- Story 004: Checkpointed Knowledge (checkpoint between iterations)
- Story 005: Semantic Routing (search strategy)
- Story 008: The "Traceable" Showcase (visualizes the same data)
