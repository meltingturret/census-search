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
import re
from importlib.metadata import version as _pkg_version
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from census_search.linker import best_scored_match
from census_search.models import CensusRecord, MilitaryRecord, SearchResult
from census_search.searchers.census_1821_1851 import Census1821_1851Searcher
from census_search.searchers.census_1901_1911 import Census1901_1911Searcher
from census_search.searchers.census_1926 import Census1926Searcher
from census_search.searchers.war_office import WarOfficeSearcher

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



def _filter_military_by_birth_year(
    records: list[MilitaryRecord], birth_year: int
) -> list[MilitaryRecord]:
    """Keep only records whose service dates are plausible for someone born in birth_year.

    Eligible window: birth_year + 18 (earliest enlistment age) to birth_year + 60.
    Records with unparseable dates are kept to avoid silently dropping real matches.
    """
    enlist_from = birth_year + 18
    enlist_to = birth_year + 60
    filtered = []
    for r in records:
        dates = r.dates or ""
        # Extract up to two 4-digit years from the dates string, e.g. "1914-1920"
        years = [int(y) for y in re.findall(r"\b(1[6-9]\d{2}|20\d{2})\b", dates)]
        if not years:
            filtered.append(r)  # can't determine — keep
            continue
        rec_start = min(years)
        rec_end = max(years)
        # Overlap check: service period must overlap with the person's eligible window
        if rec_end >= enlist_from and rec_start <= enlist_to:
            filtered.append(r)
    return filtered


SERVICE_SERIES = {"WO 372", "WO 97"}
PENSION_SERIES = {"PIN 82", "PIN 26"}


