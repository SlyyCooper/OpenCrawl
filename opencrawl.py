#!/usr/bin/env python3
"""
MULTI-FORMAT SCRAPER/CONVERTER WITH LLM FUNCTION SUPPORT
--------------------------------------------------------
A Python script that offers:
  - Single Page Conversion
  - Recursive Crawling
  - Map (full-site adjacency)
  - Recursive Crawling & Map

Output can be:
  - HTML (only main content, header/nav/footer stripped)
  - Markdown (with optional ToC)
  - JSON (structured output)

Key points:
  - Always appends suffix if file collisions occur.
  - No subdir for single-page conversion; always subdir for other features.
  - Provides a "llm_function_call(...)" for easy programmatic usage by an LLM.

USAGE:
  1) To run interactively (CLI):
       python multi_format_cli.py
  2) To import as a module (or in an LLM environment) and call either:
       - do_single_page_conversion(...) / do_recursive_crawling(...) / do_map_only(...) / do_recursive_crawling_and_map(...)
       - llm_function_call(...) (universal dispatcher for LLM usage)
"""

import os
import sys
import re
import json
from datetime import datetime
from urllib.parse import urlparse, urljoin
from collections import deque

# --- External libraries ---
#   pip install questionary requests html2text rich beautifulsoup4

import requests
import questionary
import html2text
from rich.console import Console
from rich.panel import Panel
from rich import print
from rich.progress import Progress
from rich.spinner import Spinner
from bs4 import BeautifulSoup

##############################################################################
#                               GLOBALS                                      #
##############################################################################

console = Console()

##############################################################################
#                             BANNER & UTILS                                 #
##############################################################################

def print_banner():
    banner_text = r"""
  ██████  ██████  ███████ ███    ██  ██████ ██████   █████  ██     ██ ██      
 ██    ██ ██   ██ ██      ████   ██ ██      ██   ██ ██   ██ ██     ██ ██      
 ██    ██ ██████  █████   ██ ██  ██ ██      ██████  ███████ ██  █  ██ ██      
 ██    ██ ██      ██      ██  ██ ██ ██      ██   ██ ██   ██ ██ ███ ██ ██      
  ██████  ██      ███████ ██   ████  ██████ ██   ██ ██   ██  ███ ███  ███████ 
                                                                        v1.0.0  
════════════════════════════════╦══════════════════════════════════════════════
                                ║ Web Scraping & Content Conversion Tool
════════════════════════════════╩══════════════════════════════════════════════"""
    console.print(banner_text, style="bold green")
    console.print(Panel.fit("The Ultimate HTML-to-Multi-Format CLI", style="bold magenta"))

def create_output_directory(output_dir="output"):
    """
    Creates the specified output directory if it doesn't exist.
    Returns the absolute path of the directory.
    """
    dir_path = os.path.join(os.getcwd(), output_dir)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return dir_path

def is_valid_url(url):
    parsed = urlparse(url)
    return bool(parsed.scheme) and bool(parsed.netloc)

##############################################################################
#                       FETCHING & HTML CLEANUP                               #
##############################################################################

def fetch_html(url):
    """
    Fetches raw HTML from the URL; raises an exception if it fails.
    """
    if not is_valid_url(url):
        raise ValueError(f"Invalid URL: {url}")
    try:
        with Progress() as progress:
            task = progress.add_task("[green]Fetching HTML...", total=None)
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            progress.update(task, completed=100)
        return response.text
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error fetching the URL: {e}")

