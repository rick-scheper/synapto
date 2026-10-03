/* @ds-bundle: {"format":4,"namespace":"Synapto","components":[{"name":"Button"},{"name":"Badge"},{"name":"Tabs"},{"name":"TextField"},{"name":"ProgressRing"},{"name":"LessonCard"},{"name":"Callout"},{"name":"CodeCell"},{"name":"QuizOption"},{"name":"TestResult"},{"name":"DecisionCard"}]} */
(function () {
  var R = window.React, h = R.createElement;
  function cx() { return Array.prototype.filter.call(arguments, Boolean).join(' '); }

  function Button(p) {
    var variant = p.variant || 'secondary', size = p.size || 'md';
    var rest = Object.assign({}, p); delete rest.variant; delete rest.size; delete rest.icon; delete rest.className;
    return h('button', Object.assign({ type: 'button' }, rest, { className: cx('sy-btn', 'sy-btn-' + variant, size === 'sm' && 'sy-btn-sm', p.className) }),
      p.icon ? h('span', { className: 'sy-btn-icon', 'aria-hidden': true }, p.icon) : null, p.children);
  }

  function Badge(p) {
    var tone = p.tone || 'neutral';
    var icon = { success: '✓', danger: '✕', warning: '!' }[tone];
    return h('span', { className: cx('sy-badge', 'sy-badge-' + tone) }, icon ? h('span', { 'aria-hidden': true }, icon) : null, p.children);
  }

  function Tabs(p) {
    var items = p.items || [];
    return h('div', { className: 'sy-tabs', role: 'tablist' }, items.map(function (it) {
      var id = typeof it === 'string' ? it : it.id, label = typeof it === 'string' ? it : it.label;
      var active = id === p.value;
      return h('button', { key: id, role: 'tab', 'aria-selected': active, className: cx('sy-tab', active && 'is-active'),
        onClick: function () { p.onChange && p.onChange(id); } }, label,
        it.count != null ? h('span', { className: 'sy-tab-count' }, it.count) : null);
    }));
  }

  function TextField(p) {
    return h('label', { className: 'sy-field' },
      p.label ? h('span', { className: 'sy-field-label' }, p.label) : null,
      h('input', { className: cx('sy-input', p.mono && 'is-mono', p.error && 'is-error'), value: p.value, defaultValue: p.defaultValue,
        placeholder: p.placeholder, onChange: p.onChange, disabled: p.disabled }),
      p.error ? h('span', { className: 'sy-field-error' }, '✕ ' + p.error) : p.hint ? h('span', { className: 'sy-field-hint' }, p.hint) : null);
  }

  function ProgressRing(p) {
    var size = p.size || 40, stroke = p.stroke || 4, v = Math.max(0, Math.min(1, p.value || 0));
    var r = (size - stroke) / 2, c = 2 * Math.PI * r;
    return h('span', { className: 'sy-ring', style: { width: size, height: size }, role: 'img', 'aria-label': Math.round(v * 100) + '% complete' },
      h('svg', { width: size, height: size, viewBox: '0 0 ' + size + ' ' + size },
        h('circle', { className: 'sy-ring-track', cx: size / 2, cy: size / 2, r: r, strokeWidth: stroke, fill: 'none' }),
        h('circle', { className: cx('sy-ring-fill', v >= 1 && 'is-done'), cx: size / 2, cy: size / 2, r: r, strokeWidth: stroke, fill: 'none',
          strokeDasharray: c, strokeDashoffset: c * (1 - v), strokeLinecap: 'round', transform: 'rotate(-90 ' + size / 2 + ' ' + size / 2 + ')' })),
      p.showLabel !== false && size >= 36 ? h('span', { className: 'sy-ring-label' }, v >= 1 ? '✓' : Math.round(v * 100) + '%') : null);
  }

  function LessonCard(p) {
    return h('article', { className: 'sy-card sy-lesson', tabIndex: 0 },
      h('div', { className: 'sy-lesson-top' },
        h('div', null,
          h('div', { className: 'sy-overline' }, [p.date, p.difficulty].filter(Boolean).join(' · ')),
          h('h3', { className: 'sy-h3 sy-lesson-title' }, p.title)),
        h(ProgressRing, { value: p.progress || 0, size: 40 })),
      p.summary ? h('p', { className: 'sy-lesson-summary' }, p.summary) : null,
      h('div', { className: 'sy-lesson-chips' },
        (p.concepts || []).map(function (c) { return h(Badge, { key: c, tone: 'accent' }, c); }),
        p.stale ? h(Badge, { tone: 'warning' }, 'Stale') : null),
      p.repo ? h('div', { className: 'sy-lesson-repo' }, p.repo) : null);
  }

  function Callout(p) {
    var tone = p.tone || 'info';
    var icon = { info: 'i', success: '✓', warning: '!', danger: '✕' }[tone];
    return h('div', { className: cx('sy-callout', 'sy-callout-' + tone), role: tone === 'danger' ? 'alert' : 'note' },
      h('span', { className: 'sy-callout-icon', 'aria-hidden': true }, icon),
      h('div', { className: 'sy-callout-body' }, p.title ? h('strong', null, p.title) : null, p.children ? h('div', null, p.children) : null),
      p.action || null);
  }

  var KW = /^(def|return|import|from|as|if|elif|else|for|while|in|not|and|or|is|None|True|False|class|with|lambda|yield|raise|try|except|finally|pass|break|continue|assert|async|await)$/;
  function highlight(code) {
    var out = [], re = /(#[^\n]*)|("""[\s\S]*?"""|'[^'\n]*'|"[^"\n]*")|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|([\s\S])/g, m, prevDef = false, k = 0, buf = '';
    function flush() { if (buf) { out.push(buf); buf = ''; } }
    while ((m = re.exec(code))) {
      var cls = null, t = m[0];
      if (m[1]) cls = 'c'; else if (m[2]) cls = 's'; else if (m[3]) cls = 'n';
      else if (m[4]) { if (KW.test(t)) cls = 'k'; else if (prevDef || code.charAt(re.lastIndex) === '(') cls = 'f'; }
      if (m[4]) prevDef = (t === 'def' || t === 'class'); else if (!/\s/.test(t)) prevDef = false;
      if (cls) { flush(); out.push(h('span', { key: k++, className: 'sy-tk-' + cls }, t)); } else buf += t;
    }
    flush(); return out;
  }

  function CodeCell(p) {
    var status = p.status || 'idle';
    var count = status === 'running' ? '*' : (p.execCount != null ? p.execCount : ' ');
    return h('section', { className: cx('sy-cell', 'is-' + status) },
      h('header', { className: 'sy-cell-head' },
        h('span', { className: 'sy-cell-count' }, '[' + count + ']'),
        p.role ? h('span', { className: 'sy-overline sy-cell-role' }, p.role + (p.fn ? ' · ' : '')) : null,
        p.fn ? h('span', { className: 'sy-cell-fn' }, p.fn) : null,
        h('span', { className: 'sy-cell-spacer' }),
        p.sourceRef ? h('span', { className: 'sy-cell-ref' }, p.sourceRef) : null,
        status === 'running' ? h('span', { className: 'sy-cell-live' }, h('span', { className: 'sy-dot' }), 'Running') :
          h(Button, { size: 'sm', variant: 'ghost', icon: '▶' }, 'Run')),
      h('pre', { className: 'sy-cell-code' }, h('code', null, highlight(p.code || ''))),
      p.output != null ? h('pre', { className: cx('sy-cell-out', status === 'error' && 'is-error') }, p.output) : null,
      p.time ? h('div', { className: 'sy-cell-time' }, p.time) : null);
  }

  function QuizOption(p) {
    var state = p.state || 'idle';
    var mark = { correct: '✓', wrong: '✕' }[state];
    return h('button', { type: 'button', className: cx('sy-opt', 'is-' + state), 'aria-pressed': state !== 'idle', onClick: p.onClick, disabled: p.disabled },
      h('span', { className: 'sy-opt-key' }, mark || p.optionId), h('span', { className: 'sy-opt-text' }, p.children),
      state === 'correct' ? h('span', { className: 'sy-opt-tag' }, 'Correct') : state === 'wrong' ? h('span', { className: 'sy-opt-tag' }, 'Not quite') : null);
  }

  function TestResult(p) {
    var tests = p.tests || [], passed = tests.filter(function (t) { return t.status === 'passed'; }).length;
    return h('div', { className: 'sy-tests' },
      h('div', { className: 'sy-tests-head' }, h('span', { className: 'sy-overline' }, 'Tests'),
        h(Badge, { tone: passed === tests.length ? 'success' : 'danger' }, passed + ' of ' + tests.length + ' passed')),
      tests.map(function (t) {
        var ok = t.status === 'passed';
        return h('div', { key: t.name, className: cx('sy-test', ok ? 'is-pass' : 'is-fail') },
          h('span', { className: 'sy-test-mark', 'aria-hidden': true }, ok ? '✓' : '✕'),
          h('div', { className: 'sy-test-main' }, h('span', { className: 'sy-test-name' }, t.name),
            !ok && t.message ? h('pre', { className: 'sy-test-msg' }, t.message) : null),
          h('span', { className: 'sy-test-status' }, ok ? 'Passed' : 'Failed'));
      }));
  }

  function DecisionCard(p) {
    return h('article', { className: 'sy-card sy-decision' },
      h('div', { className: 'sy-overline' }, 'Decision'),
      h('h3', { className: 'sy-h3' }, p.title),
      p.context ? h('p', { className: 'sy-decision-ctx' }, p.context) : null,
      h('ul', { className: 'sy-decision-opts' }, (p.options || []).map(function (o) {
        var chosen = o.id === p.chosen;
        return h('li', { key: o.id, className: cx('sy-decision-opt', chosen && 'is-chosen') },
          h('span', { className: 'sy-decision-id' }, o.id), h('span', null, o.label), chosen ? h(Badge, { tone: 'accent' }, 'Chosen') : null);
      })),
      p.why ? h('p', { className: 'sy-decision-why' }, h('strong', null, 'Why: '), p.why) : null,
      p.tradeoffs ? h('p', { className: 'sy-decision-why' }, h('strong', null, 'Trade-offs: '), p.tradeoffs) : null,
      h('div', { className: 'sy-decision-foot' }, h(Button, { size: 'sm', icon: '↻' }, 'Revisit decision')));
  }

  window.Synapto = Object.assign(window.Synapto || {}, {
    Button: Button, Badge: Badge, Tabs: Tabs, TextField: TextField, ProgressRing: ProgressRing, LessonCard: LessonCard,
    Callout: Callout, CodeCell: CodeCell, QuizOption: QuizOption, TestResult: TestResult, DecisionCard: DecisionCard
  });
})();
