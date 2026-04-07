
const h = React.createElement;
const { useState, useMemo } = React;
const {
  BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} = Recharts;

// ── Utilities ──
function fmt(n, decimals=1) {
  if (n == null || isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs >= 10000) return n.toLocaleString('en-US', {maximumFractionDigits: decimals});
  if (abs >= 100) return n.toFixed(decimals);
  return n.toFixed(Math.min(decimals + 1, 3));
}
function fmtSign(n, decimals=1) {
  if (n == null || isNaN(n)) return '—';
  return (n >= 0 ? '+' : '') + fmt(n, decimals) + '%';
}
function fmtComma(n) {
  if (n == null) return '—';
  return n.toLocaleString('en-US');
}

const CAT_COLORS = {
  Tree: '#55c078', Item: '#5588dd', Skill: '#d4a843',
  Base: '#a0a0b8', Jewel: '#cc5599', Other: '#6e6e88'
};
const CATEGORY_COLORS = {
  '进攻': '#e05555', '防御': '#5588dd', '混合': '#9966cc', '无效': '#6e6e88'
};

// ── KPI Cards ──
// ── Global Build Baseline Section (does not change with skill tabs) ──
function GlobalBaselineSection() {
  var g = GLOBAL_DATA || {};
  var def = g.defence_overview || {};
  var res = g.resource_overview || {};
  var bm = g.build_modifiers || {};
  var ba = g.build_attributes || {};

  // Build modifiers table
  var bmOrder = [
    { key: 'Speed_INC', label: '\u65BD\u6CD5\u901F\u5EA6 INC' },
    { key: 'Damage_INC', label: '\u4F24\u5BB3 INC' },
    { key: 'ElementalDamage_INC', label: '\u5143\u7D20\u4F24\u5BB3 INC' },
    { key: 'CritChance_INC', label: '\u66B4\u51FB\u7387 INC' },
    { key: 'CritMultiplier_INC', label: '\u66B4\u51FB\u4F24\u5BB3 INC' },
    { key: 'Damage_MORE', label: '\u4F24\u5BB3 MORE' },
  ];
  var bmRows = bmOrder.filter(function(o) { return bm[o.key]; }).map(function(o) {
    var m = bm[o.key];
    var tree = 0, item = 0, jewel = 0;
    (m.sources || []).forEach(function(s) {
      if (s.category === 'Tree') tree += s.value || 0;
      else if (s.category === 'Item') item += s.value || 0;
      else if (s.category === 'Jewel') jewel += s.value || 0;
    });
    var suffix = o.key.indexOf('INC') >= 0 ? '%' : '';
    return h('tr', { key: o.key },
      h('td', { style: { color: '#c0c0d0' } }, o.label),
      h('td', { style: { color: '#55c078', fontFamily: 'monospace' } }, '+' + Math.round(m.total) + suffix),
      h('td', { style: { color: tree ? '#44bbcc' : '#6e6e88', fontFamily: 'monospace' } }, tree ? '+' + Math.round(tree) + suffix : '\u2014'),
      h('td', { style: { color: item ? '#dd8844' : '#6e6e88', fontFamily: 'monospace' } }, item ? '+' + Math.round(item) + suffix : '\u2014'),
      h('td', { style: { color: jewel ? '#cc5599' : '#6e6e88', fontFamily: 'monospace' } }, jewel ? '+' + Math.round(jewel) + suffix : '\u2014')
    );
  });

  // Build attributes table
  var attrLabels = {
    TotalAttr: '\u603B\u5C5E\u6027', Str: '\u529B\u91CF', Dex: '\u654F\u6377', Int: '\u667A\u529B',
    Accuracy: '\u547D\u4E2D', AccuracyHitChance: '\u547D\u4E2D\u7387', StunAvoidChance: '\u7729\u6655\u907F\u514D'
  };
  var attrRows = Object.keys(attrLabels).filter(function(k) { return ba[k] != null && ba[k] !== 0; }).map(function(k) {
    return h('tr', { key: k },
      h('td', { style: { color: '#a0a0b8' } }, attrLabels[k]),
      h('td', { style: { color: '#e8e8f0', fontFamily: 'monospace', textAlign: 'right' } }, Math.abs(ba[k]) >= 100 ? Math.round(ba[k]).toLocaleString() : fmt(ba[k], 2))
    );
  });

  // Defence rows
  var resistData = def.resistances || {};
  var mhtData = def.max_hit_taken || {};
  var thmData = def.taken_hit_mult || {};
  var poolsData = def.pools || {};
  var blockData = def.block || {};
  var defItems = [
    { l: '\u751F\u547D', v: (poolsData.Life || 0).toLocaleString() },
    { l: 'ES', v: (poolsData.EnergyShield || 0).toLocaleString() },
    { l: 'Mana (MoM)', v: (poolsData.Mana || 0).toLocaleString() + (poolsData.MoMPct === 100 ? ' (100%)' : '') },
    { l: '\u62A4\u7532', v: (def.armour || 0).toLocaleString() },
    { l: '\u95EA\u907F', v: (def.evasion || 0).toLocaleString() },
    { l: '\u6781\u6027\u6297\u706B', v: resistData.Fire && resistData.Fire.Resist != null ? resistData.Fire.Resist + '%' : '-' },
    { l: '\u6781\u6027\u6297\u51B0', v: resistData.Cold && resistData.Cold.Resist != null ? resistData.Cold.Resist + '%' : '-' },
    { l: '\u6781\u6027\u6297\u96F7', v: resistData.Lightning && resistData.Lightning.Resist != null ? resistData.Lightning.Resist + '%' : '-' },
    { l: '\u6DF7\u6C8C\u6297', v: resistData.Chaos && resistData.Chaos.Resist != null ? resistData.Chaos.Resist + '%' : '-' },
    { l: '\u6700\u5927\u627F\u4F24(\u706B)', v: (mhtData.Fire || 0).toLocaleString() },
    { l: '\u6700\u5927\u627F\u4F24(\u51B0)', v: (mhtData.Cold || 0).toLocaleString() },
    { l: '\u6700\u5927\u627F\u4F24(\u96F7)', v: (mhtData.Lightning || 0).toLocaleString() },
    { l: '\u6700\u5927\u627F\u4F24(\u6DF7\u6C8C)', v: (mhtData.Chaos || 0).toLocaleString() },
    { l: '\u627F\u4F24\u4E58\u6570(\u706B)', v: fmt(thmData.Fire || 1, 2) },
    { l: '\u627F\u4F24\u4E58\u6570(\u6DF7\u6C8C)', v: fmt(thmData.Chaos || 1, 2) },
    { l: '\u6321\u683C', v: (blockData.BlockChance || 0) + '% / ' + (blockData.SpellBlockChance || 0) + '%' },
  ];

  // Resource rows
  var spiritData = res.spirit || {};
  var resItems = [
    { l: '\u751F\u547D', v: (res.life && res.life.total || 0).toLocaleString() + ' / \u5269\u4F59 ' + (res.life && res.life.unreserved || 0) },
    { l: 'Mana', v: (res.mana && res.mana.total || 0).toLocaleString() + ' / \u5269\u4F59 ' + (res.mana && res.mana.unreserved || 0) },
    { l: '\u7CBE\u9B42', v: (spiritData.total || 0) + ' / \u9884\u7EA6 ' + (spiritData.reserved_pct != null ? spiritData.reserved_pct.toFixed(1) + '%' : '-') + ' / \u5269\u4F59 ' + (spiritData.unreserved || 0) },
    { l: 'ES', v: (res.es && res.es.total || 0).toLocaleString() },
  ];

  // Jewel overview
  var jewels = g.jewel_overview || [];

  return h('div', null,
    // Build modifiers
    bmRows.length > 0 && h('div', { className: 'chart-box full-width' },
      h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '\u6784\u7B51\u4FEE\u9970\u7B26'),
      h('table', { style: { width: '100%', borderCollapse: 'collapse' } },
        h('thead', null,
          h('tr', null,
            h('th', { style: TH_STYLE }, '\u4FEE\u9970\u7B26'),
            h('th', { style: TH_STYLE }, '\u603B\u91CF'),
            h('th', { style: TH_STYLE }, '\u5929\u8D4B'),
            h('th', { style: TH_STYLE }, '\u88C5\u5907'),
            h('th', { style: TH_STYLE }, '\u73E0\u5B9D')
          )
        ),
        h('tbody', null, bmRows)
      )
    ),
    // Build attributes
    attrRows.length > 0 && h('div', { className: 'chart-box' },
      h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '\u6784\u7B51\u5C5E\u6027'),
      h('table', { style: { width: '100%', borderCollapse: 'collapse' } },
        h('tbody', null, attrRows)
      )
    ),
    // Defence (expandable)
    defItems.length > 0 && h('div', { className: 'chart-box full-width' },
      h('details', { open: false },
        h('summary', { className: 'chart-title', style: { cursor: 'pointer', userSelect: 'none' } },
          h('span', { className: 'dot' }), '\u9632\u5FA1\u9762', ' \u25B6'
        ),
        h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '2px 20px', padding: '8px 4px' } },
          defItems.map(function(r, i) {
            return h('div', { key: i, style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' } },
              h('span', { style: { color: '#a0a0b8' } }, r.l),
              h('span', { style: { color: '#e8e8f0', fontFamily: 'monospace' } }, r.v)
            );
          })
        )
      )
    ),
    // Resource (expandable)
    resItems.length > 0 && h('div', { className: 'chart-box full-width' },
      h('details', { open: false },
        h('summary', { className: 'chart-title', style: { cursor: 'pointer', userSelect: 'none' } },
          h('span', { className: 'dot' }), '\u8D44\u6E90\u9762', ' \u25B6'
        ),
        h('div', { style: { display: 'flex', flexDirection: 'column', gap: '2px', padding: '8px 4px' } },
          resItems.map(function(r, i) {
            return h('div', { key: i, style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' } },
              h('span', { style: { color: '#a0a0b8' } }, r.l),
              h('span', { style: { color: '#e8e8f0', fontFamily: 'monospace' } }, r.v)
            );
          })
        )
      )
    ),
    // Jewel overview (expandable)
    jewels.length > 0 && h('div', { className: 'chart-box full-width' },
      h('details', { open: false },
        h('summary', { className: 'chart-title', style: { cursor: 'pointer', userSelect: 'none' } },
          h('span', { className: 'dot' }), '\u73E0\u5B9D\u6982\u89C8 (' + jewels.length + ')', ' \u25B6'
        ),
        h('table', { style: { width: '100%', borderCollapse: 'collapse' } },
          h('thead', null,
            h('tr', null,
              h('th', { style: TH_STYLE }, '\u540D\u79F0'),
              h('th', { style: TH_STYLE }, '\u57FA\u5E95'),
              h('th', { style: TH_STYLE }, '\u63D2\u69FD'),
              h('th', { style: TH_STYLE }, '\u8D4B\u4E88\u5929\u8D4B')
            )
          ),
          h('tbody', null,
            jewels.map(function(j, i) {
              var passives = (j.granted_passives || []).join(', ');
              return h('tr', { key: i },
                h('td', { style: { color: '#c0c0d0', fontSize: 12 } }, j.name),
                h('td', { style: { color: '#a0a0b8', fontSize: 12 } }, j.base_type),
                h('td', { style: { color: '#a0a0b8', fontSize: 12 } }, j.slot_name),
                h('td', { style: { color: '#e8e8f0', fontSize: 12, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }, passives || '-')
              );
            })
          )
        )
      )
    )
  );
}