def get_main_content(html_content):
    """
    Returns only the <main> content, removing <header>, <nav>, <footer>.
    Falls back to <body> if <main> not found; else entire doc.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # remove tags
    for tag_name in ["header", "nav", "footer"]:
        for t in soup.find_all(tag_name):
            t.decompose()

    main_tag = soup.find("main")
    if main_tag:
        return str(main_tag)

    body_tag = soup.find("body")
    if body_tag:
        return str(body_tag)

    return str(soup)

def remove_doc_symbol_elements(soup):
    """
    Removes elements with 'doc-symbol' or 'meth' classes; also text 'meth' outside code/spans.
    """
    for elem in soup.find_all(lambda tag: tag.has_attr('class') and (
            'doc-symbol' in tag.get('class') or 'meth' in tag.get('class'))):
        elem.decompose()
    
    for text_node in soup.find_all(text=re.compile(r'\bmeth\b')):
        if text_node.parent.name not in ['code', 'span']:
            text_node.replace_with(text_node.replace('meth', ''))

##############################################################################
#                       PROMPT FOR ADVANCED SETTINGS                         #
##############################################################################

def prompt_advanced_settings():
    """
    Prompts user for advanced settings:
      - Output format (HTML, Markdown, or JSON)
      - Keep images/links/emphasis
      - (If Markdown) Generate table of contents
      - (No overwrite choice; always suffix if file exists)
    """
    output_format = questionary.select(
        "Choose output format:",
        choices=["HTML", "Markdown", "JSON"],
        default="Markdown"
    ).ask()

    keep_images = questionary.confirm(
        "Keep images in the output text?",
        default=True
    ).ask()

    keep_links = questionary.confirm(
        "Keep links in the output text?",
        default=True
    ).ask()

    keep_emphasis = questionary.confirm(
        "Preserve text emphasis (bold/italic)?",
        default=True
    ).ask()

    generate_toc = False
    if output_format == "Markdown":
        generate_toc = questionary.confirm(
            "Generate a table of contents from headings?",
            default=False
        ).ask()

    custom_filename = questionary.confirm(
        "Do you want to specify your own output filename (instead of automatic naming)?",
        default=False
    ).ask()

    output_filename = None
    if custom_filename:
        default_ext = {
            "HTML": ".html",
            "Markdown": ".md",
            "JSON": ".json"
        }[output_format]
        output_filename = questionary.text(
            f"Enter the desired output filename (e.g., my_file{default_ext}):"
        ).ask()

    return {
        "output_format": output_format,
        "keep_images": keep_images,
        "keep_links": keep_links,
        "keep_emphasis": keep_emphasis,
        "generate_toc": generate_toc,
        "custom_filename": custom_filename,
        "output_filename": output_filename,
    }

##############################################################################
#                            CONVERSION LOGIC                                #
##############################################################################

def convert_html_to_markdown(html_content, keep_links=True, keep_images=True, keep_emphasis=True):
    """
    Converts main content to Markdown, removing doc symbols.
    """
    main_html = get_main_content(html_content)
    soup = BeautifulSoup(main_html, "html.parser")
    remove_doc_symbol_elements(soup)

    converter = html2text.HTML2Text()
    converter.ignore_links = not keep_links
    converter.ignore_images = not keep_images
    converter.ignore_emphasis = not keep_emphasis
    converter.code_block_style = 'fenced'
    
    md_text = converter.handle(str(soup))
    md_text = re.sub(r'\n{3,}', '\n\n', md_text)
    md_text = re.sub(r'`{3,}', '```', md_text)
    return md_text.strip()

def convert_html_only_main(html_content):
    """
    Cleans raw HTML to only main content, returning final HTML string.
    """
    main_html = get_main_content(html_content)
    soup = BeautifulSoup(main_html, "html.parser")
    remove_doc_symbol_elements(soup)
    return str(soup)

def generate_table_of_contents(markdown_text):
    """
    Inserts a ToC near the top of Markdown if headings exist.
    """
    headings = re.findall(r'^(#+)\s+(.*)', markdown_text, flags=re.MULTILINE)
    if not headings:
        return markdown_text

    toc_lines = ["## Table of Contents\n"]
    for heading in headings:
        level = len(heading[0])
        title = heading[1].strip()
        anchor = re.sub(r'[^\w\s-]', '', title.lower()).replace(' ', '-')
        indent = "  " * (level - 1)
        toc_lines.append(f"{indent}- [{title}](#{anchor})")

    return "\n".join(toc_lines) + "\n\n" + markdown_text

def generate_filename_from_url(url, extension="md"):
    """
    Creates a filename based on domain + timestamp + extension
    (e.g. example.com-20241223-104512.md)
    """
    parsed = urlparse(url)
    domain = parsed.netloc if parsed.netloc else "domain"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{domain}-{stamp}.{extension}"

def generate_doc_header(title):
    """
    Simple front-matter style header for Markdown files.
    """
    return f"""---
title: {title}
type: reference
---

