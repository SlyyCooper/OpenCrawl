# OpenCrawl 🦊

A powerful, LLM-friendly HTML scraper and converter for seamless web content extraction.

**OpenCrawl** is an intelligent tool that empowers you to **fetch** HTML content from any URL and elegantly **transform** single or multiple pages into clean **HTML**, **Markdown**, or **JSON** formats. Generate detailed **site maps** with unlimited depth exploration to map entire domains. The script offers flexible integration through three powerful interfaces:

1. **Command-Line Interactive** - User-friendly menu-driven interface for quick operations
2. **Direct Function Calls** - Seamless integration with your Python codebase
3. **LLM Function Calls** - Structured API designed for large language model interactions

---

# Table of Contents

1. [Dependencies](#dependencies)  
2. [Installation](#installation)  
3. [Script Overview](#script-overview)  
4. [Key Functions](#key-functions)  
   1. [Single Page Conversion](#single-page-conversion)  
   2. [Recursive Crawling](#recursive-crawling)  
   3. [Map (Site Map Only)](#map-site-map-only)  
   4. [Recursive Crawling & Map](#recursive-crawling--map)  
   5. [Universal LLM Function Call](#universal-llm-function-call)  
5. [Dictionaries & Parameters](#dictionaries--parameters)  
   1. [The Settings Dictionary (CLI)](#the-settings-dictionary-cli)  
   2. [LLM Function Call Parameters](#llm-function-call-parameters)  
6. [Running the Script](#running-the-script)  
7. [Examples](#examples)  
   1. [CLI Usage](#cli-usage)  
   2. [Python Imports](#python-imports)  
   3. [LLM Function Call Example](#llm-function-call-example)  

---

## 1. Dependencies

The script uses the following **external libraries**:

- **questionary** (for CLI prompts)
- **requests**
- **html2text**
- **rich**
- **beautifulsoup4**

If you do not have them installed, run:

```bash
pip install questionary requests html2text rich beautifulsoup4
```

---

## 2. Installation

1. **Save** the script to a file, for example:  
   ```bash
   multi_format_cli.py
   ```
2. **Make it executable** (if you want to run it directly, on UNIX-like systems):  
   ```bash
   chmod +x multi_format_cli.py
   ```
3. **Run** it with Python:
   ```bash
   python multi_format_cli.py
   ```

---

## 3. Script Overview

This script fetches HTML from user-supplied URLs, extracts the **main content** (excluding `<header>`, `<nav>`, `<footer>`, and elements whose ID or class includes `"footer"`), removes doc-specific symbol elements, and converts the results into:
- **Clean HTML**,
- **Markdown** (with optional Table of Contents),
- **JSON** (containing the extracted text in a simple dictionary).

It also supports:
- **Recursive Crawling** of same-domain pages (via BFS with a user-defined depth).
- **Site Map** generation for all same-domain links (unlimited depth). The site map can be in HTML, Markdown, or JSON adjacency form.

**File collisions** are handled by **automatically appending** `"_1"`, `"_2"`, etc. whenever a filename already exists.

---

## 4. Key Functions

### 4.1 Single Page Conversion
```python
def do_single_page_conversion(
    url,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
) -> Optional[str]
```
- **Description**: Fetches **one** page from `url`, cleans it, and converts to the chosen `output_format` (**HTML**, **Markdown**, or **JSON**).  
- **Output**: The script writes the file into the **`output`** directory (no subdirectory for single page).
- **Returns**: The absolute path to the newly created file, or **None** if an error occurred (e.g. invalid URL).

### 4.2 Recursive Crawling
```python
def do_recursive_crawling(
    url,
    max_depth=1,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
) -> None
```
- **Description**: Recursively crawls all same-domain links up to `max_depth`, converting each page to the chosen `output_format`.
- **Output**: Files are saved in the **`recursive_crawl`** subdirectory.
- **Returns**: `None`.

### 4.3 Map (Site Map Only)
```python
def do_map_only(
    url,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
) -> None
```
- **Description**: Creates a **site map** (only) by traversing all same-domain links to **unlimited depth**.  
- **Output**: 
  - If **HTML**, saves `site_map.html` (with nested lists).  
  - If **Markdown**, saves `site_map.md` (nested bullet points).  
  - If **JSON**, saves `site_map.json` (dictionary adjacency).
- **Returns**: `None`.  
- **Path**: Written in **`site_map`** subdirectory.

### 4.4 Recursive Crawling & Map
```python
def do_recursive_crawling_and_map(
    url,
    max_depth=1,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
) -> None
```
- **Description**: Combines **Recursive Crawling** (with user-defined depth) and then does a **full** site map (unlimited depth).  
- **Output**:  
  - **Pages** go into **`crawl_and_map`** subdirectory.  
  - The **site map** (html/md/json) is also placed there.  
- **Returns**: `None`.

### 4.5 Universal LLM Function Call
```python
def llm_function_call(
    function_name: str,
    url: str,
    output_format: str = "Markdown",
    keep_images: bool = True,
    keep_links: bool = True,
    keep_emphasis: bool = True,
    generate_toc: bool = False,
    custom_filename: str = None,
    max_depth: int = 1
) -> Any
```
- **Description**: A **universal dispatcher** so an LLM can call the script’s features by name.  
- **Parameters**:
  - **function_name**: A string in \{
    `"do_single_page_conversion"`,
    `"do_recursive_crawling"`,
    `"do_map_only"`,
    `"do_recursive_crawling_and_map"`
    \}
  - **url**: The base URL to process.
  - **output_format**: `"HTML"`, `"Markdown"`, or `"JSON"`.
  - **keep_images**, **keep_links**, **keep_emphasis**: Booleans controlling what is kept in the output.
  - **generate_toc**: Whether to generate a table of contents if `output_format="Markdown"`.
  - **custom_filename**: Optional string for the file name.
  - **max_depth**: Only relevant for crawling functions (otherwise ignored).
- **Returns**: The result of the underlying function, typically a path or **None**.

---

## 5. Dictionaries & Parameters

### 5.1 The Settings Dictionary (CLI)

When the script is run **interactively**, it uses:
```python
settings = {
    "output_format": <"HTML"|"Markdown"|"JSON">,
    "keep_images": <bool>,
    "keep_links": <bool>,
    "keep_emphasis": <bool>,
    "generate_toc": <bool>,
    "custom_filename": <bool>,  # Did user choose a custom file name?
    "output_filename": <str or None>  # The actual custom file name if chosen
}
```

### 5.2 LLM Function Call Parameters

When calling `llm_function_call`, you pass in the **function_name** plus named arguments:

- `function_name`
- `url`
- `output_format` (default `"Markdown"`)
- `keep_images` (default `True`)
- `keep_links` (default `True`)
- `keep_emphasis` (default `True`)
- `generate_toc` (default `False`)
- `custom_filename` (default `None`)
- `max_depth` (default `1`)

---

## 6. Running the Script

### **Command-Line / Interactive Menu**
1. **Launch**:  
   ```bash
   python multi_format_cli.py
   ```
2. **Select** your desired action from the main menu:
   - **Single Page Conversion**  
   - **Recursive Crawling**  
   - **Map**  
   - **Recursive Crawling & Map**  
   - **Exit**  

3. **Answer** the prompts (URL, advanced settings, depth if applicable).  

### **Importing as a Module**
1. **Import** the script:
   ```python
   from multi_format_cli import (
       do_single_page_conversion,
       do_recursive_crawling,
       do_map_only,
       do_recursive_crawling_and_map,
       llm_function_call
   )
   ```
2. **Call** any function with your parameters.

---

## 7. Examples

### 7.1 CLI Usage

**Single Page Example**  
1. Run:
   ```bash
   python multi_format_cli.py
   ```
2. Choose **`1. Single Page Conversion`**.  
3. Enter a **URL** (e.g., `https://example.com`).  
4. Choose advanced settings (e.g., output format `Markdown`, keep images = yes, etc.).  
5. The script writes a `.md` file into the **`output`** folder.

### 7.2 Python Imports

**Single Page Conversion** programmatically:
```python
from multi_format_cli import do_single_page_conversion

result_path = do_single_page_conversion(
    url="https://example.com",
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=True,
    custom_filename=None
)

print(f"File saved to {result_path}")
```

**Recursive Crawling** programmatically:
```python
from multi_format_cli import do_recursive_crawling

do_recursive_crawling(
    url="https://example.com",
    max_depth=2,              # crawl 2 levels deep
    output_format="HTML",     # produce cleaned HTML for each page
    keep_images=False,
    keep_links=True
)
```

### 7.3 LLM Function Call Example

**Hypothetical** GPT-4–style function call in JSON (for a single page conversion):

```jsonc
{
  "name": "llm_function_call",
  "arguments": {
    "function_name": "do_single_page_conversion",
    "url": "https://example.com",
    "output_format": "Markdown",
    "keep_images": true,
    "keep_links": true,
    "keep_emphasis": true,
    "generate_toc": true,
    "custom_filename": null,
    "max_depth": 1
  }
}
```

Which translates in Python to:
```python
from multi_format_cli import llm_function_call

llm_function_call(
    function_name="do_single_page_conversion",
    url="https://example.com",
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=True,
    custom_filename=None,
    max_depth=1
)
```

This performs a **single-page** fetch & convert to **Markdown** with a table of contents, saving the file in `output/`. If a collision is detected, a suffix (`_1`, `_2`, etc.) is appended automatically.

---

**Enjoy** this script for your multi-format scraping and domain exploration needs! Feel free to extend or adapt it for your specific workflows. If you have any questions, please let us know!