var TH_STYLE = { fontSize: 11, color: '#6e6e88', fontWeight: 400, textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid rgba(46,46,74,0.4)' };

// ── Source List (reusable) ──
function SourceList({ sources }) {
  if (!sources || sources.length === 0) return null;
  return h('div', { style: { display: 'flex', flexDirection: 'column', gap: 1, marginTop: 2, marginBottom: 2 } },
    sources.map((s, si) =>
      h('div', { key: si, style: { fontSize: 12, color: '#a0a0b8', display: 'flex', gap: 8, paddingLeft: 8 } },
        h('span', { style: { width: 50, color: CAT_COLORS[s.category] || '#6e6e88', fontSize: 11 } }, s.category),
        h('span', { style: { width: 50, textAlign: 'right', color: (s.value || 0) >= 0 ? '#e8e8f0' : '#e05555', fontFamily: 'monospace' } }, (s.value >= 0 ? '+' : '') + s.value),
        h('span', { style: { flex: 1 } }, s.label || '')
      )
    )
  );
}

// ── DPS Calculation Flow (renders pre-computed stages from Python) ──
function DPSFlowTable({ data }) {
  var stages = (data && data.dps_flow_stages) || [];
  if (stages.length === 0) return null;
  // Total DPS is the last stage's formula text (already formatted by Python)
  var totalLine = stages[stages.length - 1];

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), 'DPS 计算流程'),
    h('div', { style: { display: 'flex', flexDirection: 'column' } },
      stages.slice(0, -1).map(function(r, i) {
        var detail = r.detail_items;
        var hasDetail = detail && detail.length > 0;
        var isTotal = r.label === 'Total DPS';
        return h('div', { key: i, style: {
          borderBottom: '1px solid rgba(46,46,74,0.4)', padding: '6px 10px',
          background: isTotal ? 'rgba(212,168,67,0.06)' : 'transparent'
        }},
          h('div', { style: { display: 'flex', alignItems: 'center', gap: 12 } },
            h('div', { style: { width: 110, fontSize: 13, fontWeight: 500, color: r.color } }, r.label),
            h('div', { style: { flex: 1, fontSize: 12, color: '#a0a0b8', fontFamily: 'monospace' } }, r.formula),
            h('div', { style: { width: 160, textAlign: 'right', fontSize: 12, color: '#6e6e88' } }, r.factor)
          ),
          hasDetail ? h('details', { style: { paddingLeft: 122, marginTop: 2 } },
            h('summary', { style: { fontSize: 11, color: '#6e6e88', cursor: 'pointer', userSelect: 'none' } },
              '\u25B6 ' + detail.length + ' \u4e2a\u5b50\u9879'
            ),
            detail.map(function(it, j) {
              return h('div', { key: j, style: { padding: '2px 0' } },
                h('div', { style: { fontSize: 12, color: '#c0c0d0' } },
                  h('span', { style: { fontWeight: 500 } }, it.formula_name),
                  h('span', { style: { color: r.color, marginLeft: 8, fontFamily: 'monospace' } },
                    '+' + (it.total_value < 10 ? fmt(it.total_value, 1) : Math.round(it.total_value)) + '%'
                  )
                ),
                h(SourceList, { sources: it.sources })
              );
            })
          ) : null
        );
      })
    ),
    h('div', { style: { marginTop: 8, padding: '8px 12px', background: 'rgba(212,168,67,0.08)', borderRadius: 4, textAlign: 'center' } },
      h('span', { style: { color: '#a0a0b8', fontSize: 13 } }, 'Total DPS = '),
      h('span', { style: { color: '#d4a843', fontSize: 16, fontWeight: 700 } }, totalLine.formula)
    )
  );
}