"""

##############################################################################
#                     FILE WRITING (ALWAYS APPEND SUFFIX)                    #
##############################################################################

def handle_file_write(final_text, output_dir, output_format, url, custom_filename=None):
    """
    Writes final_text to a file in the given output format:
      - HTML => .html
      - Markdown => .md (with front-matter)
      - JSON => .json
    ALWAYS appends a unique suffix if file exists, printing a warning.
    Returns the final file path.
    """
    extension = {
        "HTML": "html",
        "Markdown": "md",
        "JSON": "json"
    }[output_format]

    if custom_filename:
        base_filename = custom_filename
    else:
        base_filename = generate_filename_from_url(url, extension=extension)

    output_path = os.path.join(output_dir, base_filename)

    # Prepare final content
    if output_format == "Markdown":
        title = os.path.splitext(base_filename)[0].replace('-', ' ').title()
        header = generate_doc_header(title)
        final_output_data = header + final_text

    elif output_format == "HTML":
        final_output_data = final_text

    else:  # JSON
        final_output_data = {
            "title": os.path.splitext(base_filename)[0],
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "content": final_text
        }

    # Always append suffix if file already exists
    file_root, file_ext = os.path.splitext(output_path)
    if os.path.exists(output_path):
        console.print(f"[yellow]File '{output_path}' already exists. Appending suffix...[/yellow]")
    counter = 1
    while os.path.exists(output_path):
        output_path = f"{file_root}_{counter}{file_ext}"
        counter += 1

    # Write file
    if output_format == "Markdown":
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_output_data)
    elif output_format == "HTML":
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_output_data)
    else:  # JSON
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output_data, f, indent=2)

    return output_path

##############################################################################
#                    PUBLIC-FACING CONVERSION FUNCTIONS                      #
##############################################################################

def convert_and_save_page(
    url,
    output_dir,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
):
    """
    Fetches a single page and converts to the chosen output_format.
    - output_format in ["HTML", "Markdown", "JSON"]
    - If Markdown with generate_toc=True, inserts a table of contents.
    Returns the final file path or None on error.
    """
    try:
        html_content = fetch_html(url)
    except (ValueError, RuntimeError) as e:
        console.print(f"[red]{e}[/red]")
        return None

    if output_format == "Markdown":
        md_text = convert_html_to_markdown(html_content, keep_links, keep_images, keep_emphasis)
        if generate_toc:
            md_text = generate_table_of_contents(md_text)
        final_text = md_text

    elif output_format == "HTML":
        final_text = convert_html_only_main(html_content)

    else:  # JSON
        md_text = convert_html_to_markdown(html_content, keep_links, keep_images, keep_emphasis)
        final_text = md_text

    output_path = handle_file_write(
        final_text,
        output_dir,
        output_format,
        url,
        custom_filename=custom_filename
    )
    return output_path

##############################################################################
#                        CRAWLING & SITE MAP LOGIC                           #
##############################################################################

def scrape_links(base_url, html_content):
    """
    Finds all same-domain links in html_content; returns a set of absolute URLs.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    base_domain = urlparse(base_url).netloc
    links = set()

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        absolute_link = urljoin(base_url, href)
        parsed_link = urlparse(absolute_link)
        # same domain, skip #fragments
        if parsed_link.scheme in ['http', 'https'] and parsed_link.netloc == base_domain:
            if not parsed_link.fragment:
                links.add(absolute_link)

    return links

def crawl_links(
    base_url,
    max_depth,
    output_dir,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
):
    """
    Recursively fetches & converts all same-domain pages up to max_depth.
    Each page is written in the chosen format.
    """
    visited = set()
    queue = deque([(base_url, 0)])

    while queue:
        current_url, depth = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        console.print(f"[bold cyan]Crawling (depth={depth}):[/bold cyan] {current_url}")
        convert_and_save_page(
            current_url,
            output_dir,
            output_format=output_format,
            keep_images=keep_images,
            keep_links=keep_links,
            keep_emphasis=keep_emphasis,
            generate_toc=generate_toc,
            custom_filename=custom_filename
        )

        if depth < max_depth:
            try:
                html_content = fetch_html(current_url)
                child_links = scrape_links(current_url, html_content)
                for link in child_links:
                    if link not in visited:
                        queue.append((link, depth + 1))
            except (ValueError, RuntimeError) as e:
                console.print(f"[red]{e}[/red]")

