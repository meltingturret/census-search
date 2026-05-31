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
from importlib.metadata import version as _pkg_version
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from census_search.linker import best_scored_match
from census_search.models import CensusRecord, SearchResult
from census_search.searchers.census_1901_1911 import Census1901_1911Searcher
from census_search.searchers.census_1926 import Census1926Searcher

app = typer.Typer(
    name="census-search",
    help="Search Irish National Archives census records (1926 → 1911 → 1901).",
    invoke_without_command=True,
)
console = Console()


def _version_callback(value: bool):
    if value:
        try:
            v = _pkg_version("census-search")
        except Exception:
            v = "unknown"
        typer.echo(f"census-search {v}")
        raise typer.Exit(0)


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V",
        callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
):
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
            r.birthplace or "—",
        )
    return table


def _best_match(anchor: CensusRecord, result: SearchResult) -> tuple[CensusRecord, float] | None:
    """Return (best_record, confidence_0_to_1) from a search result, or None."""
    return best_scored_match(anchor, result)


def _person_table(
    anchor: CensusRecord,
    results: list[SearchResult],
    all_years: list[int],
) -> Table:
    """Table showing a person across census years — one row per year."""
    table = Table(box=box.SIMPLE_HEAD, show_lines=False)
    table.add_column("Year", style="yellow", width=6)
    table.add_column("Surname", style="bold")
    table.add_column("First Name")
    table.add_column("Age", justify="right")
    table.add_column("Sex")
    table.add_column("County")
    table.add_column("Townland / Street")
    table.add_column("DED")
    table.add_column("Birthplace")
    table.add_column("Match", justify="right")

    by_year = {r.census_year: r for r in results}
    for year in sorted(all_years):
        result = by_year.get(year)
        if year == anchor.census_year:
            if result and result.records:
                r = anchor
                table.add_row(
                    str(year), r.surname or "—", r.first_name or "—",
                    str(r.age) if r.age is not None else "—",
                    r.sex or "—", r.county or "—",
                    r.townland_street or "—", r.ded or "—",
                    r.birthplace or "—", "—",
                )
            else:
                table.add_row(str(year), *["—"] * 8, "[dim]no match[/dim]")
        elif result:
            match = _best_match(anchor, result)
            if match:
                r, conf = match
                conf_pct = int(conf * 100)
                if conf_pct >= 80:
                    conf_str = f"[green]{conf_pct}%[/green]"
                elif conf_pct >= 55:
                    conf_str = f"[yellow]{conf_pct}%[/yellow]"
                else:
                    conf_str = f"[dim]{conf_pct}%[/dim]"
                table.add_row(
                    str(year), r.surname or "—", r.first_name or "—",
                    str(r.age) if r.age is not None else "—",
                    r.sex or "—", r.county or "—",
                    r.townland_street or "—", r.ded or "—",
                    r.birthplace or "—", conf_str,
                )
            else:
                table.add_row(str(year), *["—"] * 8, "[dim]no match[/dim]")
        else:
            table.add_row(str(year), *["—"] * 8, "[dim]no match[/dim]")
    return table


