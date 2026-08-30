/* Result Office - Ext JS 7 classic front end for the GPA engine. */

/* Served from the same origin on Vercel. During development the Ext files come
   from :1841 while the API runs on :8000, so point at that instead. */
var LOCAL = ['localhost', '127.0.0.1', ''].indexOf(location.hostname) !== -1;
var API = LOCAL ? 'http://127.0.0.1:8000/api' : '/api';

Ext.define('RO.model.Student', {
    extend: 'Ext.data.Model',
    fields: ['id', 'roll', 'name', 'class_name', 'note', 'letter', 'failing_subjects',
             {name: 'gpa', type: 'float', allowNull: true},
             {name: 'passed', type: 'boolean', allowNull: true},
             {name: 'flags', defaultValue: []}]
});

Ext.define('RO.model.Subject', {
    extend: 'Ext.data.Model',
    fields: ['code', 'name', 'letter', 'rule_code', 'rule_text', 'component_failed',
             {name: 'is_optional', type: 'boolean'},
             {name: 'has_practical', type: 'boolean'},
             {name: 'is_absent', type: 'boolean'},
             {name: 'passed', type: 'boolean'},
             {name: 'grade_point', type: 'float'},
             {name: 'mark_used', type: 'float', allowNull: true},
             {name: 'theory_obtained', type: 'float', allowNull: true},
             {name: 'practical_obtained', type: 'float', allowNull: true},
             'theory_full', 'theory_pass', 'practical_full', 'practical_pass']
});

Ext.define('RO.model.Check', {
    extend: 'Ext.data.Model',
    fields: ['roll', 'name', 'class_name', 'letter', 'reason_text', 'detail_text',
             {name: 'student_id', type: 'int'},
             {name: 'priority', type: 'int'},
             {name: 'gpa', type: 'float'},
             {name: 'subjects_to_check', defaultValue: []}]
});

/* ---------- shared renderers ---------- */

function markCell(v) {
    return v === null || v === undefined ? '<span class="ro-absent">absent</span>' : Ext.util.Format.number(v, '0.##');
}

function gradeCell(v) {
    if (!v) { return ''; }
    var cls = v === 'F' ? 'ro-pill ro-pill-fail' : (v === 'A+' ? 'ro-pill ro-pill-top' : 'ro-pill');
    return '<span class="' + cls + '">' + v + '</span>';
}

function componentCell(obtained, full, pass) {
    if (full === null || full === undefined || full === 0) { return '<span class="ro-none">&mdash;</span>'; }
    if (obtained === null || obtained === undefined) { return '<span class="ro-absent">absent</span>'; }
    var failed = obtained < pass;
    return '<span class="ro-mark' + (failed ? ' ro-mark-fail' : '') + '">' +
           Ext.util.Format.number(obtained, '0.##') + '<i>/' + full + '</i></span>' +
           '<span class="ro-passline">pass ' + pass + '</span>';
}

