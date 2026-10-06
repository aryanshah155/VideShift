# PageRank Algorithm

def page_rank(graph, damping=0.85, tolerance=0.0001):
    pages = list(graph.keys())
    n = len(pages)

    # Initialize PageRank equally
    rank = {page: 1 / n for page in pages}

    while True:
        new_rank = {}

        for page in pages:
            incoming_sum = 0

            # Find pages that link to the current page
            for q in pages:
                if page in graph[q]:
                    out_degree = len(graph[q])

                    if out_degree > 0:
                        incoming_sum += rank[q] / out_degree

            new_rank[page] = (1 - damping) + damping * incoming_sum

        # Check convergence
        difference = sum(abs(new_rank[p] - rank[p]) for p in pages)

        rank = new_rank

        if difference < tolerance:
            break

    return rank


# Directed graph
# A -> B, C
# B -> C
# C -> A
# D -> C

graph = {
    'A': ['B', 'C'],
    'B': ['C'],
    'C': ['A'],
    'D': ['C']
}

# Calculate PageRank
ranks = page_rank(graph)

# Display results
print("PageRank Values:")
for page, value in sorted(ranks.items(), key=lambda x: x[1], reverse=True):
    print(f"{page}: {value:.4f}")
