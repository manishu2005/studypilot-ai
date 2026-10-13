import pymupdf
doc = pymupdf.open()
page1=doc.new_page()
page1.insert_text(
    (72, 72),
    "Study AI Sample Course\n"
    "Data Structures and Algorithms\n\n"
    "Breadth First Search (BFS)\n"
    "BFS traverses a graph level by level. "
    "It commonly uses a queue to process "
    "vertices in first-in, first-out order.\n"
    "BFS can be used to find shortest paths "
    "in an unweighted graph."
)

page2 = doc.new_page()
page2.insert_text(
    (72, 72),
    "Depth First Search (DFS)\n"
    "DFS explores a path deeply before "
    "backtracking. A stack can be used to "
    "implement iterative DFS.\n\n"
    "BFS and DFS are graph traversal algorithms."
)

doc.save("sample_course.pdf")
doc.close()

print("Created sample_course.pdf")