def _household_table(members: list[CensusRecord], location: str) -> Table:
    table = Table(box=box.SIMPLE_HEAD, show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Surname", style="bold")
    table.add_column("First Name")
    table.add_column("Age", justify="right")
    table.add_column("Sex")
    table.add_column("Relationship")
    table.add_column("County")
    table.add_column("Townland / Street")
    table.add_column("DED")
    table.add_column("Birthplace")
    for i, r in enumerate(members, 1):
        table.add_row(
            str(i),
            r.surname or "—",
            r.first_name or "—",
            str(r.age) if r.age is not None else "—",
            r.sex or "—",
            r.relationship or "—",
            r.county or "—",
            r.townland_street or "—",
            r.ded or "—",
            r.birthplace or "—",
        )
    return table



# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def link(
    surname: str = typer.Argument(..., help="Surname"),
    first_name: str = typer.Option("", "--first-name", "-f", help="First name"),
    birth_year: Optional[int] = typer.Option(None, "--birth-year", "-b", help="Birth year (omit to browse all ages)"),
    county: str = typer.Option("", "--county", "-c", help="County (e.g. Dublin, Cork)"),
    sex: str = typer.Option("", "--sex", "-s", help="Sex filter (Male or Female)"),
    age_tolerance: int = typer.Option(3, "--age-tolerance", help="±years for age matching"),
    age_before: Optional[int] = typer.Option(None, "--age-before", help="Years older the person may be"),
    age_after: Optional[int] = typer.Option(None, "--age-after", help="Years younger the person may be"),
    max_results: int = typer.Option(30, "--max", "-n", help="Max results per census year"),
    expand: bool = typer.Option(
        False, "--expand/--no-expand",
        help="Fetch all 1926 household members and link each to 1911 & 1901"
    ),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser headlessly"),
):
    """
    Search all three censuses (1926, 1911, 1901) for a person.

    --birth-year is optional. Without it, all age matches are returned from 1926
    only (no 1911/1901 linking). With it, records are age-filtered and linked
    across all three years.

    When exactly one 1926 record is found, the full household is shown automatically.
    Use --expand to also link each household member back to 1911 & 1901.

    Examples:

    \b
      census-search link Corrigan --county Kilkenny --sex Male
      census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --sex Male
      census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --expand
      census-search link Corrigan --first-name Joseph --birth-year 1917 --county Kilkenny --age-before 5 --age-after 10
    """
    asyncio.run(_do_link(
        surname=surname,
        first_name=first_name,
        birth_year=birth_year,
        county=county,
        sex=sex,
        age_tolerance=age_tolerance,
        age_before=age_before,
        age_after=age_after,
        max_results=max_results,
        expand=expand,
        headless=headless,
    ))


