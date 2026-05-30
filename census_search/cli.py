"""
Census Search CLI

Links a person across Irish National Archives census records (1926, 1911, 1901)
using a known birth year, then optionally expands to the full household.

Usage:
    census-search link Corrigan --first-name James --county Kilkenny --birth-year 1882 --sex Male
    census-search link Corrigan --first-name James --county Kilkenny --birth-year 1882 --expand
    census-search browse --county Dublin
"""

from __future__ import annotations

import asyncio

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from census_search.models import CensusRecord, SearchResult
from census_search.searchers.census_1901_1911 import Census1901_1911Searcher
from census_search.searchers.census_1926 import Census1926Searcher

app = typer.Typer(
    name="census-search",
    help="Search Irish National Archives census records (1926 → 1911 → 1901).",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record_table(records: list[CensusRecord], title: str) -> Table:
    table = Table(title=title, box=box.SIMPLE_HEAD, show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Surname", style="bold")
    table.add_column("First Name")
    table.add_column("Age", justify="right")
    table.add_column("Sex")
    table.add_column("County")
    table.add_column("Townland / Street")
    table.add_column("DED")
    table.add_column("Occupation")
    table.add_column("Birthplace")

    for i, r in enumerate(records, 1):
        table.add_row(
            str(i),
            r.surname or "—",
            r.first_name or "—",
            str(r.age) if r.age is not None else "—",
            r.sex or "—",
            r.county or "—",
            r.townland_street or "—",
            r.ded or "—",
            r.occupation or "—",
            r.birthplace or "—",
        )
    return table


def _record_leaf(r: CensusRecord) -> str:
    """Compact single-line description of a census record for tree nodes."""
    parts: list[str] = [f"[bold]{r.full_name}[/bold]"]
    if r.age is not None:
        parts.append(f"age {r.age}")
    location = ", ".join(filter(None, [r.townland_street, r.ded, r.county]))
    if location:
        parts.append(location)
    if r.occupation:
        parts.append(f"[dim]({r.occupation})[/dim]")
    return "  ".join(parts)


def _person_tree(
    label: str,
    results: list[SearchResult],
    all_years: list[int],
) -> Tree:
    """Tree showing a person across census years, with a branch per year."""
    tree = Tree(label)
    by_year = {r.census_year: r for r in results}
    for year in sorted(all_years):
        result = by_year.get(year)
        year_tag = f"[yellow]{year}[/yellow]"
        if result and result.records:
            branch = tree.add(f"{year_tag}  {_record_leaf(result.records[0])}")
            if result.records[0].detail_url:
                branch.add(f"[dim][link={result.records[0].detail_url}]{result.records[0].detail_url}[/link][/dim]")
        else:
            tree.add(f"{year_tag}  [dim]no match[/dim]")
    return tree


def _household_tree(
    members: list[CensusRecord],
    location: str,
    member_results: dict[int, list[SearchResult]] | None = None,
) -> Tree:
    """Tree showing household members, optionally with their 1911/1901 matches."""
    root = Tree(f"[bold]🏠 Household[/bold]  [dim]{location}[/dim]")
    for i, m in enumerate(members):
        rel = f" [dim]({m.relationship})[/dim]" if m.relationship else ""
        age = f"  age {m.age}" if m.age is not None else ""
        sex = f"  {m.sex}" if m.sex else ""
        member_label = f"[cyan]{m.full_name}[/cyan]{rel}{sex}{age}"

        if member_results is not None and m.age is not None:
            branch = root.add(member_label)
            old = member_results.get(i, [])
            matched_years = {r.census_year for r in old if r.records}
            born = m.birth_year_estimate or 0
            for year in [1911, 1901]:
                year_tag = f"[yellow]{year}[/yellow]"
                if born >= year:
                    branch.add(f"{year_tag}  [dim]not yet born[/dim]")
                elif year in matched_years:
                    rec = next(r.records[0] for r in old if r.census_year == year and r.records)
                    branch.add(f"{year_tag}  {_record_leaf(rec)}")
                else:
                    branch.add(f"{year_tag}  [dim]no match[/dim]")
        else:
            root.add(member_label)
    return root


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def link(
    surname: str = typer.Argument(..., help="Surname"),
    first_name: str = typer.Option("", "--first-name", "-f", help="First name"),
    birth_year: int = typer.Option(..., "--birth-year", "-b", help="Known or estimated birth year"),
    county: str = typer.Option("", "--county", "-c", help="County (e.g. Dublin, Cork)"),
    sex: str = typer.Option("", "--sex", "-s", help="Sex filter (Male or Female)"),
    age_tolerance: int = typer.Option(3, "--age-tolerance", help="±years for age matching (default 3)"),
    max_results: int = typer.Option(30, "--max", "-n", help="Max results per census year"),
    expand: bool = typer.Option(
        False, "--expand/--no-expand",
        help="Fetch all 1926 household members and link each to 1911 & 1901"
    ),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser headlessly"),
):
    """
    Search all three censuses (1926, 1911, 1901) for a person using a known birth year.

    When exactly one 1926 record is found, the full household is shown automatically.
    Use --expand to also link each household member back to 1911 & 1901.

    If the primary person is absent (e.g. away on military service), the closest
    surname match is used as the household address anchor.

    Examples:

    \b
      census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --sex Male
      census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --expand
    """
    asyncio.run(_do_link(
        surname=surname,
        first_name=first_name,
        birth_year=birth_year,
        county=county,
        sex=sex,
        age_tolerance=age_tolerance,
        max_results=max_results,
        expand=expand,
        headless=headless,
    ))


async def _do_link(
    surname: str,
    first_name: str,
    birth_year: int,
    county: str,
    sex: str,
    age_tolerance: int,
    max_results: int,
    expand: bool,
    headless: bool,
):
    all_results: list[SearchResult] = []
    age_1926 = 1926 - birth_year
    household_members: list[CensusRecord] = []

    async with Census1926Searcher(headless=headless) as s:
        with console.status("Searching…"):
            raw = await s.search(surname=surname, county=county, sex=sex, max_results=500)

        matched = [
            rec for rec in raw.records
            if (not first_name or (rec.first_name or "").lower() == first_name.lower())
            and (rec.age is None or abs(rec.age - age_1926) <= age_tolerance)
        ]
        aged = [rec for rec in matched if rec.age is not None]
        if aged:
            matched = aged
        all_results.append(SearchResult(
            census_year=raw.census_year, total=len(matched),
            records=matched, search_url=raw.search_url,
        ))

        if len(matched) == 1 or expand:
            anchor = (matched or raw.records or [None])[0]
            if anchor and (anchor.townland_street or anchor.ded):
                with console.status("Fetching household…"):
                    hw = await s.search(
                        county=anchor.county or county,
                        townland=anchor.townland_street,
                        ded=anchor.ded,
                        max_results=200,
                    )
                if anchor.form_id:
                    household_members = [r for r in hw.records if r.form_id == anchor.form_id]
                else:
                    tl = (anchor.townland_street or "").strip().lower()
                    household_members = [
                        r for r in hw.records
                        if tl and (r.townland_street or "").strip().lower() == tl
                    ] or hw.records
                # Exclude the primary person — they're already shown in the main tree
                household_members = [
                    r for r in household_members
                    if not (
                        r.first_name.lower() == (anchor.first_name or "").lower()
                        and r.surname.lower() == (anchor.surname or "").lower()
                        and r.age == anchor.age
                    )
                ]

    async with Census1901_1911Searcher() as s:
        with console.status("Searching 1911 & 1901…"):
            old = await s.search_both_years(
                surname=surname,
                first_name=first_name,
                county=county,
                sex=sex,
                birth_year=birth_year,
                age_tolerance=age_tolerance,
                max_results=max_results,
            )
        for r in old:
            all_results.append(r)

    # Primary person tree
    label = (
        f"[bold cyan]{first_name} {surname}[/bold cyan] [dim](born ~{birth_year})[/dim]"
    )
    console.print()
    console.print(_person_tree(label, all_results, [1926, 1911, 1901]))

    if not household_members:
        return

    location = ", ".join(filter(None, [
        household_members[0].townland_street,
        household_members[0].ded,
        household_members[0].county,
    ]))

    if not expand:
        console.print(_household_tree(household_members, location))
        return

    # Collect 1911/1901 results for each household member before rendering
    member_results: dict[int, list[SearchResult]] = {}
    async with Census1901_1911Searcher() as s:
        for i, member in enumerate(household_members):
            born = member.birth_year_estimate
            if born is None:
                continue
            years_to_search = [y for y in [1911, 1901] if born < y]
            if not years_to_search:
                continue
            with console.status(f"  {member.full_name}…"):
                res = await s.search_both_years(
                    surname=member.surname,
                    first_name=member.first_name,
                    county=member.county or county,
                    sex=member.sex,
                    birth_year=born,
                    age_tolerance=age_tolerance,
                    max_results=max_results,
                )
            member_results[i] = [r for r in res if r.census_year in years_to_search]

    console.print(_household_tree(household_members, location, member_results))


@app.command()
def browse(
    county: str = typer.Option("", "--county", "-c", help="County to browse"),
    ded: str = typer.Option("", "--ded", "-d", help="DED to browse"),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
):
    """Browse 1926 census records by county and DED (no name required)."""
    asyncio.run(_do_browse(county=county, ded=ded, headless=headless))


async def _do_browse(county: str, ded: str, headless: bool):
    console.print("\n[bold]📂 Browsing 1926 census[/bold]"
                  + (f" — [yellow]{county}[/yellow]" if county else ""))

    async with Census1926Searcher(headless=headless) as searcher:
        with console.status("Loading…"):
            result = await searcher.search(county=county, ded=ded, max_results=50)

    if not result.records:
        console.print("[red]No results found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[green]{result.total} record(s)[/green]")
    console.print(_record_table(result.records, f"1926 Census — {county or 'All Counties'}"))


if __name__ == "__main__":
    app()