def build_markdown_site_map(base_url, adjacency):
    lines = [f"# Site Map for {base_url}\n"]
    visited_nodes = set()

    def build_submap(url, level=0):
        if url in visited_nodes:
            return
        visited_nodes.add(url)

        indent = "  " * level
        lines.append(f"{indent}- {url}")

        children = sorted(adjacency.get(url, []))
        for child_url in children:
            build_submap(child_url, level + 1)

    build_submap(base_url)
    return "\n".join(lines)

def build_html_site_map(base_url, adjacency):
    visited_nodes = set()
    lines = [f"<h1>Site Map for {base_url}</h1>", "<ul>"]

    def build_submap(url):
        if url in visited_nodes:
            return
        visited_nodes.add(url)

        lines.append(f"<li>{url}")
        children = sorted(adjacency.get(url, []))
        if children:
            lines.append("<ul>")
            for child_url in children:
                build_submap(child_url)
            lines.append("</ul>")
        lines.append("</li>")

    build_submap(base_url)
    lines.append("</ul>")
    return "\n".join(lines)

def map_site(
    base_url,
    output_dir,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
):
    """
    Crawls entire same-domain site (no depth limit), building a site map in
    the chosen format: .html, .md, or .json
    """
    console.print(f"[bold green]Building site map for:[/bold green] {base_url}")
    visited = set()
    adjacency = {}
    queue = deque([base_url])

    while queue:
        current_url = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        try:
            html_content = fetch_html(current_url)
        except (ValueError, RuntimeError) as e:
            console.print(f"[red]{e}[/red]")
            continue

        children = scrape_links(current_url, html_content)
        adjacency[current_url] = children
        for child in children:
            if child not in visited:
                queue.append(child)

    if output_format == "Markdown":
        site_map_content = build_markdown_site_map(base_url, adjacency)
        map_filename = os.path.join(output_dir, "site_map.md")

        file_root, file_ext = os.path.splitext(map_filename)
        if os.path.exists(map_filename):
            console.print(f"[yellow]File '{map_filename}' already exists. Appending suffix...[/yellow]")
        counter = 1
        while os.path.exists(map_filename):
            map_filename = f"{file_root}_{counter}{file_ext}"
            counter += 1

        with open(map_filename, "w", encoding="utf-8") as f:
            f.write(site_map_content)
        console.print(f"[bold yellow]Site map has been saved to:[/bold yellow] {map_filename}")

    elif output_format == "HTML":
        site_map_content = build_html_site_map(base_url, adjacency)
        map_filename = os.path.join(output_dir, "site_map.html")

        file_root, file_ext = os.path.splitext(map_filename)
        if os.path.exists(map_filename):
            console.print(f"[yellow]File '{map_filename}' already exists. Appending suffix...[/yellow]")
        counter = 1
        while os.path.exists(map_filename):
            map_filename = f"{file_root}_{counter}{file_ext}"
            counter += 1

        with open(map_filename, "w", encoding="utf-8") as f:
            f.write(site_map_content)
        console.print(f"[bold yellow]HTML site map has been saved to:[/bold yellow] {map_filename}")

    else:  # JSON
        map_filename = os.path.join(output_dir, "site_map.json")

        file_root, file_ext = os.path.splitext(map_filename)
        if os.path.exists(map_filename):
            console.print(f"[yellow]File '{map_filename}' already exists. Appending suffix...[/yellow]")
        counter = 1
        while os.path.exists(map_filename):
            map_filename = f"{file_root}_{counter}{file_ext}"
            counter += 1

        with open(map_filename, "w", encoding="utf-8") as f:
            json.dump(adjacency, f, indent=2)
        console.print(f"[bold yellow]JSON site map has been saved to:[/bold yellow] {map_filename}")

##############################################################################
#                 PUBLIC-FACING WRAPPER FUNCTIONS (FEATURES)                #
##############################################################################

