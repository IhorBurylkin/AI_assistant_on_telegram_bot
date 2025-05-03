import pandas as pd
from config.config import MESSAGES

async def generate_report(df: pd.DataFrame, start_date: str, end_date: str, lang: str) -> str:
    # Преобразуем дату и отфильтруем по диапазону
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
    df['line_total'] = df['quantity'] * df['price']

    # Фильтрация по диапазону дат
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    df = df[(df['date'] >= start) & (df['date'] <= end)]

    # Общие показатели
    days = (end - start).days + 1
    stores = df['store'].nunique()
    checks = df.drop_duplicates(subset=['date', 'time', 'store', 'check_id']).shape[0]
    unique_positions = df.drop_duplicates(subset=['category', 'product']).shape[0]

    # Формирование заголовка
    rpt = MESSAGES[lang]['report']
    lines = [
        f"{rpt['period']} {start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}",
        f"• {rpt['days']} {days}",
        f"• {rpt['stores']} {stores}",
        f"• {rpt['checks']} {checks}",
        f"• {rpt['positions']} {unique_positions}",
        ""
    ]

    # Отчёт по каждой валюте
    for currency in sorted(df['currency'].unique()):
        sub_df = df[df['currency'] == currency]
        if sub_df.empty:
            continue
        total_expenses = sub_df['line_total'].sum()
        avg_per_day = total_expenses / days if days else 0
        lines.append(
            f"{rpt['total_spent']} {currency}: {total_expenses:.2f} {currency}"
            f" (≈ {avg_per_day:.2f} {currency}/{rpt['on_day']})"
        )
        # Разбивка по категориям для текущей валюты
        cat = sub_df.groupby('category').agg(
            count=('category', 'size'),
            sum=('line_total', 'sum')
        )
        total_count = cat['count'].sum()
        total_sum = cat['sum'].sum()
        lines.append(f"{rpt['categories']} ({currency}):")
        for category, row in cat.sort_values('sum', ascending=False).iterrows():
            pct_sum = (row['sum'] / total_sum * 100) if total_sum else 0
            pct_count = (row['count'] / total_count * 100) if total_count else 0
            lines.append(
                f"- {category}: {row['sum']:.2f} "
                f"({pct_sum:.1f}%)"
            )
        lines.append("")

    return "\n".join(lines).strip()