// ── Formula Items Breakdown ──
function FormulaBreakdown({ data }) {
  if (!data || !data.formula_items) return null;
  // Filter out aggregate/summary items
  const items = data.formula_items.filter(it =>
    it.total_value !== undefined && it.total_value !== 0
    && it.key !== 'CombinedDPS' && !it.key.endsWith('EffMult')
  );
  if (items.length === 0) return null;

  const sorted = [...items].sort((a, b) => {
    // Group by type: INC → MORE → BASE → Lucky → ConvGain → SelfGain → Speed
    const order = { '_INC': 0, '_MORE': 1, '_BASE': 2, '_Lucky': 3, 'ConvGain': 4, 'SelfGain': 5, '_BASE': 2 };
    const aType = Object.keys(order).find(k => a.key.includes(k)) || 'zz';
    const bType = Object.keys(order).find(k => b.key.includes(k)) || 'zz';
    return (order[aType] || 9) - (order[bType] || 9) || b.total_value - a.total_value;
  });

  const catColors = { Tree: '#55c078', Item: '#5588dd', Skill: '#d4a843', Base: '#a0a0b8', Jewel: '#cc5599', Enemy: '#e05555' };

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), 'DPS 乘区来源拆解'),
    h('div', { style: { display: 'flex', flexDirection: 'column', gap: 0 } },
      sorted.map((it, idx) => {
        const cats = it.category_summary || {};
        const total = Math.abs(it.total_value);
        const catKeys = Object.keys(cats).filter(k => cats[k] !== 0);
        const catEntries = catKeys.map(k => ({ key: k, value: Math.abs(cats[k]), color: catColors[k] || '#6e6e88' }));
        catEntries.sort((a, b) => b.value - a.value);
        // Compute percentages for bar
        const catSum = catEntries.reduce((s, c) => s + c.value, 0) || 1;
        // Format suffix
        const suffix = it.key.includes('Lucky') ? '%' : (it.key.includes('_MORE') || it.key.includes('Conv') || it.key.includes('Gain') || it.key.includes('Speed')) ? (it.total_value > 10 ? '' : '%') : '%';

        return h('div', { key: idx, style: { borderBottom: '1px solid rgba(46,46,74,0.4)' } },
          // Main row
          h('div', { style: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 4px' } },
            // Formula name + value
            h('div', { style: { minWidth: 260, fontSize: 13, color: '#e8e8f0' } },
              h('span', { style: { fontWeight: 500 } }, it.formula_name),
              h('span', { style: { color: '#d4a843', fontWeight: 700, marginLeft: 8 } },
                (it.total_value >= 0 ? '+' : '') + (it.key.includes('Speed') || it.total_value < 10 ? fmt(it.total_value, 1) : Math.round(it.total_value)) + suffix
              )
            ),
            // Category bar
            h('div', { style: { flex: 1, height: 16, display: 'flex', borderRadius: 3, overflow: 'hidden' } },
              catEntries.map((c, ci) =>
                h('div', { key: ci, style: { width: (c.value / catSum * 100) + '%', background: c.color, opacity: 0.7 }, title: c.key + ': ' + fmt(c.value, 1) })
              )
            ),
            // Category legend
            h('div', { style: { display: 'flex', gap: 8, minWidth: 200, justifyContent: 'flex-end' } },
              catEntries.map((c, ci) =>
                h('span', { key: ci, style: { fontSize: 11, color: c.color } }, c.key + ' ' + fmt(c.value, 0))
              )
            )
          ),
          // Expandable sources
          (it.sources && it.sources.length > 0) ? h('details', { style: { paddingLeft: 12, paddingBottom: 4 } },
            h('summary', { style: { fontSize: 11, color: '#6e6e88', cursor: 'pointer', userSelect: 'none' } }, '▼ ' + it.sources.length + ' 个来源'),
            h('div', { style: { display: 'flex', flexDirection: 'column', gap: 1, marginTop: 2 } },
              it.sources.map((s, si) =>
                h('div', { key: si, style: { fontSize: 12, color: '#a0a0b8', display: 'flex', gap: 8, paddingLeft: 8 } },
                  h('span', { style: { width: 50, color: catColors[s.category] || '#6e6e88', fontSize: 11 } }, s.category),
                  h('span', { style: { width: 50, textAlign: 'right', color: (s.value || 0) >= 0 ? '#e8e8f0' : '#e05555', fontFamily: 'monospace' } }, (s.value >= 0 ? '+' : '') + s.value),
                  h('span', { style: { flex: 1 } }, s.label || s.source),
                  h('span', { style: { fontSize: 10, color: '#6e6e88' } }, s.source)
                )
              )
            )
          ) : null
        );
      })
    )
  );
}