async def _do_link(
    surname: str,
    first_name: str,
    birth_year: Optional[int],
    county: str,
    sex: str,
    age_tolerance: int,
    age_before: Optional[int],
    age_after: Optional[int],
    max_results: int,
    expand: bool,
    headless: bool,
):
    # Resolve asymmetric tolerance: --age-before/--age-after override --age-tolerance
    tol_before = age_before if age_before is not None else age_tolerance  # person could be older
    tol_after = age_after if age_after is not None else age_tolerance     # person could be younger

    all_results: list[SearchResult] = []
    age_1926 = (1926 - birth_year) if birth_year else None
    household_members: list[CensusRecord] = []

    # Support comma-separated counties, e.g. --county "Kilkenny,Tipperary"
    counties = [c.strip() for c in county.split(",") if c.strip()] if county else []
    # Support comma-separated first names, e.g. --first-name "Joe,Joseph,Jos"
    first_names = [n.strip() for n in first_name.split(",") if n.strip()] if first_name else []

    async with Census1926Searcher(headless=headless) as s:
        with console.status("Searching…"):
            search_counties = counties if counties else ([county] if county else [""])
            all_raw: list[CensusRecord] = []
            for c in search_counties:
                r = await s.search(surname=surname, county=c, sex=sex, max_results=500)
                all_raw.extend(r.records)
            raw_url = f"multi-county: {', '.join(counties)}" if counties else ""
            seen: set[tuple] = set()
            deduped_raw: list[CensusRecord] = []
            for rec in all_raw:
                key = (rec.surname.lower(), rec.first_name.lower(), rec.age, rec.county.lower())
                if key not in seen:
                    seen.add(key)
                    deduped_raw.append(rec)
            raw = SearchResult(census_year=1926, total=len(deduped_raw), records=deduped_raw, search_url=raw_url)

        matched = [
            rec for rec in raw.records
            if (not first_names or (rec.first_name or "").lower() in {n.lower() for n in first_names})
            and (not sex or not rec.sex or rec.sex.lower().startswith(sex.lower()[0]))
            and (age_1926 is None or rec.age is None
                 or (age_1926 - tol_before) <= rec.age <= (age_1926 + tol_after))
        ]
        if age_1926 is not None:
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
                # Exclude the primary person — they're already shown in the main tree.
                # Match by name; if both records have an age, also require it to be
                # within age_tolerance so a same-named child isn't mistakenly dropped.
                def _is_primary_person(r: CensusRecord) -> bool:
                    if (r.first_name or "").lower() != (anchor.first_name or "").lower():
                        return False
                    if (r.surname or "").lower() != (anchor.surname or "").lower():
                        return False
                    if r.age is not None and anchor.age is not None:
                        return (anchor.age - tol_before) <= r.age <= (anchor.age + tol_after)
                    return True  # one or both ages unknown — treat as same person

                household_members = [r for r in household_members if not _is_primary_person(r)]

    if birth_year:
        async with Census1901_1911Searcher() as s:
            with console.status("Searching 1911 & 1901…"):
                # Sex is excluded — the 1901/1911 API uses different sex codes than 1926;
                # name + age window is specific enough without it
                old = await s.search_both_years(
                    surname=surname,
                    first_names=first_names,
                    first_name=first_names[0] if len(first_names) == 1 else "",
                    counties=counties or ([county] if county else []),
                    birth_year=birth_year,
                    age_before=tol_before,
                    age_after=tol_after,
                    max_results=max_results,
                )
            for r in old:
                all_results.append(r)

    name_label = f"{' / '.join(first_names) if first_names else ''} {surname}".strip()

    # No birth year — always show a results table regardless of match count
    if not birth_year:
        console.print()
        hint = "[dim]add --birth-year to link across 1911 & 1901[/dim]"
        count_label = f"[dim]{len(matched)} result(s)[/dim]" if matched else "[dim]no results[/dim]"
        console.print(f"[bold cyan]{name_label}[/bold cyan]  {count_label}  {hint}")
        if matched:
            console.print(_record_table(matched, ""))
        return

    # Use the 1926 match as anchor for cross-year matching; fall back to a synthetic record
    anchor_first = first_names[0] if first_names else ""
    anchor_1926 = matched[0] if matched else CensusRecord(
        census_year=1926, surname=surname, first_name=anchor_first, age=age_1926
    )
    if birth_year:
        if tol_before == tol_after:
            birth_label = f"  [dim](born ~{birth_year} ±{tol_before}yr)[/dim]"
        else:
            birth_label = f"  [dim](born ~{birth_year} -{tol_before}/+{tol_after}yr)[/dim]"
    else:
        birth_label = ""
    display_years = [1926, 1911, 1901] if birth_year else [1926]
    console.print()
    console.print(f"[bold cyan]{name_label}[/bold cyan]{birth_label}")
    console.print(_person_table(anchor_1926, all_results, display_years))

    if not household_members:
        return

    location = ", ".join(filter(None, [
        household_members[0].townland_street,
        household_members[0].ded,
        household_members[0].county,
    ]))

    console.print(f"\n[bold]Household[/bold]  [dim]{location}[/dim]")
    console.print(_household_table(household_members, location))

    if not expand:
        return

    # Collect 1911/1901 results for each household member and print per-member trees
    async with Census1901_1911Searcher() as s:
        for i, member in enumerate(household_members):
            born = member.birth_year_estimate
            if born is None:
                continue
            years_to_search = [y for y in [1911, 1901] if born < y]
            if not years_to_search:
                continue
            member_counties = ([member.county] if member.county else counties or ([county] if county else []))
            with console.status(f"  {member.full_name}…"):
                res = await s.search_both_years(
                    surname=member.surname,
                    first_name=member.first_name,
                    counties=member_counties,
                    birth_year=born,
                    age_before=tol_before,
                    age_after=tol_after,
                    max_results=max_results,
                )
            member_results = [r for r in res if r.census_year in years_to_search]
            # Build a 1926 anchor from the household member (carry relationship for scoring)
            anchor_m = CensusRecord(
                census_year=1926,
                surname=member.surname,
                first_name=member.first_name,
                age=member.age,
                sex=member.sex,
                county=member.county,
                relationship=member.relationship,
            )
            if born:
                if tol_before == tol_after:
                    born_label = f"  [dim](born ~{born} ±{tol_before}yr)[/dim]"
                else:
                    born_label = f"  [dim](born ~{born} -{tol_before}/+{tol_after}yr)[/dim]"
            else:
                born_label = ""
            console.print(f"\n[cyan]{member.full_name}[/cyan]{born_label}")
            console.print(_person_table(anchor_m, member_results, years_to_search))


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