def do_single_page_conversion(
    url,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
):
    """
    Single Page Conversion (no subdirectory). 
    Returns the final file path or None if error.
    """
    output_dir = create_output_directory()  # "output"
    return convert_and_save_page(
        url=url,
        output_dir=output_dir,
        output_format=output_format,
        keep_images=keep_images,
        keep_links=keep_links,
        keep_emphasis=keep_emphasis,
        generate_toc=generate_toc,
        custom_filename=custom_filename
    )

def do_recursive_crawling(
    url,
    max_depth=1,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
):
    """
    Recursive Crawling (always creates "recursive_crawl" subdirectory).
    """
    output_dir = create_output_directory("recursive_crawl")
    crawl_links(
        base_url=url,
        max_depth=max_depth,
        output_dir=output_dir,
        output_format=output_format,
        keep_images=keep_images,
        keep_links=keep_links,
        keep_emphasis=keep_emphasis,
        generate_toc=generate_toc,
        custom_filename=custom_filename
    )

def do_map_only(
    url,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
):
    """
    Map Only (always creates "site_map" subdirectory).
    """
    output_dir = create_output_directory("site_map")
    map_site(
        base_url=url,
        output_dir=output_dir,
        output_format=output_format,
        keep_images=keep_images,
        keep_links=keep_links,
        keep_emphasis=keep_emphasis,
        generate_toc=generate_toc,
        custom_filename=custom_filename
    )

def do_recursive_crawling_and_map(
    url,
    max_depth=1,
    output_format="Markdown",
    keep_images=True,
    keep_links=True,
    keep_emphasis=True,
    generate_toc=False,
    custom_filename=None
):
    """
    Recursive Crawling & then build a site map (always "crawl_and_map" subdir).
    """
    output_dir = create_output_directory("crawl_and_map")
    crawl_links(
        base_url=url,
        max_depth=max_depth,
        output_dir=output_dir,
        output_format=output_format,
        keep_images=keep_images,
        keep_links=keep_links,
        keep_emphasis=keep_emphasis,
        generate_toc=generate_toc,
        custom_filename=custom_filename
    )
    map_site(
        base_url=url,
        output_dir=output_dir,
        output_format=output_format,
        keep_images=keep_images,
        keep_links=keep_links,
        keep_emphasis=keep_emphasis,
        generate_toc=generate_toc,
        custom_filename=custom_filename
    )

##############################################################################
#                           LLM FUNCTION CALL                                #
##############################################################################

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
):
    """
    A universal function that an LLM can call with JSON parameters.
    The function_name must be one of:
      - "do_single_page_conversion"
      - "do_recursive_crawling"
      - "do_map_only"
      - "do_recursive_crawling_and_map"
    The other parameters match the script's typical usage.
    Returns whatever the underlying function returns (often None or a file path).
    """
    if function_name == "do_single_page_conversion":
        return do_single_page_conversion(
            url=url,
            output_format=output_format,
            keep_images=keep_images,
            keep_links=keep_links,
            keep_emphasis=keep_emphasis,
            generate_toc=generate_toc,
            custom_filename=custom_filename
        )
    elif function_name == "do_recursive_crawling":
        return do_recursive_crawling(
            url=url,
            max_depth=max_depth,
            output_format=output_format,
            keep_images=keep_images,
            keep_links=keep_links,
            keep_emphasis=keep_emphasis,
            generate_toc=generate_toc,
            custom_filename=custom_filename
        )
    elif function_name == "do_map_only":
        return do_map_only(
            url=url,
            output_format=output_format,
            keep_images=keep_images,
            keep_links=keep_links,
            keep_emphasis=keep_emphasis,
            generate_toc=generate_toc,
            custom_filename=custom_filename
        )
    elif function_name == "do_recursive_crawling_and_map":
        return do_recursive_crawling_and_map(
            url=url,
            max_depth=max_depth,
            output_format=output_format,
            keep_images=keep_images,
            keep_links=keep_links,
            keep_emphasis=keep_emphasis,
            generate_toc=generate_toc,
            custom_filename=custom_filename
        )
    else:
        console.print(f"[red]Unknown function_name: {function_name}[/red]")
        return None

##############################################################################
#                        INTERACTIVE CLI (MAIN MENU)                         #
##############################################################################