// ── Sensitivity Ranking ──
function SensitivityChart({ sensitivity }) {
  if (!sensitivity || sensitivity.length === 0) return null;
  const sorted = [...sensitivity].filter(s => s.needed_value != null && s.needed_value < 9999)
    .sort((a, b) => a.needed_value - b.needed_value).slice(0, 12);

  const chartData = sorted.map(s => ({
    name: s.label || s.key,
    needed: s.needed_value,
    dpsPerUnit: s.dps_per_unit,
    formula: s.formula || '',
    modType: s.mod_type || ''
  }));

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload[0]) return null;
    const d = payload[0].payload;
    return h('div', { style: { background: '#252540', border: '1px solid #2e2e4a', borderRadius: 6, padding: '8px 12px', fontSize: 13 } },
      h('div', { style: { fontWeight: 600, color: '#d4a843' } }, d.name, ' (', d.modType, ')'),
      h('div', null, '所需: ', h('span', { style: { color: '#e8e8f0' } }, Number(d.needed).toFixed(1))),
      h('div', null, 'DPS/单位: ', h('span', { style: { color: '#55c078' } }, Number(d.dpsPerUnit).toFixed(3), '%')),
      d.formula ? h('div', { style: { color: '#a0a0b8', marginTop: 4, fontSize: 11 } }, d.formula) : null
    );
  };

  return h('div', { className: 'chart-box' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '优化杠杆排名 (所需投入越小 = 性价比越高)'),
    h(ResponsiveContainer, { width: '100%', height: Math.max(200, chartData.length * 36) },
      h(BarChart, { data: chartData, layout: 'vertical', margin: { top: 0, right: 20, left: 120, bottom: 0 } },
        h(CartesianGrid, { strokeDasharray: '3 3', stroke: '#2e2e4a' }),
        h(XAxis, { type: 'number', tick: { fill: '#6e6e88', fontSize: 11 } }),
        h(YAxis, { type: 'category', dataKey: 'name', width: 115, tick: { fill: '#a0a0b8', fontSize: 11 } }),
        h(Tooltip, { content: CustomTooltip }),
        h(Bar, { dataKey: 'needed', fill: '#d4a843', radius: [0, 4, 4, 0], opacity: 0.85 })
      )
    )
  );
}

