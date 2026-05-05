import pandas as pd

"""Shared helper functions used across the application."""

def safe_str(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ''
    return str(val).strip()

def safe_filename(name):
    """Return a filename safe for Windows file systems."""
    import re
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'[\x00-\x1f]', '', name)
    return name.strip('_ ')

def days_diff(a, b):
    """Return difference in days between two timestamps; never negative."""
    try:
        if pd.notna(a) and pd.notna(b):
            delta = (pd.Timestamp(b) - pd.Timestamp(a)).total_seconds() / 86400
            return round(max(delta, 0), 2)
    except Exception:
        pass
    return 0

def get_distance(distance_dict, id_from, id_to):
    """Return distance between two stations by numeric id."""
    try:
        if pd.notna(id_from) and pd.notna(id_to):
            return distance_dict.get((int(id_from), int(id_to)), 0)
    except Exception:
        pass
    return 0

def get_station_codes(name: str, name_to_code: dict) -> list:
    """Return candidate station codes for a station name, including export/base variants."""
    codes = []
    name_up = name.strip().upper()
    code = name_to_code.get(name_up, '')
    if code:
        codes.append(code)
    EKS = ' (ЭКСП.)'
    if EKS in name_up:
        base = name_up.replace(EKS, '').strip()
        c2 = name_to_code.get(base, '')
        if c2 and c2 not in codes:
            codes.append(c2)
    else:
        c2 = name_to_code.get(name_up + EKS, '')
        if c2 and c2 not in codes:
            codes.append(c2)
    return codes

def precompute_streaks(rows, col='IsFull'):
    """Compute consecutive loaded/empty streak lengths for each row."""
    is_full  = (rows[col] == 1).astype(int)
    gid_full = (is_full != is_full.shift()).cumsum()
    streak_full = is_full.groupby(gid_full).transform('count') * is_full

    is_empty  = (rows[col] == 0).astype(int)
    gid_empty = (is_empty != is_empty.shift()).cumsum()
    streak_empty = is_empty.groupby(gid_empty).transform('count') * is_empty

    return streak_full.values, streak_empty.values

def get_client_group(wagon, depart_load, cargroup_dict):
    """Resolve client group at the departure date from loading."""
    if cargroup_dict is None or depart_load is None:
        return '-'
    try:
        depart_ts = pd.Timestamp(depart_load).tz_localize(None)
        wagon_key = str(wagon).strip().lstrip('0')
        entries   = cargroup_dict.get(wagon_key, [])
        min_de    = depart_ts + Timedelta(days=3)

        for db_val, de_val, grp_name in entries:
            db_ts = pd.Timestamp(db_val).tz_localize(None)
            de_ok = pd.isna(de_val) or pd.Timestamp(de_val).tz_localize(None) >= min_de
            if db_ts <= depart_ts and de_ok:
                return str(grp_name)

        best_grp, best_diff = None, None
        for db_val, de_val, grp_name in entries:
            db_ts     = pd.Timestamp(db_val).tz_localize(None)
            diff_days = (db_ts - depart_ts).total_seconds() / 86400
            if 0 < diff_days <= 3:
                if best_diff is None or diff_days < best_diff:
                    best_diff = diff_days
                    best_grp  = str(grp_name)
        if best_grp:
            return best_grp
    except Exception:
        pass
    return '-'

def prepare_df_for_excel(df):
    """Convert timestamp columns to safe strings before Excel export."""
    df = df.copy()
    date_cols = [
        'Прибытие на ст. погрузки', 'Отправление со ст. погрузки',
        'Прибытие на ст. выгрузки', 'Отправление со ст. выгрузки',
        'Прибытие на сл. погрузку',
    ]

    def safe_fmt(v):
        try:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ''
            ts = pd.Timestamp(v)
            if pd.isna(ts):
                return ''
            if ts.tzinfo is not None:
                ts = ts.tz_convert(None)
            return ts.strftime('%d.%m.%Y %H:%M')
        except Exception:
            return str(v) if v is not None else ''

    for col in date_cols:
        if col not in df.columns:
            continue
        df[col] = df[col].apply(safe_fmt)
    return df


def _clean_for_excel(df):
    """Normalize DataFrame values to Excel-safe strings and numbers."""
    df = df.copy()
    date_col_names = {
        'Прибытие на ст. погрузки', 'Отправление со ст. погрузки',
        'Прибытие на ст. выгрузки', 'Отправление со ст. выгрузки',
        'Прибытие на сл. погрузку',
    }
    num_col_names = {
        'Расстояние гружёного, км', 'Расстояние порожнего, км',
        'Вес, т', 'Простой на погрузке, сут', 'Гружёный рейс, сут',
        'Простой на выгрузке, сут', 'Порожний рейс, сут', 'Оборот, сут',
    }

    def fmt_date(v):
        try:
            if v is None: return ''
            if isinstance(v, float) and pd.isna(v): return ''
            ts = pd.Timestamp(v)
            if pd.isna(ts): return ''
            if ts.tzinfo is not None:
                ts = ts.tz_convert(None)
            return ts.strftime('%d.%m.%Y %H:%M')
        except Exception:
            return ''

    def fmt_num(v):
        try:
            if v is None: return ''
            if isinstance(v, float) and pd.isna(v): return ''
            return v
        except Exception:
            return ''

    def fmt_str(v):
        try:
            if v is None: return ''
            if isinstance(v, float) and pd.isna(v): return ''
            if isinstance(v, pd.Timestamp):
                return fmt_date(v)
            return str(v)
        except Exception:
            return ''

    for col in df.columns:
        if col in date_col_names:
            df[col] = df[col].apply(fmt_date)
        elif col in num_col_names:
            df[col] = df[col].apply(fmt_num)
        else:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].apply(fmt_date)
            else:
                df[col] = df[col].apply(fmt_str)
    return df