def _military_table(records: list[MilitaryRecord]) -> Table:
    """Service and medal records (WO 372 / WO 97)."""
    table = Table(box=box.SIMPLE_HEAD, show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Type", style="bold")
    table.add_column("Reference")
    table.add_column("Regiment")
    table.add_column("Service No", justify="right")
    table.add_column("Rank")
    table.add_column("Dates")
    table.add_column("TNA Record")
    for i, r in enumerate(records, 1):
        table.add_row(
            str(i),
            r.record_type or "—",
            r.reference or "—",
            r.regiment or "—",
            r.service_number or "—",
            r.rank or "—",
            r.dates or "—",
            r.detail_url or "—",
        )
    return table


def _pension_table(records: list[MilitaryRecord]) -> Table:
    """Dependant and pension records (PIN 82 / PIN 26)."""
    table = Table(box=box.SIMPLE_HEAD, show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Type", style="bold")
    table.add_column("Reference")
    table.add_column("Regiment / Unit")
    table.add_column("Cause of Death / Disability")
    table.add_column("Dates")
    table.add_column("TNA Record")
    for i, r in enumerate(records, 1):
        notes = r.cause_of_death or r.disability or "—"
        table.add_row(
            str(i),
            r.record_type or "—",
            r.reference or "—",
            r.regiment or "—",
            notes,
            r.dates or "—",
            r.detail_url or "—",
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
    service_number: str = typer.Option(
        "", "--service-number", "-sn",
        help="Army service number — triggers a TNA WO 372 / WO 97 military records search"
    ),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser headlessly"),
):
    """
    Search all three censuses (1926, 1911, 1901) for a person.

    --birth-year is optional. Without it, all age matches are returned from 1926
    only (no 1911/1901 linking). With it, records are age-filtered and linked
    across all three years.

    When a 1926 record is found, the full household is shown and each member
    is automatically linked back to 1911 & 1901.

    Examples:

    \b
      census-search link Corrigan --county Kilkenny --sex Male
      census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny --sex Male
      census-search link Corrigan --first-name Joseph --birth-year 1917 --county Kilkenny --age-before 5 --age-after 10
      census-search link Corrigan --first-name James --birth-year 1882 --county Kilkenny \
        --sex Male --service-number 3102

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
        service_number=service_number,
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
    service_number: str,
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

        # Auto-show household on a single match or when a service number confirms
        # the identity (even if multiple 1926 records share the same name/age).
        if len(matched) == 1 or (service_number and matched):
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

    # Military records — triggered only when a service number is supplied
    if service_number:
        async with WarOfficeSearcher() as wo:
            with console.status("Searching military records…"):
                mil_records = await wo.search(
                    surname=surname,
                    first_name=first_names[0] if first_names else "",
                    service_number=service_number,
                )
        if birth_year:
            mil_records = _filter_military_by_birth_year(mil_records, birth_year)
        service_records = [r for r in mil_records if r.series in SERVICE_SERIES]
        pension_records = [r for r in mil_records if r.series in PENSION_SERIES]
        if service_records:
            console.print("\n[bold]Military Records[/bold]  [dim]TNA WO 372 / WO 97[/dim]")
            console.print(_military_table(service_records))
        else:
            console.print("\n[dim]No service records found in WO 372 / WO 97.[/dim]")
        if pension_records:
            console.print("\n[bold]Dependants & Pensions[/bold]  [dim]TNA PIN 82 / PIN 26[/dim]")
            console.print(_pension_table(pension_records))
        else:
            console.print("[dim]No dependant or pension records found in PIN 82 / PIN 26.[/dim]")

    if not household_members:
        return

    location = ", ".join(filter(None, [
        household_members[0].townland_street,
        household_members[0].ded,
        household_members[0].county,
    ]))

    console.print(f"\n[bold]Household[/bold]  [dim]{location}[/dim]")
    console.print(_household_table(household_members, location))

    # Always link each household member back to 1911 & 1901
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
            if not any(sr.records for sr in member_results):
                continue
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
            if tol_before == tol_after:
                born_label = f"  [dim](born ~{born} ±{tol_before}yr)[/dim]"
            else:
                born_label = f"  [dim](born ~{born} -{tol_before}/+{tol_after}yr)[/dim]"
            console.print(f"\n[cyan]{member.full_name}[/cyan]{born_label}")
            console.print(_person_table(anchor_m, member_results, years_to_search))


@app.command()
def browse(
    surname: str = typer.Argument("", help="Surname to filter by (optional)"),
    county: str = typer.Option("", "--county", "-c", help="County to browse"),
    ded: str = typer.Option("", "--ded", "-d", help="DED to browse"),
    max_results: int = typer.Option(30, "--max", "-n", help="Max results to return"),
    debug: bool = typer.Option(False, "--debug", help="Print raw API record for first result"),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
):
    """Browse 1926 census records by county and/or surname."""
    asyncio.run(_do_browse(
        surname=surname, county=county, ded=ded,
        max_results=max_results, debug=debug, headless=headless,
    ))


async def _do_browse(surname: str, county: str, ded: str, max_results: int, debug: bool, headless: bool):
    label = " — ".join(filter(None, [surname or None, county or None, ded or None]))
    console.print("\n[bold]📂 Browsing 1926 census[/bold]"
                  + (f" — [yellow]{label}[/yellow]" if label else ""))

    async with Census1926Searcher(headless=headless) as searcher:
        with console.status("Loading…"):
            result = await searcher.search(
                surname=surname, county=county, ded=ded, max_results=max_results, debug=debug,
            )

    if not result.records:
        console.print("[red]No results found.[/red]")
        raise typer.Exit(1)

    console.print(f"\n[green]{result.total} record(s) — showing {len(result.records)}[/green]")
    title = "1926 Census" + (f" — {label}" if label else "")
    console.print(_record_table(result.records, title))


@app.command(name="1901")
def census_1901(
    surname: str = typer.Argument("", help="Surname to search for (optional)"),
    first_name: str = typer.Option("", "--first-name", "-f", help="First name — comma-separate variants"),
    county: str = typer.Option("", "--county", "-c", help="County or comma-separated counties"),
    sex: str = typer.Option("", "--sex", "-s", help="Sex filter (Male or Female)"),
    max_results: int = typer.Option(30, "--max", "-n", help="Max results to return"),
):
    """Browse the 1901 census directly (no 1926 anchor needed)."""
    asyncio.run(_do_census_year(
        surname=surname, first_name=first_name, county=county,
        year=1901, sex=sex, max_results=max_results,
    ))


@app.command(name="1911")
def census_1911(
    surname: str = typer.Argument("", help="Surname to search for (optional)"),
    first_name: str = typer.Option("", "--first-name", "-f", help="First name — comma-separate variants"),
    county: str = typer.Option("", "--county", "-c", help="County or comma-separated counties"),
    sex: str = typer.Option("", "--sex", "-s", help="Sex filter (Male or Female)"),
    max_results: int = typer.Option(30, "--max", "-n", help="Max results to return"),
):
    """Browse the 1911 census directly (no 1926 anchor needed)."""
    asyncio.run(_do_census_year(
        surname=surname, first_name=first_name, county=county,
        year=1911, sex=sex, max_results=max_results,
    ))


async def _do_census_year(
    surname: str,
    first_name: str,
    county: str,
    year: int,
    sex: str,
    max_results: int,
):
    counties = [c.strip() for c in county.split(",") if c.strip()] if county else [""]
    first_names = [n.strip() for n in first_name.split(",") if n.strip()] if first_name else [""]

    label_parts = [" / ".join(n for n in first_names if n), surname]
    name_label = " ".join(p for p in label_parts if p)
    console.print(f"\n[bold]📂 Browsing {year} census[/bold]"
                  + (f" — [yellow]{name_label}[/yellow]" if name_label else ""))

    async with Census1901_1911Searcher() as s:
        all_records: list[CensusRecord] = []
        total = 0
        with console.status(f"Searching {year}…"):
            for c in counties:
                for fn in first_names:
                    r = await s.search(
                        surname=surname,
                        first_name=fn,
                        county=c,
                        census_year=year,
                        max_results=max_results,
                    )
                    all_records.extend(r.records)
                    total += r.total

        # Deduplicate
        seen: set[tuple] = set()
        deduped: list[CensusRecord] = []
        for rec in all_records:
            key = (rec.surname.lower(), rec.first_name.lower(), rec.age, rec.county.lower())
            if key not in seen:
                seen.add(key)
                deduped.append(rec)

        # Client-side sex filter
        if sex:
            deduped = [
                rec for rec in deduped
                if not rec.sex or rec.sex.lower().startswith(sex.lower()[0])
            ]

        if not deduped:
            console.print("[dim]No results found.[/dim]")
            return

        console.print(f"\n[green]{total} record(s) — showing {len(deduped[:max_results])}[/green]")
        console.print(_record_table(deduped[:max_results], f"{year} Census"))


@app.command(name="1851")
def census_1851(
    surname: str = typer.Argument("", help="Surname to search for (optional)"),
    first_name: str = typer.Option("", "--first-name", "-f", help="First name"),
    county: str = typer.Option("", "--county", "-c", help="County"),
    sex: str = typer.Option("", "--sex", "-s", help="Sex filter (Male or Female)"),
    max_results: int = typer.Option(30, "--max", "-n", help="Max results to return"),
):
    """Browse the 1851 census fragment (National Archives)."""
    asyncio.run(_do_census_fragment(surname=surname, first_name=first_name, county=county,
                                    sex=sex, year=1851, max_results=max_results))


@app.command(name="1841")
def census_1841(
    surname: str = typer.Argument("", help="Surname to search for (optional)"),
    first_name: str = typer.Option("", "--first-name", "-f", help="First name"),
    county: str = typer.Option("", "--county", "-c", help="County"),
    sex: str = typer.Option("", "--sex", "-s", help="Sex filter (Male or Female)"),
    max_results: int = typer.Option(30, "--max", "-n", help="Max results to return"),
):
    """Browse the 1841 census fragment (National Archives)."""
    asyncio.run(_do_census_fragment(surname=surname, first_name=first_name, county=county,
                                    sex=sex, year=1841, max_results=max_results))


@app.command(name="1831")
def census_1831(
    surname: str = typer.Argument("", help="Surname to search for (optional)"),
    first_name: str = typer.Option("", "--first-name", "-f", help="First name"),
    county: str = typer.Option("", "--county", "-c", help="County"),
    max_results: int = typer.Option(30, "--max", "-n", help="Max results to return"),
):
    """Browse the 1831 census fragment (National Archives)."""
    asyncio.run(_do_census_fragment(surname=surname, first_name=first_name, county=county,
                                    sex="", year=1831, max_results=max_results))


@app.command(name="1821")
def census_1821(
    surname: str = typer.Argument("", help="Surname to search for (optional)"),
    first_name: str = typer.Option("", "--first-name", "-f", help="First name"),
    county: str = typer.Option("", "--county", "-c", help="County"),
    max_results: int = typer.Option(30, "--max", "-n", help="Max results to return"),
):
    """Browse the 1821 census fragment (National Archives)."""
    asyncio.run(_do_census_fragment(surname=surname, first_name=first_name, county=county,
                                    sex="", year=1821, max_results=max_results))


async def _do_census_fragment(
    surname: str,
    first_name: str,
    county: str,
    sex: str,
    year: int,
    max_results: int,
):
    name_label = " ".join(filter(None, [first_name, surname]))
    console.print(f"\n[bold]📂 Browsing {year} census fragment[/bold]"
                  + (f" — [yellow]{name_label}[/yellow]" if name_label else ""))

    async with Census1821_1851Searcher() as s:
        with console.status(f"Searching {year}…"):
            result = await s.search(
                census_year=year,
                surname=surname,
                first_name=first_name,
                county=county,
                sex=sex,
                max_results=max_results,
            )

    if not result.records:
        console.print("[dim]No results found.[/dim]")
        return

    # Client-side sex filter (1831 has no sex field; 1821 has no sex field either)
    records = result.records
    if sex:
        records = [r for r in records if not r.sex or r.sex.lower().startswith(sex.lower()[0])]

    console.print(f"\n[green]{len(records)} record(s)[/green]")
    console.print(_record_table(records, f"{year} Census Fragment"))


if __name__ == "__main__":
    app()