// ── Aura Table (条件端点展示) ──
function AuraChart({ auras }) {
  if (!auras || auras.length === 0) return null;
  const aurasWithRange = auras.filter(a => a.config_ranges && a.config_ranges.length > 0);
  const aurasStatic = auras.filter(a => !a.config_ranges || a.config_ranges.length === 0);

  const rows = [];
  aurasWithRange.forEach(aura => {
    const cr = aura.config_ranges[0];
    const paramLabel = cr.label ? cr.label.replace(':', '') : 'Value';
    const maxVal = cr.actual_max || 300;
    const pctMin = cr.dps_pct_min || 0;
    const pctMax = cr.dps_pct_max || 0;
    const bareMin = cr.bare_pct_min != null ? cr.bare_pct_min : pctMin;
    const bareMax = cr.bare_pct_max != null ? cr.bare_pct_max : pctMax;
    const supMin = pctMin - bareMin;
    const supMax = pctMax - bareMax;
    // Min 端点
    rows.push({
      name: aura.name + (aura.simulated ? ' ⚠' : ''),
      endpoint: paramLabel + '=0',
      bare: bareMin, real: pctMin, support: supMin,
      ehp: aura.ehp_pct || 0, spirit: Math.round(aura.spirit_cost || 0)
    });
    // Max 端点
    rows.push({
      name: '', endpoint: paramLabel + '=' + maxVal,
      bare: bareMax, real: pctMax, support: supMax,
      ehp: '', spirit: ''
    });
  });
  aurasStatic.forEach(a => {
    rows.push({
      name: a.name + (a.simulated ? ' ⚠' : ''),
      endpoint: '—',
      bare: a.bare_dps_pct || 0, real: a.dps_pct || 0,
      support: a.supports_extra_pct || 0,
      ehp: a.ehp_pct || 0, spirit: Math.round(a.spirit_cost || 0)
    });
  });

  return h('div', { className: 'chart-box full-width' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '光环贡献分析'),
    h('table', null,
      h('thead', null, h('tr', null,
        h('th', null, '光环'), h('th', null, '条件'), h('th', null, '裸光环'), h('th', null, '真实'),
        h('th', null, '辅助增益'), h('th', null, 'EHP'), h('th', null, '精魄')
      )),
      h('tbody', null, rows.map((r, i) => h('tr', { key: i },
        h('td', { style: r.name ? {} : { opacity: 0 } }, r.name),
        h('td', { style: { color: '#a0a0b8' } }, r.endpoint),
        h('td', null, fmtSign(r.bare)),
        h('td', { style: { color: '#55c078', fontWeight: 500 } }, fmtSign(r.real)),
        h('td', { style: { color: '#cc5599' } }, Math.abs(r.support) >= 0.05 ? fmtSign(r.support, 2) : '—'),
        h('td', null, r.ehp !== '' ? fmtSign(r.ehp) : ''),
        h('td', null, r.spirit !== '' ? r.spirit : '')
      )))
    )
  );
}

