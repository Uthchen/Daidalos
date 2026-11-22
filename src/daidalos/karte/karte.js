/* Daidalos-Karte. Liest die eingebettete Messung (daidalos.json) und Deutung (deutung.json)
   und zeichnet sie mit Cytoscape.js und ELK. Rechnet nichts Neues aus, nur Darstellung:
   Layout, Verdichtung eingeklappter Teile, Hervorhebung.

   Aufbau (A05 ergänzt hier, ohne umzubauen):
   1. Daten und Index     4. Zeichnen und Layout   7. Seitenleiste
   2. Zustand             5. Stil                  8. Sprungadressen
   3. Elemente je Ebene   6. Hervorheben           9. Bedienung und Start */
(function () {
  'use strict';

  // ------------------------------------------------------------ 1. Daten und Index
  const M = JSON.parse(document.getElementById('daidalos-daten').textContent);
  const D = JSON.parse(document.getElementById('daidalos-deutung').textContent) ||
    { schema: 1, beschreibungen: {}, bereiche: [], einschaetzungen: [], kanten: {} };

  const knoten = new Map(M.knoten.map(k => [k.id, k]));
  const kanteNachId = new Map(M.kanten.map(k => [k.id, k]));
  const befundNachId = new Map(M.befunde.map(b => [b.id, b]));
  const einschaetzung = new Map(D.einschaetzungen.map(e => [e.befund, e]));

  const CODE_SPRACHEN = new Set(['kotlin', 'java', 'c', 'cpp']);
  const GROSS_AB = 150;

  const gruppen = M.knoten.filter(k => k.art === 'modul' || k.art === 'ordner');
  const pakete = M.knoten.filter(k => k.art === 'paket');
  const mitKante = new Set();
  M.kanten.forEach(k => { if (k.art === 'nutzt' || k.art === 'jni') { mitKante.add(k.von); mitKante.add(k.nach); } });
  // Auf der Karte: Quellcode-Dateien und jede Datei mit einer Kante.
  const kartenDateien = M.knoten.filter(k => k.art === 'datei' && (CODE_SPRACHEN.has(k.sprache) || mitKante.has(k.id)));
  const gross = kartenDateien.length > GROSS_AB;
  const behaelter = d => d.modul || d.ordner;
  const ebeneVon = k => k.art === 'datei' ? 'datei' : k.art === 'paket' ? 'paket' : 'modul';

  const paketRollen = new Map();
  M.knoten.forEach(d => {
    if (d.art !== 'datei' || !d.paket) return;
    if (!paketRollen.has(d.paket)) paketRollen.set(d.paket, new Set());
    paketRollen.get(d.paket).add(d.rolle);
  });

  function name(id) {
    const k = knoten.get(id);
    if (!k) return id;
    if (k.art === 'modul') return k.gradle_pfad;
    if (k.art === 'paket') return k.name;
    if (k.art === 'ordner') return k.pfad === '.' ? '(Wurzel)' : k.pfad + '/';
    return k.pfad.split('/').pop();
  }

  // ------------------------------------------------------------ 2. Zustand
  const zustand = {
    ebene: 'modul',
    mitTests: false,
    // Kantenarten je Ebene; auf der Modulebene wahlweise Gradle oder verdichtete nutzt-Kanten.
    arten: { modul: { gradle: true, nutzt: false, jni: false }, paket: { gradle: false, nutzt: true, jni: false }, datei: { gradle: false, nutzt: true, jni: true } },
    zyklen: true,
    offen: new Set(),          // ausgeklappte Module auf der Dateiebene (nur bei großen Projekten)
    zuletztModul: null,
    auswahl: null              // { art: 'knoten' | 'befund', id }
  };
  const ARTEN_JE_EBENE = { modul: ['gradle', 'nutzt'], paket: ['nutzt'], datei: ['nutzt', 'jni'] };

  function sichtbareDatei(d) { return !d.fremd && (zustand.mitTests || d.rolle !== 'test'); }
  function sichtbaresPaket(p) {
    if (p.fremd) return false;
    const rollen = paketRollen.get(p.id) || new Set(['produktiv']);
    return zustand.mitTests || rollen.has('produktiv');
  }
  function rolleOk(k) { return zustand.mitTests || k.rolle === 'produktiv'; }

  // Standard beim ersten Öffnen der Dateiebene: zuletzt gewähltes Modul, sonst das größte.
  function standardOffen() {
    if (!gross || zustand.offen.size) return;
    if (zustand.zuletztModul) { zustand.offen.add(zustand.zuletztModul); return; }
    const zahl = new Map();
    kartenDateien.forEach(d => { if (sichtbareDatei(d)) zahl.set(behaelter(d), (zahl.get(behaelter(d)) || 0) + 1); });
    let best = null;
    gruppen.forEach(g => { if ((zahl.get(g.id) || 0) > (best ? zahl.get(best) : 0)) best = g.id; });
    if (best) zustand.offen.add(best);
  }
  const istOffen = g => !gross || zustand.offen.has(g);

  // ------------------------------------------------------------ 3. Elemente je Ebene
  const messer = document.createElement('canvas').getContext('2d');
  function breiteVon(zeilen, schrift) {
    messer.font = schrift;
    return Math.max(...zeilen.map(z => messer.measureText(z).width));
  }
  function blatt(id, zeilen, typ, extra, mono) {
    const schrift = (mono ? '11px ' + tok('--mono') : '11.5px ' + tok('--font'));
    const w = Math.max(80, Math.ceil(breiteVon(zeilen, schrift)) + 28);
    return { group: 'nodes', data: Object.assign({ id, label: zeilen.join('\n'), typ, w, h: 16 + 16 * zeilen.length }, extra) };
  }
  const breite = g => 1 + Math.min(4, Math.log2(1 + (g || 1)) * 0.7);

  // Kanten zusammenführen: gleiche Enden und Art werden eine Kante mit Summe der Gewichte.
  function sammler() {
    const liste = new Map();
    return {
      add(quelle, ziel, art, k, verdichtet) {
        if (quelle === ziel) return;
        const id = verdichtet ? 'v:' + art + ':' + quelle + '->' + ziel : k.id;
        let e = liste.get(id);
        if (!e) {
          e = { group: 'edges', data: { id, source: quelle, target: ziel, art, gewicht: 0, kanten: [], unsicher: true, verdichtet: !!verdichtet } };
          liste.set(id, e);
        }
        e.data.gewicht += k.gewicht || 1;
        e.data.kanten.push(k.id);
        e.data.unsicher = e.data.unsicher && k.sicher === false;
      },
      werte() { return [...liste.values()].sort((a, b) => a.data.id < b.data.id ? -1 : a.data.id > b.data.id ? 1 : 0); }
    };
  }

  function zyklusKanten() {
    // Kanten-Ids der Zyklen, die zur aktuellen Ansicht passen.
    const ids = new Set();
    M.befunde.forEach(b => {
      if (b.regel !== 'zyklus' || b.beleg.ebene !== zustand.ebene) return;
      if (b.beleg.rolle !== 'produktiv' && !zustand.mitTests) return;
      b.beleg.kanten.forEach(id => ids.add(id));
    });
    return ids;
  }

  function elemente() {
    const els = [];
    const kanten = sammler();
    const art = zustand.arten[zustand.ebene];
    if (zustand.ebene === 'modul') {
      gruppen.forEach(g => els.push(blatt(g.id, [name(g.id), (g.dateien || 0) + ' Dateien · ' + (g.zeilen || 0) + ' Zeilen'], 'gruppe', { ref: g.id, art: g.art })));
      M.kanten.forEach(k => {
        if (art.gradle && k.art.startsWith('gradle-') && rolleOk(k)) kanten.add(k.von, k.nach, k.art, k);
        if (art.nutzt && k.art === 'nutzt' && rolleOk(k) && istGruppe(k.von) && istGruppe(k.nach)) kanten.add(k.von, k.nach, 'nutzt', k);
      });
    } else if (zustand.ebene === 'paket') {
      const fremdBox = new Map();
      gruppen.forEach(g => els.push({ group: 'nodes', data: { id: g.id, label: name(g.id), typ: 'gruppe', ref: g.id, art: g.art } }));
      pakete.forEach(p => {
        const g = p.modul || p.ordner;
        if (p.fremd) { fremdBox.set(p.id, 'fremd:' + g); return; }
        if (sichtbaresPaket(p)) els.push(blatt(p.id, [p.name], 'paket', { parent: g, ref: p.id }, true));
      });
      zaehleFremd(fremdBox, 'Pakete').forEach(e => els.push(e));
      ohneLeereBehaelter(els);
      const abb = id => fremdBox.get(id) || id;
      const da = new Set(els.map(e => e.data.id));
      if (art.nutzt) M.kanten.forEach(k => {
        if (k.art !== 'nutzt' || !rolleOk(k) || !k.von.startsWith('paket:')) return;
        const q = abb(k.von), z = abb(k.nach);
        if (da.has(q) && da.has(z)) kanten.add(q, z, 'nutzt', k, q !== k.von || z !== k.nach);
      });
    } else {
      standardOffen();
      const ort = new Map();       // Datei-Id → sichtbarer Knoten (Datei, Fremd-Kasten oder Modul)
      const fremd = new Map();
      const sichtbarePakete = new Set();
      const anzahl = new Map();
      kartenDateien.forEach(d => { if (sichtbareDatei(d)) anzahl.set(behaelter(d), (anzahl.get(behaelter(d)) || 0) + 1); });
      gruppen.forEach(g => {
        if (istOffen(g.id)) els.push({ group: 'nodes', data: { id: g.id, label: name(g.id), typ: 'gruppe', ref: g.id, art: g.art } });
        else els.push(blatt(g.id, [name(g.id), (anzahl.get(g.id) || 0) + ' Dateien · eingeklappt'], 'zu', { ref: g.id, art: g.art }));
      });
      kartenDateien.forEach(d => {
        const g = behaelter(d);
        if (!istOffen(g)) { if (sichtbareDatei(d) || d.fremd) ort.set(d.id, g); return; }
        if (d.fremd) { fremd.set(d.id, 'fremd:' + g); ort.set(d.id, 'fremd:' + g); return; }
        if (!sichtbareDatei(d)) return;
        const eltern = d.paket || g;
        if (d.paket) sichtbarePakete.add(d.paket);
        els.push(blatt(d.id, [name(d.id)], 'datei', { parent: eltern, ref: d.id, rolle: d.rolle }));
        ort.set(d.id, d.id);
      });
      pakete.forEach(p => { if (sichtbarePakete.has(p.id)) els.push({ group: 'nodes', data: { id: p.id, label: p.name, typ: 'paket', parent: p.modul || p.ordner, ref: p.id } }); });
      zaehleFremd(fremd, 'Dateien').forEach(e => els.push(e));
      ohneLeereBehaelter(els);
      M.kanten.forEach(k => {
        if (!((k.art === 'nutzt' && art.nutzt) || (k.art === 'jni' && art.jni)) || !rolleOk(k) || !k.von.startsWith('datei:')) return;
        const q = ort.get(k.von), z = ort.get(k.nach);
        if (q && z) kanten.add(q, z, k.art, k, q !== k.von || z !== k.nach);
      });
    }
    const zyk = zyklusKanten();
    const mitLabel = zustand.ebene !== 'datei';
    kanten.werte().forEach(e => {
      const d = e.data;
      d.breite = breite(d.gewicht);
      d.label = mitLabel ? kurzArt(d.art) + ' · ' + d.gewicht : '';
      const cls = [];
      if (d.unsicher) cls.push('unsicher');
      if (d.verdichtet) cls.push('verdichtet');
      if (d.kanten.some(id => zyk.has(id))) cls.push('zyk');
      if (d.art === 'jni') cls.push('jni');
      e.classes = cls.join(' ');
      els.push(e);
    });
    els.forEach(e => {
      if (e.group !== 'nodes') return;
      const k = knoten.get(e.data.id);
      const cls = [];
      if (e.data.rolle === 'test') cls.push('test');
      if (e.data.typ === 'fremd') cls.push('fremd');
      if (k && k.art === 'ordner') cls.push('ordner');
      e.classes = cls.join(' ');
    });
    return els;
  }
  // Module und Ordner ohne sichtbaren Inhalt fallen auf Paket- und Dateiebene weg.
  function ohneLeereBehaelter(els) {
    const eltern = new Set(els.map(e => e.data.parent).filter(Boolean));
    for (let i = els.length - 1; i >= 0; i--) {
      const d = els[i].data;
      if (d.typ === 'gruppe' && !eltern.has(d.id)) els.splice(i, 1);
    }
  }
  function istGruppe(id) { const k = knoten.get(id); return !!k && (k.art === 'modul' || k.art === 'ordner'); }
  function kurzArt(art) { return art.startsWith('gradle-') ? art.slice(7) : art; }
  function zaehleFremd(abbildung, was) {
    const zahl = new Map();
    abbildung.forEach(box => zahl.set(box, (zahl.get(box) || 0) + 1));
    return [...zahl.keys()].sort().map(box => blatt(box, ['Fremd · ' + zahl.get(box) + ' ' + was], 'fremd', { parent: box.slice(6), ref: box.slice(6) }));
  }

  // ------------------------------------------------------------ 4. Zeichnen und Layout
  const ruhig = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const cy = cytoscape({
    container: document.getElementById('cy'), elements: [], style: [],
    wheelSensitivity: 0.3, minZoom: 0.03, maxZoom: 3, boxSelectionEnabled: false, autoungrabify: true
  });
  const layoutCache = new Map();
  const zeiten = {};
  let lauf = 0;

  function layoutSchluessel() {
    const a = zustand.arten[zustand.ebene];
    return [zustand.ebene, zustand.mitTests ? 't' : 'p', a.gradle ? 'g' : '', a.nutzt ? 'n' : '', a.jni ? 'j' : '',
      zustand.ebene === 'datei' && gross ? [...zustand.offen].sort().join(',') : ''].join('|');
  }
  const ELK = {
    algorithm: 'layered',
    'elk.direction': 'DOWN',
    'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
    'elk.layered.spacing.nodeNodeBetweenLayers': 46,
    'elk.spacing.nodeNode': 22,
    'elk.layered.spacing.edgeNodeBetweenLayers': 16,
    'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
    'elk.layered.crossingMinimization.forceNodeModelOrder': false,
    'elk.randomSeed': 1
  };

  // Zeichnet die aktuelle Ebene neu. Liefert ein Promise, das nach dem Layout erfüllt ist.
  function zeichne() {
    const nr = ++lauf;
    const schluessel = layoutSchluessel();
    const beginn = performance.now();
    document.documentElement.dataset.zustand = 'rechnet';
    cy.batch(() => { cy.elements().remove(); cy.add(elemente()); });
    cy.style(stil());
    zeigeSchalter();
    return new Promise(fertig => {
      const ende = () => {
        if (nr !== lauf) return fertig(false);
        einpassen(cy.elements(), 30);
        zeiten[schluessel] = Math.round(performance.now() - beginn);
        document.getElementById('lade').hidden = true;
        document.documentElement.dataset.zustand = 'bereit';
        fertig(true);
      };
      const gespeichert = layoutCache.get(schluessel);
      if (gespeichert) {
        cy.layout({ name: 'preset', positions: n => gespeichert[n.id()], fit: false }).run();
        ende();
        return;
      }
      document.getElementById('lade').hidden = false;
      const layout = cy.layout({
        name: 'elk', fit: false, animate: false, nodeDimensionsIncludeLabels: false,
        elk: ELK,
        nodeLayoutOptions: n => n.isParent() ? { 'elk.padding': '[top=30,left=14,bottom=14,right=14]' } : undefined
      });
      layout.one('layoutstop', () => {
        if (nr === lauf) {
          const pos = {};
          cy.nodes().forEach(n => { if (!n.isParent()) pos[n.id()] = Object.assign({}, n.position()); });
          layoutCache.set(schluessel, pos);
        }
        ende();
      });
      // Das Layout erst nach dem nächsten Bild starten, damit „Layout wird berechnet“ sichtbar wird.
      requestAnimationFrame(() => setTimeout(() => { if (nr === lauf) layout.run(); else fertig(false); }, 0));
    });
  }

  // ------------------------------------------------------------ 5. Stil
  const tok = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  function stil() {
    const f = tok('--font'), mono = tok('--mono');
    const regeln = [
      { selector: 'node', style: { 'font-family': f, color: tok('--fg'), 'text-wrap': 'wrap', 'font-size': 11.5, 'text-valign': 'center', 'text-halign': 'center', shape: 'round-rectangle', 'background-color': tok('--node'), 'border-width': 1, 'border-color': tok('--edge'), label: 'data(label)', 'line-height': 1.35 } },
      { selector: 'node[w]', style: { width: 'data(w)', height: 'data(h)' } },
      { selector: 'node[typ="gruppe"]', style: { 'background-color': tok('--mod'), 'border-width': 1.5, 'font-size': 13, 'font-weight': 600 } },
      { selector: 'node[typ="gruppe"]:parent', style: { 'text-valign': 'top', 'text-margin-y': -5, padding: 14 } },
      { selector: 'node[typ="gruppe"]:childless', style: { 'background-color': tok('--node') } },
      { selector: 'node[typ="zu"]', style: { 'background-color': tok('--mod'), 'border-width': 1.5, 'border-style': 'dashed', 'font-weight': 600 } },
      { selector: 'node[typ="paket"]', style: { 'font-family': mono, 'font-size': 11 } },
      { selector: 'node[typ="paket"]:parent', style: { 'background-color': tok('--pkg'), 'border-color': tok('--line'), 'text-valign': 'top', 'text-margin-y': -4, color: tok('--muted'), 'font-size': 10.5, padding: 12 } },
      { selector: 'node.ordner', style: { 'border-style': 'dotted' } },
      { selector: 'node.test', style: { 'border-style': 'dashed', 'font-style': 'italic', color: tok('--muted') } },
      { selector: 'node.fremd', style: { 'background-color': tok('--pkg'), 'border-style': 'dotted', color: tok('--muted'), 'font-style': 'italic' } },
      { selector: 'edge', style: { 'curve-style': 'bezier', width: 'data(breite)', 'line-color': tok('--edge'), 'target-arrow-color': tok('--edge'), 'target-arrow-shape': 'triangle', 'arrow-scale': 0.9, label: 'data(label)', 'font-size': 10, color: tok('--muted'), 'font-family': f, 'text-background-color': tok('--panel'), 'text-background-opacity': 0.9, 'text-background-padding': 2, 'text-rotation': 'autorotate', opacity: 0.85 } },
      { selector: 'edge.jni', style: { 'line-color': tok('--adr'), 'target-arrow-color': tok('--adr') } },
      { selector: 'edge.unsicher', style: { 'line-style': 'dashed', 'line-dash-pattern': [6, 4] } },
      { selector: 'edge.verdichtet', style: { 'line-style': 'dashed', 'line-dash-pattern': [2, 4] } },
      { selector: 'node.blass, edge.blass', style: { opacity: parseFloat(tok('--o-blass')) } },
      { selector: 'node.hl', style: { 'overlay-color': tok('--accent'), 'overlay-opacity': 0.14, 'overlay-padding': 5 } },
      { selector: 'edge.hl', style: { 'line-color': tok('--accent'), 'target-arrow-color': tok('--accent'), width: 3, opacity: 1 } },
      { selector: 'node.gewaehlt', style: { 'border-color': tok('--accent'), 'border-width': 3 } },
      { selector: 'node.einstieg', style: { 'border-color': tok('--warn'), 'border-width': 3.5 } },
      { selector: 'edge.einstieg', style: { 'line-color': tok('--warn'), 'target-arrow-color': tok('--warn'), width: 2.4, opacity: 1, label: 'Einstieg', color: tok('--warn') } }
    ];
    if (zustand.zyklen) {
      regeln.push({ selector: 'edge.zyk', style: { 'line-color': tok('--crit'), 'target-arrow-color': tok('--crit'), opacity: 1 } });
      regeln.push({ selector: 'edge.zyk.hl', style: { width: 3 } });
    }
    regeln.push({ selector: 'edge.trenn', style: { 'line-color': tok('--crit'), 'target-arrow-color': tok('--crit'), width: 6, opacity: 1, label: 'data(trennText)', color: tok('--crit'), 'font-weight': 700, 'font-size': 12 } });
    return regeln;
  }

  // ------------------------------------------------------------ 6. Hervorheben
  const pfadinfo = document.getElementById('pfadinfo');
  function leeren() {
    cy.elements().removeClass('blass hl gewaehlt einstieg trenn');
    cy.edges().removeData('trennText');
    pfadinfo.hidden = true;
  }
  const kantenMit = ids => { const s = new Set(ids); return cy.edges().filter(e => e.data('kanten').some(id => s.has(id))); };
  const MAX_ZOOM_PASSEN = 1.3;
  // Einpassen ohne zu starke Vergrößerung bei wenigen Knoten.
  function ziel(eles, padding) {
    const bb = eles.boundingBox();
    const w = Math.max(1, cy.width() - 2 * padding), h = Math.max(1, cy.height() - 2 * padding);
    const zoom = Math.min(MAX_ZOOM_PASSEN, w / Math.max(1, bb.w), h / Math.max(1, bb.h));
    return { zoom, pan: { x: cy.width() / 2 - zoom * (bb.x1 + bb.w / 2), y: cy.height() / 2 - zoom * (bb.y1 + bb.h / 2) } };
  }
  function einpassen(eles, padding) { if (eles.nonempty()) cy.viewport(ziel(eles, padding)); }
  function passen(eles, padding) {
    if (!eles.nonempty()) return;
    cy.stop(true, true);
    if (ruhig()) einpassen(eles, padding); else cy.animate(Object.assign(ziel(eles, padding), { duration: 300 }));
  }

  function hebeKnotenHervor(id) {
    leeren();
    const n = cy.getElementById(id);
    if (!n.nonempty()) return;
    n.addClass('gewaehlt hl');
    n.connectedEdges().addClass('hl');
    passen(n.union(n.neighborhood()), 60);
  }

  function hebeZyklusHervor(b) {
    leeren();
    const mitglieder = cy.collection(b.beleg.knoten.map(id => cy.getElementById(id)).filter(e => e.nonempty()));
    const ring = kantenMit(b.beleg.kanten);
    const einstiege = new Set(b.beleg.einstiege.map(e => e.knoten));
    const quellen = new Set(b.beleg.einstiege.flatMap(e => e.quellen));
    const rein = cy.edges().filter(e => einstiege.has(e.target().id()) && !ring.contains(e) &&
      e.data('kanten').some(id => { const k = kanteNachId.get(id); return k && quellen.has(k.von); }));
    cy.elements().not(mitglieder).not(mitglieder.ancestors()).not(ring).not(rein).not(rein.sources()).not(rein.sources().ancestors()).addClass('blass');
    mitglieder.addClass('hl');
    ring.addClass('hl');
    mitglieder.filter(n => einstiege.has(n.id())).addClass('einstieg');
    rein.addClass('einstieg');
    const trennIds = b.beleg.trennstelle ? [b.beleg.trennstelle] : (b.beleg.kleinste_trennmenge || []);
    const trenn = kantenMit(trennIds).filter(e => ring.contains(e));
    trenn.addClass('trenn').data('trennText', b.beleg.trennstelle ? 'günstigste Trennstelle' : 'kleinste Trennmenge');
    const teile = [befundTitel(b)];
    if (b.beleg.einstiege.length) teile.push('Einstieg: ' + b.beleg.einstiege.map(e => name(e.knoten) + ' (von ' + e.quellen.map(name).join(', ') + ')').join('; '));
    if (b.beleg.trennstelle) teile.push('günstigste Trennstelle: ' + kanteText(b.beleg.trennstelle));
    else if (b.beleg.kleinste_trennmenge) teile.push('kleinste Trennmenge: ' + b.beleg.kleinste_trennmenge.map(kanteText).join(', '));
    pfadinfo.textContent = teile.join(' · ');
    pfadinfo.hidden = false;
    passen(mitglieder.union(ring), 70);
  }
  function kanteText(id) {
    const k = kanteNachId.get(id);
    return k ? name(k.von) + ' → ' + name(k.nach) + ' (Gewicht ' + k.gewicht + ')' : id;
  }

  // ------------------------------------------------------------ 7. Seitenleiste
  const seite = document.getElementById('seite');
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const EBENEN_TEXT = { datei: 'Dateien', paket: 'Paketen', modul: 'Modulen' };
  const zahl = v => v === null || v === undefined ? '–' : String(v).replace('.', ',');

  function befundTitel(b) {
    const beleg = b.beleg;
    if (b.regel === 'zyklus') {
      let t = 'Zyklus aus ' + beleg.knoten.length + ' ' + EBENEN_TEXT[beleg.ebene];
      if (beleg.kantenart) t += ' (' + beleg.kantenart + ')';
      return t + (beleg.rolle === 'mit-tests' ? ' mit Tests' : '');
    }
    if (b.regel === 'jni-ohne-gegenstueck') return 'JNI ohne Gegenstück';
    if (b.regel === 'unaufgeloest') return beleg.importe.length + ' unaufgelöste Importe';
    return b.regel;
  }
  function befundBeleg(b) {
    if (b.regel === 'zyklus') return b.beleg.knoten.map(name).join(' · ');
    if (b.regel === 'jni-ohne-gegenstueck') return b.beleg.funktion + ' (' + (b.beleg.seite === 'c' ? 'C' : 'Kotlin') + ', Zeile ' + b.beleg.zeile + ')';
    if (b.regel === 'unaufgeloest') return name(b.knoten[0]) + ': ' + b.beleg.importe.map(i => i.import).join(', ');
    return b.knoten.map(name).join(', ');
  }
  const farbe = b => b.regel === 'zyklus' ? 'crit' : 'warn';

  function befundKnopf(b, nr) {
    const e = einschaetzung.get(b.id);
    const titel = e ? e.titel : befundTitel(b);
    const unter = e ? (e.vorschlag || e.begruendung) : '';
    const aktuell = zustand.auswahl && zustand.auswahl.art === 'befund' && zustand.auswahl.id === b.id;
    return `<li><button type="button" data-befund="${esc(b.id)}"${aktuell ? ' aria-current="true"' : ''}><span class="prio ${farbe(b)}">${esc(nr)}</span><span class="bt">${esc(titel)}</span><span class="bm">${esc(befundBeleg(b))}</span>${unter ? `<span class="bd">${esc(unter)}</span>` : '<span></span>'}</button></li>`;
  }

  function sortierteBefunde() {
    const mitDeutung = D.einschaetzungen.map(e => befundNachId.get(e.befund)).filter(Boolean);
    const rest = M.befunde.filter(b => !einschaetzung.has(b.id));
    const rang = { zyklus: 0, 'jni-ohne-gegenstueck': 1, unaufgeloest: 2 };
    rest.sort((a, b) => (rang[a.regel] ?? 3) - (rang[b.regel] ?? 3) ||
      (b.regel === 'zyklus' ? b.knoten.length - a.knoten.length : 0) || (a.id < b.id ? -1 : 1));
    return { mitDeutung, rest };
  }

  function uebersicht() {
    const { mitDeutung, rest } = sortierteBefunde();
    const zaehle = art => M.knoten.filter(k => k.art === art).length;
    const dateienAlle = M.knoten.filter(k => k.art === 'datei');
    const dk = M.kanten.filter(k => k.art === 'nutzt' && k.von.startsWith('datei:'));
    const zyklen = { datei: 0, paket: 0, modul: 0 };
    M.befunde.forEach(b => { if (b.regel === 'zyklus') zyklen[b.beleg.ebene]++; });
    let html = `<div><h2>Überblick</h2><p class="leer">Klick auf einen Befund hebt ihn hervor, Klick auf einen Knoten zeigt Details. Doppelklick wechselt in die nächste Ebene${gross ? ' bzw. klappt auf der Dateiebene ein Modul aus oder ein' : ''}.</p></div>`;
    if (mitDeutung.length) {
      html += `<div><h3 class="quelle-d">Befunde, gewichtet <em>gedeutet · deutung.json</em></h3><ol class="befunde">${mitDeutung.map(b => befundKnopf(b, einschaetzung.get(b.id).prioritaet ?? '·')).join('')}</ol></div>`;
    }
    html += `<div><h3 class="quelle-m">Befunde <em>gemessen · daidalos.json</em></h3>${rest.length ? `<ol class="befunde">${rest.map(b => befundKnopf(b, b.regel === 'zyklus' ? b.knoten.length : '!')).join('')}</ol>` : '<p class="leer">Keine Befunde.</p>'}</div>`;
    html += `<div><h3 class="quelle-m">Auf einen Blick <em>gemessen · daidalos.json</em></h3><table>
      <tr><td>Module · Ordner · Pakete</td><td>${zaehle('modul')} · ${zaehle('ordner')} · ${zaehle('paket')}</td></tr>
      <tr><td>Dateien (fremd)</td><td>${dateienAlle.length} (${dateienAlle.filter(d => d.fremd).length})</td></tr>
      <tr><td>Zeilen</td><td>${dateienAlle.reduce((s, d) => s + (d.zeilen || 0), 0)}</td></tr>
      <tr><td>nutzt-Kanten zwischen Dateien (unsicher)</td><td>${dk.length} (${dk.filter(k => !k.sicher).length})</td></tr>
      <tr><td>Gradle-Kanten</td><td>${M.kanten.filter(k => k.art.startsWith('gradle-')).length}</td></tr>
      <tr><td>JNI-Paare</td><td>${M.kanten.filter(k => k.art === 'jni').reduce((s, k) => s + k.gewicht, 0)}</td></tr>
      <tr><td>Zyklen Datei · Paket · Modul</td><td>${zyklen.datei} · ${zyklen.paket} · ${zyklen.modul}</td></tr>
    </table></div>`;
    if (D.bereiche.length) {
      html += `<div><h3 class="quelle-d">Bereiche <em>gedeutet · deutung.json</em></h3>${D.bereiche.map(b => `<div class="bereich"><p><b>${esc(b.name)}</b></p>${b.beschreibung ? `<p class="deut">${esc(b.beschreibung)}</p>` : ''}<p class="pfad">${b.knoten.map(name).map(esc).join(' · ')}</p></div>`).join('')}</div>`;
    }
    seite.innerHTML = html;
    verdrahte();
  }

  function beschreibungHtml(id) {
    const b = D.beschreibungen[id];
    if (!b) return `<div><h3 class="quelle-d">Beschreibung <em>gedeutet · deutung.json</em></h3><p class="leer">Noch keine Beschreibung.</p></div>`;
    return `<div><h3 class="quelle-d">Beschreibung <em>gedeutet · deutung.json</em></h3><p class="deut">${esc(b.text)}</p>${b.veraltet ? '<div class="chips" style="margin-top:6px"><span class="chip warn" title="Der Knoten hat sich seit der Deutung geändert">veraltet</span></div>' : ''}</div>`;
  }

  function verbindungen(id) {
    const k = knoten.get(id);
    const passt = e => (e.art === 'nutzt' || e.art === 'jni' || e.art.startsWith('gradle-')) && rolleOk(e);
    const fmt = (e, gegen) => `<li><code>${esc(name(gegen))}</code> <span class="leer">${esc(kurzArt(e.art))} · Gewicht ${e.gewicht}${e.sicher === false ? ' · unsicher' : ''}${e.rolle === 'test' ? ' · Test' : ''}</span></li>`;
    const sortiere = (a, b) => b.gewicht - a.gewicht || (a.id < b.id ? -1 : 1);
    const raus = M.kanten.filter(e => e.von === id && passt(e)).sort(sortiere);
    const rein = M.kanten.filter(e => e.nach === id && passt(e)).sort(sortiere);
    const hinweis = k.art === 'datei' ? '' : ' (verdichtet)';
    return `<div><h3 class="quelle-m">Nutzt${hinweis} <em>${raus.length}</em></h3>${raus.length ? '<ul class="liste">' + raus.map(e => fmt(e, e.nach)).join('') + '</ul>' : '<p class="leer">nichts</p>'}</div>
      <div><h3 class="quelle-m">Wird genutzt von${hinweis} <em>${rein.length}</em></h3>${rein.length ? '<ul class="liste">' + rein.map(e => fmt(e, e.von)).join('') + '</ul>' : '<p class="leer">niemandem</p>'}</div>`;
  }

  function knotenDetails(id) {
    const k = knoten.get(id);
    if (!k) { uebersicht(); return; }
    let unter = '';
    if (k.art === 'datei') unter = k.pfad;
    else if (k.art === 'modul') unter = 'Gradle-Modul · ' + k.pfad + '/';
    else if (k.art === 'paket') unter = 'Paket in ' + name(k.modul || k.ordner);
    else unter = 'Ordner außerhalb der Module';
    const chips = [];
    if (k.sprache) chips.push(`<span class="chip">${esc(k.sprache)}</span>`);
    if (k.rolle === 'test') chips.push('<span class="chip warn">Test</span>');
    if (k.quellsatz) chips.push(`<span class="chip">${esc(k.quellsatz)}</span>`);
    if (k.fremd) chips.push('<span class="chip adr">fremd</span>');
    const m = k.metriken || {};
    const zeilen = [];
    if (k.zeilen !== undefined) zeilen.push(['Zeilen', k.zeilen]);
    if (k.dateien !== undefined) zeilen.push(['Dateien (eigene)', k.dateien]);
    zeilen.push(['Fan-in · Fan-out', zahl(m.fan_in) + ' · ' + zahl(m.fan_out)]);
    zeilen.push(['Instabilität', zahl(m.instabilitaet)]);
    const bf = M.befunde.filter(b => b.knoten.includes(id));
    seite.innerHTML = `<button type="button" class="zur" data-zurueck>← Übersicht</button>
      <div><h2>${esc(name(id))}</h2><p class="pfad">${esc(unter)}</p>${chips.length ? `<div class="chips" style="margin-top:6px">${chips.join('')}</div>` : ''}</div>
      ${beschreibungHtml(id)}
      <div><h3 class="quelle-m">Messwerte <em>gemessen · daidalos.json</em></h3><table>${zeilen.map(([a, b]) => `<tr><td>${esc(a)}</td><td>${esc(b)}</td></tr>`).join('')}</table></div>
      ${verbindungen(id)}
      ${bf.length ? `<div><h3 class="quelle-m">Befunde an diesem Knoten <em>${bf.length}</em></h3><ol class="befunde">${bf.map(b => befundKnopf(b, b.regel === 'zyklus' ? b.knoten.length : '!')).join('')}</ol></div>` : ''}`;
    verdrahte();
  }

  function befundDetails(b) {
    const e = einschaetzung.get(b.id);
    let html = `<button type="button" class="zur" data-zurueck>← Übersicht</button><div><h2>${esc(e ? e.titel : befundTitel(b))}</h2><p class="pfad">${esc(b.id)}</p></div>`;
    if (e) {
      html += `<div><h3 class="quelle-d">Einschätzung <em>gedeutet · deutung.json</em></h3><div class="deut">${e.prioritaet !== null ? `<p><b>Priorität ${esc(e.prioritaet)}</b></p>` : ''}${e.begruendung ? `<p>${esc(e.begruendung)}</p>` : ''}${e.vorschlag ? `<p style="margin-top:6px"><b>Vorschlag:</b> ${esc(e.vorschlag)}</p>` : ''}</div></div>`;
    }
    const beleg = b.beleg;
    let mess = '';
    if (b.regel === 'zyklus') {
      mess += `<table><tr><td>Ebene</td><td>${esc(beleg.ebene)}${beleg.kantenart ? ' · ' + esc(beleg.kantenart) : ''}</td></tr><tr><td>Rolle</td><td>${esc(beleg.rolle)}</td></tr><tr><td>Kanten im Zyklus</td><td>${beleg.kanten.length}</td></tr><tr><td>unsichere Kante beteiligt</td><td>${beleg.unsicher ? 'ja' : 'nein'}</td></tr></table>`;
      mess += `<p style="margin-top:8px"><b>Mitglieder</b></p><ul class="liste">${beleg.knoten.map(id => `<li><code>${esc(name(id))}</code></li>`).join('')}</ul>`;
      mess += `<p style="margin-top:8px"><b>Einstiege</b></p>${beleg.einstiege.length ? `<ul class="liste">${beleg.einstiege.map(x => `<li><code>${esc(name(x.knoten))}</code> <span class="leer">von ${x.quellen.map(name).map(esc).join(', ')}</span></li>`).join('')}</ul>` : '<p class="leer">keine</p>'}`;
      mess += `<p style="margin-top:8px"><b>Trennstelle</b></p>${beleg.trennstelle ? `<p>günstigste Trennstelle: <code>${esc(kanteText(beleg.trennstelle))}</code></p>` : beleg.kleinste_trennmenge ? `<p>keine einzelne; kleinste Trennmenge: ${beleg.kleinste_trennmenge.map(kanteText).map(t => `<code>${esc(t)}</code>`).join(', ')}</p>` : '<p class="leer">keine einzelne Trennstelle</p>'}`;
      if (beleg.enthaelt_produktiv) mess += `<p style="margin-top:8px">Enthält ${beleg.enthaelt_produktiv.length} produktive Zyklen.</p>`;
    } else if (b.regel === 'jni-ohne-gegenstueck') {
      mess += `<table><tr><td>Funktion</td><td>${esc(beleg.funktion)}</td></tr><tr><td>Seite</td><td>${beleg.seite === 'c' ? 'C/C++' : 'Kotlin'}</td></tr><tr><td>Datei</td><td>${esc(name(b.knoten[0]))}</td></tr><tr><td>Zeile</td><td>${beleg.zeile}</td></tr></table>`;
    } else if (b.regel === 'unaufgeloest') {
      mess += `<p>${esc(name(b.knoten[0]))}</p><ul class="liste">${beleg.importe.map(i => `<li><code>${esc(i.import)}</code> <span class="leer">Zeile ${i.zeile}</span></li>`).join('')}</ul>`;
    }
    html += `<div><h3 class="quelle-m">Beleg <em>gemessen · daidalos.json</em></h3><div class="mess">${mess}</div></div>`;
    seite.innerHTML = html;
    verdrahte();
  }

  function verdrahte() {
    seite.querySelectorAll('[data-befund]').forEach(b => b.addEventListener('click', () => zeigeBefund(b.dataset.befund)));
    seite.querySelectorAll('[data-zurueck]').forEach(b => b.addEventListener('click', () => { zustand.auswahl = null; leeren(); uebersicht(); schreibeAdresse(); }));
  }

  // ------------------------------------------------------------ 8. Auswahl und Sprungadressen
  function setzeAuswahl(a) { zustand.auswahl = a; schreibeAdresse(); }

  async function zeigeKnoten(id) {
    const k = knoten.get(id);
    if (!k) return;
    const ebene = ebeneVon(k);
    if (k.art === 'datei') {
      if (k.rolle === 'test') zustand.mitTests = true;
      if (gross && !zustand.offen.has(behaelter(k))) zustand.offen.add(behaelter(k));
    }
    if (k.art === 'modul' || k.art === 'ordner') zustand.zuletztModul = k.id;
    else if (k.art === 'datei') zustand.zuletztModul = behaelter(k);
    else zustand.zuletztModul = k.modul || k.ordner;
    setzeAuswahl({ art: 'knoten', id });
    if (ebene !== zustand.ebene || !cy.getElementById(id).nonempty()) { zustand.ebene = ebene; await zeichne(); }
    hebeKnotenHervor(id);
    knotenDetails(id);
  }

  async function zeigeBefund(id) {
    const b = befundNachId.get(id);
    if (!b) return;
    setzeAuswahl({ art: 'befund', id });
    if (b.regel === 'zyklus') {
      const beleg = b.beleg;
      let neu = zustand.ebene !== beleg.ebene;
      zustand.ebene = beleg.ebene;
      if (beleg.rolle === 'mit-tests' && !zustand.mitTests) { zustand.mitTests = true; neu = true; }
      if (!zustand.zyklen) { zustand.zyklen = true; document.getElementById('u-zyklen').checked = true; neu = true; }
      const art = zustand.arten[beleg.ebene];
      const brauche = beleg.ebene === 'modul' ? [beleg.kantenart === 'gradle' ? 'gradle' : 'nutzt'] : beleg.ebene === 'datei' ? ['nutzt', 'jni'] : ['nutzt'];
      brauche.forEach(a => { if (!art[a]) { art[a] = true; neu = true; } });
      if (beleg.ebene === 'datei' && gross) {
        beleg.knoten.forEach(m => { const g = behaelter(knoten.get(m)); if (!zustand.offen.has(g)) { zustand.offen.add(g); neu = true; } });
      }
      if (neu || !cy.nodes().nonempty()) await zeichne();
      hebeZyklusHervor(b);
    } else {
      const ziel = b.knoten[0];
      const k = knoten.get(ziel);
      if (k && k.art === 'datei') {
        if (k.rolle === 'test') zustand.mitTests = true;
        if (gross) zustand.offen.add(behaelter(k));
        if (zustand.ebene !== 'datei' || !cy.getElementById(ziel).nonempty()) { zustand.ebene = 'datei'; await zeichne(); }
        hebeKnotenHervor(ziel);
      }
    }
    befundDetails(b);
  }

  function schreibeAdresse() {
    let hash;
    if (zustand.auswahl) hash = zustand.auswahl.art + '=' + encodeURIComponent(zustand.auswahl.id);
    else hash = 'ebene=' + zustand.ebene;
    try { history.replaceState(null, '', '#' + hash); } catch (e) { /* file:// ohne History */ }
  }

  async function leseAdresse() {
    const p = new URLSearchParams(location.hash.replace(/^#/, ''));
    const ebene = p.get('ebene');
    if (ebene && ARTEN_JE_EBENE[ebene]) zustand.ebene = ebene;
    if (p.get('befund') && befundNachId.has(p.get('befund'))) { await zeigeBefund(p.get('befund')); return; }
    if (p.get('knoten') && knoten.has(p.get('knoten'))) { await zeigeKnoten(p.get('knoten')); return; }
    zustand.auswahl = null;
    await zeichne();
    uebersicht();
  }

  // ------------------------------------------------------------ 9. Bedienung und Start
  function zeigeSchalter() {
    document.querySelectorAll('#ebenen button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.ebene === zustand.ebene)));
    document.querySelectorAll('#rollen button').forEach(b => b.setAttribute('aria-pressed', String((b.dataset.rolle === 'mit-tests') === zustand.mitTests)));
    ['gradle', 'nutzt', 'jni'].forEach(a => {
      const c = document.getElementById('k-' + a);
      const moeglich = ARTEN_JE_EBENE[zustand.ebene].includes(a);
      c.disabled = !moeglich;
      c.checked = moeglich && zustand.arten[zustand.ebene][a];
      c.closest('label').classList.toggle('aus', !moeglich);
    });
  }

  async function neuZeichnen() {
    const a = zustand.auswahl;
    await zeichne();
    if (a && a.art === 'befund') zeigeBefund(a.id);
    else if (a && a.art === 'knoten' && cy.getElementById(a.id).nonempty()) hebeKnotenHervor(a.id);
  }

  document.querySelectorAll('#ebenen button').forEach(b => b.addEventListener('click', async () => {
    zustand.ebene = b.dataset.ebene;
    zustand.auswahl = null;
    schreibeAdresse();
    await zeichne();
    uebersicht();
  }));
  document.querySelectorAll('#rollen button').forEach(b => b.addEventListener('click', () => {
    zustand.mitTests = b.dataset.rolle === 'mit-tests';
    neuZeichnen();
  }));
  ['gradle', 'nutzt', 'jni'].forEach(a => document.getElementById('k-' + a).addEventListener('change', e => {
    zustand.arten[zustand.ebene][a] = e.target.checked;
    neuZeichnen();
  }));
  document.getElementById('u-zyklen').addEventListener('change', e => { zustand.zyklen = e.target.checked; cy.style(stil()); });
  document.getElementById('einpassen').addEventListener('click', () => passen(cy.elements(), 30));

  cy.on('tap', 'node', e => {
    const ref = e.target.data('ref');
    if (!ref) return;
    zustand.zuletztModul = istGruppe(ref) ? ref : zustand.zuletztModul;
    setzeAuswahl({ art: 'knoten', id: ref });
    if (cy.getElementById(ref).nonempty()) hebeKnotenHervor(ref);
    knotenDetails(ref);
  });
  cy.on('dbltap', 'node', async e => {
    const n = e.target, ref = n.data('ref'), typ = n.data('typ');
    if (zustand.ebene === 'modul' && istGruppe(ref)) {
      zustand.zuletztModul = ref;
      zustand.ebene = 'paket';
      setzeAuswahl({ art: 'knoten', id: ref });
      await zeichne();
      hebeKnotenHervor(ref);
      knotenDetails(ref);
    } else if (zustand.ebene === 'paket' && typ === 'paket') {
      const p = knoten.get(ref);
      zustand.zuletztModul = p.modul || p.ordner;
      if (gross) zustand.offen.add(zustand.zuletztModul);
      zustand.ebene = 'datei';
      setzeAuswahl({ art: 'knoten', id: ref });
      await zeichne();
      hebeKnotenHervor(ref);
      knotenDetails(ref);
    } else if (zustand.ebene === 'datei' && gross && (typ === 'gruppe' || typ === 'zu')) {
      if (zustand.offen.has(ref)) zustand.offen.delete(ref); else zustand.offen.add(ref);
      zustand.zuletztModul = ref;
      await zeichne();
      hebeKnotenHervor(ref);
    }
  });
  cy.on('tap', e => { if (e.target === cy) { zustand.auswahl = null; leeren(); uebersicht(); schreibeAdresse(); } });
  window.addEventListener('hashchange', leseAdresse);
  window.addEventListener('resize', () => cy.resize());

  // Darstellung: Dunkel ist Standard, die Wahl merkt sich der Browser, wenn er darf.
  function setzeThema(t) {
    if (t === 'system') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', t);
    document.querySelectorAll('.thema button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.thema === t)));
    try { localStorage.setItem('daidalos-thema', t); } catch (e) { /* ohne Speicher */ }
    cy.style(stil());
  }
  let gemerkt = null;
  try { gemerkt = localStorage.getItem('daidalos-thema'); } catch (e) { /* ohne Speicher */ }
  document.querySelectorAll('.thema button').forEach(b => b.addEventListener('click', () => setzeThema(b.dataset.thema)));
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => cy.style(stil()));
  setzeThema(['dark', 'light', 'system'].includes(gemerkt) ? gemerkt : 'dark');

  // Kopfzeile
  document.getElementById('projekt').textContent = M.ziel.name;
  const stand = document.getElementById('stand');
  const commit = M.ziel.git_commit ? 'Commit ' + M.ziel.git_commit.slice(0, 7) : 'ohne Git-Commit';
  stand.textContent = commit + ' · ' + gruppen.filter(g => g.art === 'modul').length + ' Module · ' + kartenDateien.length + ' Dateien auf der Karte';
  document.getElementById('aenderungen').hidden = !M.ziel.git_aenderungen;

  // Für Tests und spätere Erweiterungen (A05).
  window.daidalos = { cy, zustand, zeiten, zeichne, zeigeBefund, zeigeKnoten, kartenDateien, gross };
  leseAdresse();
})();
