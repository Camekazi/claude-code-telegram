"""Quick commands that bypass Claude for instant responses.

These commands query local databases/APIs directly for speed.
"""

import json
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import structlog
from telegram import Update
from telegram.ext import ContextTypes

logger = structlog.get_logger()

# Cal.com CLI path
CALCOM_CLI = Path.home() / ".claude/bin/calcom-cli"

# Database paths
GROCERIES_DB = Path("/Users/joppa/eobsidian/02_Areas/Family/groceries.db")


async def groceries_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /groceries command - instant grocery stats."""
    args = " ".join(context.args) if context.args else ""

    if not GROCERIES_DB.exists():
        await update.message.reply_text(
            "❌ **Grocery Database Not Found**\n\n"
            f"Expected at: `{GROCERIES_DB}`"
        )
        return

    try:
        conn = sqlite3.connect(GROCERIES_DB)
        conn.row_factory = sqlite3.Row

        if args.lower() in ["", "summary", "stats"]:
            # Default: Show summary
            result = await _groceries_summary(conn)
        elif args.lower().startswith("store"):
            result = await _groceries_by_store(conn)
        elif args.lower().startswith("month"):
            result = await _groceries_monthly(conn)
        elif args.lower().startswith("top"):
            result = await _groceries_top_products(conn)
        elif args.lower().startswith("recent"):
            result = await _groceries_recent(conn)
        else:
            result = (
                "📊 **Grocery Commands**\n\n"
                "• `/groceries` - Summary stats\n"
                "• `/groceries store` - Spend by store\n"
                "• `/groceries month` - Monthly trend\n"
                "• `/groceries top` - Top products\n"
                "• `/groceries recent` - Recent purchases\n\n"
                "_For complex queries, just ask me naturally!_"
            )

        conn.close()
        await update.message.reply_text(result, parse_mode="Markdown")

    except Exception as e:
        logger.error("Groceries command error", error=str(e))
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def _groceries_summary(conn) -> str:
    """Get grocery spending summary."""
    # Total spend
    total = conn.execute(
        "SELECT SUM(price * quantity) as total, COUNT(*) as items FROM purchases"
    ).fetchone()

    # Date range
    dates = conn.execute(
        "SELECT MIN(date) as min_date, MAX(date) as max_date FROM purchases"
    ).fetchone()

    # By store
    stores = conn.execute("""
        SELECT store, SUM(price * quantity) as spend, COUNT(*) as items
        FROM purchases GROUP BY store ORDER BY spend DESC
    """).fetchall()

    # Format
    lines = [
        "📊 **Grocery Summary**",
        "",
        f"💰 Total: **£{total['total']:,.2f}** ({total['items']} items)",
        f"📅 {dates['min_date']} to {dates['max_date']}",
        "",
        "🏪 **By Store:**"
    ]

    for s in stores:
        pct = (s['spend'] / total['total'] * 100) if total['total'] else 0
        lines.append(f"  • {s['store']}: £{s['spend']:,.2f} ({pct:.0f}%)")

    return "\n".join(lines)


async def _groceries_by_store(conn) -> str:
    """Get detailed store breakdown."""
    stores = conn.execute("""
        SELECT store,
               SUM(price * quantity) as spend,
               COUNT(*) as items,
               COUNT(DISTINCT email_id) as orders
        FROM purchases GROUP BY store ORDER BY spend DESC
    """).fetchall()

    lines = ["🏪 **Spend by Store**", ""]
    for s in stores:
        avg_order = s['spend'] / s['orders'] if s['orders'] else 0
        lines.append(f"**{s['store']}**")
        lines.append(f"  £{s['spend']:,.2f} | {s['orders']} orders | ~£{avg_order:.0f}/order")

    return "\n".join(lines)


async def _groceries_monthly(conn) -> str:
    """Get monthly spending trend."""
    monthly = conn.execute("""
        SELECT strftime('%Y-%m', date) as month,
               SUM(price * quantity) as spend,
               COUNT(*) as items
        FROM purchases
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
    """).fetchall()

    lines = ["📈 **Monthly Trend**", ""]
    prev_spend = None
    for m in reversed(monthly):
        change = ""
        if prev_spend:
            pct = ((m['spend'] - prev_spend) / prev_spend) * 100
            change = f" ({'+' if pct > 0 else ''}{pct:.0f}%)"
        lines.append(f"  {m['month']}: £{m['spend']:,.2f}{change}")
        prev_spend = m['spend']

    return "\n".join(lines)


async def _groceries_top_products(conn) -> str:
    """Get top products by spend."""
    products = conn.execute("""
        SELECT product, SUM(price * quantity) as total, COUNT(*) as times
        FROM purchases
        GROUP BY product
        ORDER BY total DESC
        LIMIT 10
    """).fetchall()

    lines = ["🏆 **Top Products by Spend**", ""]
    for i, p in enumerate(products, 1):
        name = p['product'][:35] + "..." if len(p['product']) > 35 else p['product']
        lines.append(f"{i}. {name}")
        lines.append(f"   £{p['total']:,.2f} ({p['times']}x)")

    return "\n".join(lines)


async def _groceries_recent(conn) -> str:
    """Get recent purchases."""
    recent = conn.execute("""
        SELECT date, store, product, price, quantity
        FROM purchases
        ORDER BY date DESC, id DESC
        LIMIT 15
    """).fetchall()

    lines = ["🛒 **Recent Purchases**", ""]
    current_date = None
    for r in recent:
        if r['date'] != current_date:
            current_date = r['date']
            lines.append(f"\n**{r['date']}** ({r['store']})")
        name = r['product'][:30] + "..." if len(r['product']) > 30 else r['product']
        lines.append(f"  • {name} - £{r['price']:.2f}")

    return "\n".join(lines)


async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /calendar command - today's schedule."""
    try:
        # Use the cal-events CLI tool
        result = subprocess.run(
            ["/Users/joppa/.claude/bin/cal-events", "--today"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            events = result.stdout.strip()
            await update.message.reply_text(
                f"📅 **Today's Calendar**\n\n{events}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "📅 **Today's Calendar**\n\n_No events scheduled_"
            )
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏰ Calendar query timed out")
    except FileNotFoundError:
        await update.message.reply_text(
            "❌ Calendar CLI not found. Ask me about your schedule instead!"
        )
    except Exception as e:
        logger.error("Calendar command error", error=str(e))
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reminders command - show Apple Reminders."""
    try:
        # Use AppleScript to get reminders
        script = '''
        tell application "Reminders"
            set output to ""
            repeat with r in (reminders whose completed is false)
                set output to output & "• " & name of r & "\n"
            end repeat
            return output
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            reminders = result.stdout.strip()
            await update.message.reply_text(
                f"✅ **Pending Reminders**\n\n{reminders}"
            )
        else:
            await update.message.reply_text(
                "✅ **Reminders**\n\n_No pending reminders_"
            )
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏰ Reminders query timed out")
    except Exception as e:
        logger.error("Reminders command error", error=str(e))
        await update.message.reply_text(f"❌ Error: {str(e)}")


def _parse_natural_time(text: str) -> tuple[datetime | None, str | None]:
    """Parse natural language time expressions.

    Returns (datetime, title) or (None, error_message).

    Supports:
    - "tomorrow at 2pm" / "tomorrow 2pm"
    - "monday at 3pm" / "next monday 3pm"
    - "friday 10:30am"
    - "today at 4pm"
    - "in 2 hours"
    - Explicit: "2024-03-15 14:00"
    """
    text = text.lower().strip()
    now = datetime.now()

    # Pattern: extract time and remaining text as title
    time_patterns = [
        # "at HH:MM" or "at Hpm/am"
        r'at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?',
        # "HH:MM" standalone or "Hpm/am"
        r'(\d{1,2}):(\d{2})\s*(am|pm)?',
        r'(\d{1,2})\s*(am|pm)',
    ]

    # Day patterns
    day_keywords = {
        'today': 0,
        'tomorrow': 1,
        'monday': None, 'tuesday': None, 'wednesday': None,
        'thursday': None, 'friday': None, 'saturday': None, 'sunday': None,
    }

    day_map = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6,
    }

    # Try "in X hours" pattern
    in_hours_match = re.search(r'in\s+(\d+)\s*hours?', text)
    if in_hours_match:
        hours = int(in_hours_match.group(1))
        target = now + timedelta(hours=hours)
        title = re.sub(r'in\s+\d+\s*hours?', '', text).strip()
        return target, title if title else None

    # Find time in text
    hour, minute, period = None, 0, None

    for pattern in time_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            hour = int(groups[0])
            # Handle different pattern structures
            if len(groups) == 3:
                # Patterns with hour, minute, period
                if groups[1] and groups[1].isdigit():
                    minute = int(groups[1])
                if groups[2]:
                    period = groups[2]
            elif len(groups) == 2:
                # Pattern: (\d{1,2})\s*(am|pm) - hour and period only
                if groups[1] in ('am', 'pm'):
                    period = groups[1]
                elif groups[1] and groups[1].isdigit():
                    minute = int(groups[1])
            break

    if hour is None:
        return None, "Couldn't find a time. Try: 'tomorrow at 2pm' or 'monday 3:30pm'"

    # Convert to 24h
    if period == 'pm' and hour < 12:
        hour += 12
    elif period == 'am' and hour == 12:
        hour = 0

    # Find day reference
    target_date = now.date()

    if 'tomorrow' in text:
        target_date = (now + timedelta(days=1)).date()
    elif 'today' in text:
        target_date = now.date()
    else:
        # Check for day names
        for day_name, weekday in day_map.items():
            if day_name in text:
                # Find next occurrence of this day
                days_ahead = weekday - now.weekday()
                if days_ahead <= 0:  # Target day already happened this week or is today
                    if 'next' in text:
                        days_ahead += 7
                    elif days_ahead < 0:
                        days_ahead += 7
                target_date = (now + timedelta(days=days_ahead)).date()
                break

    # Build target datetime
    try:
        target = datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))
    except ValueError as e:
        return None, f"Invalid time: {e}"

    # Extract title (remove time/day references)
    title = text
    # Remove common patterns
    title = re.sub(r'(next\s+)?(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)', '', title)
    title = re.sub(r'at\s+\d{1,2}:?\d{0,2}\s*(am|pm)?', '', title)
    title = re.sub(r'\d{1,2}:\d{2}\s*(am|pm)?', '', title)
    title = re.sub(r'\d{1,2}\s*(am|pm)', '', title)
    title = title.strip(' ,-:')

    return target, title if title else None


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /schedule command - create calendar proposals via Cal.com.

    Usage:
    /schedule tomorrow at 2pm Team meeting
    /schedule monday 3pm Client call --family
    /schedule friday 10am Doctor appointment --family
    """
    if not context.args:
        await update.message.reply_text(
            "📅 **Schedule Command**\n\n"
            "Create calendar proposals quickly.\n\n"
            "**Usage:**\n"
            "`/schedule <when> <title> [--family]`\n\n"
            "**Examples:**\n"
            "• `/schedule tomorrow at 2pm Team meeting`\n"
            "• `/schedule monday 3pm Client call`\n"
            "• `/schedule friday 10am Doctor --family`\n\n"
            "**Time formats:**\n"
            "• `tomorrow at 2pm`\n"
            "• `monday 3:30pm`\n"
            "• `friday 10am`\n"
            "• `in 2 hours`\n\n"
            "_Events are proposed to Cal.com for approval._",
            parse_mode="Markdown"
        )
        return

    full_text = " ".join(context.args)

    # Check for --family flag
    is_family = "--family" in full_text.lower()
    full_text = re.sub(r'--family', '', full_text, flags=re.IGNORECASE).strip()

    # Parse time and title
    parsed_time, title = _parse_natural_time(full_text)

    if parsed_time is None:
        await update.message.reply_text(f"❌ {title}")  # title contains error message
        return

    if not title:
        await update.message.reply_text(
            "❌ Please include a title for the event.\n\n"
            "Example: `/schedule tomorrow at 2pm Team meeting`",
            parse_mode="Markdown"
        )
        return

    # Format title properly (capitalize)
    title = title.title()

    # Calculate end time (default 1 hour)
    end_time = parsed_time + timedelta(hours=1)

    # Format for calcom-cli
    start_iso = parsed_time.strftime("%Y-%m-%dT%H:%M:%S")
    end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S")
    context_type = "family" if is_family else "personal"

    # Call calcom-cli
    if not CALCOM_CLI.exists():
        await update.message.reply_text(
            "❌ **Cal.com CLI not found**\n\n"
            f"Expected at: `{CALCOM_CLI}`",
            parse_mode="Markdown"
        )
        return

    try:
        cmd = [
            str(CALCOM_CLI),
            "propose",
            title,
            "--start", start_iso,
            "--end", end_iso,
            "--context", context_type,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            # Parse response for confirmation
            calendar_emoji = "👨‍👩‍👧" if is_family else "📅"
            time_str = parsed_time.strftime("%a %b %d at %H:%M")

            await update.message.reply_text(
                f"{calendar_emoji} **Event Proposed**\n\n"
                f"📝 **{title}**\n"
                f"📆 {time_str}\n"
                f"🗓️ Context: {context_type.title()}\n\n"
                "_Check Cal.com to approve this event._",
                parse_mode="Markdown"
            )
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            await update.message.reply_text(
                f"❌ **Failed to create proposal**\n\n"
                f"Error: {error_msg}",
                parse_mode="Markdown"
            )

    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏰ Cal.com request timed out")
    except Exception as e:
        logger.error("Schedule command error", error=str(e))
        await update.message.reply_text(f"❌ Error: {str(e)}")