// ── Talent Scatter ──
function TalentScatter({ talents }) {
  if (!talents || talents.length === 0) return null;
  const data = talents.filter(t => Math.abs(t.dps_pct) > 0.01 || Math.abs(t.ehp_pct) > 0.01)
    .map(t => ({
      name: t.name, type: t.type, x: t.dps_pct, y: t.ehp_pct,
      category: t.category || '无效', color: CATEGORY_COLORS[t.category] || CATEGORY_COLORS['无效']
    }));

  if (data.length === 0) return null;
  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload[0]) return null;
    const d = payload[0].payload;
    return h('div', { style: { background: '#252540', border: '1px solid #2e2e4a', borderRadius: 6, padding: '8px 12px', fontSize: 13 } },
      h('div', { style: { fontWeight: 600, color: d.color } }, d.name, ' (', d.type, ')'),
      h('div', null, 'DPS: ', h('span', { style: { color: '#e8e8f0' } }, fmtSign(d.x))),
      h('div', null, 'EHP: ', h('span', { style: { color: '#e8e8f0' } }, fmtSign(d.y))),
      h('div', { style: { color: '#a0a0b8', fontSize: 11 } }, d.category)
    );
  };

  return h('div', { className: 'chart-box' },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '天赋价值矩阵'),
    h(ResponsiveContainer, { width: '100%', height: 300 },
      h(ScatterChart, { margin: { top: 5, right: 20, left: 10, bottom: 5 } },
        h(CartesianGrid, { strokeDasharray: '3 3', stroke: '#2e2e4a' }),
        h(XAxis, { dataKey: 'x', tick: { fill: '#6e6e88', fontSize: 11 }, tickFormatter: v => fmtSign(v, 0), label: { value: 'DPS%', position: 'insideBottom', offset: -2, fill: '#a0a0b8', fontSize: 11 } }),
        h(YAxis, { dataKey: 'y', tick: { fill: '#6e6e88', fontSize: 11 }, tickFormatter: v => fmtSign(v, 0), label: { value: 'EHP%', angle: -90, position: 'insideLeft', fill: '#a0a0b8', fontSize: 11 } }),
        h(Tooltip, { content: CustomTooltip }),
        h(Scatter, { data, fill: '#d4a843', opacity: 0.8 })
      )
    )
  );
}

