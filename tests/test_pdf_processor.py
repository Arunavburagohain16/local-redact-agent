from app.services.pdf_processor import PAGE_SEPARATOR, split_markdown_by_page


def test_split_markdown_by_page_with_markers() -> None:
    markdown = f"{{1}}{PAGE_SEPARATOR}\n# Page 1\n{{2}}{PAGE_SEPARATOR}\n# Page 2"

    pages = split_markdown_by_page(markdown)

    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert pages[0]["markdown"] == "# Page 1"
    assert pages[1]["page_number"] == 2
    assert pages[1]["markdown"] == "# Page 2"


def test_split_markdown_by_page_without_markers() -> None:
    pages = split_markdown_by_page("# Single page")

    assert len(pages) == 1
    assert pages[0]["page_number"] == 1
    assert pages[0]["markdown"] == "# Single page"