Ext.application({
    name: 'RO',
    launch: function () {

        var classStore = Ext.create('Ext.data.Store', {
            fields: ['id', 'name'],
            proxy: {type: 'ajax', url: API + '/classes', reader: {type: 'json', rootProperty: 'data'}},
            autoLoad: true
        });

        var studentStore = Ext.create('Ext.data.Store', {
            model: 'RO.model.Student',
            proxy: {
                type: 'ajax', url: API + '/students',
                extraParams: {limit: 500},
                reader: {type: 'json', rootProperty: 'data', totalProperty: 'total'}
            },
            autoLoad: true
        });

        var subjectStore = Ext.create('Ext.data.Store', {model: 'RO.model.Subject'});

        var checkStore = Ext.create('Ext.data.Store', {
            model: 'RO.model.Check',
            proxy: {type: 'ajax', url: API + '/reports/verification',
                    reader: {type: 'json', rootProperty: 'data'}},
            autoLoad: true
        });

        /* ---------- the trace panel ---------- */

        var traceHeader = Ext.create('Ext.Component', {
            cls: 'ro-trace-head',
            html: '<div class="ro-empty">Pick a student to see how their result was worked out.</div>'
        });

        var traceGrid = Ext.create('Ext.grid.Panel', {
            store: subjectStore,
            flex: 1,
            cls: 'ro-trace-grid',
            hidden: true,
            columns: [
                {text: 'Subject', dataIndex: 'name', flex: 1.1, renderer: function (v, m, r) {
                    return v + (r.get('is_optional') ? ' <span class="ro-tag">optional</span>' : '');
                }},
                {text: 'Theory', width: 110, align: 'right', sortable: false, renderer: function (v, m, r) {
                    return componentCell(r.get('theory_obtained'), r.get('theory_full'), r.get('theory_pass'));
                }},
                {text: 'Practical', width: 110, align: 'right', sortable: false, renderer: function (v, m, r) {
                    return componentCell(r.get('practical_obtained'), r.get('practical_full'), r.get('practical_pass'));
                }},
                {text: 'Mark used', dataIndex: 'mark_used', width: 95, align: 'right', renderer: markCell},
                {text: 'Point', dataIndex: 'grade_point', width: 70, align: 'right',
                 renderer: function (v) { return Ext.util.Format.number(v, '0.00'); }},
                {text: 'Grade', dataIndex: 'letter', width: 80, align: 'center', renderer: gradeCell},
                {text: 'Rule that decided it', dataIndex: 'rule_text', flex: 2, renderer: function (v, m, r) {
                    m.tdCls = r.get('passed') ? '' : 'ro-row-fail';
                    return '<span class="ro-rule">' + r.get('rule_code') + '</span> ' + Ext.String.htmlEncode(v);
                }}
            ]
        });

        function showTrace(studentId) {
            Ext.Ajax.request({
                url: API + '/students/' + studentId + '/result',
                success: function (res) {
                    var d = Ext.decode(res.responseText).data;
                    subjectStore.loadData(d.subjects);
                    traceGrid.show();

                    var notes = d.gpa_rule_notes.map(function (n, i) {
                        return '<li><span class="ro-rule">' + d.gpa_rule_codes[i] + '</span> ' +
                               Ext.String.htmlEncode(n) + '</li>';
                    }).join('');

                    var causedBy = '';
                    if (!d.passed) {
                        causedBy = '<div class="ro-cause"><b>Result turned on:</b> ' +
                                   Ext.String.htmlEncode(d.failing_subjects.join(', ')) +
                                   '. Average across the six compulsory subjects was ' +
                                   Ext.util.Format.number(d.compulsory_average_mark, '0.00') + '.</div>';
                    }

                    var flags = d.flag_labels.length
                        ? '<div class="ro-flags">' + d.flag_labels.map(function (f) {
                              return '<span class="ro-flag">' + Ext.String.htmlEncode(f) + '</span>';
                          }).join('') + '</div>'
                        : '';

                    traceHeader.setHtml(
                        '<div class="ro-trace-top">' +
                          '<div class="ro-who"><span class="ro-roll">' + d.roll + '</span>' +
                            '<h2>' + Ext.String.htmlEncode(d.name) + '</h2>' +
                            '<p>' + Ext.String.htmlEncode(d.class_name) + '</p></div>' +
                          '<div class="ro-gpa' + (d.passed ? '' : ' ro-gpa-fail') + '">' +
                            '<span class="ro-gpa-num">' + Ext.util.Format.number(d.gpa, '0.00') + '</span>' +
                            '<span class="ro-gpa-letter">' + d.letter + '</span>' +
                            '<span class="ro-gpa-label">GPA</span></div>' +
                        '</div>' + causedBy +
                        '<ul class="ro-notes">' + notes + '</ul>' + flags
                    );
                }
            });
        }

        var studentGrid = Ext.create('Ext.grid.Panel', {
            title: 'Students',
            store: studentStore,
            width: 520,
            split: true,
            region: 'west',
            columns: [
                {text: 'Roll', dataIndex: 'roll', width: 90},
                {text: 'Name', dataIndex: 'name', flex: 1, renderer: function (v, m, r) {
                    return Ext.String.htmlEncode(v) +
                        (r.get('note') ? ' <span class="ro-tag ro-tag-edge">edge case</span>' : '');
                }},
                {text: 'GPA', dataIndex: 'gpa', width: 70, align: 'right', renderer: function (v) {
                    return v === null ? '<span class="ro-none">not run</span>' : Ext.util.Format.number(v, '0.00');
                }},
                {text: 'Grade', dataIndex: 'letter', width: 75, align: 'center', renderer: gradeCell}
            ],
            listeners: {
                select: function (grid, record) { showTrace(record.get('id')); }
            },
            tbar: [
                {xtype: 'combo', fieldLabel: 'Class', labelWidth: 40, width: 260, store: classStore,
                 displayField: 'name', valueField: 'id', queryMode: 'local', editable: false,
                 emptyText: 'All classes',
                 listeners: {
                     select: function (cb, rec) {
                         studentStore.getProxy().setExtraParam('class_id', rec.get('id'));
                         checkStore.getProxy().setExtraParam('class_id', rec.get('id'));
                         studentStore.load(); checkStore.load();
                     }
                 }},
                {xtype: 'textfield', emptyText: 'Search roll or name', flex: 1, enableKeyEvents: true,
                 listeners: {
                     keyup: Ext.Function.createBuffered(function (f) {
                         studentStore.getProxy().setExtraParam('q', f.getValue());
                         studentStore.load();
                     }, 300)
                 }}
            ]
        });

        var tracePanel = Ext.create('Ext.panel.Panel', {
            region: 'center',
            layout: {type: 'vbox', align: 'stretch'},
            cls: 'ro-trace',
            items: [traceHeader, traceGrid]
        });

        var checkGrid = Ext.create('Ext.grid.Panel', {
            title: 'Checking list',
            store: checkStore,
            cls: 'ro-check-grid',
            columns: [
                {text: '', dataIndex: 'priority', width: 46, align: 'center', renderer: function (v) {
                    return '<span class="ro-prio ro-prio-' + v + '">' + v + '</span>';
                }},
                {text: 'Roll', dataIndex: 'roll', width: 90},
                {text: 'Name', dataIndex: 'name', width: 170},
                {text: 'Class', dataIndex: 'class_name', width: 150},
                {text: 'GPA', dataIndex: 'gpa', width: 65, align: 'right',
                 renderer: function (v) { return Ext.util.Format.number(v, '0.00'); }},
                {text: 'Grade', dataIndex: 'letter', width: 75, align: 'center', renderer: gradeCell},
                {text: 'Why it needs checking', dataIndex: 'reason_text', flex: 1.2},
                {text: 'Subjects to check', dataIndex: 'subjects_to_check', width: 190,
                 renderer: function (v) { return (v || []).join(', '); }},
                {text: 'What to verify', dataIndex: 'detail_text', flex: 1.6},
                {text: 'Checked by', width: 110, sortable: false,
                 renderer: function () { return '<span class="ro-signline"></span>'; }}
            ],
            tbar: [
                {xtype: 'component', cls: 'ro-hint',
                 html: 'Priority 1 turned the result. Priority 2 applied or withheld a rule.'},
                '->',
                {xtype: 'checkbox', boxLabel: 'Include routine optional-subject changes',
                 listeners: {
                     change: function (cb, v) {
                         checkStore.getProxy().setExtraParam('include_routine', v);
                         checkStore.load();
                     }
                 }},
                {text: 'Download CSV', iconCls: 'x-fa fa-download', handler: function () {
                    var p = checkStore.getProxy().getExtraParams();
                    window.open(API + '/reports/verification.csv?' + Ext.Object.toQueryString(p));
                }}
            ],
            listeners: {
                select: function (g, r) {
                    mainTabs.setActiveTab(0);
                    var rec = studentStore.findRecord('id', r.get('student_id'));
                    if (rec) { studentGrid.getSelectionModel().select(rec); }
                    else { showTrace(r.get('student_id')); }
                }
            }
        });

        var mainTabs = Ext.create('Ext.tab.Panel', {
            region: 'center',
            items: [
                {title: 'Results and trace', layout: 'border', items: [studentGrid, tracePanel]},
                checkGrid
            ]
        });

        var viewport = Ext.create('Ext.container.Viewport', {
            layout: 'border',
            items: [
                {
                    region: 'north', xtype: 'toolbar', cls: 'ro-header', height: 56,
                    items: [
                        {xtype: 'component', flex: 1, html: '<span class="ro-mark-logo">GP</span>' +
                            '<span class="ro-title">Result Office</span>' +
                            '<span class="ro-sub">Six compulsory subjects, one optional fourth subject</span>'},
                        '->',
                        {text: 'Run the engine', cls: 'ro-run', handler: function (btn) {
                            btn.setDisabled(true).setText('Running');
                            var p = studentStore.getProxy().getExtraParams();
                            Ext.Ajax.request({
                                url: API + '/results/compute' + (p.class_id ? '?class_id=' + p.class_id : ''),
                                method: 'POST',
                                callback: function () { btn.setDisabled(false).setText('Run the engine'); },
                                success: function (res) {
                                    var n = Ext.decode(res.responseText).data.processed;
                                    studentStore.load();
                                    checkStore.load();
                                    if (Ext.toast) { Ext.toast(n + ' results computed and stored.'); }
                                    else { Ext.Msg.alert('Done', n + ' results computed and stored.'); }
                                },
                                failure: function () {
                                    Ext.Msg.alert('Engine did not run',
                                        'The API did not respond. Start it with: uvicorn app.main:app --reload');
                                }
                            });
                        }}
                    ]
                },
                mainTabs
            ]
        });

        function relayout() { if (viewport) { viewport.updateLayout(); } }

        if (document.fonts && document.fonts.ready) {
            document.fonts.ready.then(relayout);
        }
        Ext.defer(relayout, 400);
        Ext.on('resize', relayout);
    }
});