// ── Defence Radar (SVG) ──
function DefenceRadar({ baseline }) {
  if (!baseline) return null;
  const metrics = [
    { key: 'Life', max: 5000, value: baseline.Life || 0 },
    { key: 'ES', max: 3000, value: baseline.EnergyShield || 0 },
    { key: 'Evasion', max: 10000, value: baseline.MeleeEvasion || 0 },
    { key: 'Armour', max: 20000, value: baseline.ArmourDefense || 0 },
    { key: 'EHP', max: 15000, value: baseline.TotalEHP || 0 },
    { key: 'Mana', max: 3000, value: baseline.Mana || 0 },
  ];
  const n = metrics.length;
  const cx = 140, cy = 130, r = 90;
  const levels = [0.25, 0.5, 0.75, 1.0];
  const angle = (i) => (Math.PI * 2 * i / n) - Math.PI / 2;

  return h('div', { className: 'chart-box', style: { display: 'flex', flexDirection: 'column', alignItems: 'center' } },
    h('div', { className: 'chart-title' }, h('span', { className: 'dot' }), '防御属性雷达图'),
    h('svg', { width: 300, height: 280, viewBox: '0 0 300 280' },
      // Grid
      levels.map(lv => {
        const pts = [];
        for (let i = 0; i < n; i++) {
          const a = angle(i);
          pts.push(`${cx + Math.cos(a) * r * lv},${cy + Math.sin(a) * r * lv}`);
        }
        return h('polygon', { key: lv, points: pts.join(' '), fill: 'none', stroke: '#2e2e4a', strokeWidth: 1 });
      }),
      // Axes
      metrics.map((m, i) => {
        const a = angle(i);
        const x2 = cx + Math.cos(a) * r;
        const y2 = cy + Math.sin(a) * r;
        return h('line', { key: m.key, x1: cx, y1: cy, x2, y2, stroke: '#2e2e4a', strokeWidth: 1 });
      }),
      // Data polygon
      (() => {
        const pts = metrics.map((m, i) => {
          const a = angle(i);
          const val = Math.min(m.value / m.max, 1);
          return `${cx + Math.cos(a) * r * val},${cy + Math.sin(a) * r * val}`;
        });
        return h('polygon', { points: pts.join(' '), fill: 'rgba(212,168,67,0.15)', stroke: '#d4a843', strokeWidth: 2 });
      })(),
      // Data points + labels
      metrics.map((m, i) => {
        const a = angle(i);
        const val = Math.min(m.value / m.max, 1);
        const px = cx + Math.cos(a) * r * val;
        const py = cy + Math.sin(a) * r * val;
        const lx = cx + Math.cos(a) * (r + 22);
        const ly = cy + Math.sin(a) * (r + 22);
        const anchor = Math.abs(Math.cos(a)) < 0.1 ? 'middle' : (Math.cos(a) > 0 ? 'start' : 'end');
        return h('g', { key: m.key },
          h('circle', { cx: px, cy: py, r: 4, fill: '#d4a843' }),
          h('text', { x: lx, y: ly + 4, textAnchor: anchor, fill: '#a0a0b8', fontSize: 11 },
            m.key, ' (', Math.round(m.value).toLocaleString(), ')')
        );
      })
    )
  );
}

// ── Detail Tables ──
function DetailSection({ title, children, defaultOpen }) {
  return h('details', { open: defaultOpen },
    h('summary', null, title),
    h('div', { className: 'detail-content' }, children)
  );
}

function TalentValueTable({ talents }) {
  if (!talents) return null;
  return h(DetailSection, { title: `天赋价值 (${talents.length})`, defaultOpen: false },
    h('table', null,
      h('thead', null, h('tr', null, h('th', null, '名称'), h('th', null, '类型'), h('th', null, 'DPS%'), h('th', null, 'EHP%'), h('th', null, '分类'))),
      h('tbody', null,
        [...talents].sort((a, b) => a.dps_pct - b.dps_pct).map(t =>
          h('tr', { key: t.id || t.name },
            h('td', null, t.name),
            h('td', null, t.type),
            h('td', { style: { color: t.dps_pct >= 0 ? '#55c078' : '#e05555' } }, fmtSign(t.dps_pct)),
            h('td', { style: { color: t.ehp_pct >= 0 ? '#55c078' : '#e05555' } }, fmtSign(t.ehp_pct)),
            h('td', null, h('span', { style: { color: CATEGORY_COLORS[t.category] || '#a0a0b8' } }, t.category))
          )
        )
      )
    )
  );
}

function SensitivityTable({ sensitivity }) {
  if (!sensitivity) return null;
  return h(DetailSection, { title: `灵敏度分析 (${sensitivity.length})`, defaultOpen: false },
    h('table', null,
      h('thead', null, h('tr', null, h('th', null, '维度'), h('th', null, '类型'), h('th', null, '所需'), h('th', null, 'DPS/单位'), h('th', null, '公式'))),
      h('tbody', null, sensitivity.map((s, i) =>
        h('tr', { key: i },
          h('td', null, s.label),
          h('td', null, s.mod_type),
          h('td', null, s.needed_value != null ? fmt(s.needed_value, 1) + (s.unit || '') : '—'),
          h('td', null, s.dps_per_unit ? s.dps_per_unit.toFixed(3) + '%' : '—'),
          h('td', { style: { color: '#a0a0b8', fontSize: 11 } }, s.formula || '')
        )
      ))
    )
  );
}

