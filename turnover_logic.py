from collections import Counter
from pandas import Timedelta
import pandas as pd

"""Turnover calculation logic for wagon movement histories."""

# Типы фитинговых платформ: IsFull определяется по весу, а не из БД
FITTING_PLATFORM_TYPES = {
    'Платформа фитинговая 40 -фут',
    'Платформа фитинговая 80 -фут',
}
FITTING_MIN_WEIGHT_T = 5.0  # вес > 5т → гружёный, иначе → порожний

def find_turnovers(group, distance_dict, cargo_dict,
                   cargroup_dict, passport_dict,
                   name_to_code, code_to_name,
                   skip_first=False, log_fn=None, code_to_group=None):
    """Build turnover cycles for a wagon movement history."""
    if log_fn is None:
        log_fn = lambda msg: None
    if code_to_group is None:
        code_to_group = {}

    def dbg(tag, **kwargs):
        parts = [f"{k}={v}" for k, v in kwargs.items()]
        suffix = (' ' + ' '.join(parts)) if parts else ''
        log_fn(f"[TRACE] вагон={wagon} tag={tag}{suffix}")
    turnovers = []
    wagon = str(group['Номер_вагона'].iloc[0]).strip()
    rows  = group.sort_values('Дата_операции').reset_index(drop=True)
    n     = len(rows)

    _passport_entries = passport_dict.get(wagon, []) if passport_dict else []

    def _get_passport(dep_date):
        """Возвращает (собственник, в_управлении, тип) актуальные на dep_date."""
        if not _passport_entries:
            return '-', '-', '-'
        try:
            dep_ts = pd.Timestamp(dep_date).tz_localize(None)
        except Exception:
            dep_ts = None
        best = None
        for dt, sobst, uprav, tip in _passport_entries:
            try:
                dt_ts = pd.Timestamp(dt).tz_localize(None)
            except Exception:
                continue
            if dep_ts is None or dt_ts <= dep_ts:
                best = (sobst, uprav, tip)
        return best if best else ('-', '-', '-')

    v_upravlenii = '-'
    sobstvennik  = '-'
    _tip_wagon   = '-'

    # ── Ранний тип вагона (константа на весь период) ─────────────────────────
    # Берём последнюю паспортную запись до главного цикла — тип не меняется.
    # Нужно чтобы фильтр по типу в UI работал с первой итерации.
    if _passport_entries:
        _, _sb, _up, _tp = _passport_entries[-1]
        sobstvennik  = str(_sb).strip() if _sb else '-'
        v_upravlenii = str(_up).strip() if _up else '-'
        _tip_wagon   = str(_tp).strip() if _tp else '-'

    isfull  = rows['IsFull'].astype(int).values.copy()
    st_code = rows['Код_текущей_станции'].astype(str).str.strip().values
    st_name = rows['Станция_текущая'].fillna('').astype(str).str.strip().values
    st_id   = pd.to_numeric(rows['id_текущей_станции'],    errors='coerce').values
    dst_id   = pd.to_numeric(rows['id_станции_назначения'], errors='coerce').values
    dst_name = rows['Станция_назначения'].fillna('').astype(str).str.strip().values
    nakl    = [str(v).strip() if v is not None else '' for v in rows['Накладная'].values]
    cargov  = pd.to_numeric(rows['Код_груза'], errors='coerce').values
    weightv = pd.to_numeric(rows['Вес'],       errors='coerce').fillna(0).values
    dates   = rows['Дата_операции'].values

    st_norm = [code_to_group.get(str(c).strip(), str(c).strip()) for c in st_code]

    import re as _re
    _eksп_re = _re.compile(r'(?i)\s*\([^)]*\)\s*$')
    def _display_st(name):
        return _eksп_re.sub('', name).strip()

    # ── Фитинговые платформы: переопределяем isfull по весу ──────────────────
    is_fitting = _tip_wagon in FITTING_PLATFORM_TYPES
    if is_fitting:
        for k in range(n):
            isfull[k] = 1 if weightv[k] > FITTING_MIN_WEIGHT_T else 0

    # ── Чистка призрачных блоков ─────────────────────────────────────────────
    # Блок считается призраком если: все строки на одной станции, станция та же
    # до и после блока, и IsFull до/после одинаковый и противоположен блоку.
    # Итерируем до сходимости (ловим цепочки).
    changed = True
    while changed:
        changed = False
        k = 0
        while k < n:
            val = isfull[k]
            blk_start = k
            blk_end = k
            while blk_end + 1 < n and isfull[blk_end + 1] == val:
                blk_end += 1
            blk_len = blk_end - blk_start + 1
            if blk_len >= 2:
                prev_sc  = st_norm[blk_start - 1] if blk_start > 0 else None
                next_sc  = st_norm[blk_end + 1]   if blk_end + 1 < n else None
                blk_sc   = st_norm[blk_start]
                all_same = all(st_norm[j] == blk_sc for j in range(blk_start, blk_end + 1))
                same_prev = (prev_sc is not None and prev_sc == blk_sc)
                same_next = (next_sc is not None and next_sc == blk_sc)
                if all_same and same_prev and same_next:
                    val_before = isfull[blk_start - 1] if blk_start > 0 else None
                    val_after  = isfull[blk_end + 1]   if blk_end + 1 < n else None
                    if (val_before is not None and val_after is not None
                            and val_before != val and val_after != val
                            and val_before == val_after):
                        for j in range(blk_start, blk_end + 1):
                            isfull[j] = val_before
                        changed = True
            k = blk_end + 1

    # ── Серии (считаем ПОСЛЕ всех переопределений isfull) ────────────────────
    s1 = [0] * n
    s0 = [0] * n
    for k in range(n):
        if isfull[k] == 1:
            s1[k] = (s1[k-1] + 1) if k > 0 else 1
        else:
            s0[k] = (s0[k-1] + 1) if k > 0 else 1

    def dist_id(a, b):
        try:
            ia, ib = int(a), int(b)
            return distance_dict.get((ia, ib), distance_dict.get((ib, ia), 0))
        except Exception:
            return 0


    def ts(v):
        try:
            return pd.Timestamp(v) if v is not None and pd.notna(v) else None
        except Exception:
            return None

    def visit_end(start):
        """Конец непрерывного визита на той же станции что и start.
        (эксп.) и базовая версия станции считаются одной станцией."""
        sc = st_norm[start]
        if not sc or sc in ('nan', 'None', ''):  # защита от пустой нормы
            return start
        j  = start
        while j + 1 < n and st_norm[j + 1] == sc:
            j += 1
        return j

    def visit_start_back(idx):
        """Начало непрерывного визита (идём назад) для той же станции что idx.
        (эксп.) и базовая версия станции считаются одной станцией."""
        sc = st_norm[idx]
        if not sc or sc in ('nan', 'None', ''):  # защита от пустой нормы
            return idx
        j  = idx
        while j > 0 and st_norm[j - 1] == sc:
            j -= 1
        return j

    def append_row(status, d):
        base = {
            'Вагон': wagon, 'Тип вагона': _tip_wagon,
            'В управлении': v_upravlenii, 'Собственник': sobstvennik,
            'Группа клиента': '-', 'Накладные': '',
            'Станция погрузки': None,
            'Прибытие на ст. погрузки': None,
            'Отправление со ст. погрузки': None,
            'Расстояние гружёного, км': 0,
            'Груз': '-', 'Вес, т': 0,
            'Станция выгрузки': None,
            'Прибытие на ст. выгрузки': None,
            'Отправление со ст. выгрузки': None,
            'Ст. назначения (порожний)': None,
            'Прибытие на сл. погрузку': None,
            'Расстояние порожнего, км': 0,
            'Простой на погрузке, сут': 0,
            'Гружёный рейс, сут': 0,
            'Простой на выгрузке, сут': 0,
            'Порожний рейс, сут': 0,
            'Оборот, сут': 0,
            'Сдвойка': 'Нет',
            'Статус': status,
        }
        base.update(d)
        turnovers.append(base)

    # ── ШАГ 0: позиционирование в начале периода ─────────────────────────────
    # Случай А (skip_first=False): пропускаем порожние строки в начале.
    # Случай Б (skip_first=True): вагон гружёный, погрузка была до date_from.
    #   Lookback-данные уже добавлены в group (в workers.py).
    #   Восстанавливаем рейс: ищем последний блок IsFull=0 >= 2, затем
    #   первый IsFull=1 >= 2 после него — это реальная станция погрузки.
    i = 0
    if skip_first:
        last_empty_end = -1
        k = n - 1
        while k >= 1:
            if isfull[k] == 0 and isfull[k - 1] == 0:
                last_empty_end = k
                while k > 0 and isfull[k - 1] == 0:
                    k -= 1
                break
            k -= 1
        if last_empty_end >= 0:
            j = last_empty_end + 1
            while j < n and s1[j] < 2:
                j += 1
            i = (j - s1[j] + 1) if j < n else n
        else:
            i = 0  # весь массив гружёный — начинаем с начала
    else:
        while i < n and isfull[i] == 0:
            i += 1

    while i < n:

        while i < n and s1[i] < 3:
            i += 1
        if i >= n:
            break

        load_i   = i                   # первая строка устойчивой серии IsFull=1
        load_sc  = st_code[load_i]     # код станции погрузки
        load_stn = _display_st(st_name[load_i])  # имя станции погрузки (без эксп.)
        load_sid = st_id[load_i]       # id станции погрузки

        load_end = visit_end(load_i)

        arr_load_i = visit_start_back(load_i)
        arr_load   = dates[arr_load_i]

        dep_load_i = load_end
        for k in range(load_end, load_i - 1, -1):
            if isfull[k] == 1:
                dep_load_i = k
                break
        dep_load = dates[dep_load_i]

        load_nakl = str(nakl[load_i]).strip()
        if load_nakl.lower() in ('nan', 'none', ''):
            load_nakl = ''
        cv = [int(cargov[k]) for k in range(load_i, load_end + 1)
              if isfull[k] == 1 and pd.notna(cargov[k])]
        cargo_code = Counter(cv).most_common(1)[0][0] if cv else None
        cargo_name = cargo_dict.get(cargo_code, '-') if cargo_code else '-'
        wv = [weightv[k] for k in range(load_i, load_end + 1)
              if isfull[k] == 1 and weightv[k] > 0]
        weight_val = round(max(wv), 1) if wv else 0

        sobstvennik, v_upravlenii, _tip_wagon = _get_passport(dep_load)

        client_group = get_client_group(wagon, dep_load, cargroup_dict)

        dep_dst_id = dst_id[dep_load_i]

        loaded_dist  = dist_id(load_sid, dep_dst_id)   # базовый отрезок
        prev_dst_id  = dep_dst_id
        k = load_end + 1
        while k < n and isfull[k] == 1:
            new_dst = dst_id[k]
            if pd.notna(new_dst) and pd.notna(prev_dst_id):
                if int(new_dst) != int(prev_dst_id):
                    loaded_dist += dist_id(st_id[k - 1], new_dst)
                    prev_dst_id  = new_dst
            k += 1

        double_load = False
        unload_i    = -1
        unload_sc   = None
        unload_stn  = None
        unload_sid  = None
        next_stn    = None
        next_sid    = None
        arr_next    = None
        empty_dist  = 0
        empty_nakls = []
        next_load_i = -1

        k = load_end + 1
        while k < n:

            if isfull[k] != 0:
                k += 1
                continue

            zero_start = k
            zero_end   = k
            while zero_end + 1 < n and isfull[zero_end + 1] == 0:
                zero_end += 1
            zero_len = zero_end - zero_start + 1

            if zero_len >= 2:
                unload_i   = zero_start
                unload_sc  = st_code[unload_i]
                unload_sid = st_id[unload_i]
                _last_loaded = unload_i - 1
                while _last_loaded >= 0 and isfull[_last_loaded] != 1:
                    _last_loaded -= 1
                if _last_loaded >= 0 and dst_name[_last_loaded].strip() not in ('', 'nan', 'None'):
                    unload_stn = _display_st(dst_name[_last_loaded])
                else:
                    unload_stn = _display_st(st_name[unload_i])
                break

            else:
                next_one = zero_end + 1
                if next_one >= n:
                    break

                if isfull[next_one] != 1:
                    k = zero_end + 1  # прыгаем за конец серии порожних
                    continue

                ncv = [int(cargov[m]) for m in range(next_one, min(next_one + 15, n))
                       if isfull[m] == 1 and pd.notna(cargov[m])]
                nwv = [weightv[m] for m in range(next_one, min(next_one + 15, n))
                       if isfull[m] == 1 and weightv[m] > 0]
                new_cargo  = Counter(ncv).most_common(1)[0][0] if ncv else None
                new_weight = round(max(nwv), 1) if nwv else 0
                cargo_chg  = new_cargo is not None and new_cargo != cargo_code
                weight_chg = new_weight > 0 and abs(new_weight - weight_val) > 1

                if cargo_chg and weight_chg:
                    unload_i   = zero_start
                    unload_sc  = st_code[unload_i]
                    unload_sid = st_id[unload_i]
                    _last_loaded = unload_i - 1
                    while _last_loaded >= 0 and isfull[_last_loaded] != 1:
                        _last_loaded -= 1
                    if _last_loaded >= 0 and dst_name[_last_loaded].strip() not in ('', 'nan', 'None'):
                        unload_stn = _display_st(dst_name[_last_loaded])
                    else:
                        unload_stn = _display_st(st_name[unload_i])
                    double_load = True
                    new_load_i  = next_one
                    next_stn    = unload_stn
                    next_sid    = unload_sid
                    arr_next    = dates[next_one]
                    next_load_i = next_one
                    break
                else:
                    k = next_one
                    continue

        if unload_i == -1:
            append_row('Не завершён', {
                'Группа клиента':              client_group,
                'Накладные':                   load_nakl,
                'Станция погрузки':            load_stn,
                'Прибытие на ст. погрузки':    ts(arr_load),
                'Отправление со ст. погрузки': ts(dep_load),
                'Расстояние гружёного, км':    loaded_dist,
                'Груз':                        cargo_name,
                'Вес, т':                      weight_val,
                'Простой на погрузке, сут':    days_diff(arr_load, dep_load),
            })
            break

        unload_visit_end = visit_end(unload_i)
        unload_end = unload_i
        for j in range(unload_i, unload_visit_end + 1):
            if isfull[j] == 0:
                unload_end = j

        arr_unload_back = unload_i
        while arr_unload_back > 0 and st_norm[arr_unload_back - 1] == st_norm[unload_i]:
            arr_unload_back -= 1
            if arr_unload_back < unload_i - 50:  # защита от бесконечного цикла
                arr_unload_back = unload_i
                break
        arr_unload = dates[arr_unload_back]

        dep_unload_i = unload_end
        dep_unload   = dates[dep_unload_i]

        if double_load:
            dep_unload   = dates[next_load_i]
            dep_unload_i = next_load_i

        if not double_load:
            seen = {load_nakl}
            k = unload_end + 1
            while k < n:
                if isfull[k] == 0:
                    nv = str(nakl[k]).strip()
                    if nv and nv.lower() not in ('nan', 'none', '') and nv not in seen:
                        seen.add(nv)
                        empty_nakls.append(nv)
                elif s1[k] >= 3:
                    break
                k += 1

            k = unload_end + 1
            while k < n:
                if s1[k] >= 3:
                    next_load_i = k
                    next_sid    = st_id[next_load_i]
                    _last_empty = next_load_i - 1
                    while _last_empty >= 0 and isfull[_last_empty] != 0:
                        _last_empty -= 1
                    if _last_empty >= 0 and dst_name[_last_empty].strip() not in ('', 'nan', 'None'):
                        next_stn = _display_st(dst_name[_last_empty])
                    else:
                        next_stn = _display_st(st_name[next_load_i])
                    arr_next = dates[visit_start_back(next_load_i)]
                    if dep_unload is not None and arr_next is not None and dep_unload > arr_next:
                        dbg('warn_dep_unload_after_next_arr', dep_unload=dep_unload, arr_next=arr_next,
                            unload_stn=unload_stn, next_stn=next_stn, next_load_i=next_load_i, unload_end=unload_end)
                        if unload_stn == next_stn:
                            double_load = True
                            arr_next = dep_unload
                            next_sid = unload_sid
                            next_stn = unload_stn
                            empty_nakls = []
                            dbg('same_station_double_load', station=unload_stn, next_load_i=next_load_i, dep_unload=dep_unload)
                    break
                k += 1

            if next_load_i == -1:
                append_row('Не завершён', {
                    'Группа клиента':              client_group,
                    'Накладные':                   load_nakl,
                    'Станция погрузки':            load_stn,
                    'Прибытие на ст. погрузки':    ts(arr_load),
                    'Отправление со ст. погрузки': ts(dep_load),
                    'Расстояние гружёного, км':    loaded_dist,
                    'Груз':                        cargo_name,
                    'Вес, т':                      weight_val,
                    'Станция выгрузки':            unload_stn,
                    'Прибытие на ст. выгрузки':    ts(arr_unload),
                    'Отправление со ст. выгрузки': ts(dep_unload),
                    'Простой на погрузке, сут':    days_diff(arr_load,   dep_load),
                    'Гружёный рейс, сут':          days_diff(dep_load,   arr_unload),
                    'Простой на выгрузке, сут':    days_diff(arr_unload, dep_unload),
                })
                break

            empty_dist = dist_id(unload_sid, next_sid)

        all_nakls = ([load_nakl] if load_nakl else []) + empty_nakls
        nakl_str  = ' / '.join(all_nakls) if all_nakls else ''

        idle_load   = days_diff(arr_load,   dep_load)
        loaded_run  = days_diff(dep_load,   arr_unload)
        idle_unload = days_diff(arr_unload, dep_unload)
        empty_run   = 0 if double_load else days_diff(dep_unload, arr_next)
        total       = idle_load + loaded_run + idle_unload + empty_run

        append_row('Завершён', {
            'Группа клиента':              client_group,
            'Накладные':                   nakl_str,
            'Станция погрузки':            load_stn,
            'Прибытие на ст. погрузки':    ts(arr_load),
            'Отправление со ст. погрузки': ts(dep_load),
            'Расстояние гружёного, км':    loaded_dist,
            'Груз':                        cargo_name,
            'Вес, т':                      weight_val,
            'Станция выгрузки':            unload_stn,
            'Прибытие на ст. выгрузки':    ts(arr_unload),
            'Отправление со ст. выгрузки': ts(dep_unload),
            'Ст. назначения (порожний)':   'Сдвойка' if double_load else (next_stn or '-'),
            'Прибытие на сл. погрузку':    ts(arr_next),
            'Расстояние порожнего, км':    0 if double_load else empty_dist,
            'Простой на погрузке, сут':    idle_load,
            'Гружёный рейс, сут':          loaded_run,
            'Простой на выгрузке, сут':    idle_unload,
            'Порожний рейс, сут':          empty_run,
            'Оборот, сут':                 total,
            'Сдвойка':                     'Да' if double_load else 'Нет',
        })

        if next_load_i < 0 or next_load_i >= n:
            break  # нет следующей погрузки — выходим
        if next_load_i <= i:
            fallback_i = max(i + 1, unload_end + 1)
            dbg('NO_ADVANCE', current_i=i, next_load_i=next_load_i, fallback_i=fallback_i)
            if fallback_i <= i or fallback_i >= n:
                break
            i = fallback_i
            continue
        i = next_load_i

    return pd.DataFrame(turnovers)
