import json
for skill in ['spark', 'comet']:
    with open(f'analysis_{skill}.json') as f:
        d = json.load(f)
    print(f'=== {skill} ===')
    for it in d['dps_breakdown']['formula_items']:
        found = False
        for s in it['sources']:
            src = s.get('source', '').lower()
            if 'conflux' in src or 'charge' in src or 'infusion' in src:
                found = True
                print(f'  {it["key"]}: src={s["source"]} val={s["value"]} cat={s["category"]}')
        if found:
            print(f'    >> display_value={it["display_value"]} total_value={it["total_value"]}')
    # Also search all sources for any Conflux/Charge Infusion mention
    for it in d['dps_breakdown']['formula_items']:
        for s in it['sources']:
            src = s.get('source', '')
            if 'onflux' in src or 'nfusion' in src or 'harge' in src:
                print(f'  ALL: {it["key"]}: {src} val={s["value"]}')
    print()