function TalentExplorationTable({ talents }) {
  if (!talents || talents.length === 0) return null;
  return h(DetailSection, { title: `天赋探索推荐 (${talents.length})`, defaultOpen: false },
    h('table', null,
      h('thead', null, h('tr', null, h('th', null, '名称'), h('th', null, '类型'), h('th', null, 'DPS%'), h('th', null, 'EHP%'))),
      h('tbody', null,
        [...talents].sort((a, b) => b.dps_pct - a.dps_pct).map(t =>
          h('tr', { key: t.id || t.name },
            h('td', null, t.name),
            h('td', null, t.type),
            h('td', { style: { color: '#55c078' } }, fmtSign(t.dps_pct)),
            h('td', { style: { color: t.ehp_pct >= 0 ? '#55c078' : '#e05555' } }, fmtSign(t.ehp_pct))
          )
        )
      )
    )
  );
}

function JewelDiagnosisTable({ jewels }) {
  if (!jewels || jewels.length === 0) return null;
  return h(DetailSection, { title: `珠宝诊断 (${jewels.length})`, defaultOpen: false },
    h('table', null,
      h('thead', null, h('tr', null, h('th', null, '名称'), h('th', null, '插槽'), h('th', null, 'DPS%'), h('th', null, '状态'), h('th', null, 'Granted'))),
      h('tbody', null, jewels.map((j, i) =>
        h('tr', { key: i },
          h('td', null, j.name || '—'),
          h('td', null, j.slot_name || '—'),
          h('td', { style: { color: (j.dps_pct || 0) >= 0 ? '#e8e8f0' : '#e05555' } }, fmtSign(j.dps_pct)),
          h('td', null, h('span', { style: { color: j.status === 'ok' ? '#55c078' : '#e05555' } }, j.status || '—')),
          h('td', { style: { color: '#a0a0b8', fontSize: 11 } }, (j.granted_passives || []).join(', ') || '—')
        )
      ))
    )
  );
}

// ── Main App ──
function App() {
  const skillNames = useMemo(() => Object.keys(SKILLS_DATA), []);
  const [activeTab, setActiveTab] = useState(skillNames[0] || '');
  const data = SKILLS_DATA[activeTab] || {};

  const metaTitle = BUILD_META
    ? (BUILD_META.class_name || '') + ' ' + (BUILD_META.ascendancy || '') + ' Lv' + (BUILD_META.level || '')
    : 'POB Build Analysis';

  var bl = data.baseline || {};
  var skillDps = Math.round(bl.TotalDPS || 0);
  var avgHit = Math.round(bl.AverageHit || 0);
  var speed = bl.Speed || 0;
  var cc = bl.CritChance || 0;
  var cm = bl.CritMultiplier || 0;

  return h('div', null,
    // Header
    h('div', { className: 'header' },
      h('h1', null, metaTitle),
      BUILD_META ? h('div', { className: 'subtitle' }, 'Build ID: ', BUILD_META.build_id) : null
    ),
    // Global section (does not change with tabs)
    h(GlobalBaselineSection, null),
    // Skill tabs
    h('div', { className: 'tabs' },
      skillNames.map(function(name) {
        return h('div', {
          key: name,
          className: 'tab' + (activeTab === name ? ' active' : ''),
          onClick: function() { setActiveTab(name); }
        }, name.charAt(0).toUpperCase() + name.slice(1).replace('_', ' '));
      })
    ),
    // Skill KPI cards (per-tab)
    h('div', { className: 'kpi-row' },
      [
        { label: 'TotalDPS', value: fmtComma(skillDps), warn: false },
        { label: 'AverageHit', value: fmtComma(avgHit), warn: false },
        { label: 'Speed', value: fmt(speed, 2) + '/s', warn: false },
        { label: 'CritChance', value: fmt(cc, 1) + '%', warn: false },
        { label: 'CritMultiplier', value: fmt(cm, 2) + 'x', warn: false },
      ].map(function(k) {
        return h('div', { className: 'kpi-card', key: k.label },
          h('div', { className: 'label' }, k.label),
          h('div', { className: 'value' + (k.warn ? ' warn' : '') }, k.value)
        );
      })
    ),
    // Skill-specific sections
    h(DPSFlowTable, { data: data.dps_breakdown }),
    h(FormulaBreakdown, { data: data.dps_breakdown }),
    h('div', { className: 'chart-grid' },
      h(SensitivityChart, { sensitivity: data.sensitivity }),
      h(AuraChart, { auras: (data.aura_spirit || {}).existing_auras }),
      h(TalentScatter, { talents: data.talent_value }),
      h(DefenceRadar, { baseline: data.baseline })
    ),
    h(TalentValueTable, { talents: data.talent_value }),
    h(SensitivityTable, { sensitivity: data.sensitivity }),
    h(TalentExplorationTable, { talents: data.talent_exploration }),
    h(JewelDiagnosisTable, { jewels: data.jewel_diagnosis })
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(h(App));