def single_page_conversion_cli():
    """
    CLI flow for single-page conversion (option 1).
    """
    url = questionary.text(
        "Enter the URL for single-page conversion (or press Enter to cancel):"
    ).ask()
    if not url:
        console.print("[yellow]No URL provided, returning to main menu...[/yellow]")
        return
    settings = prompt_advanced_settings()

    spinner = Spinner("dots", text="Converting single page...")
    with console.status(spinner):
        do_single_page_conversion(
            url=url,
            output_format=settings["output_format"],
            keep_images=settings["keep_images"],
            keep_links=settings["keep_links"],
            keep_emphasis=settings["keep_emphasis"],
            generate_toc=settings["generate_toc"],
            custom_filename=settings["output_filename"] if settings["custom_filename"] else None
        )

def recursive_crawling_cli():
    """
    CLI flow for recursive crawling (option 2).
    """
    url = questionary.text(
        "Enter the base URL to recursively crawl (or press Enter to cancel):"
    ).ask()
    if not url:
        console.print("[yellow]No URL provided, returning to main menu...[/yellow]")
        return
    settings = prompt_advanced_settings()

    max_depth = questionary.text(
        "Enter max recursion depth (e.g., 1, 2, 3...). [Default=1]",
        default="1"
    ).ask()
    try:
        max_depth_int = int(max_depth)
    except ValueError:
        console.print("[red]Invalid depth. Defaulting to 1.[/red]")
        max_depth_int = 1

    do_recursive_crawling(
        url=url,
        max_depth=max_depth_int,
        output_format=settings["output_format"],
        keep_images=settings["keep_images"],
        keep_links=settings["keep_links"],
        keep_emphasis=settings["keep_emphasis"],
        generate_toc=settings["generate_toc"],
        custom_filename=settings["output_filename"] if settings["custom_filename"] else None
    )

def map_only_cli():
    """
    CLI flow for map only (option 3).
    """
    url = questionary.text(
        "Enter the base URL to map (or press Enter to cancel):"
    ).ask()
    if not url:
        console.print("[yellow]No URL provided, returning to main menu...[/yellow]")
        return
    settings = prompt_advanced_settings()

    do_map_only(
        url=url,
        output_format=settings["output_format"],
        keep_images=settings["keep_images"],
        keep_links=settings["keep_links"],
        keep_emphasis=settings["keep_emphasis"],
        generate_toc=settings["generate_toc"],
        custom_filename=settings["output_filename"] if settings["custom_filename"] else None
    )

def recursive_crawling_and_map_cli():
    """
    CLI flow for recursive crawling & map (option 4).
    """
    url = questionary.text(
        "Enter the base URL (or press Enter to cancel):"
    ).ask()
    if not url:
        console.print("[yellow]No URL provided, returning to main menu...[/yellow]")
        return
    settings = prompt_advanced_settings()

    max_depth = questionary.text(
        "Enter max recursion depth (e.g., 1, 2, 3...). [Default=1]",
        default="1"
    ).ask()
    try:
        max_depth_int = int(max_depth)
    except ValueError:
        console.print("[red]Invalid depth. Defaulting to 1.[/red]")
        max_depth_int = 1

    do_recursive_crawling_and_map(
        url=url,
        max_depth=max_depth_int,
        output_format=settings["output_format"],
        keep_images=settings["keep_images"],
        keep_links=settings["keep_links"],
        keep_emphasis=settings["keep_emphasis"],
        generate_toc=settings["generate_toc"],
        custom_filename=settings["output_filename"] if settings["custom_filename"] else None
    )

def main_menu():
    """
    Interactive main menu. 
    Allows user to choose 1 of 4 operations, or exit.
    """
    while True:
        choice = questionary.select(
            "MAIN MENU - Choose an action:",
            choices=[
                "1. Single Page Conversion",
                "2. Recursive Crawling",
                "3. Map",
                "4. Recursive Crawling & Map",
                "Exit"
            ]
        ).ask()

        if choice.startswith("1"):
            single_page_conversion_cli()
        elif choice.startswith("2"):
            recursive_crawling_cli()
        elif choice.startswith("3"):
            map_only_cli()
        elif choice.startswith("4"):
            recursive_crawling_and_map_cli()
        elif choice == "Exit":
            console.print("[bold cyan]Goodbye![/bold cyan]")
            break

def main():
    print_banner()
    main_menu()

if __name__ == "__main__":
    main()
